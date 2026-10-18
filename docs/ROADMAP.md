# Roadmap — the honest gap list

What is left to do, kept current. Each item says what is true now, where it
was recorded, and what comes first. An open item goes into code only after it
has been measured; the measurement comes first and the decision is made on
it, in its own commit.

Last revised 2026-10-18.

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
   نباشه»), a nearness («نزدیک», «اطراف»), a plate («پلاک»), «خراسان» or
   «آذربایجان» alone, which begin several names, and «خلیج فارس», which
   holds one. What it declines stays under «نفهمیدیم». It was built and
   checked on constructed phrasings: no log of what buyers write exists, so
   how they write a place is not measured. Known, and left:
   - A province's name inside a longer name that is not a place is read as
     the province, with the assumption shown: «کرمان موتور», «یزد خودرو»,
     «گیلان خودرو». «خلیجفارس» with no space is not matched at all, and
     «خلیجِ فارس» typed with a kasra is read as the province, since a
     diacritic is not stripped.
   - A city (مشهد, شیراز, کرج) is not read (D74). In a clause that names a
     model it was dropped without a word, because such a clause is taken
     as understood whole: of 350 phrasings of 35 cities, 10 were listed
     under «نفهمیدیم» and 340 dropped (D83). A cue the reader already
     knows («در», «توی», «ساکن», «اطراف», «نزدیک به», «غیر از», «پلاک» …) is
     now listed with the one or two words after it, past «شهر» and
     «استان»: «در مشهد», «ساکن در شهر بندر عباس», and «پلاک ملی در مشهد» as
     two, «پلاک ملی» and «در مشهد». So is one after a budget's amount, which
     the budget clause used to take whole (item 4). Nothing is read from it;
     the page says the city was seen and not used, and the province panel
     and the ranked path are as they were. On the prototype it shows the
     city in 220 of the 350 phrasings. Known, and left, each pinned by a
     test so that it changes on purpose: a city no cue stands before
     («پراید مشهد»); a second one after « و » or «یا», where «یا» is itself
     taken as the second word of «در مشهد یا»; and «نه» and «بدون», which
     the reader knows and this does not, so «پراید نه مشهد» is still
     dropped. And any word after a cue that is no place is listed all the
     same, unless it is one of the three the stoplist holds: «حد», «حال»,
     «بودجه».
   - «تهرانپارس» adds the model `pars`, because the alias is matched as a
     substring; «پارس‌آباد» does the same, «شاهین‌شهر» adds `shahin` and
     «شهریار» sets a commute use. None of them shows the city, and after a
     cue «تهرانپارس» lists «در تهران», the part before the alias, which
     reads as a province. It was so before D82; item 4 has the rest.

