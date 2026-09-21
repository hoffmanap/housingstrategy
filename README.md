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

### Three design rules the engine follows

These emerged from auditing the formulas and are worth stating explicitly, since violating any of them has produced real bugs in earlier versions:

1. **Zero policies means zero net change, in every scenario.** A base scenario is a framing for how reform yield is counted, not a source of yield on its own. Selecting "Commercial Only" or "Vertical Mixed Use" with no policy checked correctly produces 0 units and 0 jobs — so every reported number is attributable to a specific policy choice, and the do-nothing baseline is a genuine counterfactual to compare against.
2. **Adding a policy can never reduce the total.** Where two mechanisms both apply to a parcel, the model takes the larger rather than letting one replace the other. Earlier versions had several cases where checking an additional box lowered the citywide number — always because a value was silently replaced by a different formula instead of combined with what was already there.
3. **The same physical capacity is never counted twice.** Where two policies describe the same square footage (parking reform and Midrise both freeing the same land, or both claiming the same ground-floor commercial space), the model takes the maximum, not the sum.

---

## Parcel Eligibility: The Underutilization Threshold

Some — not all — policies require a parcel to pass an underutilization screen first. This test asks one specific question: is there spare, underused land on this lot? A parcel is considered underutilized if any of the following are true:

- It is classified as vacant in the Texas assessor state code (`state_cd`) data. Vacant classifications include: residential vacant lots (A7, A8), platted vacant residential lots (C1), platted vacant commercial lots (C10), colonia lots and land tracts (C2), vacant rural or recreational lots (C3), vacant lots with limited utilities (C6, C7, C8, C9), and undeveloped rural/agricultural/desert acreage (D series).
- Its building-to-lot coverage ratio is below a threshold:
  - **Below 15%** for residential and current-use scenarios. This threshold is appropriate for El Paso's context, where single-story residential buildings on large lots commonly have coverage ratios of 10% or less, correctly identifying them as candidates for densification.
  - **Below 45%** for commercial and mixed-use scenarios (relaxed to reflect that job-generating redevelopment is viable even on partially-built commercial parcels)
- It has no existing units and no building square footage recorded

**This screen applies to ADUs, Lot Splits, Midrise, the parking-reform boost, and SB840 Baseline** — all policies about adding a new use to land that isn't fully built out.

**It does NOT apply to Mansion Conversion or either Missing Middle tier.** These are about redeveloping a lot that already has a home on it, and coverage ratio doesn't measure whether that's a good candidate — a normal, occupied single-family home routinely covers well over 15% of its lot, which is exactly what you'd expect from a house that's actually there. An earlier version of this tool gated Missing Middle on this test anyway, which incorrectly excluded the majority of real small-residential parcels (a check against actual parcel data found 61-65% of occupied 1-3 unit properties exceed the 15% threshold and were being wrongly filtered out). That's fixed: Missing Middle's eligibility is 1-3 existing units, and Mansion Conversion's is any residential building with recorded floor area — coverage ratio plays no role in either.

Mansion Conversion can still net zero for reasons unrelated to coverage — see "Why a residential parcel can still net zero" in its section below. The most common is a data gap: roughly 20-30% of residential parcels (depending on district) have no recorded footprint or interior square footage. The parcel popup flags this distinctly, separate from the "no existing-conditions data at all" flag used elsewhere.

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

**The base scenario only decides how the checked reforms are applied — it never produces housing or jobs on its own.** Every unit and every job in the model traces back to a specific reform's own formula; the scenario is a filter on those results. With no reform checked, every scenario shows zero.

| Scenario | Housing from reforms | Jobs from reforms |
|---|---|---|
| **Current Land Use** | Kept on residential and vacant/other parcels; dropped on commercial parcels | Kept on commercial and vacant/other parcels; dropped on residential parcels |
| **Residential Only** | Kept | Dropped (except the Eliminate Parking Minimums job boost — see below) |
| **Commercial Only** | Dropped | Kept |
| **Vertical Mixed Use** | Kept | Kept |

