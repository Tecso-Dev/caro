# Roadmap — the honest gap list

What is left to do, kept current. Each item says what is true now, where it
was recorded, and what comes first. An open item goes into code only after it
has been measured; the measurement comes first and the decision is made on
it, in its own commit.

Last revised 2026-10-04, at `8f855f6`.

## Where it stands against the brief

The brief asks for: **crawl offers → normalize messy data → rank by user
intent → explain the best choice**.

| Requirement | State |
|---|---|
| crawl offers | ⚠️ **one source run.** `BamaAdapter` has run, and its output is the published corpus `data/corpora/run11.json`: 76 listings, 71 of them appraisable. `DivarCarAdapter` is built and tested offline, and its live path has never run. Sheypoor and Khodro45 have no adapter. |
| normalize messy data | ✅ **built.** Persian numerals and amount words, toman and rial, mileage, Jalali and Gregorian years, make/model aliases, trim, gearbox, fuel, colour, and body condition from free text. |
| rank by user intent | ⚠️ **built, not served on real data.** `caro/ranking.py` parses Persian intent, filters, relaxes and scores. No estimator has cleared the acceptance gate on a real corpus (D43), so on run11 the site shows evidence, not a ranking. |
| explain the best choice | ✅ **built.** |
| deployed | ✅ https://caro-rho.vercel.app — one Vercel project of two services (D64). |

## Next — small, open, recorded

1. **Links to the old repository.** The repository is now
   `github.com/Tecso-Dev/caro`. Four places still name the old one: the
   contact page's GitHub Issues link (`ELSEWHERE` in `webapp/api/contact.py`),
   which the deployed site shows; the clone command in `README.md`;
   `docs/WORKING_AGREEMENT.md`; and `docs/DEMO_SCRIPT.md`.

2. **The buyer's own constraints fail open** (D60, still open in D61).
   `keeps()` in `webapp/api/main.py` lets a listing whose price, year or
   mileage is unknown through the budget, year and mileage it was asked for.
   Seen on the deployed site: «پراید زیر ۳۰۰ میلیون» returned four rows of
   evidence, and two of them had no price. First: count, on run11 and the
   search page's example queries, how many rows pass only because a value is
   missing. Then decide: leave them out, or show them apart and say what is
   not known.

3. **`/api/search/reweight` takes any `k`** (D60), where `/api/search` caps it
   at 24.

4. **`mileage_status` is not on the payload** (D61). FIELD_PROVENANCE.md
   marks it `card=yes`, but no rule states how an odometer's status travels
   with the number, the way one does for a price.

5. **Writing an Issue needs a GitHub account**, and the contact page does not
   say so; reading them does not. One sentence, if wanted.

## Next — the product gaps

1. **Data.**
   - Divar: a first live run of `DivarCarAdapter`. Review Divar's terms and
     robots directives for the car category first, and record the finding
     whatever it says. One city and a handful of pages; volume is not the
     point. `CARO_SELLER_SALT` must be set. Expect to be blocked; the adapter
     stops and says so, and that is the design.
   - Sheypoor and Khodro45: adapters, under the same rules.
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

5. **Deploy on push.** Not connected. The Vercel GitHub App has to be
   installed where the repository now lives, `Tecso-Dev`. Until then each
   deployment is a pull and a `vercel deploy --prod` by hand.

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
