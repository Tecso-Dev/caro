"""What a reader is shown for a listing that is not a car.

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

WHAT IT CANNOT SEE. The wiring from `useEffect` to the component. The pages
fetch; these two draw; this feeds the drawing half what the fetching half
would get. Every listing is drawn WITH a decision's refusal, vehicle or not:
a non-car file must not turn into a car file because somebody asked for an
estimate.

THE CONTROL. A vehicle, drawn the same way, must carry every one of the car
file's own claims. Without it the negative checks below could pass on a
page whose wording had merely changed.
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


def render(component: str, export: str, props: list) -> tuple[dict | None, str]:
    req = {"component": component, "export": export, "props": props,
           "consts": {"module": "lib/format.ts",
                      "names": ["NOT_A_CAR_FA", "PRODUCT_CLASS_FA"]}}
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


print()
if FAILS:
    print(f"FAILED ({len(FAILS)}): " + ", ".join(FAILS))
    raise SystemExit(1)
print("all tests passed")
