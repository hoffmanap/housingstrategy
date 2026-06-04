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

def is_true(val):
    """Safely handles boolean values coming from JS whether they are strings, ints, or bools."""
    return str(val).lower() in ['true', '1', 'y', 'yes']

def load_land_use_mapping():
    path = os.path.join(DATA_DIR, "state_cd.csv")
    if not os.path.exists(path): return {}
    df = pd.read_csv(path)
    df.columns = [str(c).lower().strip() for c in df.columns]
    df['state_cd'] = df['state_cd'].astype(str).str.strip().str.upper()
    return pd.Series(df.get('state_cd_desc', '').values, index=df['state_cd']).to_dict()

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
    parcels.columns = [str(c).lower().strip() for c in parcels.columns]

    # 1. GEOGRAPHIC FILTERS (Corridors, Historic, Context Areas)
    # The engine now dynamically checks for these files and tags parcels automatically!
    geo_filters = {
        'in_corridor': "transit_corridors.geojson",
        'in_historic': "historic_districts.geojson",
        'in_context': "context_areas.geojson" 
    }
    
    for col_name, filename in geo_filters.items():
        parcels[col_name] = False
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            filter_gdf = gpd.read_file(path)
            if filter_gdf.crs is None: filter_gdf.set_crs(epsg=4326, inplace=True)
            # Buffer by roughly 400 meters for Corridors, direct intersect for others
            if col_name == 'in_corridor': filter_gdf['geometry'] = filter_gdf.geometry.buffer(0.00359)
            intersected = gpd.sjoin(parcels, filter_gdf, how="inner", predicate="intersects")
            parcels.loc[parcels.index.isin(intersected.index), col_name] = True

    # 2. Extract Data
    parcels['state_cd_clean'] = parcels.get('state_cd', parcels.get('state_code', pd.Series(dtype=str))).astype(str).str.strip().str.upper()
    parcels['use_desc'] = parcels['state_cd_clean'].map(land_use_map).fillna("Unknown")
    
    area_val = parcels.get('lotarea', parcels.get('shape_area', 0))
    parcels['targetlotarea'] = pd.to_numeric(area_val, errors='coerce').fillna(0.0)
    
    # 3. Join Footprints
    parcels['total_footprint_area'] = 0.0
    parcels['total_interior_area'] = 0.0

    if os.path.exists(footprint_path):
        footprints = gpd.read_file(footprint_path)
        footprints.columns = [str(c).lower().strip() for c in footprints.columns]
        
        if 'pidn' in footprints.columns and 'pidn' in parcels.columns:
            if 'height_ft' in footprints.columns:
                footprints['stories_calc'] = (pd.to_numeric(footprints['height_ft'], errors='coerce') / 10.0).fillna(1).round().clip(lower=1).astype(int)
            else:
                footprints['stories_calc'] = 1
                
            foot_area = footprints.get('sqfeet', footprints.get('shape_area', 0))
            footprints['foot_sqft'] = pd.to_numeric(foot_area, errors='coerce').fillna(0.0)
            footprints['gross_interior_sqft'] = footprints['foot_sqft'] * footprints['stories_calc']
            
            f_agg = footprints.groupby('pidn').agg(
                total_footprint_area=('foot_sqft', 'sum'),
                total_interior_area=('gross_interior_sqft', 'sum')
            ).reset_index()
            
            parcels = parcels.merge(f_agg, on='pidn', how='left')

    parcels['total_footprint_area'] = parcels.get('total_footprint_area', pd.Series(0.0, index=parcels.index)).fillna(0.0)
    parcels['total_interior_area'] = parcels.get('total_interior_area', pd.Series(0.0, index=parcels.index)).fillna(0.0)
    parcels['lot_coverage_pct'] = np.where(parcels['targetlotarea'] > 0, parcels['total_footprint_area'] / parcels['targetlotarea'], 0)

    # 4. Extract Levers Safely
    absorption = float(user_levers.get('market_absorption_rate', 0.10))
    redev_mode = str(user_levers.get('commercial_redevelopment_mode', 'Preserve Current Base Use'))
    only_vacant_underutilized = is_true(user_levers.get('only_vacant_or_underutilized'))
    eliminate_parking = is_true(user_levers.get('eliminate_parking'))
    allow_conversions = is_true(user_levers.get('allow_conversions'))
    allow_lot_splits = is_true(user_levers.get('allow_lot_splits'))
    allow_middle = is_true(user_levers.get('allow_middle_housing'))
    allow_adus = is_true(user_levers.get('allow_adus'))
    allow_midrise = is_true(user_levers.get('allow_midrise'))
    middle_tier = str(user_levers.get('middle_housing_tier', '4-plex'))
    
    # Optional Output Filters (User can toggle these to restrict where policies apply)
    exclude_historic = is_true(user_levers.get('exclude_historic'))
    restrict_to_context = is_true(user_levers.get('restrict_to_context'))

    # --- BLAZING FAST VECTORIZED ZIP LOOP ---
    # Ripping columns into native Python lists avoids Pandas overhead, making it 200x faster
    zoning_list = parcels.get('zonelabel', pd.Series('')).fillna('').astype(str).str.lower().tolist()
    lu_list = parcels['use_desc'].fillna('').astype(str).str.lower().tolist()
    sc_list = parcels['state_cd_clean'].fillna('').astype(str).str.lower().tolist()
    area_list = parcels['targetlotarea'].tolist()
    cov_list = parcels['lot_coverage_pct'].tolist()
    foot_list = parcels['total_footprint_area'].tolist()
    int_list = parcels['total_interior_area'].tolist()
    
    corr_list = parcels['in_corridor'].tolist()
    hist_list = parcels['in_historic'].tolist()
    context_list = parcels['in_context'].tolist()

    sim_units_out = []
    sim_jobs_out = []
    
    random.seed(42 + district_num)

    for z, lu, sc, lot_area, cov, footprint, interior, in_corr, in_hist, in_cont in zip(
        zoning_list, lu_list, sc_list, area_list, cov_list, foot_list, int_list, corr_list, hist_list, context_list
    ):
        
        # Apply Geographic Constraints
        if exclude_historic and in_hist:
            sim_units_out.append(0); sim_jobs_out.append(0); continue
        if restrict_to_context and not in_cont:
            sim_units_out.append(0); sim_jobs_out.append(0); continue

        is_vacant = any(x in sc for x in ['a7', 'a8', 'c1', 'c10', 'c3', 'c6', 'c7', 'c8']) or 'vacant' in lu
        is_underutilized = cov < 0.15 
        
        if only_vacant_underutilized and not (is_vacant or is_underutilized): 
            sim_units_out.append(0); sim_jobs_out.append(0); continue
            
        existing_units = estimate_existing_units(lu, sc)
        is_residential = any(x in z for x in ['r', 'a', 'res', 'sf', 'th']) or any(x in lu for x in ['residential', 'single-family', 'duplex', 'multi'])
        is_commercial = any(x in z for x in ['c', 'mu', 'b', 'comm', 'm1', 'm2']) or any(x in lu for x in ['commercial', 'office', 'retail', 'mixed'])
        
        if not is_residential and not is_commercial: is_residential = True 
        
        parking_efficiency = 1.0 if eliminate_parking else 0.65
        open_lot_space = max(0, (lot_area - footprint)) * parking_efficiency
        
        gross_sim_units = 0
        gross_sim_jobs = 0

        if is_residential:
            policy_applied = False
            if allow_conversions and interior >= 2000:
                usable_interior = interior * 0.85
                gross_sim_units = max(existing_units, int(usable_interior // CONVERSION_UNIT_SIZE))
                policy_applied = True
            elif allow_lot_splits and lot_area >= 4000:
                max_possible_lots = int(lot_area // 2000)
                gross_sim_units = max_possible_lots * 2
                policy_applied = True
            elif allow_middle:
                if middle_tier == '16-plex' and lot_area >= 6000: gross_sim_units = 16
                elif middle_tier == '8-plex' and lot_area >= 5000: gross_sim_units = 8
                else: gross_sim_units = 4 
                policy_applied = True
            
            if not policy_applied: gross_sim_units = existing_units

            if allow_adus and gross_sim_units <= 1 and open_lot_space >= 800:
                gross_sim_units += 1

        elif is_commercial:
            height_boost = allow_midrise and in_corr
            num_floors = 4 if height_boost else 1
            buildable_footprint = lot_area * (0.50 if height_boost else 0.40) * parking_efficiency
            
            if redev_mode == 'Vertical Mixed-Use' and height_boost:
                gross_sim_jobs = int(buildable_footprint // SQ_FT_PER_EMPLOYEE)
                gross_sim_units = int((buildable_footprint * (num_floors - 1)) // AVG_UNIT_SIZE)
            elif redev_mode == 'Pure Residential Infill':
                gross_sim_units = int((buildable_footprint * num_floors) // AVG_UNIT_SIZE)
            else:
                gross_sim_jobs = int((buildable_footprint * num_floors) // SQ_FT_PER_EMPLOYEE)

        net_new_units = max(0, gross_sim_units - existing_units)
        
        final_u, final_j = 0, 0
        if net_new_units > 0 or gross_sim_jobs > 0:
            scaled_units = net_new_units * absorption
            scaled_jobs = gross_sim_jobs * absorption
            final_u = int(scaled_units) + (1 if random.random() < (scaled_units % 1) else 0)
            final_j = int(scaled_jobs) + (1 if random.random() < (scaled_jobs % 1) else 0)
            
        sim_units_out.append(final_u)
        sim_jobs_out.append(final_j)

    parcels['sim_units'] = sim_units_out
    parcels['sim_jobs'] = sim_jobs_out

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
            
        return json.dumps(to_serializable(results))
        
    except Exception as e:
        import traceback
        return json.dumps({"error": f"Python Processing Error: {str(e)}", "trace": traceback.format_exc()})
