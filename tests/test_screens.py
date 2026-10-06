"""What a reader is shown: a listing that is not a car, the car page in each
state its two requests can leave it in, a year that stays apart from the name
it follows, search's matches kept apart from listings that could not be
checked, where the closed inbox sends a reader, and an odometer drawn only
with its grade.

Run: PYTHONPATH=. python3 tests/test_screens.py

The contract for detail and compare, chosen after both were measured: they
answer 200 with the listing and its class, and the SCREEN is obliged to say
what the listing is. `tests/test_api_contract.py` §11 checks the API half —
every non-vehicle reaches the screen with its class. This is the other half,
and the one that matters: whether the screen then draws it as a car.

HOW. The two components the pages draw with, `ListingFile` (detail) and
`EvidenceRows` (compare), are rendered with what the API really returns,
through `tests/render_view.cjs` — the web app's own TypeScript and react-dom,
no browser, nothing the app does not already depend on. The assertions are
about the markup a reader gets, not about which fields a component mentions:
a component can read `product_class` and draw a car anyway, which is the
failure this suite exists for.

THE CAR PAGE'S STATE (§3). The car page asks two things — the listing, then
a decision for it — and which screen a reader gets is decided from what the
two requests came to by one pure function, `detailScreen`. §3 hands it real
API answers, and failures shaped the way the page records them, and checks
what it decides; then it draws `CarDetailView` from the same inputs and checks
what a reader gets. Among the cases are the ones a deployment found: a
decision that fails after its listing arrived — no answer, something that is
not this API, or this API's own 404 — leaves the listing's file on the page,
and only the decision says it did not come.

WHAT IT CANNOT SEE. The wiring from `useEffect` to the component. The pages
fetch; these draw; this feeds the drawing half what the fetching half would
get. For the car page that half is now thin, but it is not empty: whether the
effect records what each request came to — `failure()` in CarDetail.tsx,
`json()` in lib/api.ts — and asks for a decision exactly when
`asksForDecision` says so. §1 draws every listing WITH a decision's refusal,
vehicle or not: a non-car file must not turn into a car file because
somebody asked for an estimate.

THE CONTROL. A vehicle, drawn the same way, must carry every one of the car
file's own claims. Without it the negative checks below could pass on a
page whose wording had merely changed. §3 keeps the same rule for the other
screens: a sentence it checks is absent is one it first finds where it
belongs.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import caro.corpus_reader as corpus_reader                         # noqa: E402
from caro.ingest.corpus import SCHEMA                              # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import webapp.api.corpus as corpus_mod                         # noqa: E402
    from webapp.api import main as api                             # noqa: E402
from webapp.api import schemas                                     # noqa: E402

FAILS: list[str] = []
_OUT = sys.stdout


def check(name, cond, detail=""):
    if cond:
        print(f"  ✓ {name}", file=_OUT)
    else:
        print(f"  ✗ {name}  {detail}", file=_OUT)
        FAILS.append(name)


RUN = corpus_mod.DEFAULT_RUN
WEB = ROOT / "webapp" / "web"

# What the car file says about the thing it shows. Every phrase must appear
# when a vehicle is drawn (the control), and none may appear when anything
# else is.
CAR_CLAIMS = ("پرونده‌ی خودرو", "برای این خودرو", "قیمت پیشنهادی")


@contextlib.contextmanager
def serving(directory: Path, run: str | None = None):
    """Point the reader at `directory` for the block, and put it back. With
    `run`, that run is served as the configured one; without, the default."""
    was, was_run = corpus_reader.CORPORA, os.environ.get(corpus_mod.RUN_ENV)
    corpus_reader.CORPORA = directory
    if run:
        os.environ[corpus_mod.RUN_ENV] = run
    else:
        os.environ.pop(corpus_mod.RUN_ENV, None)
    corpus_mod.active.cache_clear()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            yield
    finally:
        corpus_reader.CORPORA = was
        if was_run is None:
            os.environ.pop(corpus_mod.RUN_ENV, None)
        else:
            os.environ[corpus_mod.RUN_ENV] = was_run
        corpus_mod.active.cache_clear()


def classless(n: int = 2) -> str:
    """An artifact whose rows carry no `product_class`, as the schema allows —
    the loader records them as `unknown`. Written to a temp directory, never
    under data/corpora/, for the reason test_api_contract gives."""
    return json.dumps({
        "schema": SCHEMA, "run_id": RUN, "source": "bama.ir",
        "collected_on": "2026-09-09",
        "listings": [{"listing_id": f"b{i}", "asking_price_toman": 500_000_000,
                      "year_jalali": 1392, "mileage_km": 90_000,
                      "make": "peugeot", "model": "206", "trim": "TU5"}
                     for i in range(n)]}, ensure_ascii=False)


def node(req: dict) -> tuple[dict | None, str]:
    """One request to tests/render_view.cjs: draw, read constants, call."""
    try:
        p = subprocess.run(
            ["node", str(ROOT / "tests" / "render_view.cjs"), str(WEB)],
            input=json.dumps(req, ensure_ascii=False), capture_output=True,
            text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)[:160]
    if p.returncode != 0:
        # node ends a thrown error with its own version line; the line worth
        # printing is the error, not the footer.
        lines = p.stderr.strip().splitlines() or ["no output"]
        err = next((ln for ln in lines if re.match(r"\s*\w*Error:", ln)),
                   lines[-1])
        return None, err.strip()[:160]
    return json.loads(p.stdout), ""


def render(component: str, export: str, props: list) -> tuple[dict | None, str]:
    return node({"component": component, "export": export, "props": props,
                 "consts": {"module": "lib/format.ts",
                            "names": ["NOT_A_CAR_FA", "PRODUCT_CLASS_FA"]}})


def call(module: str, name: str, args: list) -> tuple[list | None, str]:
    """`name` from `module`, once per argument list; what each call returned."""
    out, why = node({"call": {"module": module, "name": name, "args": args}})
    return (out["calls"] if out is not None else None), why


def as_json(model) -> dict:
    return model.model_dump(mode="json")


# ---------------------------------------------------------------------------
print("0 — what there is to draw with, and to draw")
# ---------------------------------------------------------------------------
check("node, and the web app's own node_modules",
      shutil.which("node") is not None
      and (WEB / "node_modules" / "typescript").is_dir()
      and (WEB / "node_modules" / "react-dom").is_dir(),
      "run_all skips this suite when they are absent; reaching here without "
      "them means it was run by hand — `cd webapp/web && npm install`")

# Sections 0 to 3 draw a listing that is not a car beside one that is. The
# one real non-vehicle any published corpus holds is run11's assignment, so
# they read run11 by name, served as the configured run, whatever the default
# is. Every other section draws what the default serves.
ART = ROOT / "data" / "corpora" / f"{RUN}.json"
NV_RUN = "run11"
NV_ART = ROOT / "data" / "corpora" / f"{NV_RUN}.json"
CLS = {x["listing_id"]: x.get("product_class")
       for x in json.loads(NV_ART.read_text(encoding="utf-8"))["listings"]}
NVS = sorted(i for i, c in CLS.items() if c != "vehicle")
_served0 = json.loads(ART.read_text(encoding="utf-8"))["listings"]
print(f"    the default corpus ({RUN}) holds "
      f"{sum(x.get('product_class') != 'vehicle' for x in _served0)}"
      f" non-vehicle(s); sections 0 to 3 draw {NV_RUN}'s")
check(f"  {NV_RUN} holds {len(NVS)} non-vehicle(s)", len(NVS) > 0,
      "nothing to draw — said, not passed")

with serving(NV_ART.parent, NV_RUN):
    VEH = next(r.listing_id for r in corpus_mod.active().rows)
    refusal = api.compare(schemas.CompareRequest(ids=[VEH], q="خودرو"))
    files = [(i, CLS[i], api.listing(i)) for i in [VEH] + NVS]
    tables = [((i,), api.compare(schemas.CompareRequest(ids=[i], q="خودرو")))
              for i in NVS]
    tables += [((i, VEH), api.compare(schemas.CompareRequest(
                   ids=[i, VEH], q="خودرو"))) for i in NVS]

with tempfile.TemporaryDirectory() as d:
    (Path(d) / f"{RUN}.json").write_text(classless(), encoding="utf-8")
    with serving(Path(d)):
        files.append(("b0", "unknown", api.listing("b0")))
        tables.append((("b0",), api.compare(schemas.CompareRequest(
            ids=["b0"], q="۲۰۶"))))
WANT = {**CLS, "b0": "unknown"}
REFUSED = (refusal.fault.message if refusal.fault
           else "no estimator is gated on this corpus")


# ---------------------------------------------------------------------------
print("\n1 — the detail page: a listing file, never a car file")
# ---------------------------------------------------------------------------
drawn = [(i, c, d) for i, c, d in files if d.listing is not None]
check(f"every listing asked for came back to be drawn ({len(drawn)} of "
      f"{len(files)})", len(drawn) == len(files),
      "a withheld listing is §11's failure; nothing to draw here")
out, why = render("components/CarDetail.tsx", "ListingFile", [
    {"id": i, "listing": as_json(d.listing), "corpus": as_json(d.corpus),
     "scored": None, "refused": REFUSED} for i, c, d in drawn])
check("  ListingFile could be drawn", out is not None, why)
if out is not None:
    SAY, LABEL = out["consts"]["NOT_A_CAR_FA"], out["consts"]["PRODUCT_CLASS_FA"]
    for (i, c, _), html in zip(drawn, out["markup"]):
        if c == "vehicle":
            missing = [x for x in CAR_CLAIMS if x not in html]
            check(f"  control: {i}, a vehicle, is drawn as a car file",
                  not missing and SAY not in html,
                  f"missing {missing}" if missing else "it says it is not a car")
            continue
        claims = [x for x in CAR_CLAIMS if x in html]
        check(f"  {i} ({c}) is not drawn as a car file", not claims,
              f"it carries {claims}")
        check(f"    and says so, naming it «{LABEL.get(c, c)}»",
              SAY in html and LABEL.get(c, c) in html,
              "the page does not say what the listing is")


# ---------------------------------------------------------------------------
print("\n2 — compare: every row it was asked for, a non-car said to be one")
# ---------------------------------------------------------------------------
tout, why = render("components/CompareTable.tsx", "EvidenceRows", [
    {"evidence": [as_json(x) for x in r.evidence]} for _, r in tables])
check("EvidenceRows could be drawn", tout is not None, why)
if tout is not None:
    SAY = tout["consts"]["NOT_A_CAR_FA"]
    LABEL = tout["consts"]["PRODUCT_CLASS_FA"]
    for (ids, _), html in zip(tables, tout["markup"]):
        rows = dict(re.findall(r'<tr data-listing="([^"]+)">(.*?)</tr>',
                               html, re.S))
        for i in ids:
            row = rows.get(i)
            if WANT[i] == "vehicle":
                check(f"  {' + '.join(ids)}: {i} is drawn as a car",
                      row is not None and SAY not in row
                      and not any(v in row for v in LABEL.values()),
                      "no row" if row is None else "it is labelled")
            else:
                lab = LABEL.get(WANT[i], WANT[i])
                check(f"  {' + '.join(ids)}: {i} says it is «{lab}», not a car",
                      row is not None and SAY in row and lab in row,
                      "no row" if row is None else "drawn like a car")


# ---------------------------------------------------------------------------
print("\n3 — the car page: which screen each pair of answers gets")
# ---------------------------------------------------------------------------
# The car page asks for the listing, then — for a car — for a decision, and
# what a reader gets is decided from what the two requests came to. Each case
# below is such a pair: answers the API really gives, and failures shaped the
# way the page records a request that failed (`Outcome` in CarDetail.tsx).
GONE = "bama:not-in-any-corpus"
car = files[0][2]                            # VEH, first entry of §0's files
nv_id, nv_cls, nv = files[1]                 # a listing that is not a car
b0 = files[-1][2]                            # the classless fixture's row
with serving(NV_ART.parent, NV_RUN):
    missing = api.listing(GONE)
    none_of = api.compare(schemas.CompareRequest(ids=[GONE], q="خودرو"))
    # A configured run that is not on disk: nothing is read, so the page may
    # not even say the car is absent. `serving` puts the variable back.
    os.environ[corpus_mod.RUN_ENV] = "run_no_such_thing"
    corpus_mod.active.cache_clear()
    unread = api.listing(VEH)
check("  the API's own answers for the cases below: "
      f"{missing.fault.code if missing.fault else None}, "
      f"{none_of.fault.code if none_of.fault else None}, "
      f"{unread.fault.code if unread.fault else None}",
      missing.fault is not None and missing.fault.code == "LISTING_NOT_FOUND"
      and none_of.fault is not None
      and none_of.fault.code == "COMPARE_IDS_NOT_FOUND"
      and unread.listing is None and unread.fault is not None
      and unread.fault.code == "RUN_NOT_FOUND",
      "the fixtures are not what the cases below say they are")

PENDING = {"k": "pending"}


def ok(model) -> dict:
    return {"k": "ok", "body": as_json(model)}


def failed(status: int, fault=None) -> dict:
    """A request that failed, as the page records it: the status, the message
    it would show under «جزئیات فنی», and the fault when this API sent one."""
    f = as_json(fault) if fault is not None else None
    return {"k": "failed", "status": status,
            "message": f["message"] if f else str(status), "fault": f}


STATES = [
    # what happened; the listing's outcome, the decision's; screen, and the
    # decision it holds (a file) or the fault it shows (blocked)
    ("nothing has come back yet", PENDING, None, "loading", None),
    ("the listing got no answer", failed(0), None, "no_answer", None),
    ("the listing got a 500 that is not this API's", failed(500), None,
     "no_answer", None),
    ("the API says the listing is not in its corpus",
     failed(404, missing.fault), None, "blocked", "LISTING_NOT_FOUND"),
    ("the API read no corpus at all", ok(unread), None,
     "blocked", "RUN_NOT_FOUND"),
    (f"{VEH}, a car, before its decision is asked for", ok(car), None,
     "file", "deciding"),
    (f"{VEH}, its decision on the way", ok(car), PENDING, "file", "deciding"),
    (f"{VEH}, its decision refused", ok(car), ok(refusal), "file", "refused"),
    # A decision that failed after its listing arrived. The file stays; the
    # decision says it did not come — whatever the failure was.
    (f"{VEH}, its decision got no answer", ok(car), failed(0),
     "file", "unanswered"),
    (f"{VEH}, its decision got a 500 that is not this API's", ok(car),
     failed(500), "file", "unanswered"),
    (f"{VEH}, its decision got a 504", ok(car), failed(504),
     "file", "unanswered"),
    (f"{VEH}, its decision answered 404 with this API's own fault", ok(car),
     failed(404, none_of.fault), "file", "unanswered"),
    (f"{nv_id} ({nv_cls}), for which no decision is asked", ok(nv), None,
     "file", "not_asked"),
    ("b0 (unknown), for which no decision is asked", ok(b0), None,
     "file", "not_asked"),
]


def held(s: dict):
    if s.get("k") == "file":
        return (s.get("decision") or {}).get("k")
    if s.get("k") == "blocked":
        return (s.get("fault") or {}).get("code")
    return None


got, why = call("components/CarDetail.tsx", "detailScreen",
                [[lo, co] for _, lo, co, _, _ in STATES])
check("detailScreen could be called", got is not None, why)
if got is not None:
    for (what, _, _, k, h), s in zip(STATES, got):
        check(f"  {what} → {k}{' · ' + h if h else ''}",
              (s.get("k"), held(s)) == (k, h),
              f"got {s.get('k')} · {held(s)}")

ASKS = [("a car", car, True), (f"{nv_id} ({nv_cls})", nv, False),
        ("b0 (unknown)", b0, False), ("no corpus read", unread, False)]
asks, why = call("components/CarDetail.tsx", "asksForDecision",
                 [[as_json(r)] for _, r, _ in ASKS])
check("asksForDecision could be called", asks is not None, why)
if asks is not None:
    for (what, _, want), a in zip(ASKS, asks):
        check(f"  a decision is asked for {what}: {want}", a is want,
              f"got {a}")

# What a reader gets. The sentences are recognised the way CAR_CLAIMS
# recognises the car file, and each is first found where it belongs — the
# controls — so a reworded screen fails here instead of letting a check that
# it is absent pass.
KNOW_NOTHING = "هیچ چیزی نمی‌دانیم"
NOT_IN_CORPUS = "این آگهی در پیکره‌ی جاری نیست"
DECIDING = "در حال محاسبه‌ی تصمیم"
NO_DECISION = "تصمیمی به این صفحه نرسید"


def car_file(html: str) -> bool:
    """The listing's own file: its heading, its id, its asking price."""
    return CAR_CLAIMS[0] in html and VEH in html and CAR_CLAIMS[2] in html


