# Roadmap — the honest gap list

What is left to do, kept current. Each item says what is true now, where it
was recorded, and what comes first. An open item goes into code only after it
has been measured; the measurement comes first and the decision is made on
it, in its own commit.

Last revised 2026-10-17.

## Where it stands against the brief

The brief asks for: **crawl offers → normalize messy data → rank by user
intent → explain the best choice**.

| Requirement | State |
|---|---|
| crawl offers | ⚠️ **one source.** Four `BamaAdapter` runs on one pin are published, and the API serves the fourth by default, `data/corpora/run16.json` (2026-10-15): 73 listings, 63 of them appraisable. run11 (2026-09-10), run13 (2026-10-06) and run14 (2026-10-11) stay published. `DivarCarAdapter` is built and tested offline, and its live path has never run. Sheypoor and Khodro45 have no adapter. |
| normalize messy data | ✅ **built.** Persian numerals and amount words, toman and rial, mileage, Jalali and Gregorian years, make/model aliases, trim, gearbox, fuel, colour, and body condition from free text. |
| rank by user intent | ⚠️ **built, not served on real data.** `caro/ranking.py` parses Persian intent, filters, relaxes and scores. No estimator has cleared the acceptance gate on a real corpus (D43), so the site shows evidence, not a ranking. |
| explain the best choice | ✅ **built.** |
| deployed | ✅ **from each push to `main`.** https://caro-rho.vercel.app — one Vercel project of two services (D64) — served `1ebbf4a` within about three minutes of its push on 2026-10-15, as seen from outside (D80); see «Deploying» below. |

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

2. **The ranked path's province — blocked with the first** (D43, D82). A
   query that names a province is a constraint on the evidence path
   (`webapp/api/constraints.py`). `_passes` has no rule for it, because an
   appraisal `Row` carries no province, so wherever the ranking is served a
   spec that names one is not narrowed. Today that is the SYNTHETIC corpus
   alone, where the intent panel lists «استان» as understood and the
   shortlist is the one without it. It is left as it is, as the red lines
   are, and pinned: `tests/test_ranking.py` turns red the day a `Row`
   carries a province or `_passes` reads one, and `tests/test_api_contract.py`
   section 18 the day a published corpus is ranked. It reopens with the
   first item: an estimator clears the gate on a real corpus, the rows
   ranking scores carry a province, and what an unknown province does there
   — held apart, as on the evidence path, or let through — is measured and
   decided before it is written.

3. **Reading the place a buyer writes — what is not covered** (D82). The
   reader takes a full province name, with a locative («در», «توی», «ساکن»,
   «استان») or without, and declines what is not a place the car should be
   in: a negation before or after the name («غیر از تهران», «تهران
   نباشه»), a nearness («نزدیک», «اطراف»), a plate («پلاک»), and «خراسان»
   or «آذربایجان» alone, which begin several names. What it declines stays
   under «نفهمیدیم». It was built and checked on constructed phrasings: no
   log of what buyers write exists, so how they write a place is not
   measured. Known, and left:
   - «فارس» is read as the province wherever it stands, «خلیج فارس»
     included.
   - A city (مشهد, شیراز, کرج) is not read (D74), and in a clause that names
     a model it is dropped without a word, because such a clause is taken
     as understood whole. That is the clause rule's fault, not the
     reader's, and it wants a round of its own: what the parser leaves
     unparsed, judged by what remains of the sentence and not by clause.
   - «تهرانپارس» adds the model `pars`, because the alias is matched as a
     substring. It was so before this round.

## Next — the product gaps

1. **Data.**
   - Divar: a first live run of `DivarCarAdapter`. Review Divar's terms and
     robots directives for the car category first, and record the finding
     whatever it says. One city and a handful of pages; volume is not the
     point. `CARO_SELLER_SALT` must be set. Expect to be blocked; the adapter
     stops and says so, and that is the design.
   - Sheypoor and Khodro45: adapters, under the same rules.
   - `province` where the market is. run16, the corpus served, carries it
     on all 73 rows: 42 stated, 31 by a city that shares its province's
     name, where run14 had 76 of 77 and run13 34 of 74. Every line of run16
     was read before it was published, and no district named like a
     province stands behind any of its 42 stated rows (D80). The car page
     and the lists — search's tables and compare's evidence rows — draw it,
     with how it was read (D81). The search reads it (D82): «پراید در
     تهران» is a constraint like the budget, so a car in another province
     is left out, one with none is held apart and named, and the panel
     lists «استان: تهران». On run16 that is 18 matches and none apart; on
     run13, 3 matches and 31 cars apart; on run11, which holds no province,
     no match and every Pride apart. The ranked path does not read it (item
     2 above).
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
   2026-10-14 (D78). A push to `main` now deploys: `1ebbf4a` was on the
   site within about three minutes of its push on 2026-10-15, as
   `.github/workflows/ci.yml` says the hosts build from each push (D80) —
   unless the holder deployed it by hand in those minutes, which was not
   asked. Not checked: the contact page's inbox — `CARO_INBOX=off`, with
   Issues at `Tecso-Dev/caro` in its place (D68) — and the car page's
   province cell on the live site.

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
