import os
import glob
import pandas as pd
import geopandas as gpd

# Define the absolute directory path where your data sits
DATA_DIR = r"C:\Users\Angelica\OneDrive\Housing Strategy\data"
STATE_CD_PATH = os.path.join(DATA_DIR, "state_cd.csv")

# Constants for Capacity Math
AVG_UNIT_SIZE = 850        # Sq Ft for regular housing units
CONVERSION_UNIT_SIZE = 600 # Min size for adaptive reuse mansion conversion
SQ_FT_PER_EMPLOYEE = 300   # Average square footage per job space

def load_land_use_mapping():
    """Loads the state_cd CSV and creates a quick mapping dictionary."""
    if not os.path.exists(STATE_CD_PATH):
        print(f"WARNING: state_cd.csv not found at {STATE_CD_PATH}. Defaulting to codes.")
        return {}
    df = pd.read_csv(STATE_CD_PATH)
    df.columns = df.columns.str.strip()
    df['state_cd'] = df['state_cd'].astype(str).str.strip()
    return pd.Series(df.state_cd_desc.values, index=df.state_cd).to_dict()

def estimate_existing_units(land_use_desc, state_code):
    """Estimates baseline housing units already sitting on a parcel to compute NET increases."""
    code = str(state_code).upper().strip()
    desc = str(land_use_desc).upper()
    
    if any(x in code for x in ['A7', 'A8', 'C1', 'C10', 'C3', 'C6', 'C7', 'C8']):
        return 0  # Confirmed Vacant Lots
    if 'SINGLE-FAMILY' in desc or code == 'A1':
        return 1
    if 'DUPLEX' in desc or code in ['A51', 'B1']:
        return 2
    if 'TRIPLEX' in desc or code in ['A53', 'B3']:
        return 3
    if 'QUADRUPLEX' in desc or 'QUADPLEX' in desc or code in ['A54', 'B4', 'B9']:
        return 4
    if 'FIVEPLEX' in desc or code in ['A55', 'B5', 'B7']:
        return 5
    if 'SIXPLEX' in desc or code in ['A56', 'B6', 'B8']:
        return 6
    if 'APARTMENT' in desc or 'MULTI FAMILY' in desc or code in ['A52', 'B2']:
        return 12  
    return 0