DRAWN = [("no answer", failed(0), None),
         ("not in corpus", failed(404, missing.fault), None),
         ("deciding", ok(car), PENDING),
         ("refused", ok(car), ok(refusal)),
         ("no answer to the decision", ok(car), failed(0)),
         ("a 500 to the decision", ok(car), failed(500)),
         ("a 504 to the decision", ok(car), failed(504)),
         ("this API's 404 to the decision", ok(car),
          failed(404, none_of.fault))]
dout, why = render("components/CarDetail.tsx", "CarDetailView", [
    {"id": VEH, "listingOutcome": lo, "compareOutcome": co}
    for _, lo, co in DRAWN])
check("CarDetailView could be drawn", dout is not None, why)
if dout is not None:
    page = dict(zip((n for n, _, _ in DRAWN), dout["markup"]))
    check(f"  control: a listing that got no answer says «{KNOW_NOTHING}»",
          KNOW_NOTHING in page["no answer"] and not car_file(page["no answer"]),
          "the sentence the checks below look for is not where it belongs")
    check(f"  control: a listing the corpus does not hold says "
          f"«{NOT_IN_CORPUS}»", NOT_IN_CORPUS in page["not in corpus"],
          "the sentence the checks below look for is not where it belongs")
    check(f"  {VEH}, its decision on the way: its file, and «{DECIDING}…»",
          car_file(page["deciding"]) and DECIDING in page["deciding"])
    check(f"  {VEH}, its decision refused: its file, with every claim",
          all(x in page["refused"] for x in CAR_CLAIMS)
          and VEH in page["refused"])
    for n in ("no answer to the decision", "a 500 to the decision",
              "a 504 to the decision", "this API's 404 to the decision"):
        html = page[n]
        check(f"  {VEH}, {n}: its file is still drawn", car_file(html),
              "the listing that arrived is not on the page")
        said = [x for x in (KNOW_NOTHING, NOT_IN_CORPUS) if x in html]
        check(f"    and only the decision says it did not come",
              NO_DECISION in html and not said,
              f"it says «{'», «'.join(said)}»" if said
              else "the decision's panel does not say so")


