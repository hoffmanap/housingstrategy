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

**4. Core Calculation Assumptions** 

Underutilized Filter: Parcels are evaluated for new capacity only if they are entirely vacant (e.g., property tags A7, A8, C1, C10) or if the existing building footprint occupies less than 15% of the total lot area.

Market Absorption Rate: A probability multiplier (default 10%, adjustable 5%–25%) is applied to all results, reflecting the likelihood of development over a 10-to-20-year horizon.Net-Positive Yield Calculation: The engine calculates total new capacity and subtracts existing units/jobs on the site to ensure the reported totals represent net-new growth.

Parking Elimination Multiplier: When the "Eliminate Parking Minimums" policy is toggled, the engine assumes that land previously required for surface or structured parking is repurposed for development, applying a 1.20x multiplier to the final unit and job yield calculations for all applied interventions.

Policy Intervention LogicInterventionUnit Calculation AssumptionJob Calculation Assumption
  ADU+1 net unit (requires lot ≥ 3,000 sq. ft. & existing unit)0
  Lot Splits+1 net unit (requires lot ≥ 7,000 sq. ft.)0
  Mansion Conversions
    4 units for lots > 4,000 sq. ft.; 
    8 units for lots > 6,000 sq. ft.0
  Missing Middle (4-8)
    4 units for lots > 4,000 sq. ft.; 
    8 units for lots > 7,000 sq. ft.0Missing Middle (9-16)
    9 units for lots > 6,000 sq. ft.; 16 units for lots > 
    10,000 sq. ft.0
  Midrise (5-Story) 50% footprint; 
    4 floors housing (850 sq. ft./unit)
    1 floor commercial (300 sq. ft./employee)
  Eliminate Parking+20% capacity bonus to all the above units/jobs+20% capacity bonus
Base Scenario Logic
  Vertical Mixed Use: Enforces a blend of commercial (jobs) and residential (units). Parking elimination expands the total floor area available for both uses.
  Commercial Only: Zeroes out residential. Yield is based on 40% lot coverage and 300 sq. ft. per employee. Parking elimination increases available site coverage for commercial use.
  Residential Only: Zeroes out jobs. Parking elimination allows for higher density per residential lot.

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
