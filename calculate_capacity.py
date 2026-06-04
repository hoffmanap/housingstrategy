import os
import json
import random
import numpy as np
import pandas as pd
import geopandas as gpd

DATA_DIR = "./data"
AVG_UNIT_SIZE = 850
CONVERSION_UNIT_SIZE = 600
SQ_FT_PER_EMPLOYEE = 300

def to_serializable(val):
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
    df['state_cd'] = df['state_cd'].astype(str).str.strip().str.upper()
    return pd.Series(df.state_cd_desc.values, index=df.state_cd).to_dict()

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

    # Load Parcels
    parcels = gpd.read_file(parcel_path)
    if parcels.crs is None: parcels.set_crs(epsg=4326, inplace=True)

    # 1. Corridor Intersection (Using raw degrees to bypass Pyodide Projection limits)
    parcels['in_corridor'] = False
    corridor_path = os.path.join(DATA_DIR, "transit_corridors.geojson")
    if user_levers.get('allow_midrise', False) and os.path.exists(corridor_path):
        corridors = gpd.read_file(corridor_path)
        if corridors.crs is None: corridors.set_crs(epsg=4326, inplace=True)
        # 0.00359 degrees is roughly equal to 400 meters
        corridors['geometry'] = corridors.geometry.buffer(0.00359)
        parcels_in_corr = gpd.sjoin(parcels, corridors, how="inner", predicate="intersects")
        parcels.loc[parcels.index.isin(parcels_in_corr.index), 'in_corridor'] = True

    # 2. Safely Extract Target Columns
    parcels['STATE_CD_CLEAN'] = parcels.get('STATE_CD', parcels.get('State_Code', '')).astype(str).str.strip().str.upper()
    parcels['USE_DESC'] = parcels['STATE_CD_CLEAN'].map(land_use_map).fillna("Unknown")
    
    # Use exact provided Area column
    parcels['TargetLotArea'] = parcels.get('LotArea', parcels.get('Shape_Area', 0)).astype(float)
    
    parcels['total_footprint_area'] = 0.0
    parcels['total_interior_area'] = 0.0

    # 3. Join Footprints using the explicit PIDN (Incredibly fast and accurate)
    if os.path.exists(footprint_path):
        footprints = gpd.read_file(footprint_path)
        if not footprints.empty and 'PIDN' in footprints.columns and 'PIDN' in parcels.columns:
            
            # Use exact provided Footprint attributes
            if 'HEIGHT_FT' in footprints.columns:
                footprints['stories_calc'] = (footprints['HEIGHT_FT'] / 10.0).fillna(1).round().clip(lower=1).astype(int)
            else:
                footprints['stories_calc'] = 1
                
            footprints['foot_sqft'] = footprints.get('SQFEET', footprints.get('Shape_Area', 0)).astype(float)
            footprints['gross_interior_sqft'] = footprints['foot_sqft'] * footprints['stories_calc']
            
            # Group by PIDN and merge
            f_agg = footprints.groupby('PIDN').agg(
                total_footprint_area=('foot_sqft', 'sum'),
                total_interior_area=('gross_interior_sqft', 'sum')
            ).reset_index()
            
            parcels = parcels.merge(f_agg, on='PIDN', how='left')

    parcels['total_footprint_area'] = parcels.get('total_footprint_area', pd.Series(0.0, index=parcels.index)).fillna(0.0)
    parcels['total_interior_area'] = parcels.get('total_interior_area', pd.Series(0.0, index=parcels.index)).fillna(0.0)
    parcels['lot_coverage_pct'] = np.where(parcels['TargetLotArea'] > 0, parcels['total_footprint_area'] / parcels['TargetLotArea'], 0)

    absorption = user_levers.get('market_absorption_rate', 0.10)
    redev_mode = user_levers.get('commercial_redevelopment_mode', 'Preserve Current Base Use')
    
    parcels['sim_units'] = 0
    parcels['sim_jobs'] = 0

    random.seed(42 + district_num)

    # 4. --- CORE CALCULATION LOOP ---
    for idx, parcel in parcels.iterrows():
        zoning = str(parcel.get('ZONELABEL', '')).upper()
        land_use = str(parcel.get('USE_DESC', '')).upper()
        state_cd = str(parcel.get('STATE_CD_CLEAN', ''))
        lot_area = float(parcel.get('TargetLotArea', 0.0))
        coverage = float(parcel.get('lot_coverage_pct', 0.0))
        
        is_vacant = any(x in state_cd for x in ['A7', 'A8', 'C1', 'C10', 'C3', 'C6', 'C7', 'C8']) or 'VACANT' in land_use
        is_underutilized = coverage < 0.15 
        
        if user_levers.get('only_vacant_or_underutilized', False) and not (is_vacant or is_underutilized): continue 
        
        existing_units = estimate_existing_units(land_use, state_cd)
        
        is_residential = any(x in zoning for x in ['R', 'A', 'RES', 'SF', 'TH']) or any(x in land_use for x in ['RESIDENTIAL', 'SINGLE-FAMILY', 'DUPLEX', 'MULTI'])
        is_commercial = any(x in zoning for x in ['C', 'MU', 'B', 'COMM', 'M1', 'M2']) or any(x in land_use for x in ['COMMERCIAL', 'OFFICE', 'RETAIL', 'MIXED'])
        
        # Safety net: Defaults to Residential if strictly undefined
        if not is_residential and not is_commercial:
            is_residential = True 
        
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
        
        if net_new_units > 0 or gross_sim_jobs > 0:
            if random.random() <= absorption:
                parcels.at[idx, 'sim_units'] = int(net_new_units)
                parcels.at[idx, 'sim_jobs'] = int(gross_sim_jobs)

    # 5. Output
    yield_subset = parcels[(parcels['sim_units'] > 0) | (parcels['sim_jobs'] > 0)].copy()
    return yield_subset if not yield_subset.empty else None

def run_simulation(levers_input):
    try:
        user_levers = json.loads(levers_input) if isinstance(levers_input, str) else levers_input
            
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
            final_map = pd.concat(all_yield_parcels)
            if final_map.crs is None: final_map.set_crs(epsg=4326, inplace=True)
            results["map_data"] = final_map.to_json()
            
        clean_results = to_serializable(results)
        return json.dumps(clean_results)
        
    except Exception as e:
        import traceback
        return json.dumps({"error": f"Python Processing Error: {str(e)}", "trace": traceback.format_exc()})