# ---------------------------------------------------------------------------
print("\n4 — the year beside a car's name is a unit of its own")
# ---------------------------------------------------------------------------
# A name that ends in a trim code or a number — «۱۳۱ SE», «manualr ۲۰۲۲» — is
# a left-to-right run, and a year drawn after it in a plain span joined that
# run: on the name's wrong side with no gap, «SE۱۳۹۶», or read as one number
# with it, «۲۰۲۲۱۴۰۱». Measured in a browser on run11's car pages, 69 of 75
# headings did that. How a browser lays a line out is not visible from here;
# the cause is. So the check is that the year is drawn isolated, in a <bdi>,
# on each surface this suite can draw that puts a year after a name: the car
# file for every vehicle in run11, and the card a gated corpus serves.
# Compare's scored header does the same, but is drawn only inside the page's
# effect, and is not checked here.
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def isolated_year(html: str, tag: str, year) -> bool:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.S)
    y = str(year).translate(_FA)
    return bool(m and re.search(rf"<bdi[^>]*>\s*{y}\s*</bdi>", m.group(1)))


_CLS4 = {x["listing_id"]: x.get("product_class")
         for x in json.loads(ART.read_text(encoding="utf-8"))["listings"]}
with serving(ART.parent):
    _cars = [(x.listing_id, api.listing(x.listing_id))
             for x in corpus_mod.active().listings
             if _CLS4.get(x.listing_id) == "vehicle"]