Only two reforms generate jobs at all — Midrise (ground-floor commercial) and Eliminate Parking Minimums — so a scenario that "keeps jobs" still shows zero jobs unless one of those is checked. Current Land Use classifies parcels by Texas assessor state code (A/B residential; F1/F2 commercial), falling back to the land-use description for codes those patterns don't recognize.

**A corrected error worth documenting:** earlier versions gave Commercial Only and Vertical Mixed Use their own flat floor yields — `(lot × 0.5) ÷ job size` in jobs and `(lot × 0.25) ÷ unit size` in units — on every underutilized parcel once *any* box was checked. Checking ADUs alone under Vertical Mixed Use reported ~50,000 units and ~85,000 jobs, versus 416 units from ADUs under any other scenario: the scenario itself was generating the yield. Those floors are removed. Checking ADUs now produces the same 416 units under Current, Residential, and Mixed Use, and zero under Commercial Only, which drops housing.

---

## Policy Interventions

Policy interventions are the only source of units and jobs. The base scenario then filters their results (see above). Multiple interventions can be active simultaneously; the model takes the **highest single-intervention yield** for units and jobs separately (they do not stack additively), except where noted.

### Accessory Dwelling Units (ADUs)
**Eligibility:** Parcels with exactly 1 existing unit (single-family). No lot-size minimum — a real ADU-enabling ordinance applies regardless of lot size; buildability at the margins is the homeowner's problem, not a citywide capacity assumption. Does not use the underutilization screen (see above).
**Yield:** 1 net new unit per eligible parcel.
**Rationale:** ADUs are assumed to be attached or detached secondary units added to existing single-family homes specifically — a duplex or larger already has multiple units and isn't what "an ADU" describes.

