import os
import json
import random
import math
import numpy as np
import pandas as pd
import geopandas as gpd

DATA_DIR = "./data"
AVG_UNIT_SIZE = 850
CONVERSION_UNIT_SIZE = 600
SQ_FT_PER_EMPLOYEE = 300

# El Paso Latitude used to correct Web Mercator distortion without needing local pyproj.db
EL_PASO_LAT = 31.76

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

def get_col(df, possible_names, exact=False):
    """Safely finds columns despite case sensitivity variations in GeoJSON exports."""
    for c in df.columns:
        cl = c.lower()
        for p in possible_names:
            if exact and cl == p: return c
            if not exact and p in cl: return c
    return None

def process_district(district_num, user_levers, land_use_map):
    parcel_path = os.path.join(DATA_DIR, f"D{district_num}GrowthParcels.geojson")
    footprint_path = os.path.join(DATA_DIR, f"footprints_d{district_num}.geojson")

    if not os.path.exists(parcel_path): return None

    parcels = gpd.read_file(parcel_path)
    
    # 1. FORCE WEB MERCATOR (EPSG:3857) to prevent Pyodide Local DB projection failures
    if parcels.crs is None: parcels.set_crs(epsg=4326, inplace=True)
    parcels = parcels.to_crs(epsg=3857)

    # 2. Transit Corridor Spatial Math
    parcels['in_corridor'] = False
    corridor_path = os.path.join(DATA_DIR, "transit_corridors.geojson")
    if user_levers.get('allow_midrise', False) and os.path.exists(corridor_path):
        corridors = gpd.read_file(corridor_path)
        if corridors.crs is None: corridors.set_crs(epsg=4326, inplace=True)
        corridors = corridors.to_crs(epsg=3857)
        # Fix Web Mercator buffer distortion
        scale_factor = 1.0 / math.cos(math.radians(EL_PASO_LAT))
        corridors['geometry'] = corridors.geometry.buffer(400 * scale_factor)
        parcels_in_corr = gpd.sjoin(parcels, corridors, how="inner", predicate="intersects")
        parcels.loc[parcels.index.isin(parcels_in_corr.index), 'in_corridor'] = True

    # 3. Calculate True Area using Cosine Correction
    area_col = get_col(parcels, ['lotarea', 'shape_area', 'area_sqft', 'parcel_area'], exact=True)
    if area_col:
        parcels['LotArea'] = parcels[area_col]
    else:
        lat_correction = (math.cos(math.radians(EL_PASO_LAT))) ** 2
        parcels['LotArea'] = parcels['geometry'].area * lat_correction * 10.7639

    # 4. Safely Extract IDs and Zoning Codes
    pid_col = get_col(parcels, ['pid', 'id', 'objectid', 'parcel', 'prop_id'])
    
    # EXACT match required so we don't accidentally grab 'OBJECTID' as 'cd'
    raw_state_col = get_col(parcels, ['state_cd', 'statecd', 'state class', 'state_class', 'use_cd', 'landuse', 'land_use'], exact=True)
    if not raw_state_col:
        raw_state_col = get_col(parcels, ['state'])
    
    if raw_state_col:
        parcels['STATE_CD_CLEAN'] = parcels[raw_state_col].astype(str).str.strip().str.upper()
        parcels['USE_DESC'] = parcels['STATE_CD_CLEAN'].map(land_use_map).fillna("Unknown")
    else:
        parcels['STATE_CD_CLEAN'] = ""
        parcels['USE_DESC'] = "Unknown"

    parcels['total_footprint_area'] = 0.0
    parcels['total_interior_area'] = 0.0

    # 5. Extract Footprint Data
    if os.path.exists(footprint_path):
        footprints = gpd.read_file(footprint_path).to_crs(parcels.crs)
        if not footprints.empty:
            h_field = get_col(footprints, ['height', 'story', 'stories'])
            footprints['stories_calc'] = footprints[h_field].fillna(1).astype(int).clip(lower=1) if h_field else 1
            
            foot_correction = (math.cos(math.radians(EL_PASO_LAT))) ** 2
            footprints['gross_interior_sqft'] = footprints['geometry'].area * foot_correction * 10.7639 * footprints['stories_calc']
            
            # Safe spatial join mapping strictly back to parcels via explicit ID
            parcels_idx = parcels[['geometry']].copy()
            parcels_idx['parcel_idx'] = parcels_idx.index
            f_joined = gpd.sjoin(footprints, parcels_idx, how="inner", predicate="within")
            
            if not f_joined.empty:
                f_agg = f_joined.groupby('parcel_idx').agg(
                    total_footprint_area=('geometry', lambda x: x.area.sum() * foot_correction * 10.7639),
                    total_interior_area=('gross_interior_sqft', 'sum')
                ).reset_index().set_index('parcel_idx')
                parcels = parcels.join(f_agg, how='left')

    parcels['total_footprint_area'] = parcels.get('total_footprint_area', pd.Series(0.0, index=parcels.index)).fillna(0.0)
    parcels['total_interior_area'] = parcels.get('total_interior_area', pd.Series(0.0, index=parcels.index)).fillna(0.0)
    
    # Avoid divide by zero
    parcels['lot_coverage_pct'] = np.where(parcels['LotArea'] > 0, parcels['total_footprint_area'] / parcels['LotArea'], 0)

    zoning_col = get_col(parcels, ['zoning', 'zone', 'base_zone'])
    absorption = user_levers.get('market_absorption_rate', 0.10)
    redev_mode = user_levers.get('commercial_redevelopment_mode', 'Preserve Current Base Use')
    
    parcels['sim_units'] = 0
    parcels['sim_jobs'] = 0

    # 6. --- CORE CALCULATION LOOP ---
    for idx, parcel in parcels.iterrows():
        zoning = str(parcel.get(zoning_col, '')).upper() if zoning_col else ''
        land_use = str(parcel.get('USE_DESC', '')).upper()
        state_cd = str(parcel.get('STATE_CD_CLEAN', ''))
        lot_area = float(parcel.get('LotArea', 0.0))
        coverage = float(parcel.get('lot_coverage_pct', 0.0))
        
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
        
        # PROBABILISTIC ABSORPTION
        if net_new_units > 0 or gross_sim_jobs > 0:
            if random.random() <= absorption:
                parcels.at[idx, 'sim_units'] = int(net_new_units)
                parcels.at[idx, 'sim_jobs'] = int(gross_sim_jobs)

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
            # Re-project to Global GPS coordinate system for the Leaflet Map
            final_map = pd.concat(all_yield_parcels).to_crs(epsg=4326)
            results["map_data"] = final_map.to_json()
            
        clean_results = to_serializable(results)
        return json.dumps(clean_results)
        
    except Exception as e:
        import traceback
        return json.dumps({"error": f"Python Processing Error: {str(e)}", "trace": traceback.format_exc()})