_cout, why = render("components/CarDetail.tsx", "ListingFile", [
    {"id": i, "listing": as_json(d.listing), "corpus": as_json(d.corpus),
     "scored": None, "refused": REFUSED} for i, d in _cars])
check(f"every vehicle in {RUN} drawn as its car file ({len(_cars)})",
      _cout is not None and len(_cars) > 0, why or "no vehicles to draw")
if _cout is not None:
    _run = [i for (i, d), html in zip(_cars, _cout["markup"])
            if not isolated_year(html, "h1", d.listing.year_jalali)]
    check(f"  the year beside the name is isolated in all "
          f"{len(_cars) - len(_run)} of {len(_cars)}", not _run,
          f"a plain span in {len(_run)}, e.g. {_run[:3]}")

with tempfile.TemporaryDirectory() as d:
    with serving(Path(d)):
        _found = api.search(q="پراید", k=8)
_items = list(_found.items)
_kout, why = render("components/ListingCard.tsx", "default",
                    [{"item": as_json(x)} for x in _items])
check(f"the cards a gated corpus serves could be drawn ({len(_items)})",
      _kout is not None and len(_items) > 0, why or "no cards to draw")
if _kout is not None:
    _run = [x.id for x, html in zip(_items, _kout["markup"])
            if not isolated_year(html, "h3", x.year_jalali)]
    check(f"  the year beside the name is isolated on all "
          f"{len(_items) - len(_run)} of {len(_items)}", not _run,
          f"a plain span on {len(_run)}")


