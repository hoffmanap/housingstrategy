import os
import pandas as pd
import geopandas as gpd

DATA_DIR = "./data"

def get_existing_units(land_use, state_code):
    c = str(state_code).upper(); d = str(land_use).upper()
    if any(x in c for x in ['A7', 'A8', 'C1', 'C10', 'C3', 'C6', 'C7', 'C8']): return 0
    if 'SINGLE-FAMILY' in d or c == 'A1': return 1
    if 'DUPLEX' in d or c in ['A51', 'B1']: return 2
    if 'TRIPLEX' in d or c in ['A53', 'B3']: return 3
    if 'QUAD' in d or c in ['A54', 'B4', 'B9']: return 4
    if 'FIVE' in d or c in ['A55', 'B5', 'B7']: return 5
    if 'SIX' in d or c in ['A56', 'B6', 'B8']: return 6
    if 'APARTMENT' in d or 'MULTI' in d or c in ['A52', 'B2']: return 12  
    return 0

print("Loading Land Use Map...")
try:
    land_use_df = pd.read_csv(os.path.join(DATA_DIR, "state_cd.csv"))
    land_use_df.columns = [str(c).lower().strip() for c in land_use_df.columns]
    land_use_map = pd.Series(land_use_df.get('state_cd_desc', '').values, index=land_use_df['state_cd'].astype(str).str.strip().str.upper()).to_dict()
except:
    print("Warning: state_cd.csv not found or unreadable. Using blank land use map.")
    land_use_map = {}

for d in range(1, 9):
    parcel_file = f"D{d}GrowthParcels.geojson"
    if not os.path.exists(os.path.join(DATA_DIR, parcel_file)): continue
        
    print(f"\n--- Processing District {d} ---")
    parcels = gpd.read_file(os.path.join(DATA_DIR, parcel_file))
    parcels.columns = [str(c).lower().strip() for c in parcels.columns]
    if parcels.crs is None: parcels.set_crs(epsg=4326, inplace=True)

    # Base Attributes
    parcels['district'] = d # REQUIREMENT: Track district for summaries
    parcels['state_cd_clean'] = parcels.get('state_cd', parcels.get('state_code', pd.Series(dtype=str))).astype(str).str.strip().str.upper()
    parcels['use_desc'] = parcels['state_cd_clean'].map(land_use_map).fillna("Unknown")
    parcels['targetlotarea'] = pd.to_numeric(parcels.get('lotarea', parcels.get('shape_area', 0)), errors='coerce').fillna(0.0)
    parcels['existing_units'] = parcels.apply(lambda row: get_existing_units(row['use_desc'], row['state_cd_clean']), axis=1)

    # Footprints
    parcels['footprint_sqft'] = 0.0
    parcels['interior_sqft'] = 0.0
    foot_path = os.path.join(DATA_DIR, f"footprints_d{d}.geojson")
    if os.path.exists(foot_path):
        ft = gpd.read_file(foot_path)
        ft.columns = [str(c).lower().strip() for c in ft.columns]
        if 'pidn' in ft.columns and 'pidn' in parcels.columns:
            ft['stories'] = (pd.to_numeric(ft.get('height_ft', 0), errors='coerce') / 10.0).fillna(1).round().clip(lower=1).astype(int)
            ft['base_sqft'] = pd.to_numeric(ft.get('sqfeet', ft.get('shape_area', 0)), errors='coerce').fillna(0.0)
            ft['gross_sqft'] = ft['base_sqft'] * ft['stories']
            agg = ft.groupby('pidn').agg(footprint_sqft=('base_sqft', 'sum'), interior_sqft=('gross_sqft', 'sum')).reset_index()
            parcels = parcels.merge(agg, on='pidn', how='left', suffixes=('', '_dup'))
            parcels['footprint_sqft'] = parcels['footprint_sqft_dup'].fillna(0.0)
            parcels['interior_sqft'] = parcels['interior_sqft_dup'].fillna(0.0)
            parcels.drop(columns=['footprint_sqft_dup', 'interior_sqft_dup'], inplace=True, errors='ignore')

    parcels['coverage_pct'] = parcels.apply(lambda r: r['footprint_sqft'] / r['targetlotarea'] if r['targetlotarea'] > 0 else 0, axis=1)

    # Historic & Corridor Filters
    for col, file in [('in_corridor', 'transit_corridors.geojson'), ('in_historic', 'historic_districts.geojson')]:
        parcels[col] = False
        path = os.path.join(DATA_DIR, file)
        if os.path.exists(path):
            limiter = gpd.read_file(path)
            if limiter.crs is None: limiter.set_crs(epsg=4326, inplace=True)
            if col == 'in_corridor': 
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    limiter['geometry'] = limiter.geometry.buffer(0.00359)
            intersected = gpd.sjoin(parcels, limiter, how="inner", predicate="intersects")
            parcels.loc[parcels.index.isin(intersected.index), col] = True

    # REQUIREMENT: Context Areas (Extract Urban vs Suburban label directly)
    parcels['context_type'] = "None"
    ctx_path = os.path.join(DATA_DIR, 'context_areas.geojson')
    if os.path.exists(ctx_path):
        ctx = gpd.read_file(ctx_path)
        if ctx.crs is None: ctx.set_crs(epsg=4326, inplace=True)
        # Find the text column that holds 'Urban' or 'Suburban'
        text_cols = ctx.select_dtypes(include=['object']).columns
        if len(text_cols) > 0:
            type_col = text_cols[0] # Assume the first text column holds the typology name
            ctx_subset = ctx[['geometry', type_col]].rename(columns={type_col: 'extracted_context'})
            parcels = gpd.sjoin(parcels, ctx_subset, how="left", predicate="intersects")
            parcels['context_type'] = parcels['extracted_context'].fillna("None")
            parcels.drop(columns=['index_right', 'extracted_context'], inplace=True, errors='ignore')
            parcels = parcels[~parcels.index.duplicated(keep='first')] # Remove duplicate intersections

    cols_to_keep = ['geometry', 'pidn', 'district', 'zonelabel', 'state_cd_clean', 'use_desc', 'targetlotarea', 'existing_units', 'footprint_sqft', 'interior_sqft', 'coverage_pct', 'in_corridor', 'in_historic', 'context_type']
    final_parcels = parcels[[c for c in cols_to_keep if c in parcels.columns]]

    out_file = os.path.join(DATA_DIR, f"Ready_Parcels_D{d}.geojson")
    final_parcels.to_file(out_file, driver="GeoJSON")
    print(f"SUCCESS: Saved {out_file}")