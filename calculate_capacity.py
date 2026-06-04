import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd

# Define the absolute directory path where your data sits
DATA_DIR = r"C:\Users\Angelica\OneDrive\Housing Strategy\data"
STATE_CD_PATH = os.path.join(DATA_DIR, "state_cd.csv")

# Constants
AVG_UNIT_SIZE = 850
SQ_FT_PER_EMPLOYEE = 300

def default_converter(o):
    if isinstance(o, (np.int64, np.int32)): return int(o)
    if isinstance(o, (np.float64, np.float32)): return float(o)
    raise TypeError

def load_land_use_mapping():
    if not os.path.exists(STATE_CD_PATH): return {}
    df = pd.read_csv(STATE_CD_PATH)
    df.columns = df.columns.str.strip()
    return pd.Series(df.state_cd_desc.values, index=df.state_cd.astype(str).str.strip()).to_dict()

def process_district_capacity(district_num, user_levers, land_use_map):
    # Pattern: D1GrowthParcels.geojson and Footprints_D1.geojson
    parcel_file = os.path.join(DATA_DIR, f"D{district_num}GrowthParcels.geojson")
    footprint_file = os.path.join(DATA_DIR, f"Footprints_D{district_num}.geojson")
    
    if not os.path.exists(parcel_file):
        print(f"Skipping D{district_num}: {parcel_file} not found.")
        return None

    parcels = gpd.read_file(parcel_file)
    if parcels.crs is None: parcels.set_crs(epsg=4326, inplace=True)
    parcels = parcels.to_crs(epsg=32139)

    # Optional Transit Corridor
    parcels['in_corridor'] = False
    corridor_path = os.path.join(DATA_DIR, "transit_corridors.geojson")
    if user_levers.get('allow_midrise', False) and os.path.exists(corridor_path):
        corridors = gpd.read_file(corridor_path).to_crs(parcels.crs)
        corridors['geometry'] = corridors.geometry.buffer(400)
        parcels_in_corr = gpd.sjoin(parcels, corridors, how="inner", predicate="intersects")
        parcels.loc[parcels.index.isin(parcels_in_corr.index), 'in_corridor'] = True

    # Capacity Logic (Simplified for demonstration of structural fix)
    parcels['sim_units'] = 0
    parcels['sim_jobs'] = 0
    
    # ... (Rest of your original logic here) ...
    # Ensure all math returns pure Python types:
    parcels['sim_units'] = parcels['sim_units'].astype(int)
    parcels['sim_jobs'] = parcels['sim_jobs'].astype(int)
    
    return parcels
