# El Paso Housing Strategy Simulator

An interactive parcel-level simulation tool for exploring how different land use policy interventions could contribute toward El Paso's housing and job creation targets. The tool allows planners, policymakers, and the public to combine base development scenarios with specific policy levers, apply geographic constraints, and visualize cumulative potential across all eight City Council districts.

View the Simulator here: https://hoffmanap.github.io/housingstrategy/
---

## Using the Tool

The sidebar's **"How this model works"** button opens an in-app methodology
panel covering eligibility rules, yield logic, and known caveats — the
condensed version of everything documented below. **Click any parcel on the
map** to see which specific rule produced its yield (base scenario, ADU, lot
split, missing middle, midrise, or parking reform), along with the parcel's
underlying lot size, land use code, and existing unit count. The top banner
reports two numbers per category: a **conservative headline figure** (highest
single intervention per parcel — see below) and an **"up to" upper bound**
(what the same parcels would yield if every eligible policy stacked
additively instead). Treat the true answer as somewhere between the two,
not as the headline number alone.

## How the Model Works

The simulator operates at the individual parcel level. For every parcel in the dataset, the model evaluates whether a given combination of scenario and policy interventions would yield new housing units or jobs, applies a market absorption rate to translate theoretical capacity into realistic near-term production, and then aggregates results across all parcels to produce citywide and district-level totals.

The output is a **potential capacity estimate under realistic but favorable conditions** — not a guarantee of development. Every number produced is a function of parcel size, existing conditions, the selected scenario, any active policy interventions, and any applicable constraints.

**All calculation happens client-side, in the browser, in `index.html`.** There is no separate offline data-processing pipeline — the JavaScript simulation engine in `index.html` is the single, authoritative implementation of the model described below.

---

## Parcel Eligibility: The Underutilization Threshold

Before any scenario or policy calculation runs, each parcel must pass an underutilization screen. A parcel is considered underutilized — and therefore eligible for redevelopment yield — if any of the following are true:

- It is classified as vacant in the Texas assessor state code (`state_cd`) data. Vacant classifications include: residential vacant lots (A7, A8), platted vacant residential lots (C1), platted vacant commercial lots (C10), colonia lots and land tracts (C2), vacant rural or recreational lots (C3), vacant lots with limited utilities (C6, C7, C8, C9), and undeveloped rural/agricultural/desert acreage (D series).
- Its building-to-lot coverage ratio is below a threshold:
  - **Below 15%** for residential and current-use scenarios. This threshold is appropriate for El Paso's context, where single-story residential buildings on large lots commonly have coverage ratios of 10% or less, correctly identifying them as candidates for densification.
  - **Below 45%** for commercial and mixed-use scenarios (relaxed to reflect that job-generating redevelopment is viable even on partially-built commercial parcels)
- It has no existing units and no building square footage recorded

Parcels that do not meet the underutilization threshold are skipped for most policy calculations, though ADU eligibility is an exception (see below).

---

## Market Absorption Rate

All gross capacity figures are multiplied by a user-adjustable **absorption rate** before being counted in the totals. This rate represents the share of theoretically eligible parcels that would realistically redevelop over a planning horizon given market conditions, financing constraints, owner willingness, and timing. The slider runs from **0% to 100%**, with a default of **8%**.