# ---------------------------------------------------------------------------
print("\n5 — search: a match is drawn as one only where it was checked")
# ---------------------------------------------------------------------------
# The API now sends the evidence in two lists: listings every stated
# constraint was checked against and met, and listings that broke none but
# could not be checked against some (`webapp/api/constraints.py`). The
# second kind is not a match, and the reader must not be told it is one. So
# `SearchEvidence` is drawn with what search really returns for every example
# chip on run11, at the k=8 the results page asks for; for two queries that
# match nothing — one with listings apart, one without; and for one whose
# listings apart are more than a table holds. The checks read the markup:
# which table each row is in, and what it says is missing.
_BOX5 = (WEB / "components" / "SearchBox.tsx").read_text(encoding="utf-8")
_m5 = re.search(r"const EXAMPLES = \[(.*?)\];", _BOX5, re.S)
_Q5 = (re.findall(r"'([^']+)'", _m5.group(1)) if _m5 else []) \
    + ["پراید زیر ۱۰ میلیون", "تیبا زیر ۱۰ میلیون", "پراید سند آزاد"]
with serving(ART.parent):
    _found5 = [(q, api.search(q=q, k=8)) for q in _Q5]

_eout, why = node({"component": "components/SearchEvidence.tsx",
                   "export": "SearchEvidence",
                   "props": [{"data": as_json(r)} for _, r in _found5],
                   "consts": {"module": "components/SearchEvidence.tsx",
                              "names": ["MATCHED_FA", "APART_FA", "NONE_FA"]}})
_fout, why2 = node({"consts": {"module": "lib/format.ts",
                               "names": ["UNCHECKED_FA"]}})
check(f"SearchEvidence could be drawn for {len(_found5)} answers",
      _eout is not None and _fout is not None, why or why2)


def _sections(html: str) -> dict[str, str]:
    return dict(re.findall(
        r'<section[^>]*data-evidence="(\w+)"[^>]*>(.*?)</section>', html, re.S))


def _rows(html: str) -> dict[str, str]:
    return dict(re.findall(r'<tr data-listing="([^"]+)">(.*?)</tr>', html,
                           re.S))


def _text(html: str) -> str:
    """What a reader reads: no tags, no React's text-node comments."""
    t = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t))


_reach5 = {"matched beyond k": False, "apart": False,
           "apart beyond k": False, "none+apart": False, "none": False}