4. **What the parser drops without a word** (D83). Three ways, found while
   the cities were measured and tried on the real parser. The owner asked
   for all three to be measured before any was touched, with the predictions
   written beforehand, and each is changed only where the measurement showed
   the change clean:
   - A distance cap with no «کارکرد» before it («۲۰۶ زیر ۱۰۰ هزار کیلومتر»)
     was neither read nor listed. It is read now, in four shapes: a cap word,
     a figure and a distance word («زیر ۱۰۰ هزار کیلومتر»); the figure first
     («۱۰۰ هزار کیلومتر یا کمتر»); the distance word first («کیلومتر زیر ۱۰۰
     هزار»); and «زیر ۱۰۰k». «حداکثر» joins the «کارکرد» form. Of 20 caps
     written for it 19 are read, none wrong, and none of the 12 phrases that
     hold a distance and are no odometer, nor of the 8 that give a figure and
     no cap. With neither «هزار» nor «کارکرد» before the figure, it is a cap
     only from 10000 on: «تا ۱۰۰۰ کیلومتر دورتر» is a distance to travel and
     «وانت تا ۱۵۰۰ کیلو» a weight. Known, and left, each pinned by a test so
     that it changes on purpose, each read by nothing and, in a clause that
     names a model, listed by nothing either: a bare figure («پراید ۵۰ هزار
     کیلومتر»); a cap from 1000 to 9999 with no «هزار» and no «کارکرد»
     before it, so «تا ۵۰۰۰ کیلومتر کارکرد» too; «بیشتر از ۵۰ هزار کیلومتر
     نباشه»; and «کیلومتری» («زیر ۱۰۰ هزار کیلومتری»).
   - The budget clause takes everything after its amount up to the next
     «،», so a word after the amount went with it, and
     «پراید تا ۳۰۰ میلیون در مشهد» lost the city. The clause is still taken
     whole, and the budget and the rest of the spec are as they were; what
     stands after the amount is now read as one more clause by the rule of
     item 3, for a cue and no more, cut the way the rest of the query is
     (a year clause taken out, what was acted on blanked). Of 35 cities
     written after a budget, 35 are listed; none of the 171 queries the
     suites and the measurement hold changes; a colour, a filler, a trim
     or a unit word after the amount lists nothing, as before. Known, and
     left, each pinned by a test so that it changes on purpose: what stands
     between the cue and the amount («قیمت در مشهد ۳۰۰ میلیون») is still
     taken with the clause and dropped; and a second budget in the same
     clause lends its «تا» to the place before it, as «یا» does.
   - A model's number inside an amount or a year added a model nobody wrote:
     «دنا تا ۱۳۱۰ میلیون» added `pride`, «تیبا مدل ۱۴۰۵» added `405`. A number
     is read now only where it stands alone: in the query less its amounts
     of money, and not beside another digit. Of 2901 budgets «تیبا تا N
     میلیون» 54 added a model, and of 26 years «تیبا مدل Y» 1; none does.
     The 45 uses of a number as a model written for the measurement are all
     read, the 18 amounts and years that hold one give the models written,
     and none of the suites' 51 queries, nor of 120 ordinary sentences,
     changes. Known, and left, each pinned by a test so that it changes on
     purpose: a number after «و» that follows a scale word is the amount's
     («تا ۳۰۰ میلیون و ۲۰۶»), as it was for the budget; and a name is matched
     as ever, so «پژو۲۰۶۹» and «پژو 206 میلیون» still read 206.
   - A cue or a model alias is matched inside a longer word: «محدوده» sets a
     flexible budget, «بارفروش» a cargo use, «پارس‌آباد» the model `pars`.
     Measured, not changed, and left to the owner, since which letters may
     stand beside a word is a choice about Persian and not a measurement.
     On 69 words that hold a cue or an alias and are no use of it, and 33
     true forms that carry a suffix: no letter before it clears 30 of the
     69 and loses none of the 33, but stops reading a name with a prefix
     typed on, «وتیبا»; no letter on either side clears 63 and loses 16 of
     the 33; the same with a list of suffixes, written by hand for it,
     clears 58 and loses 2.

5. **The budget floor — read from a year, and set as a ceiling too.**
   Found while the third change of item 4 was tested, and older than all
   three: the parser as pushed before them reads the same. Measured, not
   changed, and left to the owner: which words make a floor, and whether
   a bare figure («از ۳۰۰ به بالا») is one, are choices about Persian.
   For the ceiling the second is settled: a budget is taken only from a
   number that is money (`_MONEY`). No test reads a floor from a query,
   and the panel prints what is read under «کف بودجه». Three faults:
   - The text between «از» or «بالای» and «به بالا» goes to `parse_amount`,
     which takes a bare number for millions. «از» is matched at the end of
     a word («شیراز», «اهواز», «نیاز») and as the word of «غیر از», and «به
     بالا» is also the tail of a year clause, so «پراید از مدل ۹۸ به بالا»
     sets a floor of 98,000,000 and «پراید ساکن شیراز مدل ۱۴۰۱ به بالا»
     one of 1,401,000,000. Of 35 such phrases, five years after seven
     lead-ins, 35 set a floor; none of 6 with no «از», or with a comma
     between it and «به بالا», does. On run16, «پراید از مدل ۱۴۰۱ به بالا»
     finds none of the 53 Pride listings, and «پراید مدل ۱۴۰۱ به بالا»
     finds 1.
   - A floor is read as a ceiling too. With no cue clause the first amount
     of money is taken for the ceiling, with the assumption «عدد قیمت را
     سقف بودجه فرض کردیم» printed, and a floor's amount is that amount:
     «پراید از ۴۰۰ میلیون به بالا» has both at 400,000,000, so on run16 it
     finds none of the 53 and holds 3 apart, though 47 of the 50 Pride
     listings that carry a price are at or above it. 5 of 5 floors written
     with no ceiling clause do so.
   - «بالای ۴۰۰ میلیون», without «به بالا», sets no floor, and its amount
     is taken for the ceiling: the meaning reversed, with the assumption
     printed.

   One change was measured in memory and is not built: read the floor by
   `money_amount`, as the ceiling is read. It reads a floor on 0 of the 35
   and 0 of the 6, keeps all 6 floors that are meant, and of 16378 queries
   written for the checks of the last three changes it differs on 162,
   each holding «به بالا» and each in the floor alone. It leaves the
   second and third faults as they are, and it stops reading «از ۳۰۰ به
   بالا» as 300 million, which is the owner's to decide.

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
