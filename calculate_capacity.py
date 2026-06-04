import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd

DATA_DIR = "./data"

def to_serializable(val):
    """Recursively convert NumPy types to standard Python types for JSON."""
    if isinstance(val, (np.int64, np.int32, np.int_)): return int(val)
    if isinstance(val, (np.float64, np.float32)): return float(val)
    if isinstance(val, dict): return {k: to_serializable(v) for k, v in val.items()}
    if isinstance(val, list): return [to_serializable(v) for v in val]
    return val

def process_district(district_num, user_levers):
    # Filename fixed to match your requirement: footprints_d{n}
    parcel_path = os.path.join(DATA_DIR, f"D{district_num}GrowthParcels.geojson")
    footprint_path = os.path.join(DATA_DIR, f"footprints_d{district_num}.geojson")
    
    if not os.path.exists(parcel_path): return None
    
    parcels = gpd.read_file(parcel_path).to_crs(epsg=32139)
    # Placeholder: Your actual capacity logic here
    parcels['sim_units'] = 50 # Example placeholder
    parcels['sim_jobs'] = 10
    return parcels[['sim_units', 'sim_jobs', 'geometry']]

def run_simulation(user_levers):
    districts = user_levers.get('active_representative_districts', [1])
    results = {"totals": {"units": 0, "jobs": 0}, "breakdowns": {}, "map_data": []}
    
    for d in districts:
        gdf = process_district(d, user_levers)
        if gdf is not None:
            u = int(gdf['sim_units'].sum())
            j = int(gdf['sim_jobs'].sum())
            results["breakdowns"][d] = {"units": u, "jobs": j}
            results["totals"]["units"] += u
            results["totals"]["jobs"] += j
            
    # Clean the data before serialization
    clean_results = to_serializable(results)
    return json.dumps(clean_results)