if _eout is not None and _fout is not None:
    MATCHED, APART, NONE = (_eout["consts"][n]
                            for n in ("MATCHED_FA", "APART_FA", "NONE_FA"))
    PHRASE = _fout["consts"]["UNCHECKED_FA"]
    for (q, r), html in zip(_found5, _eout["markup"]):
        sec = _sections(html)
        got_m = _rows(sec.get("matched", ""))
        got_a = _rows(sec.get("apart", ""))
        want_m = [x.id for x in r.evidence]
        want_a = {x.id: x.unchecked for x in r.evidence_unchecked}
        check(f"  «{q[:30]}» — {len(want_m)} drawn as matches, "
              f"{len(want_a)} apart, each in its own table",
              list(got_m) == want_m and set(got_a) == set(want_a)
              and not set(got_m) & set(want_a),
              f"matches drawn {list(got_m)} · apart drawn {list(got_a)}")
        _named = [i for i, keys in want_a.items()
                  if not all(PHRASE[k] in got_a.get(i, "") for k in keys)]
        check("    each row apart says what is missing",
              not _named, f"not said for {_named}")
        _quiet = [i for i, row in got_m.items()
                  if any(p in row for p in PHRASE.values())]
        check("    and no match carries such a phrase (the control)",
              not _quiet, f"on {_quiet}")
        check("    the heading that says «منطبق» is over matches alone",
              (MATCHED in sec.get("matched", "")) == (r.evidence_total > 0)
              and MATCHED not in sec.get("apart", "")
              and (APART in sec.get("apart", "")) == bool(want_a),
              f"sections drawn: {sorted(sec)}")
        check(f"    «{NONE}» exactly when nothing matched "
              f"({r.evidence_total})",
              (NONE in html) == (r.evidence_total == 0)
              and ("none" in sec) == (r.evidence_total == 0))
        for kind, shown, total in (
                ("matched", len(r.evidence), r.evidence_total),
                ("apart", len(r.evidence_unchecked),
                 r.evidence_unchecked_total)):
            if total > shown:
                _of = (f"{shown} از {total}").translate(_FA)
                check(f"    {kind}: says it shows {shown} of {total}",
                      _of in _text(sec.get(kind, "")),
                      "a table of the first k reads as all of them")
                _reach5[f"{kind} beyond k"] = True
        if want_a:
            _reach5["apart"] = True
        if r.evidence_total == 0:
            _reach5["none+apart" if want_a else "none"] = True

for _case, _hit in _reach5.items():
    check(f"  the answers reach the case «{_case}»", _hit,
          "nothing drawn for it — said, not passed")


# ---------------------------------------------------------------------------
print("\n6 — the closed inbox: where to go, and what it takes")
# ---------------------------------------------------------------------------
# With CARO_INBOX=off the contact page draws no form, only the place to write
# instead — GitHub Issues, from `contact.ELSEWHERE` by way of
# /api/contact/status. Drawn with that constant: the link must be it, and the
# page must say that writing there needs a GitHub account and reading does
# not, before anyone arrives at a sign-in page.
from webapp.api import contact as _contact                        # noqa: E402

_iout, why = node({"component": "components/ContactForm.tsx",
                   "export": "InboxClosed",
                   "props": [{"elsewhere": _contact.ELSEWHERE}],
                   "consts": {"module": "components/ContactForm.tsx",
                              "names": ["ACCOUNT_FA"]}})
check("InboxClosed could be drawn", _iout is not None, why)
if _iout is not None:
    _ihtml = _iout["markup"][0]
    check(f"  its one link is {_contact.ELSEWHERE}",
          re.findall(r'href="([^"]+)"', _ihtml) == [_contact.ELSEWHERE],
          str(re.findall(r'href="([^"]+)"', _ihtml)))
    check("  and it says what writing there takes",
          bool(_iout["consts"]["ACCOUNT_FA"])
          and _iout["consts"]["ACCOUNT_FA"] in _text(_ihtml),
          "the sentence is not on the page")



# ---------------------------------------------------------------------------
print("\n7 — an odometer is drawn with its grade, on every surface")
# ---------------------------------------------------------------------------
# The API sends `mileage_status` beside `mileage_km`, and the constraint lets
# only a plausible reading decide (test_api_contract §13, §15). This is the
# page's half: search's two tables, the car file and compare's evidence rows,
# each drawn with what the API returns for the same eight cases contract §15
# sends — from a temporary artifact, because run11 holds no suspicious or
# impossible reading. A number is drawn only where it is plausible; every
# other grade is said in its place, in one of the phrases that keep D22's
# three cases apart.
_ODO7 = [   # id, odometer, grade (None: the record states none), year
    ("o_ok", 100_000, "plausible", 1398), ("o_hi", 200_000, "plausible", 1398),
    ("o_none", None, "unknown", 1398), ("o_low", 1, "suspicious", 1385),
    ("o_ph", 999_990, "suspicious", 1398), ("o_neg", -5_000, "impossible", 1398),
    ("o_huge", 2_000_000, "impossible", 1398), ("o_bare", 90_000, None, 1398),
]
_rows7 = []
for _i, _km, _ms, _y in _ODO7:
    _r = {"listing_id": _i, "product_class": "vehicle",
          "asking_price_toman": 500_000_000, "price_kind": "cash",
          "price_status": "display_confirmed", "year_jalali": _y,
          "make": "peugeot", "model": "206", "trim": "TU5"}
    if _km is not None:
        _r["mileage_km"] = _km
    if _ms is not None:
        _r["mileage_status"] = _ms
    _rows7.append(_r)

with tempfile.TemporaryDirectory() as d:
    (Path(d) / f"{RUN}.json").write_text(json.dumps(
        {"schema": SCHEMA, "run_id": RUN, "source": "bama.ir",
         "collected_on": "2026-10-05", "listings": _rows7},
        ensure_ascii=False), encoding="utf-8")
    with serving(Path(d)):
        _search7 = api.search(q="۲۰۶ کم‌کارکرد", k=24)
        _detail7 = [(i, api.listing(i)) for i, *_ in _ODO7]
        _cmp7 = api.compare(schemas.CompareRequest(
            ids=[i for i, *_ in _ODO7], q="۲۰۶"))

