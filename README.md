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

### Why does the model need this at all?

Without it, the tool would report what happens if *every single eligible parcel redeveloped simultaneously* — which never happens in real cities. Some owners never sell or build. Some parcels aren't financially attractive to a developer even when zoning allows it. Some sit untouched for decades simply because nothing prompts the owner to act. The absorption rate is the model's way of saying "only some share of what's technically possible actually gets built in a real planning window," rather than reporting a number no city could ever achieve.

### A worked example

Say a given policy combination makes 8,000 parcels citywide eligible, and on average each eligible parcel could gain 2.5 net units under that combination. That's a **gross capacity of 20,000 units** — the number you'd get at 100% absorption, i.e. if every eligible owner redeveloped at once.

At the default **8% absorption rate**, the model instead counts:

> 20,000 gross units × 8% = **1,600 units**

as the realistic outcome over the model's 10-year horizon. The other 18,400 units of "theoretical capacity" remain possible under the reformed zoning, but the model doesn't assume they'll actually get built — most of those parcels will simply stay as they are for the next decade, the way most parcels in most cities do even after upzoning.

### Where the 8% number itself comes from

This is the one number in the model we could ground in actual regional data rather than a generic planning rule of thumb, so here's the full chain of reasoning:

1. **Start with real construction activity.** El Paso County averaged roughly 2,517 new housing permits per year from 2020–2024 (U.S. Census Bureau / FRED series [BPPRIV048141](https://fred.stlouisfed.org/series/BPPRIV048141)). For context, that's *down* from ~3,100/year over 2013–2022 and ~4,300/year over 2003–2012 (reported by [El Paso Matters](https://elpasomatters.org/2024/02/25/el-paso-growth-sprawl-impacts-water-bills/), citing Federal Reserve data) — the pace of new housing construction has been shrinking, not growing.
2. **Recognize what that number actually represents.** That El Paso Matters reporting also notes city population has stayed roughly flat despite all that permitting — meaning much of it has been greenfield subdivision development spreading outward at the county's edge, not redevelopment of parcels that are already built up within city limits. This model only touches that second category — existing, already-parcelized, underutilized land — so the true "infill-only" pace is smaller than 2,517/year, though public data doesn't let us isolate exactly how much smaller.
3. **Choose a conservative default in that light.** Rather than use the full county-wide pace (which would overstate infill activity) or an arbitrary round number, 8% was chosen specifically to sit clearly below the county-wide historical pace, reflecting that infill redevelopment is a slower, harder process than greenfield building on open land — new utility hookups aren't needed, but existing structures, existing owners, and existing neighbors all have to be worked around.

**Be clear about what this number is and isn't.** It's a defensible, data-grounded *starting point* — not a validated calibration. A true calibration would compare actual annual infill permits against this model's own count of eligible underutilized parcels, a comparison the underlying dataset doesn't yet make possible. Until that comparison exists, 8% should be treated as a reasonable default to stress-test, not a precise forecast — which is exactly why the slider goes all the way from 0% to 100% rather than locking in a single number.

---

## Base Development Scenarios

The base scenario sets the fundamental land use character assumed for redevelopment. It determines whether a parcel's yield is counted as housing, jobs, or both.

### Current Use
Parcels are assumed to redevelop consistent with their existing use as identified by the Texas assessor state code (`state_cd`). Residentially-classified parcels (state codes beginning with A or B) contribute housing yield only. Commercially or industrially-classified parcels (state codes F1 — general commercial, and F2 — industrial) contribute jobs only, calculated as 50% lot coverage at 1,000 square feet per job (default; adjustable). **This job yield only applies when at least one policy intervention is active.** With Current Use selected and no interventions checked, the model shows zero net change citywide — a true do-nothing baseline to compare reforms against, not a floor that fires on its own. (An earlier version of this tool applied the commercial job yield unconditionally under Current Use, which made "no intervention selected" misleadingly show large citywide job totals — e.g. tens of thousands of jobs with nothing checked. That's fixed.)

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

### Missing Middle Housing (4–8 Units) & Missing Middle Housing (9–16 Units)

**Why these caps and this eligibility rule exist — Texas SB840:** SB840 requires that any zone permitting more than 3 units must allow 4 floors and the city's maximum density (145 units/acre) — a state mandate the city cannot restrict. The one exception is a "workaround": on parcels that currently have 1–3 existing units (single-family, duplex, or triplex), the city may impose additional local limits in exchange for offering a density bonus. Both Missing Middle checkboxes model this bonus program specifically — which is why eligibility is restricted to exactly 1, 2, or 3 existing units.

**Eligibility:** Underutilized parcels with exactly 1, 2, or 3 existing units.

**Yield — same formula, different cap:**
1. Compute the buildable envelope: 35 ft height cap (≈3 floors, at a standard ~11.7 ft floor-to-floor height — a local limit below SB840's full 4-floor mandate, part of the city's workaround) × 50% lot coverage × lot area, divided by the adjustable unit size assumption — `envelope units = floor((lot sq ft × 0.5 × 3) / unit size)`.
2. Subtract existing units from the envelope first, to get the additional capacity the site can support beyond what's already there.
3. Cap that additional capacity at **8** (the 4-8 checkbox) or **16** (the 9-16 checkbox) — up to and including that number.

This means the two checkboxes only diverge once a lot's envelope has enough spare capacity to exceed 8 — on small lots where the site itself can't support more than 8 *additional* units regardless of which is chosen, both checkboxes agree (correctly, since the physical constraint binds before the policy cap does). On larger single-family/duplex/triplex lots, or with a smaller unit size assumption, the 16-unit cap allows meaningfully more than the 8-unit cap.

**A known limitation — unit size vs. lot width:** this formula sizes buildings by dividing available floor area by an assumed unit size. Dan Parolek's *Missing Middle Housing* argues building size (and therefore unit count) should instead be driven by lot width, which better reflects a building's street-facing massing and fit within existing neighborhood character. This dataset has lot area but not lot width, and approximating width from parcel geometry (e.g. a bounding-box calculation) is unreliable for irregular or non-rectangular parcels — so unit size is used here as a practical substitute, not because it's judged to be the more theoretically correct approach. If reliable lot-width or frontage data becomes available, switching to Parolek's method would be a meaningful improvement.

### SB840 Baseline (Commercial & 4+ Unit Parcels) — a last resort, not a recommended outcome

**What this models:** everything the Missing Middle bonus program above does *not* cover — commercial parcels, vacant land, and anything already at 4+ units (a quadplex or larger, or plainly described as multifamily/multiplex). These parcels aren't the 1-3 unit properties the Missing Middle "workaround" is offered to, so SB840's flat mandate applies to them directly and in full: 4 floors (the state's actual minimum — not the Missing Middle workaround's reduced 35 ft height) and the citywide maximum density, with no local discretion to restrict it further.

**Eligibility:** Underutilized parcels that are commercial, vacant (0 existing units), or already at 4+ units.

**Yield:** Same minimum-unit-size approach as Missing Middle, at SB840's actual mandated floor count — `gross units = floor((lot sq ft × 0.5 × 4) / unit size)`, minus existing units.

**Read this as a last resort, not a preferred policy.** Its numbers are intentionally large and out of scale with typical neighborhood character — that's the point, not an error to fix. This is what happens by default, everywhere it applies, absent any more tailored local action: a blunt, one-size-fits-all state mandate rather than the context-sensitive infill the other interventions represent. It's deliberately excluded from "Load Full Reform Package" in the tool and kept visually separate in the sidebar (styled distinctly, under a "Last Resort — Not a Preferred Outcome" label) for exactly this reason: the ADU, lot split, mansion conversion, Missing Middle, Midrise, and parking reform policies exist precisely so this blunt instrument doesn't have to be the only path to added density and jobs. The scale of what SB840 forces absent local action is itself the argument for the alternatives.

This is modeled as its own opt-in checkbox rather than an always-on baseline, even though SB840 is current law rather than a hypothetical reform, so that a true zero-policy run still shows zero net change — consistent with every other policy in this tool. Toggle it on to see what the state mandate alone forces, independent of any local policy choice — and to make the case for why the alternatives above are preferable.

**Midrise's floor selector also has a 4-floor minimum**, for the same reason: SB840 sets 4 floors as a floor, not a suggestion, wherever this level of density is permitted.

### Midrise Development
**Eligibility:** Underutilized parcels.
**Yield (units):** Uses the same citywide density standard as SB840 Baseline above — 145 units/acre, scaled by the number of floors selected, representing the full building envelope: `gross units = floor(145 × acres × floors)`. If off-street parking is still required (the "Eliminate Parking Minimums" policy is NOT active), the achievable count is reduced by however much land that parking would consume — 300 sq ft/space, assuming the standard 1 space per unit ratio. With parking eliminated, the full envelope is available for housing. Net units subtract existing units. **The floor selector's minimum is 4 floors** — SB840 sets this as the state-mandated minimum wherever this density is permitted, not a suggestion, so fewer floors isn't an option (default: 4).
**Yield (jobs):** Ground floor is assumed to be commercial space at 1,000 sq ft per job (adjustable), calculated as `(lot sq ft × 0.5) / job size` — independent of the residential envelope calculation above.
**Single-use rule:**
- Residential scenario: units only, no jobs
- Commercial scenario: jobs only, no units
- Vertical mixed use: both units and jobs
- Current use: units only (ground-floor commercial is not assumed unless the scenario explicitly allows it)

**A stark consequence worth knowing:** because 145 units/acre × 300 sq ft/space ≈ 43,500 sq ft — almost exactly one acre — the parking requirement alone consumes nearly the entire buildable envelope at this density if off-street parking is required. In practice, Midrise produces close to zero units unless paired with "Eliminate Parking Minimums." This isn't a bug; it's a direct, if stark, mathematical illustration of why parking minimums are fundamentally in tension with modern density targets.

**Rationale:** Midrise is the most intensive intervention in the model. The 50% lot coverage assumption reflects typical urban setback and parking requirements even under reformed zoning.

**Where 850 sq ft/unit and 1,000 sq ft/job come from, honestly:** these are general planning-literature benchmarks, not figures derived from El Paso-specific data — unlike the absorption rate above, no local dataset exists to calibrate them against. 850 sq ft approximates a modest, efficient one- to two-bedroom multifamily unit — near the lower-middle of the range for newly built small multifamily nationally. 1,000 sq ft/job sits in the middle of a wide range: dense uses like retail or office can run closer to 200–500 sq ft/employee, while warehouse and light-industrial space can run 1,000–2,000+ sq ft/employee. Rather than assume the densest possible commercial use everywhere — which would inflate job counts — the model uses a single blended, moderate figure across all commercial yield calculations. This is a real simplification: a parcel that would realistically become dense ground-floor retail is likely undercounted on jobs, while one that would become light-industrial space is likely overcounted.

**Both figures are adjustable.** Rather than lock in defaults we can't fully validate, the tool exposes both as sliders under "Model Assumptions (Advanced)" in the sidebar (500–1,400 sq ft/unit, 250–2,000 sq ft/job), each with inline guidance on which direction to move them and why. Refining this into use-specific job densities (matched to what's actually zoned or plausible per parcel) would still be a meaningful improvement to a future version of this model — the sliders let a user approximate that manually in the meantime.

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

**Why 20%, in plain English:** A standard parking space plus its share of drive aisles and maneuvering room typically consumes 300–400 square feet — more land, in many cases, than the housing unit it serves. This isn't a new observation; it's the central finding of decades of parking-policy research, most notably UCLA planning professor Donald Shoup's *The High Cost of Free Parking*, which documents how minimum parking requirements convert a large share of a typical development site into space for cars rather than people, and how removing that mandate frees up buildable area for housing or commercial space instead ([Shoup, "The Trouble with Minimum Parking Requirements," *Transportation Research Part A*, 1999](https://www.vtpi.org/shoup.pdf)).

**Be honest about the specific number.** Shoup's research establishes *why* parking minimums meaningfully constrain buildable area — it does not hand us a single universal "X% more units" conversion factor, because the actual land recovered depends heavily on lot shape, existing setback rules, and how a specific city's parking code is written. 20% is this model's own simplifying default: a deliberately moderate, round-number estimate of the yield boost from freed-up land, chosen to be clearly noticeable without assuming an unrealistically large windfall. It is not itself a number pulled from a study of El Paso specifically.

**This number is adjustable.** The "Parking Reform Boost" slider under "Model Assumptions (Advanced)" runs 0–50%. Move it toward 0% for a maximally conservative estimate that assumes parking reform has little practical effect on what actually gets built; move it toward 30–50% if you believe El Paso's current parking minimums are unusually large relative to actual demand — freeing up more land than a typical city's parking reform would.

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

## Known Data Quality Issues

Two real issues were found while investigating why parcel-level detail looked wrong — one is fixed in this version, one is a source-data gap that still needs attention before relying on District 1's numbers.

### Fixed: field-name mismatch was making every parcel look vacant

The engine's data-extraction logic was written against assumed field names (`building_sqft`, `lot_sqft`, `state_cd`) using loose substring matching. The actual parcel files use different field names entirely (`footprint_sqft`, `targetlotarea`, `state_cd_clean`, `existing_units`, `use_desc`). The substring matching didn't reliably find the real fields — in particular, no field name contains "bldg" or "build", so building square footage was **never populated for any parcel**, regardless of what the source data actually said. Combined with the underutilization rule (`existingUnits === 0 && bldgSqft === 0` counts as underutilized), this made every parcel with a real building look artificially vacant. This is now fixed: the engine reads the exact verified field names, and the parcel popup shows a plain-English land use description (`use_desc`) alongside the assessor code (`state_cd_clean`) where available.

### Not fixed — needs attention: District 1's parcel file has no existing-conditions data

Checking all eight district files directly, `Ready_Parcels_D1.geojson` has **zero** parcels (out of 950) with any existing-conditions data — every single one shows `existing_units: 0`, `coverage_pct: 0`, `footprint_sqft: 0`, `use_desc: "Unknown"`, and `state_cd_clean: null`. Every other district file (D2–D8) has substantial real data — for example, D8 has real values for roughly 45–66% of its parcels depending on the field. This strongly suggests District 1's file was generated without the assessor-data join that the other seven districts received, rather than District 1 genuinely being 950 uniformly vacant parcels.

**What this means in practice:** with the field-mapping fix above, every other district's "underutilized" and yield numbers now reflect real building conditions. District 1's numbers still can't be trusted — they'll look like every parcel is vacant and eligible, because the source file has no data to say otherwise, not because that's true. The parcel popup now flags this directly (a data-gap warning appears on any parcel with zero data across every field), but that's a symptom flag, not a fix. **Regenerating `Ready_Parcels_D1.geojson` with the same assessor join used for the other seven districts is the actual fix**, and should happen before District 1's numbers are used for anything — including this competition submission, if District 1 factors into the citywide totals you present.

---



**This model estimates potential capacity, not predicted outcomes.** Development depends on factors not captured here, including land prices, construction costs, financing availability, infrastructure capacity, owner intent, and permitting timelines.

**The model does not check current base zoning.** Each policy intervention is assumed to supply its own entitlement — the tool models capacity *under the reform*, not capacity under today's zoning code. Eligibility is based on parcel physical characteristics (coverage ratio, vacancy, existing units), not on what current zoning permits.

**Parcel data quality affects results.** Missing lot square footage values default to 6,000 sq ft. Missing building square footage is treated as zero — which tends to count undocumented parcels as underutilized/eligible rather than excluding them, so totals in data-sparse areas should be treated with extra caution. Zoning tag matching uses string pattern detection and may not capture every parcel correctly.

**Interventions do not stack additively.** When multiple housing policies are active, the model's headline number takes the single highest-yielding intervention per parcel for units and for jobs separately. This is a deliberately conservative assumption. The interface now reports an "up to" upper bound alongside the headline figure, reflecting what the same parcels would yield if every eligible policy stacked instead — treat the true answer as falling between the two, not as either bound alone.

**Per-unit and per-job area assumptions are fixed planning benchmarks**, not parcel-specific or El Paso-specific estimates: 1,000 sq ft per job, 850 sq ft per multifamily unit, 50% ground-floor coverage. See "Where 850 sq ft/unit and 1,000 sq ft/job come from, honestly" under Midrise Development above for the full reasoning and its limits — these will over- or under-state yield on any individual parcel that differs from the citywide averages they're built on.

**The absorption rate is the most consequential single assumption.** At lower absorption rates, even aggressive policy combinations produce modest totals. Calibrating this rate to El Paso's historical development pace — e.g. against actual permitting activity — is recommended for scenario analysis intended to inform policy, rather than treating the default as authoritative.

**Covenant data coverage may be incomplete.** The deed restriction overlay reflects recorded covenants in the dataset but does not capture all private deed restrictions, HOA rules, or informal agreements that might limit redevelopment.

**No equity or displacement dimension is modeled.** The tool reports capacity by council district but does not flag concentration of yield in historically under-invested or majority-renter areas. Cross-referencing output with ACS/HMDA demographic data is recommended before using results to argue for or against a specific policy's distributional effects.

---

## License

This repository is licensed under the MIT License (see `LICENSE`). The underlying parcel, assessor, and covenant data are sourced from public records and are not covered by the code license — see their original sources for terms of use.