**Where the 8% default comes from:** El Paso County averaged roughly 2,517 new housing permits per year from 2020–2024 (U.S. Census Bureau / FRED series [BPPRIV048141](https://fred.stlouisfed.org/series/BPPRIV048141)), down from an average of ~3,100/year over 2013–2022 and ~4,300/year over 2003–2012 (reported by [El Paso Matters](https://elpasomatters.org/2024/02/25/el-paso-growth-sprawl-impacts-water-bills/), citing Federal Reserve data). That reporting also notes that city population has been roughly flat despite this permitting activity, indicating much of the recent volume has been greenfield subdivision development outside city limits rather than redevelopment of already-built-up parcels — the specific category of parcel this model targets. Because the model's absorption rate applies specifically to the *infill/underutilized-parcel* pool, and county-wide permitting overstates that pool's activity, the default is set conservatively at 8% rather than at the higher county-wide pace.

**This is an order-of-magnitude anchor, not a precise calibration.** A rigorous calibration would compare actual infill permit counts against the model's own count of eligible underutilized parcels — a cross-reference this repository doesn't yet make. Until that comparison exists, treat 8% as a defensible conservative default grounded in real regional data, not as a validated estimate. A rate of 100% means all eligible parcels are assumed to redevelop (full theoretical build-out); lower rates produce more conservative, near-term estimates.

---

## Base Development Scenarios

The base scenario sets the fundamental land use character assumed for redevelopment. It determines whether a parcel's yield is counted as housing, jobs, or both, and provides a floor yield calculation for parcels that are eligible but have no active policy intervention selected.

### Current Use
Parcels are assumed to redevelop consistent with their existing use as identified by the Texas assessor state code (`state_cd`). Residentially-classified parcels (state codes beginning with A or B) contribute housing yield only. Commercially or industrially-classified parcels (state codes F1 — general commercial, and F2 — industrial) contribute jobs only, calculated as 50% lot coverage at 1,000 square feet per job. No cross-use yield is generated.

### All Residential
All eligible parcels are assumed to redevelop as residential. Jobs are hard-zeroed across all parcels in this scenario — no policy intervention (except eliminate parking minimums, which is treated as an infrastructure policy; see below) generates jobs when this scenario is active.

### All Commercial
All eligible parcels are assumed to redevelop for commercial or employment uses. Housing units are hard-zeroed. Job yield is calculated as 50% lot coverage at 1,000 square feet per job.

### Vertical Mixed Use
The only scenario in which a single parcel can produce both housing units and jobs simultaneously. Job yield follows the same 50% coverage / 1,000 sq ft formula. Housing yield follows the same rules as the residential scenario. Policy interventions that generate jobs (midrise, eliminate parking minimums) are fully active in this scenario.

---

## Policy Interventions

Policy interventions are layered on top of the base scenario. They modify the unit or job yield for eligible parcels, either by setting a specific gross yield or by boosting yield from other interventions. Multiple interventions can be active simultaneously; the model takes the **highest single-intervention yield** for units and jobs separately (they do not stack additively), except where noted.

### Accessory Dwelling Units (ADUs)
**Eligibility:** Parcels with at least one existing unit and a minimum lot size of 3,000 sq ft.
**Yield:** 1 net new unit per eligible parcel.
**Rationale:** ADUs are assumed to be attached or detached secondary units added to existing single-family or small multifamily lots. The one-unit-per-parcel assumption reflects typical municipal ADU ordinance limits and realistic construction patterns.

### Lot Splits
**Eligibility:** Underutilized parcels with a minimum lot size of 7,000 sq ft.
**Yield:** 1 net new unit per eligible parcel.
**Rationale:** Lot splits allow a single large residential parcel to be subdivided into two developable lots, each capable of supporting one unit. The 7,000 sq ft minimum reflects a practical lower bound for producing two viable buildable lots in El Paso's residential fabric.

### Mansion Conversions
**Eligibility:** Underutilized parcels with a minimum lot size of 4,000 sq ft.
**Yield:** 4 gross units, minus existing units.
**Rationale:** This intervention models the internal conversion of a single existing large-footprint home into up to 4 apartments — a distinct pathway from Missing Middle Housing below, which assumes new construction from scratch. Capping at 4 units (rather than scaling with lot size) reflects that conversion yield is bounded by the existing structure's floor area, not by how much additional land is available. Net yield subtracts existing units to avoid double-counting.

### Missing Middle Housing (4–8 Units)
**Eligibility:** Underutilized parcels.
**Yield:**
- Lots over 7,000 sq ft: 8 gross units, minus existing units
- Lots between 4,000–7,000 sq ft: 4 gross units, minus existing units
- Lots under 4,000 sq ft: ineligible

**Rationale:** Targets the "missing middle" typology — duplexes, triplexes, fourplexes, and small apartment buildings — built new rather than converted from an existing structure, and scaling with lot size the way ground-up construction naturally would. Lot size thresholds reflect the minimum footprints needed to feasibly build at these densities in El Paso.

### Missing Middle Housing (9–16 Units)
**Eligibility:** Underutilized parcels.
**Yield:**
- Lots over 10,000 sq ft: 16 gross units, minus existing units
- Lots between 6,000–10,000 sq ft: 9 gross units, minus existing units
- Lots under 6,000 sq ft: ineligible

**Rationale:** Represents the upper end of missing middle — courtyard apartments, stacked flats, and small apartment buildings. Larger lot minimums reflect the greater footprint required at this scale.

### Midrise Development
**Eligibility:** Underutilized parcels.
**Yield (units):** Assumes 50% lot coverage for the building footprint. Upper-floor residential area is calculated as `(footprint × (floors − 1))`, divided by 850 sq ft per unit (a typical floor plate per unit for midrise multifamily). Net units subtract existing units. The number of floors is user-adjustable (default: 5).
**Yield (jobs):** Ground floor is assumed to be commercial space at 1,000 sq ft per job, calculated as `(lotSqft × 0.5) / 1000`. The 1,000 sq ft figure is the conservative midpoint of the 500–1,500 sq ft per job range identified for El Paso's commercial context, chosen to avoid overstating employment capacity.
**Single-use rule:**
- Residential scenario: units only, no jobs
- Commercial scenario: jobs only, no units
- Vertical mixed use: both units and jobs
- Current use: units only (ground-floor commercial is not assumed unless the scenario explicitly allows it)

**Rationale:** Midrise is the most intensive intervention in the model. The 50% lot coverage assumption reflects typical urban setback and parking requirements even under reformed zoning. The 850 sq ft per-unit figure reflects a modest but realistic average unit size for multifamily in El Paso's market.

### Eliminate Parking Minimums
This intervention is treated differently from the housing interventions. It is an **infrastructure and regulatory policy**, not a land use designation, and its job yield survives the residential scenario's hard-zero because parking reform enables commercial activity regardless of the dominant land use type.

**When used alone:**
- Units: `lotSqft / 5,000` (a modest floor yield reflecting small-scale infill enabled by eliminating required parking)
- Jobs: `(lotSqft × 0.5) / 1000` (ground-floor commercial space at 1,000 sq ft per job)

**When combined with other interventions:**
- Units from other policies are multiplied by 1.20 (a 20% boost reflecting that eliminating parking requirements enables more of the lot to be used for building)
- Jobs: `(lotSqft × 0.5) / 1000` (same formula, applied independently)

**Single-use rule:**
- Residential scenario: unit boost only; job yield is set to zero from base scenario but the parking job boost is re-added afterward
- Commercial scenario: job boost only; no unit multiplier
- Vertical mixed use / current use: both unit multiplier and job boost apply

**Rationale:** Parking minimums consume significant land area on urban parcels. Eliminating them does not guarantee redevelopment but meaningfully expands what is financially and physically feasible. The 20% unit boost and independent job yield reflect empirical research on the relationship between parking requirements and development feasibility.

---

## Geographic Constraints

Three spatial overlays can be toggled to restrict which parcels contribute to the estimates.

### Historic District Protection
When enabled, parcels within designated historic districts are excluded from all yield calculations. This reflects the assumption that historic preservation rules would prevent most forms of significant densification on these parcels.

### Transit Corridor Focus
When enabled, only parcels within approximately a half-mile of transit corridors are included in calculations. This allows the model to explore a transit-oriented development scenario by concentrating estimated yield near existing or planned high-frequency routes.

### Apply Deed Restrictions (Restrictive Covenants)
When enabled, the model reads parcel-level covenant data from `covenants1.geojson` and `covenants2.geojson` and applies the following rules as a **final override** — meaning covenant restrictions are applied after all scenario and policy calculations, and always take precedence.

The covenant data uses the following fields:

| Field | Meaning |
|---|---|
| `RESTRICTIONS` | Descriptive label — not used in calculations |
| `SINGLE FAMILY ONLY` | `Y` = parcel is restricted to one single-family detached unit; multifamily and commercial uses are prohibited |
| `allow_mf` | `false` = multifamily is not permitted; units are capped at 1 |
| `allow_com` | `false` = commercial uses are not permitted; jobs are set to zero |
| `max_units` | Integer hard cap on total units; yield cannot exceed this value regardless of intervention |

Covenant restrictions apply regardless of which base scenario or policy interventions are active. A parcel with `SINGLE FAMILY ONLY = Y` will never produce more than 1 unit and will never produce jobs, even under a vertical mixed use scenario with midrise and parking reform enabled.

---

## Output Targets

The model tracks cumulative yield against two planning targets displayed in the top banner:

- **35,000 net new housing units**
- **55,000 net new jobs**

These targets represent El Paso's long-range housing and employment goals. When cumulative yield meets or exceeds a target, the counter turns green. The district-level breakdown table shows how yield is distributed across all eight City Council districts.

---

## Key Limitations and Caveats

**This model estimates potential capacity, not predicted outcomes.** Development depends on factors not captured here, including land prices, construction costs, financing availability, infrastructure capacity, owner intent, and permitting timelines.

**The model does not check current base zoning.** Each policy intervention is assumed to supply its own entitlement — the tool models capacity *under the reform*, not capacity under today's zoning code. Eligibility is based on parcel physical characteristics (coverage ratio, vacancy, existing units), not on what current zoning permits.

**Parcel data quality affects results.** Missing lot square footage values default to 6,000 sq ft. Missing building square footage is treated as zero — which tends to count undocumented parcels as underutilized/eligible rather than excluding them, so totals in data-sparse areas should be treated with extra caution. Zoning tag matching uses string pattern detection and may not capture every parcel correctly.

**Interventions do not stack additively.** When multiple housing policies are active, the model's headline number takes the single highest-yielding intervention per parcel for units and for jobs separately. This is a deliberately conservative assumption. The interface now reports an "up to" upper bound alongside the headline figure, reflecting what the same parcels would yield if every eligible policy stacked instead — treat the true answer as falling between the two, not as either bound alone.

**Per-unit and per-job area assumptions are fixed planning benchmarks**, not parcel-specific estimates: 1,000 sq ft per job, 850 sq ft per multifamily unit, 50% ground-floor coverage. These are reasonable citywide averages but will over- or under-state yield on any individual parcel that differs from them.

**The absorption rate is the most consequential single assumption.** At lower absorption rates, even aggressive policy combinations produce modest totals. Calibrating this rate to El Paso's historical development pace — e.g. against actual permitting activity — is recommended for scenario analysis intended to inform policy, rather than treating the default as authoritative.

**Covenant data coverage may be incomplete.** The deed restriction overlay reflects recorded covenants in the dataset but does not capture all private deed restrictions, HOA rules, or informal agreements that might limit redevelopment.

**No equity or displacement dimension is modeled.** The tool reports capacity by council district but does not flag concentration of yield in historically under-invested or majority-renter areas. Cross-referencing output with ACS/HMDA demographic data is recommended before using results to argue for or against a specific policy's distributional effects.

---

## License

This repository is licensed under the MIT License (see `LICENSE`). The underlying parcel, assessor, and covenant data are sourced from public records and are not covered by the code license — see their original sources for terms of use.
