import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd

DATA_DIR = "./data" # This path works for both local server and GitHub Pages

def json_serial(obj):
    """Helper to fix the int64 JSON serialization error."""
    if isinstance(obj, (np.int64, np.int32, np.int_)): return int(obj)
    if isinstance(obj, (np.float64, np.float32)): return float(obj)
    raise TypeError

def load_land_use_mapping():
    path = os.path.join(DATA_DIR, "state_cd.csv")
    if not os.path.exists(path): return {}
    df = pd.read_csv(path)
    return pd.Series(df.state_cd_desc.values, index=df.state_cd.astype(str).str.strip()).to_dict()

def process_district(district_num, levers, land_use_map):
    parcel_path = os.path.join(DATA_DIR, f"D{district_num}GrowthParcels.geojson")
    if not os.path.exists(parcel_path): return None
    
    parcels = gpd.read_file(parcel_path).to_crs(epsg=32139)
    
    # Simple Capacity Math
    parcels['sim_units'] = (parcels['LotArea'] // 2000) * 1  # Placeholder logic
    parcels['sim_jobs'] = 0
    
    # Return specific parcels that changed
    return parcels[['sim_units', 'sim_jobs', 'geometry']]

# This is the function the index.html calls
def run_simulation(user_levers):
    districts = user_levers.get('active_representative_districts', [1])
    land_use_map = load_land_use_mapping()
    
    results = {"totals": {"units": 0, "jobs": 0}, "breakdowns": {}, "map_data": []}
    
    for d in districts:
        gdf = process_district(d, user_levers, land_use_map)
        if gdf is not None:
            u = int(gdf['sim_units'].sum())
            j = int(gdf['sim_jobs'].sum())
            results["breakdowns"][d] = {"units": u, "jobs": j}
            results["totals"]["units"] += u
            results["totals"]["jobs"] += j
    
    return json.dumps(results, default=json_serial)
