**El Paso Housing Strategy Simulator**
**Overview**
The El Paso Housing Strategy Simulator is an interactive, browser-based spatial analysis tool designed to test the impact of urban planning policy interventions on housing and job growth. By simulating development scenarios across the city's eight representative districts, this tool enables planners to visualize capacity changes in real-time.
Link: https://hoffmanap.github.io/housingstrategy/

**Methodology**
**1. Spatial Pre-processing (ArcGIS)**
To ensure high performance in a web browser, we shift the heavy spatial computation from the "runtime" (when the user clicks) to the "prep-time" (data creation).

Spatial Join Enrichment: Using ArcGIS, we perform a Point-in-Polygon join between raw parcel geometry and policy layers:

Historic Districts: Flagging parcels for exclusion based on preservation policies.

Context Areas: Attributing parcels as either "Urban" or "Suburban."

Transit Corridors: Identifying parcels with high-frequency transit access.

Standardization: We enforce a uniform schema across all 8 districts. Every parcel is normalized to hold the required attributes: district, zonelabel, in_historic, in_corridor, context_type, and targetlotarea.

**2. Data Structuring (Python)**
The prep_data.py script ensures our data is "frontend-ready."

Data Sanitization: We handle null values and standardize coordinate systems to EPSG:4326 (WGS84).

Chunking: Large city-wide datasets are split into district-level GeoJSON files (Ready_Parcels_D1.geojson through D8). This allows the simulator to load data asynchronously, preventing browser crashes.

**3. Simulation Logic (JavaScript)**
The simulation engine runs on the client side using a three-stage logic pipeline:

Visibility Filter: Before calculations, the script checks if a parcel survives the user's selected filters (District, Transit, Historic, etc.).

Designation Logic: Based on zonelabel and user-selected Scenarios, the parcel is assigned a "DNA" of being Residential, Commercial, or Mixed-Use.

Additive Calculation: * The engine iterates through every visible parcel, applying policy multipliers (e.g., adding units for ADUs or jobs for Midrise).

Absorption Rate: Raw potential is multiplied by an absorption percentage to simulate real-world market capacity.

Accumulation: To ensure accuracy, the tool sums decimal results across the district before rounding to an integer, preventing significant data loss caused by rounding errors.

**Project Structure**
/data/: Contains the processed Ready_Parcels_D{n}.geojson files.

index.html: The primary interface containing the Leaflet map and simulation engine.

prep_data.py: The automation script for GIS data standardization.

requirements.txt: Project dependencies including geopandas and pandas.

**How to Run**
Local Server: Browsers prevent loading local data files for security. You must launch a local server from your project root:

Bash
python -m http.server 8000
Access: Open your browser to http://localhost:8000.

_Methodology Logic Flow_
Residential Calculation: if(adus) units += 1; if(lot_splits) units += 2;

Commercial Calculation: parcelJobs += 5 (baseline); if(midrise) { parcelJobs += 15; units += floors; }

_Scenario Overrides_: Global switches force parcels to ignore their zoning base and adopt the user's current scenario design (e.g., all parcels treated as Mixed-Use).
