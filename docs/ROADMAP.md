# Roadmap — the honest gap list

What is left to do, kept current. Each item says what is true now, where it
was recorded, and what comes first. An open item goes into code only after it
has been measured; the measurement comes first and the decision is made on
it, in its own commit.

Last revised 2026-10-11.

## Where it stands against the brief

The brief asks for: **crawl offers → normalize messy data → rank by user
intent → explain the best choice**.

| Requirement | State |
|---|---|
| crawl offers | ⚠️ **one source.** Three `BamaAdapter` runs on one pin are published, and the API serves the third by default, `data/corpora/run14.json` (2026-10-11): 77 listings, 64 of them appraisable. run11 (2026-09-10) and run13 (2026-10-06) stay published. `DivarCarAdapter` is built and tested offline, and its live path has never run. Sheypoor and Khodro45 have no adapter. |
| normalize messy data | ✅ **built.** Persian numerals and amount words, toman and rial, mileage, Jalali and Gregorian years, make/model aliases, trim, gearbox, fuel, colour, and body condition from free text. |
| rank by user intent | ⚠️ **built, not served on real data.** `caro/ranking.py` parses Persian intent, filters, relaxes and scores. No estimator has cleared the acceptance gate on a real corpus (D43), so the site shows evidence, not a ranking. |
| explain the best choice | ✅ **built.** |
| deployed | ✅ **at `main`, 2026-10-14.** https://caro-rho.vercel.app — one Vercel project of two services (D64) — serves `bd8d56d`, and run14 with it, as seen from outside (D78). How the next deployment is made is not recorded; see «Deploying» below. |

## Next — small, open, recorded

1. **The ranked path's red lines — blocked by a real estimator** (D43, D66).
   `_passes` in `caro/ranking.py` has no rule for `manual` or `repaint` and
   lets an unknown through all four; the evidence path judges all four and
   holds an unknown apart (`webapp/api/constraints.py`). Measured on
   SYNTHETIC and left as it is: its rows carry none of the fields the
   evidence rules read, and swapping `_passes` alone sends an unknown into
   budget and odometer relaxation and an empty shortlist (D66). It reopens
   when all three hold: an estimator clears the acceptance gate on a real
   corpus; the rows real ranking scores carry the evidence the four rules
   read; and the measurement is run again — met, broken and unknown, the
   shortlist, the relaxation ladder, and the comparison with price-sort. No
   commit makes the ranked path evidence-aware before then.

## Next — the product gaps

1. **Data.**
   - Divar: a first live run of `DivarCarAdapter`. Review Divar's terms and
     robots directives for the car category first, and record the finding
     whatever it says. One city and a handful of pages; volume is not the
     point. `CARO_SELLER_SALT` must be set. Expect to be blocked; the adapter
     stops and says so, and that is the design.
   - Sheypoor and Khodro45: adapters, under the same rules.
   - `province` where the market is. run14, the corpus served, carries it
     on 76 of 77 rows: 44 stated, 32 by a city that shares its province's
     name, where run13 had 34 of 74. The car page draws it, with how it was
     read. Lists and search do not until the district hazard is measured —
     a district named like a province is read as that province, stated —
     and the next collection keeps the line each province is read from in
     its snapshot for that (FIELD_PROVENANCE.md).
   - Longitudinal collection. Time-dependent and unrecoverable: a day not
     collected is gone. A second discovery run is a new sample, not a
     series: on run11's pin, 26 days later, 3 of its 76 listings were drawn
     again (TEMPORAL_CONTRACT.md §10).

2. **An estimator that clears the gate on real data** (D43). Run the ladder
   in `caro/appraisal.py` — `GlobalQuantiles`, `ComparableQuantiles`,
   `LogLinearQuantiles`, and `PartialPoolingQuantiles` — against
   `AcceptanceGate` on a larger real corpus, and report whichever wins; if it
   is the baseline, ship the baseline and say why. Until one clears, nothing
   is ranked on real data, and compare's gated branch stays unmeasurable:
   when it becomes measurable, build the three-state fixture (vehicle,
   assignment, `unknown`) and measure detail, compare alone, compare beside a
   vehicle, and search.

3. **Accident damage from listing photos.** Not built. When it is, its output
   is recorded as inferred, not observed, and says «قابل تشخیص نیست» when it
   cannot tell.

4. **Authenticator-based login.** Not built. The admin view opens today with
   `CARO_ADMIN_TOKEN`, and with the token unset it does not open at all.

5. **Deploying.** The Vercel project is in another account than the
   owner's, and its holder deployed `main` from `Tecso-Dev/caro` on
   2026-10-14: the site serves `bd8d56d` (D78). Whether a push to `main`
   now deploys on its own, or each deployment is made by hand, is not
   recorded; until it is, a commit is on the site only once the site has
   been checked for it. Not checked on that deployment: the contact page's
   inbox — `CARO_INBOX=off`, with Issues at `Tecso-Dev/caro` in its place
   (D68) — and the car page's province cell.

6. **Calibrate the confidence policy.** The bands are judgement. With real
   data they should be revisited against observed decision quality and
   relabelled — or kept, and described honestly as policy.

## Requests

Items to add. Each one moves into a list above once it has been measured and
decided.

-

## Deliberately not planned

TCO / maintenance-cost estimates. No Iranian maintenance dataset exists, so
every component would be an invented number wearing a confidence label — the
exact fake precision this system exists to avoid. Corpus-derived reliability
signals (engine-replacement rate per model, and similar) are the grounded
substitute.