_c7, why = node({"consts": {"module": "lib/format.ts",
                            "names": ["ODOMETER_FA", "ODOMETER_UNGRADED_FA"]}})
check("the phrases could be read", _c7 is not None, why)
if _c7 is not None:
    _FA7 = _c7["consts"]["ODOMETER_FA"]
    _phr = {"unknown": _FA7["unknown"], "suspicious": _FA7["suspicious"],
            "impossible": _FA7["impossible"],
            None: _c7["consts"]["ODOMETER_UNGRADED_FA"]}
    check("  three grades, three different phrases, and a fourth for none",
          len(set(_phr.values())) == 4, str(_phr))

    def _expect7(km, ms):
        """Exactly what goes where the odometer is drawn: the number where
        the grade is plausible, the grade's phrase everywhere else."""
        if ms == "plausible":
            return (f"{km:,}".replace(",", "٬").translate(_FA) + " کیلومتر")
        return _phr[ms]

    def _cells(row_html):
        return [_text(c).strip()
                for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)]

    _sout, why = node({"component": "components/SearchEvidence.tsx",
                       "export": "SearchEvidence",
                       "props": [{"data": as_json(_search7)}]})
    _fout, why2 = render("components/CarDetail.tsx", "ListingFile", [
        {"id": i, "listing": as_json(r.listing), "corpus": as_json(r.corpus),
         "scored": None, "refused": REFUSED} for i, r in _detail7])
    _eout, why3 = render("components/CompareTable.tsx", "EvidenceRows",
                         [{"evidence": [as_json(x) for x in _cmp7.evidence]}])
    check("search, the car file and compare could be drawn",
          None not in (_sout, _fout, _eout), why or why2 or why3)
    if None not in (_sout, _fout, _eout):
        _srows = _rows(_sout["markup"][0])
        _erows = _rows(_eout["markup"][0])
        for (_i, _km, _ms, _y), _fhtml in zip(_ODO7, _fout["markup"]):
            _want = _expect7(_km, _ms)
            _seen, _bad = [], []
            if _i in _srows:
                # A match: name, year, odometer, price, link. Held apart:
                # name, why, year, odometer, price, link — and the why is the
                # odometer's own grade, since the cap is all it was asked.
                _c = _cells(_srows[_i])
                _odo = _c[3] if len(_c) == 6 else _c[2]
                _why = _c[1] if len(_c) == 6 else None
                _seen.append("search")
                if _odo != _want or (_why is not None and _why != _want):
                    _bad.append(f"search: {_odo!r} / why {_why!r}")
            _dd = re.search(r"<dt[^>]*>کارکرد</dt><dd[^>]*>(.*?)</dd>", _fhtml,
                            re.S)
            _seen.append("car file")
            if (not _dd or _text(_dd.group(1)).strip() != _want
                    or (_ms != "plausible" and "کیلومتر" in _text(_fhtml))):
                _bad.append(f"car file: "
                            f"{_text(_dd.group(1)).strip() if _dd else None!r}")
            if _i in _erows:
                _odo = _cells(_erows[_i])[2]
                _seen.append("compare")
                if _odo != _want:
                    _bad.append(f"compare: {_odo!r}")
            check(f"  {_i} ({_ms or 'no grade'}, {_km}) → «{_want}» on "
                  f"{' · '.join(_seen)}", not _bad, "; ".join(_bad))
        _apart = {x.id for x in _search7.evidence_unchecked}
        check("  search holds every grade but plausible apart, and draws the "
              "plausible one under the cap as its match",
              _apart == {"o_none", "o_low", "o_ph", "o_neg", "o_huge", "o_bare"}
              and [x.id for x in _search7.evidence] == ["o_ok"],
              f"apart {sorted(_apart)} · matched {[x.id for x in _search7.evidence]}")


# ---------------------------------------------------------------------------
print("\n8 — the car page says a price the way search and compare do")
# ---------------------------------------------------------------------------
# FIELD_PROVENANCE.md's rule for a price — `price_kind` cash and a
# `price_status` that is not unusable, or the figure is not an asking price —
# is `askingPrice()` in lib/format.ts. Search and compare drew with it; the
# car page drew `toman()`, so on run11 its heading and its «قیمت پیشنهادی»
# cell said «ثبت‌نشده» for the two listings search and compare call
# «توافقی». Drawn here: six listings, one for each kind of price, served from
# a temporary artifact the way the API sends them; an appraisal row, which
# carries neither field; and run11's own «توافقی» listings beside a cash one.
# Both places must say exactly the expected thing, and an amount that is not
# an asking price must be nowhere on the page.
_P8 = [   # id, kind, status, amount, what both places say
    ("p_cash", "cash", "display_confirmed", 500_000_000, "amount"),
    ("p_so", "cash", "structured_only", 450_000_000, "amount"),
    ("p_neg", "negotiable", "absent", None, ("kind", "negotiable")),
    ("p_fin", "financing_total", "display_confirmed", 900_000_000,
     ("kind", "financing_total")),
    ("p_amb", "cash", "ambiguous", 500_000_000, ("status", "ambiguous")),
    ("p_abs", "absent", "absent", None, ("kind", "absent")),
]
_rows8 = []
for _i, _k, _s, _a, _ in _P8:
    _r = {"listing_id": _i, "product_class": "vehicle", "price_kind": _k,
          "price_status": _s, "year_jalali": 1398, "mileage_km": 90_000,
          "mileage_status": "plausible", "make": "peugeot", "model": "206",
          "trim": "TU5"}
    if _a is not None:
        _r["asking_price_toman"] = _a
    _rows8.append(_r)

