# Roadmap — the honest gap list

What is left to do, kept current. Each item says what is true now, where it
was recorded, and what comes first. An open item goes into code only after it
has been measured; the measurement comes first and the decision is made on
it, in its own commit.

Last revised 2026-10-05.

## Where it stands against the brief

The brief asks for: **crawl offers → normalize messy data → rank by user
intent → explain the best choice**.

| Requirement | State |
|---|---|
| crawl offers | ⚠️ **one source run.** `BamaAdapter` has run, and its output is the published corpus `data/corpora/run11.json`: 76 listings, 71 of them appraisable. `DivarCarAdapter` is built and tested offline, and its live path has never run. Sheypoor and Khodro45 have no adapter. |
| normalize messy data | ✅ **built.** Persian numerals and amount words, toman and rial, mileage, Jalali and Gregorian years, make/model aliases, trim, gearbox, fuel, colour, and body condition from free text. |
| rank by user intent | ⚠️ **built, not served on real data.** `caro/ranking.py` parses Persian intent, filters, relaxes and scores. No estimator has cleared the acceptance gate on a real corpus (D43), so on run11 the site shows evidence, not a ranking. |
| explain the best choice | ✅ **built.** |
| deployed | ⚠️ **behind `main`.** https://caro-rho.vercel.app — one Vercel project of two services (D64) — serves `a636ea6`. The deploy after it was refused; see «Deploying» below. |

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

2. **The car page draws a price without the rule search and compare use.**
   `ListingFile` in `CarDetail.tsx` draws its heading and its «قیمت
   پیشنهادی» cell with `toman()`; search and compare draw the same field
   with `askingPrice()`, the rule FIELD_PROVENANCE.md states for a price,
   and the car page is sent both fields that rule reads (`detail=yes`).
   Measured on 2026-10-05: on run11 the two surfaces disagree on 2 of 75
   cars — the two whose price is «توافقی» and carries no amount are drawn
   «ثبت‌نشده» in both places on their car page, and «توافقی» in search and
   compare. A financing total or an unusable extraction would be drawn on
   the car page as the asking price; run11 carries neither. Not decided.

## Next — the product gaps

1. **Data.**
   - Divar: a first live run of `DivarCarAdapter`. Review Divar's terms and
     robots directives for the car category first, and record the finding
     whatever it says. One city and a handful of pages; volume is not the
     point. `CARO_SELLER_SALT` must be set. Expect to be blocked; the adapter
     stops and says so, and that is the design.
   - Sheypoor and Khodro45: adapters, under the same rules.
   - `gearbox` and `fuel` into the next corpus. Both are parsed on every
     page and neither has been promoted (FIELD_PROVENANCE.md). Until one is,
     «اتومات» cannot be answered: on run11 the Quik example under the search
     box matches none and shows eight listings apart, one more left out
     because its trim is the word `manual`.
   - Longitudinal collection. Time-dependent and unrecoverable: a day not
     collected is gone.

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

5. **Deploying.** Neither way works today. On push: not connected — the
   Vercel GitHub App has to be installed where the repository now lives,
   `Tecso-Dev`. By hand: refused on 2026-10-05, the CLI (62.2.0) answering
   «Error: Not authorized» in the deploy clone. Until one of them works the
   site serves `a636ea6`, and nothing D65 records is on it. Before the next
   deployment, Issues has to be on at `Tecso-Dev/caro`: the contact page
   now sends people there.

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