### Lot Splits
**Eligibility:** Underutilized parcels at least double a minimum buildable lot size (3,500 sq ft — a documented assumption, not derived from El Paso's actual subdivision code), for a combined minimum of 7,000 sq ft.
**Yield:** The lot becomes two buildable lots; net yield is `max(0, 2 − existing units)`.
**Rationale:** A lot split needs to leave two genuinely buildable halves, not just any subdivision. The minimum lot size is a stated assumption, not an empirical figure — see the methodology modal for the reasoning.

### Mansion Conversions — a square-footage rule with no parking required

**What it is:** dividing an existing residential building into more units than it holds today. It's positioned as its own tool, separate from SB840 and Missing Middle, because of one defining difference: **conversions require no additional parking**, while Missing Middle and SB840 Baseline are framed around one space per unit. Because it doesn't depend on SB840's trigger, it has no unit-count threshold.

**Formula:**
```
gross units   = floor(building sq ft ÷ 500)
net new units = gross units − existing units   (never below 0)
```
- **Building sq ft** is total floor area across all stories (`interior_sqft`) when recorded, otherwise the ground-floor footprint (`footprint_sqft`).
- **500 sq ft per unit** is the default rule, adjustable under Model Assumptions → *Conversion Size* (300–1,000). It's deliberately smaller than the 850 sq ft used for new construction, since conversions carve existing floor area into efficient units.
- **Existing units** come from the assessor-derived `existing_units` field. A residential building recorded with 0 units (an assessor code the unit mapping doesn't cover) is treated as holding 1, so an existing home isn't credited as though it were empty.

**Worked examples:**

| Building | Existing units | Gross (÷ 500) | Net new |
|---|---|---|---|
| 900 sq ft single-family | 1 | 1 | 0 |
| 2,000 sq ft single-family | 1 | 4 | **3** |
| 3,200 sq ft duplex | 2 | 6 | **4** |
| 5,000 sq ft fourplex | 4 | 10 | **6** |
| 6,000 sq ft, 12-unit apartment | 12 | 12 | 0 |

**Eligibility:** any residential parcel — Texas assessor A or B codes (excluding vacant A7/A8), or a land-use description containing "residential" — with recorded building floor area. Commercial parcels are never eligible. There is no unit-count ceiling and no underutilization/lot-coverage screen: whether a building can be divided depends on the building, not on how much of the lot it covers.

**No parking, no stacking:** since conversions already assume no added parking, the separate 20% "Eliminate Parking Minimums" boost is **not** applied on top of them — that would credit the same freed-up space twice (design rule 3). Verified: adding parking reform to Mansion Conversion leaves every converted parcel credited to the conversion, unboosted.

**Why a residential parcel can still net zero** (checked against real parcel data):
- **Under 1,000 sq ft** — can't yield a second 500 sq ft unit (~830 parcels).
- **Already at one unit per 500 sq ft or denser** — nothing left to carve out, as with most existing apartment buildings (~840 parcels).
- **No recorded building size** — roughly 20–30% of residential parcels depending on district (~2,600 parcels). A data gap, not a judgment; the parcel popup flags it.
- **Inside a historic district** while "Protect Historic Districts" is on (~900 parcels).

**A corrected error worth documenting:** earlier versions discounted floor area by 15% and divided by the 850 sq ft new-construction unit size, so a 2,000 sq ft house yielded 2 gross − 1 existing = **1** net unit and an 1,800 sq ft house yielded **0**. About 4,300 residential parcels displayed "not eligible" purely from that rounding. Earlier versions also capped eligibility at 4 existing units. With the square-footage rule, the number of residential parcels credited with a conversion rose from about 2,100 to about 5,800, and a 2,000 sq ft single-family house now nets 3 units.

### SB840's 3-unit trigger (governs Missing Middle and SB840 Baseline)

SB840 applies to anything permitting *more than 3 units*, so above that line the state mandate governs and the city has no discretion. A local density-bonus program can therefore only be offered as an *alternative* for properties currently at 3 units or fewer. **Both Missing Middle tiers** use this threshold, and **SB840 Baseline** is its exact complement — every parcel falls on one side or the other, never both. (Mansion Conversion does not use this threshold — see above.)

**Texas assessor state codes are the proxy**, via the `existing_units` field derived in `prep_data.py`:

| Code | Units | Missing Middle (≤ 3) | SB840 Baseline (> 3, or commercial/vacant) |
|---|---|---|---|
| A1 — single-family | 1 | ✓ | — |
| A51 / B1 — duplex | 2 | ✓ | — |
| A53 / B3 — triplex | 3 | ✓ | — |
| A54 / B4 / B9 — quadplex | 4 | — | ✓ |
| A55 / B5 / B7 — fiveplex | 5 | — | ✓ |
| A56 / B6 / B8 — sixplex | 6 | — | ✓ |
| A52 / B2 — apartment | 12 | — | ✓ |

The threshold is a single named constant in the code (`SB840_TRIGGER_MAX_UNITS = 3`) so it can't drift apart between the two programs that share it.

### Missing Middle Housing (4–8 Units) & Missing Middle Housing (9–16 Units)

**Why these caps and this eligibility rule exist — Texas SB840:** SB840 requires that any zone permitting more than 3 units must allow 4 floors and the city's maximum density (145 units/acre) — a state mandate the city cannot restrict. The one exception is a "workaround": on parcels that currently have 1–3 existing units (single-family, duplex, or triplex) — i.e. those *not* already triggering the bill — the city may impose additional local limits in exchange for offering a density bonus. Both Missing Middle checkboxes model this bonus program specifically, which is why eligibility is restricted to parcels currently at 3 units or fewer.

**Eligibility:** Between 1 and 3 existing units, inclusive (single-family, duplex, or triplex) — above 3 units SB840 itself governs, so the bonus program isn't available. Does not use the underutilization screen (see above) — an earlier version of this tool did, which incorrectly excluded the majority of real candidates (a check against actual parcel data found 61-65% of occupied small-residential parcels exceed the 15% coverage threshold, since that's just what a normal house on a normal lot looks like).

**Yield — same formula, different cap:**
1. Compute the buildable envelope: 35 ft height cap (≈3 floors, at a standard ~11.7 ft floor-to-floor height — a local limit below SB840's full 4-floor mandate, part of the city's workaround) × 50% lot coverage × lot area, divided by the adjustable unit size assumption — `envelope units = floor((lot sq ft × 0.5 × 3) / unit size)`.
2. Subtract existing units from the envelope first, to get the additional capacity the site can support beyond what's already there.
3. Cap that additional capacity at **8** (the 4-8 checkbox) or **16** (the 9-16 checkbox) — up to and including that number.

This means the two checkboxes only diverge once a lot's envelope has enough spare capacity to exceed 8 — on small lots where the site itself can't support more than 8 *additional* units regardless of which is chosen, both checkboxes agree (correctly, since the physical constraint binds before the policy cap does). On larger 1-3 unit lots, or with a smaller unit size assumption, the 16-unit cap allows meaningfully more than the 8-unit cap.

**A known limitation — unit size vs. lot width:** this formula sizes buildings by dividing available floor area by an assumed unit size. Dan Parolek's *Missing Middle Housing* argues building size (and therefore unit count) should instead be driven by lot width, which better reflects a building's street-facing massing and fit within existing neighborhood character. This dataset has lot area but not lot width, and approximating width from parcel geometry (e.g. a bounding-box calculation) is unreliable for irregular or non-rectangular parcels — so unit size is used here as a practical substitute, not because it's judged to be the more theoretically correct approach. If reliable lot-width or frontage data becomes available, switching to Parolek's method would be a meaningful improvement.

### SB840 Baseline (Commercial & 4+ Unit Parcels) — a last resort, not a recommended outcome

**What this models:** everything the Missing Middle bonus program above does *not* cover — commercial parcels, vacant land, and anything already **above** 3 units (a quadplex or larger, or plainly multifamily). These parcels aren't the 1-3 unit properties the Missing Middle "workaround" is offered to, so SB840's flat mandate applies to them directly and in full: 4 floors (the state's actual minimum — not the Missing Middle workaround's reduced 35 ft height) and the citywide maximum density, with no local discretion to restrict it further.

**Eligibility:** Underutilized parcels that are commercial, vacant (0 existing units), or already at 4+ units.

**Yield:** Same minimum-unit-size approach as Missing Middle, at SB840's actual mandated floor count — `gross units = floor((lot sq ft × 0.5 × 4) / unit size)`, minus existing units.

**Read this as a last resort, not a preferred policy.** Its numbers are intentionally large and out of scale with typical neighborhood character — that's the point, not an error to fix. This is what happens by default, everywhere it applies, absent any more tailored local action: a blunt, one-size-fits-all state mandate rather than the context-sensitive infill the other interventions represent. It's deliberately excluded from "Load Full Reform Package" in the tool and kept visually separate in the sidebar (styled distinctly, under a "Last Resort — Not a Preferred Outcome" label) for exactly this reason: the ADU, lot split, mansion conversion, Missing Middle, Midrise, and parking reform policies exist precisely so this blunt instrument doesn't have to be the only path to added density and jobs. The scale of what SB840 forces absent local action is itself the argument for the alternatives.

This is modeled as its own opt-in checkbox rather than an always-on baseline, even though SB840 is current law rather than a hypothetical reform, so that a true zero-policy run still shows zero net change — consistent with every other policy in this tool. Toggle it on to see what the state mandate alone forces, independent of any local policy choice — and to make the case for why the alternatives above are preferable.

**Midrise's floor selector also has a 4-floor minimum**, for the same reason: SB840 sets 4 floors as a floor, not a suggestion, wherever this level of density is permitted.

### Midrise Development
**Eligibility:** Underutilized parcels.
**Yield (units):** Uses the same floor-area envelope formula as Missing Middle and SB840 Baseline — `envelope = floor((lot sq ft × 0.5 coverage × floors) / unit size)` — then **capped at the citywide maximum density of 145 units per acre of land**: `gross units = min(envelope, floor(145 × acres))`. If off-street parking is still required (the "Eliminate Parking Minimums" policy is NOT active), the achievable count is reduced by however much land that parking would consume — 300 sq ft/space, assuming the standard 1 space per unit ratio. Net units subtract existing units. **The floor selector's minimum is 4 floors** — SB840 sets this as the state-mandated minimum wherever this density is permitted, not a suggestion, so fewer floors isn't an option (default: 4).

**Why the cap is essential — a corrected error worth documenting:** 145 units/acre is a *land* density figure; it already presumes a multi-story building. An earlier version of this model multiplied 145/acre *by* the floor count, which implied 580 units/acre at 4 floors — roughly 4× the very figure El Paso states as its maximum, and about 5× Manhattan's overall density. That produced citywide totals near 780,000 units. The envelope formula scales correctly with floor count (a taller building genuinely holds more units), while the 145/acre cap keeps the stated maximum binding. At the default 4 floors this yields about 102 units/acre; the cap begins binding at roughly 6 floors.
**Yield (jobs):** Ground floor is assumed to be commercial space at 1,000 sq ft per job (adjustable), calculated as `(lot sq ft × 0.5) / job size` — independent of the residential envelope calculation above.
**Single-use rule:**
- Residential scenario: units only, no jobs
- Commercial scenario: jobs only, no units
- Vertical mixed use: both units and jobs
- Current use: units only (ground-floor commercial is not assumed unless the scenario explicitly allows it)

**The parking effect, quantified:** requiring off-street parking cuts Midrise's unit yield substantially — on a one-acre lot at 4 floors, roughly 102 units become about 30, a ~70% reduction, because the parking consumes land that would otherwise hold housing. (An earlier version of this model, before the density-cap correction above, produced near-zero units in this case; that was an artifact of the uncapped formula, not a real finding. The corrected figures still show parking requirements as a major constraint on achievable density — just a severe one rather than an absolute one.)

**Rationale:** Midrise is the most intensive intervention in the model. The 50% lot coverage assumption reflects typical urban setback and parking requirements even under reformed zoning.

**Where 850 sq ft/unit and 1,000 sq ft/job come from, honestly:** these are general planning-literature benchmarks, not figures derived from El Paso-specific data — unlike the absorption rate above, no local dataset exists to calibrate them against. 850 sq ft approximates a modest, efficient one- to two-bedroom multifamily unit — near the lower-middle of the range for newly built small multifamily nationally. 1,000 sq ft/job sits in the middle of a wide range: dense uses like retail or office can run closer to 200–500 sq ft/employee, while warehouse and light-industrial space can run 1,000–2,000+ sq ft/employee. Rather than assume the densest possible commercial use everywhere — which would inflate job counts — the model uses a single blended, moderate figure across all commercial yield calculations. This is a real simplification: a parcel that would realistically become dense ground-floor retail is likely undercounted on jobs, while one that would become light-industrial space is likely overcounted.

**Both figures are adjustable.** Rather than lock in defaults we can't fully validate, the tool exposes both as sliders under "Model Assumptions (Advanced)" in the sidebar (500–1,400 sq ft/unit, 250–2,000 sq ft/job), each with inline guidance on which direction to move them and why. Refining this into use-specific job densities (matched to what's actually zoned or plausible per parcel) would still be a meaningful improvement to a future version of this model — the sliders let a user approximate that manually in the meantime.

### Eliminate Parking Minimums
This intervention is treated differently from the housing interventions. It is an **infrastructure and regulatory policy**, not a land use designation, and its job yield survives the residential scenario's hard-zero because parking reform enables commercial activity regardless of the dominant land use type.

**When used alone:**
- Units: `lotSqft / 5,000` (a modest floor yield reflecting small-scale infill enabled by eliminating required parking)
- Jobs: `(lotSqft × 0.5) / 1000` (ground-floor commercial space at 1,000 sq ft per job)

**When combined with other interventions:**
- Units from other policies are multiplied by 1.20 (a 20% boost reflecting that eliminating parking requirements enables more of the lot to be used for building) — **except Midrise and Mansion Conversion**, which already model parking directly (Midrise by skipping its own parking-land deduction, Mansion Conversion by assuming no parking at all). Boosting them again would count the same freed-up space twice.
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
