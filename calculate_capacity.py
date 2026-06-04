import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd

DATA_DIR = "./data"
AVG_UNIT_SIZE = 850
CONVERSION_UNIT_SIZE = 600
SQ_FT_PER_EMPLOYEE = 300

def to_serializable(val):
    """Recursively convert NumPy types to standard Python types for JSON."""
    if isinstance(val, (np.int64, np.int32, np.int_)): return int(val)
    if isinstance(val, (np.float64, np.float32)): return float(val)
    if isinstance(val, dict): return {k: to_serializable(v) for k, v in val.items()}
    if isinstance(val, list): return [to_serializable(v) for v in val]
    return val

def load_land_use_mapping():
    path = os.path.join(DATA_DIR, "state_cd.csv")
    if not os.path.exists(path): return {}
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    return pd.Series(df.state_cd_desc.values, index=df.state_cd.astype(str).str.strip()).to_dict()

def estimate_existing_units(land_use_desc, state_code):
    code = str(state_code).upper().strip()
    desc = str(land_use_desc).upper()
    if any(x in code for x in ['A7', 'A8', 'C1', 'C10', 'C3', 'C6', 'C7', 'C8']): return 0
    if 'SINGLE-FAMILY' in desc or code == 'A1': return 1
    if 'DUPLEX' in desc or code in ['A51', 'B1']: return 2
    if 'TRIPLEX' in desc or code in ['A53', 'B3']: return 3
    if 'QUADRUPLEX' in desc or 'QUADPLEX' in desc or code in ['A54', 'B4', 'B9']: return 4
    if 'FIVEPLEX' in desc or code in ['A55', 'B5', 'B7']: return 5
    if 'SIXPLEX' in desc or code in ['A56', 'B6', 'B8']: return 6
    if 'APARTMENT' in desc or 'MULTI FAMILY' in desc or code in ['A52', 'B2']: return 12  
    return 0