with tempfile.TemporaryDirectory() as d:
    (Path(d) / f"{RUN}.json").write_text(json.dumps(
        {"schema": SCHEMA, "run_id": RUN, "source": "bama.ir",
         "collected_on": "2026-10-06", "listings": _rows8},
        ensure_ascii=False), encoding="utf-8")
    with serving(Path(d)):
        _built8 = [(i, api.listing(i)) for i, *_ in _P8]

_L11 = json.loads(ART.read_text(encoding="utf-8"))["listings"]
_neg11 = sorted(x["listing_id"] for x in _L11
                if x.get("product_class") == "vehicle"
                and x.get("price_kind") == "negotiable")
_cash11 = next(x for x in _L11 if x.get("product_class") == "vehicle"
               and x.get("price_kind") == "cash"
               and x.get("price_status") == "display_confirmed"
               and x.get("asking_price_toman"))
with serving(ART.parent):
    _run8 = [(i, api.listing(i)) for i in _neg11 + [_cash11["listing_id"]]]

check("the API sends each built listing's price fields as the artifact "
      "holds them",
      all(r.listing is not None
          and (r.listing.price_kind, r.listing.price_status,
               r.listing.asking_price_toman) == (k, s, a)
          for (_, r), (_i, k, s, a, _w) in zip(_built8, _P8)),
      str([(r.listing.price_kind, r.listing.price_status,
            r.listing.asking_price_toman) if r.listing else None
           for _, r in _built8]))
check(f"{RUN} holds «توافقی» listings to draw, and a cash one",
      len(_neg11) > 0, "nothing to draw — said, not passed")

_row8 = {"id": "p_row", "url": "", "model_key": "peugeot 206 TU5",
         "make": "peugeot", "model": "206", "trim": "TU5",
         "year_jalali": 1398, "mileage_km": 90_000,
         "asking_price_toman": 500_000_000, "product_class": "vehicle",
         "price_status": None, "price_kind": None, "mileage_status": None}
_props8 = ([{"id": i, "listing": as_json(r.listing), "corpus": as_json(r.corpus),
             "scored": None, "refused": REFUSED} for i, r in _built8]
           + [{"id": "p_row", "listing": _row8,
               "corpus": as_json(_built8[0][1].corpus), "scored": None,
               "refused": REFUSED}]
           + [{"id": i, "listing": as_json(r.listing),
               "corpus": as_json(r.corpus), "scored": None,
               "refused": REFUSED} for i, r in _run8])
_out8, why = node({"component": "components/CarDetail.tsx",
                   "export": "ListingFile", "props": _props8,
                   "consts": {"module": "lib/format.ts",
                              "names": ["PRICE_KIND_FA", "PRICE_STATUS_FA"]}})
check("the car file could be drawn for each", _out8 is not None, why)
if _out8 is not None:
    _KIND8 = _out8["consts"]["PRICE_KIND_FA"]
    _STAT8 = _out8["consts"]["PRICE_STATUS_FA"]

    def _toman8(a):
        return f"{a:,}".replace(",", "٬").translate(_FA) + " تومان"

    _cases8 = ([(i, a, w) for i, _k, _s, a, w in _P8]
               + [("p_row", 500_000_000, "amount")]
               + [(i, None, ("kind", "negotiable")) for i in _neg11]
               + [(_cash11["listing_id"], _cash11["asking_price_toman"],
                   "amount")])
    for (_i, _a, _w), _html in zip(_cases8, _out8["markup"]):
        _want = (_toman8(_a) if _w == "amount"
                 else (_KIND8 if _w[0] == "kind" else _STAT8)[_w[1]])
        _head = re.search(r'class="mt-2 mb-0[^"]*"><span class="fig">(.*?)'
                          r'</span>', _html, re.S)
        _cell = re.search(r"<dt[^>]*>قیمت پیشنهادی</dt><dd[^>]*>(.*?)</dd>",
                          _html, re.S)
        _got = [_text(m.group(1)).strip() if m else None
                for m in (_head, _cell)]
        _shown = (_a is not None and _w != "amount"
                  and _toman8(_a).split(" ")[0] in _text(_html))
        check(f"  {_i} → «{_want}» in the heading and under «قیمت پیشنهادی»"
              + ("" if _w == "amount" or _a is None
                 else ", its amount nowhere"),
              _got == [_want, _want] and not _shown,
              f"heading {_got[0]!r} · cell {_got[1]!r}"
              + (" · the amount is on the page" if _shown else ""))

print()
if FAILS:
    print(f"FAILED ({len(FAILS)}): " + ", ".join(FAILS))
    raise SystemExit(1)
print("all tests passed")
