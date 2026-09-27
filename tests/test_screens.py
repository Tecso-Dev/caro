"""What a reader is shown: a listing that is not a car, and the car page in
each state its two requests can leave it in.

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
def serving(directory: Path):
    """Point the reader at `directory` for the block, and put it back."""
    was, was_run = corpus_reader.CORPORA, os.environ.get(corpus_mod.RUN_ENV)
    corpus_reader.CORPORA = directory
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

ART = ROOT / "data" / "corpora" / f"{RUN}.json"
CLS = {x["listing_id"]: x.get("product_class")
       for x in json.loads(ART.read_text(encoding="utf-8"))["listings"]}
NVS = sorted(i for i, c in CLS.items() if c != "vehicle")
check(f"  the shipped corpus holds {len(NVS)} non-vehicle(s)", len(NVS) > 0,
      "nothing to draw — said, not passed")

with serving(ART.parent):
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
with serving(ART.parent):
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


print()
if FAILS:
    print(f"FAILED ({len(FAILS)}): " + ", ".join(FAILS))
    raise SystemExit(1)
print("all tests passed")