def process_district(district_num, user_levers, land_use_map):
    parcel_path = os.path.join(DATA_DIR, f"D{district_num}GrowthParcels.geojson")
    footprint_path = os.path.join(DATA_DIR, f"footprints_d{district_num}.geojson")

    if not os.path.exists(parcel_path): return None

    parcels = gpd.read_file(parcel_path)
    if parcels.crs is None: parcels.set_crs(epsg=4326, inplace=True)
    parcels = parcels.to_crs(epsg=32139)

    parcels['in_corridor'] = False
    corridor_path = os.path.join(DATA_DIR, "transit_corridors.geojson")
    if user_levers.get('allow_midrise', False) and os.path.exists(corridor_path):
        corridors = gpd.read_file(corridor_path)
        if corridors.crs is None: corridors.set_crs(epsg=4326, inplace=True)
        corridors = corridors.to_crs(epsg=32139)
        corridors['geometry'] = corridors.geometry.buffer(400)
        parcels_in_corr = gpd.sjoin(parcels, corridors, how="inner", predicate="intersects")
        parcels.loc[parcels.index.isin(parcels_in_corr.index), 'in_corridor'] = True

    if 'LotArea' not in parcels.columns:
        parcels['LotArea'] = parcels['geometry'].area * 10.7639 

    pid_options = [c for c in parcels.columns if any(x in c.lower() for x in ['pid', 'id', 'objectid', 'parcel'])]
    pid_col = pid_options[0] if pid_options else None

    raw_state_col = 'STATE_CD'
    state_cols = [c for c in parcels.columns if 'state' in c.lower() or 'cd' in c.lower() or 'use' in c.lower()]
    if state_cols: raw_state_col = state_cols[0]
    
    parcels['USE_DESC'] = parcels.get(raw_state_col, pd.Series("Unknown", index=parcels.index)).astype(str).str.strip().map(land_use_map).fillna("Unknown")
    parcels['total_footprint_area'] = 0.0
    parcels['total_interior_area'] = 0.0

    if os.path.exists(footprint_path):
        footprints = gpd.read_file(footprint_path).to_crs(parcels.crs)
        if not footprints.empty:
            height_col = [c for c in footprints.columns if any(x in c.lower() for x in ['height', 'story', 'stories'])]
            if height_col:
                h_field = height_col[0]
                footprints['stories_calc'] = footprints[h_field].fillna(1).astype(int).clip(lower=1)
            else:
                footprints['stories_calc'] = 1
                
            footprints['gross_interior_sqft'] = footprints['geometry'].area * 10.7639 * footprints['stories_calc']
            
            if pid_col and pid_col in footprints.columns:
                f_agg = footprints.groupby(pid_col).agg(
                    total_footprint_area=('geometry', lambda x: x.area.sum() * 10.7639),
                    total_interior_area=('gross_interior_sqft', 'sum')
                ).reset_index()
                parcels = parcels.merge(f_agg, on=pid_col, how='left')
            else:
                f_joined = gpd.sjoin(footprints, parcels[[pid_col or 'geometry', 'geometry']].reset_index(), how="inner", predicate="within")
                if not f_joined.empty:
                    f_agg = f_joined.groupby('index').agg(
                        total_footprint_area=('geometry', lambda x: x.area.sum() * 10.7639),
                        total_interior_area=('gross_interior_sqft', 'sum')
                    ).reset_index().set_index('index')
                    parcels = parcels.join(f_agg, how='left')

    if 'total_footprint_area' not in parcels.columns: parcels['total_footprint_area'] = 0.0
    if 'total_interior_area' not in parcels.columns: parcels['total_interior_area'] = 0.0
    parcels['total_footprint_area'] = parcels['total_footprint_area'].fillna(0.0)
    parcels['total_interior_area'] = parcels['total_interior_area'].fillna(0.0)
    parcels['lot_coverage_pct'] = parcels['total_footprint_area'] / parcels['LotArea']

    # --- CORE CALCULATION LOOP ---
    zoning_cols = [c for c in parcels.columns if any(x in c.lower() for x in ['zon', 'label', 'class', 'dist'])]
    absorption = user_levers.get('market_absorption_rate', 0.10)
    redev_mode = user_levers.get('commercial_redevelopment_mode', 'Preserve Current Base Use')
    
    parcels['sim_units'] = 0
    parcels['sim_jobs'] = 0

    for idx, parcel in parcels.iterrows():
        zoning = str(parcel.get(zoning_cols[0], '')).upper() if zoning_cols else ''
        land_use = str(parcel.get('USE_DESC', '')).upper()
        state_cd = str(parcel.get(raw_state_col, ''))
        lot_area = parcel.get('LotArea', 0)
        coverage = parcel.get('lot_coverage_pct', 0)
        
        is_vacant = any(x in state_cd for x in ['A7', 'A8', 'C1', 'C10', 'C3', 'C6', 'C7', 'C8']) or 'VACANT' in land_use
        is_underutilized = coverage < 0.15 
        
        if user_levers.get('only_vacant_or_underutilized', False) and not (is_vacant or is_underutilized): continue 
        
        existing_units = estimate_existing_units(land_use, state_cd)
        is_residential = any(x in zoning for x in ['R', 'A', 'RES', 'SF', 'TH']) or any(x in land_use for x in ['RESIDENTIAL', 'SINGLE-FAMILY', 'DUPLEX', 'MULTI'])
        is_commercial = any(x in zoning for x in ['C', 'MU', 'B', 'COMM', 'M1', 'M2']) or any(x in land_use for x in ['COMMERCIAL', 'OFFICE', 'RETAIL', 'MIXED']) or zoning == ''
        
        parking_efficiency = 1.0 if user_levers.get('eliminate_parking', False) else 0.65
        open_lot_space = max(0, (lot_area - parcel['total_footprint_area'])) * parking_efficiency
        
        gross_sim_units = 0
        gross_sim_jobs = 0

        if is_residential:
            policy_applied = False
            
            if user_levers.get('allow_conversions', False) and parcel['total_interior_area'] >= 2000:
                usable_interior = parcel['total_interior_area'] * 0.85
                gross_sim_units = max(existing_units, int(usable_interior // CONVERSION_UNIT_SIZE))
                policy_applied = True
                
            if not policy_applied and user_levers.get('allow_lot_splits', False) and lot_area >= 4000:
                max_possible_lots = int(lot_area // 2000)
                gross_sim_units = max_possible_lots * 2
                policy_applied = True
                
            if not policy_applied and user_levers.get('allow_middle_housing', False):
                tier = user_levers.get('middle_housing_tier', '4-plex')
                if tier == '16-plex' and lot_area >= 6000: gross_sim_units = 16
                elif tier == '8-plex' and lot_area >= 5000: gross_sim_units = 8
                else: gross_sim_units = 4 
                policy_applied = True
            
            if not policy_applied: gross_sim_units = existing_units

            if user_levers.get('allow_adus', False) and gross_sim_units <= 1:
                if open_lot_space >= 800: gross_sim_units += 1

        elif is_commercial:
            allow_height = user_levers.get('allow_midrise', False) and parcel.get('in_corridor', False)
            num_floors = 4 if allow_height else 1
            buildable_footprint = lot_area * (0.50 if allow_height else 0.40) * parking_efficiency
            
            if redev_mode == 'Vertical Mixed-Use' and allow_height:
                gross_sim_jobs = int(buildable_footprint // SQ_FT_PER_EMPLOYEE)
                gross_sim_units = int((buildable_footprint * (num_floors - 1)) // AVG_UNIT_SIZE)
            elif redev_mode == 'Pure Residential Infill':
                gross_sim_units = int((buildable_footprint * num_floors) // AVG_UNIT_SIZE)
            else:
                gross_sim_jobs = int((buildable_footprint * num_floors) // SQ_FT_PER_EMPLOYEE)

        net_new_units = max(0, gross_sim_units - existing_units)
        parcels.at[idx, 'sim_units'] = int(net_new_units * absorption)
        parcels.at[idx, 'sim_jobs'] = int(gross_sim_jobs * absorption)

    yield_subset = parcels[(parcels['sim_units'] > 0) | (parcels['sim_jobs'] > 0)].copy()
    return yield_subset if not yield_subset.empty else None

def run_simulation(levers_input):
    """
    CRITICAL FIX: This safely handles the input whether JavaScript 
    sends it as a raw string or an already-parsed dictionary.
    """
    try:
        if isinstance(levers_input, str):
            user_levers = json.loads(levers_input)
        else:
            user_levers = levers_input
            
        districts = user_levers.get('active_representative_districts', [1])
        land_use_map = load_land_use_mapping()
        
        results = {"totals": {"units": 0, "jobs": 0}, "breakdowns": {}, "map_data": "{}"}
        all_yield_parcels = []
        
        for d in districts:
            gdf = process_district(d, user_levers, land_use_map)
            if gdf is not None:
                u = int(gdf['sim_units'].sum())
                j = int(gdf['sim_jobs'].sum())
                results["breakdowns"][d] = {"units": u, "jobs": j}
                results["totals"]["units"] += u
                results["totals"]["jobs"] += j
                all_yield_parcels.append(gdf[['sim_units', 'sim_jobs', 'geometry']])
            else:
                results["breakdowns"][d] = {"units": 0, "jobs": 0}
                
        if all_yield_parcels:
            final_map = pd.concat(all_yield_parcels).to_crs(epsg=4326)
            results["map_data"] = final_map.to_json()
            
        clean_results = to_serializable(results)
        return json.dumps(clean_results)
        
    except Exception as e:
        # If anything fails, return the error safely to the dashboard
        return json.dumps({"error": f"Python Processing Error: {str(e)}"})
