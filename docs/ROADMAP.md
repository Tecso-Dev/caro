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
| deployed | ✅ https://caro-rho.vercel.app — one Vercel project of two services (D64). |

## Next — small, open, recorded

1. **The contact page still sends people to the old repository.** Its GitHub
   Issues link (`ELSEWHERE` in `webapp/api/contact.py`) names
   `sahandmusanezhad/caro`, and that is still where an issue can be written:
   `Tecso-Dev/caro` is a fork of it, and a fork starts with Issues turned
   off — its page, seen signed out on 2026-10-04, has no Issues tab. First:
   decide where issues are written. If on `Tecso-Dev/caro`, turn Issues on
   there (Settings → General → Features), and only then move the link.

2. **The intent panel contradicts itself on two of the five examples.**
   Text the parser acted on is listed again under «بخش‌هایی که نفهمیدیم —
   نادیده گرفته شدند»: «ماشین اول خانواده» and «تصادفی نباشه» on the family
   example, «ماشین برای اسنپ» and «کم مصرف» on the Snapp one, because
   `unparsed` in `RuleIntentParser` counts only the budget and year clauses
   as consumed. The same two examples print a raw token among the
   assumptions: «وزن‌ها از پیش‌فرض «ride_hailing» شروع شد». Both are also in
   `demo/ranking_data.json` and the hand-kept `demo/index.html`, so fixing
   the parser is a decision about the demo as well.

3. **The ranked path's red lines are not the evidence path's.** `_passes` in
   `caro/ranking.py` has no rule for `manual` or `repaint` — no corpus sets
   `has_manual` or `has_repaint` — and lets a listing whose condition or
   documents are unknown through `accident` and `unclear_documents`. The
   evidence path judges all four and holds an unknown apart
   (`webapp/api/constraints.py`). Nothing is ranked on a real corpus yet
   (D43); before anything is, the two should apply one rule.

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