def process_district_capacity(district_num, user_levers, land_use_map):
    """Processes a single representative district's parcels and footprints."""
    
    parcel_file = os.path.join(DATA_DIR, f"D{district_num}GrowthParcels.geojson")
    footprint_file = os.path.join(DATA_DIR, f"footprintsd{district_num}.geojson")
    
    if not os.path.exists(parcel_file):
        print(f"Skipping District {district_num}: Parcel file not found ({os.path.basename(parcel_file)}).")
        return None

    # Load district parcels
    parcels = gpd.read_file(parcel_file)
    
    if parcels.crs is None:
        parcels.set_crs(epsg=4326, inplace=True)
    if parcels.crs.is_geographic:
        parcels = parcels.to_crs(epsg=32139)

    # Spatial Joins for Historic & Context Toggles
    if user_levers.get('filter_exclude_historic', False):
        historic_path = os.path.join(DATA_DIR, "historic.geojson")
        if os.path.exists(historic_path):
            historic_layer = gpd.read_file(historic_path).to_crs(parcels.crs)
            parcels_in_historic = gpd.sjoin(parcels, historic_layer, how="inner", predicate="intersects")
            parcels = parcels[~parcels.index.isin(parcels_in_historic.index)]

    context_filter = user_levers.get('filter_context_area', 'All')
    if context_filter in ['Urban', 'Suburban']:
        context_path = os.path.join(DATA_DIR, "context_areas.geojson")
        if os.path.exists(context_path):
            context_layer = gpd.read_file(context_path).to_crs(parcels.crs)
            joined = gpd.sjoin(parcels, context_layer, how="inner", predicate="intersects")
            possible_cols = [col for col in joined.columns if any(x in col.lower() for x in ['type', 'context', 'name', 'zone'])]
            if possible_cols:
                parcels = joined[joined[possible_cols[0]].astype(str).str.contains(context_filter, case=False, na=False)]
            else:
                parcels = joined

    if parcels.empty:
        return None

    if 'LotArea' not in parcels.columns or parcels['LotArea'].sum() == 0:
        parcels['LotArea'] = parcels['geometry'].area * 10.7639 

    pid_options = [c for c in parcels.columns if any(x in c.lower() for x in ['pid', 'id', 'objectid', 'parcel'])]
    pid_col = pid_options[0] if pid_options else None

    raw_state_col = 'STATE_CD'
    state_cols = [c for c in parcels.columns if 'state' in c.lower() or 'cd' in c.lower() or 'use' in c.lower()]
    if state_cols:
        raw_state_col = state_cols[0]
        parcels['USE_DESC'] = parcels[raw_state_col].astype(str).str.strip().map(land_use_map).fillna("Unknown")
    else:
        parcels['USE_DESC'] = "Unknown"

    parcels['sim_units'] = 0
    parcels['sim_jobs'] = 0
    parcels['total_footprint_area'] = 0.0
    parcels['total_interior_area'] = 0.0

    if os.path.exists(footprint_file):
        footprints = gpd.read_file(footprint_file).to_crs(parcels.crs)
        if not footprints.empty:
            height_col = [c for c in footprints.columns if any(x in c.lower() for x in ['height', 'story', 'stories', 'bldghgt'])]
            if height_col:
                h_field = height_col[0]
                if 'story' in h_field.lower() or 'stories' in h_field.lower():
                    footprints['stories_calc'] = footprints[h_field].fillna(1).astype(int).clip(lower=1)
                else:
                    footprints['stories_calc'] = (footprints[h_field].fillna(10) / 10.0).round().astype(int).clip(lower=1)
            else:
                footprints['stories_calc'] = 1
                
            footprints['gross_interior_sqft'] = footprints['geometry'].area * 10.7639 * footprints['stories_calc']
            
            if pid_col and pid_col in footprints.columns:
                footprint_agg = footprints.groupby(pid_col).agg(
                    calc_footprint_area=('geometry', lambda x: x.area.sum() * 10.7639),
                    calc_interior_area=('gross_interior_sqft', 'sum')
                ).reset_index()
                parcels = parcels.drop(columns=['total_footprint_area', 'total_interior_area']).merge(footprint_agg, on=pid_col, how='left')
                parcels = parcels.rename(columns={'calc_footprint_area': 'total_footprint_area', 'calc_interior_area': 'total_interior_area'})
            else:
                footprints_joined = gpd.sjoin(footprints, parcels[[pid_col or 'geometry', 'geometry']].reset_index(), how="inner", predicate="within")
                if not footprints_joined.empty:
                    footprint_agg = footprints_joined.groupby('index').agg(
                        calc_footprint_area=('geometry', lambda x: x.area.sum() * 10.7639),
                        calc_interior_area=('gross_interior_sqft', 'sum')
                    ).reset_index().set_index('index')
                    parcels = parcels.drop(columns=['total_footprint_area', 'total_interior_area']).join(footprint_agg, how='left')
                    parcels = parcels.rename(columns={'calc_footprint_area': 'total_footprint_area', 'calc_interior_area': 'total_interior_area'})

    parcels['total_footprint_area'] = parcels['total_footprint_area'].fillna(0.0)
    parcels['total_interior_area'] = parcels['total_interior_area'].fillna(0.0)
    parcels['lot_coverage_pct'] = parcels['total_footprint_area'] / parcels['LotArea']

    # -------------------------------------------------------------------------
    # SCENARIO CALCULATIONS CORE WITH PRIORITY CASCADE MUTUAL EXCLUSIVITY
    # -------------------------------------------------------------------------
    zoning_cols = [c for c in parcels.columns if any(x in c.lower() for x in ['zon', 'label', 'class', 'dist'])]
    absorption = user_levers.get('market_absorption_rate', 1.0)
    redev_mode = user_levers.get('commercial_redevelopment_mode', 'Preserve Current Base Use')
    
    for idx, parcel in parcels.iterrows():
        zoning = str(parcel.get(zoning_cols[0], '')).upper() if zoning_cols else ''
        land_use = str(parcel.get('USE_DESC', '')).upper()
        state_cd = str(parcel.get(raw_state_col, ''))
        lot_area = parcel.get('LotArea', 0)
        coverage = parcel.get('lot_coverage_pct', 0)
        
        is_vacant = any(x in state_cd for x in ['A7', 'A8', 'C1', 'C10', 'C3', 'C6', 'C7', 'C8']) or 'VACANT' in land_use
        is_underutilized = coverage < 0.15 
        
        if user_levers.get('only_vacant_or_underutilized', False):
            if not (is_vacant or is_underutilized):
                continue 
        
        existing_units = estimate_existing_units(land_use, state_cd)
        
        is_residential = any(x in zoning for x in ['R', 'A', 'RES', 'SF', 'TH']) or any(x in land_use for x in ['RESIDENTIAL', 'SINGLE-FAMILY', 'DUPLEX', 'MULTI'])
        is_commercial = any(x in zoning for x in ['C', 'MU', 'B', 'COMM', 'M1', 'M2']) or any(x in land_use for x in ['COMMERCIAL', 'OFFICE', 'RETAIL', 'MIXED']) or zoning == ''
        
        parking_efficiency = 1.0 if user_levers['eliminate_parking'] else 0.65
        open_lot_space = max(0, (lot_area - parcel['total_footprint_area'])) * parking_efficiency
        
        gross_sim_units = 0
        gross_sim_jobs = 0

        # STREAM 1: RESIDENTIAL LAND PARCELS (MUTUALLY EXCLUSIVE CASCADE LOGIC)
        if is_residential:
            policy_applied = False
            
            # Priority 1: Allow Mansion Conversions (Usurps other policies if active and structure is huge)
            if user_levers.get('allow_conversions', False) and parcel['total_interior_area'] >= 2,000:
                usable_interior = parcel['total_interior_area'] * 0.85
                gross_sim_units = max(existing_units, int(usable_interior // CONVERSION_UNIT_SIZE))
                policy_applied = True
                
            # Priority 2: Lot Splits (Runs if Conversions failed/skipped, and lot is big enough)
            if not policy_applied and user_levers.get('allow_lot_splits', False) and lot_area >= user_levers.get('lot_split_trigger_size', 4000):
                max_possible_lots = int(lot_area // user_levers.get('lot_split_min_floor', 2000))
                gross_sim_units = max_possible_lots * (2 if user_levers.get('allow_townhomes', False) else 1)
                policy_applied = True
                
            # Priority 3: Middle Housing Typology Overlays (Runs if parcel was not split or converted)
            if not policy_applied and user_levers.get('allow_middle_housing', False):
                tier = user_levers.get('middle_housing_tier', '4-plex')
                if tier == '9-16' and lot_area >= 6000:
                    gross_sim_units = 16
                elif tier == '5-8' and lot_area >= 5000:
                    gross_sim_units = 8
                else:
                    gross_sim_units = 4 
                policy_applied = True
            
            # Baseline Catch: If no high-density policy applied, inherit existing physical site infrastructure unit count
            if Pis_residential and not policy_applied:
                gross_sim_units = existing_units

            # Accessory Dwelling Units Addendum (Can append only to single standalone single-family homes)
            if user_levers.get('allow_adus', False) and gross_sim_units <= 1:
                if open_lot_space >= 800: 
                    gross_sim_units += 1
            
            gross_sim_jobs = 0

        # STREAM 2: COMMERCIAL LAND PARCELS
        elif is_commercial:
            num_floors = user_levers.get('midrise_stories', 4)
            buildable_footprint = lot_area * 0.50 * parking_efficiency if user_levers.get('allow_midrise', False) else lot_area * 0.40 * parking_efficiency
            
            if redev_mode == 'Vertical Mixed-Use' and user_levers.get('allow_midrise', False):
                gross_sim_jobs = int(buildable_footprint // SQ_FT_PER_EMPLOYEE)
                gross_sim_units = int((buildable_footprint * (num_floors - 1)) // AVG_UNIT_SIZE)
            elif redev_mode == 'Pure Residential Infill':
                gross_sim_jobs = 0
                total_residential_floors = num_floors if user_levers.get('allow_midrise', False) else 1
                gross_sim_units = int((buildable_footprint * total_residential_floors) // AVG_UNIT_SIZE)
            elif redev_mode == 'Pure Commercial Jobs':
                gross_sim_units = 0
                total_commercial_floors = num_floors if user_levers.get('allow_midrise', False) else 1
                gross_sim_jobs = int((buildable_footprint * total_commercial_floors) // SQ_FT_PER_EMPLOYEE)
            elif redev_mode == 'Preserve Current Base Use':
                gross_sim_units = 0
                total_commercial_floors = num_floors if user_levers.get('allow_midrise', False) else 1
                gross_sim_jobs = int((buildable_footprint * total_commercial_floors) // SQ_FT_PER_EMPLOYEE)

        net_new_units = max(0, gross_sim_units - existing_units)
        parcels.at[idx, 'sim_units'] = int(net_new_units * absorption)
        parcels.at[idx, 'sim_jobs'] = int(gross_sim_jobs * absorption)

    return parcels

def run_master_simulation(user_levers):
    """Loops through all representative districts and aggregates results."""
    land_use_map = load_land_use_mapping()
    total_housing_units = 0
    total_jobs = 0

    target_districts = user_levers.get('active_representative_districts', list(range(1, 9)))
    for dist in target_districts:
        processed_gdf = process_district_capacity(dist, user_levers, land_use_map)
        if processed_gdf is not None:
            total_housing_units += processed_gdf['sim_units'].sum()
            total_jobs += processed_gdf['sim_jobs'].sum()

    print(f"Units Yielded: {total_housing_units} | Jobs Yielded: {total_jobs}")

if __name__ == "__main__":
    test_scenario_levers = {
        'eliminate_parking': True,            
        'allow_adus': True,                   
        'allow_lot_splits': True,             
        'allow_townhomes': True,              
        'allow_conversions': False,            
        'allow_middle_housing': True,         
        'middle_housing_tier': '5-8',        
        'allow_midrise': True,                
        'midrise_stories': 4,
        'only_vacant_or_underutilized': True,    
        'market_absorption_rate': 0.10,         
        'commercial_redevelopment_mode': 'Preserve Current Base Use', 
        'filter_exclude_historic': False,            
        'filter_context_area': 'All'
    }
    run_master_simulation(test_scenario_levers)
