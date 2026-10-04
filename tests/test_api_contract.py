"""The API's contract, checked in every corpus state — and against the client.

Run: PYTHONPATH=. python3 tests/test_api_contract.py

A suite that asserted "the endpoint returned 200" would pass on every bug this
project has actually had. The endpoint returned 200 when it claimed to have
ranked an empty corpus. It returned 200 while serving generated data under a
truthful label because a real artifact had silently failed to load. Status
codes are not the contract.

What is checked instead:

    1  a valid synthetic corpus     → the response model validates
    2  a valid real corpus          → validates, and carries a sha256
    3  a missing DEFAULT corpus     → SYNTHETIC, no fault, and it names
                                      the artifact it looked for
    3b a missing CONFIGURED run     → UNUSABLE / RUN_NOT_FOUND, never a
                                      silent substitution
    3c listing / compare on it      → the envelope, not a 404 claiming the
                                      car is not there
    3d the same, as real HTTP       → 200 when the fault is about the SOURCE,
                                      404 when it is about the RESOURCE, and
                                      an envelope on both
    4  a broken corpus              → UNUSABLE, a fault, and never SYNTHETIC
    5  an ungated corpus            → evidence may exist, no estimate is
                                      fabricated for it
    6  a refusal                    → HTTP 200, a product state, schema-valid
    7  the client's TypeScript      → the same fields AND the same union
                                      members as the Python models

Seven is the one that cannot be written any other way. `lib/api.ts` is a
second hand-written description of `webapp/api/schemas.py`, and TypeScript
validates the client against ITS OWN belief about the server. That belief is
exactly what goes stale. So this reads the file.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import typing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from caro.ingest.corpus import SCHEMA                              # noqa: E402
import caro.corpus_reader as corpus_reader                         # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import webapp.api.corpus as corpus_mod                         # noqa: E402
    from webapp.api import main as api                             # noqa: E402
from webapp.api import schemas                                     # noqa: E402

FAILS = []

# Loading a corpus prints — `_synthetic()` imports the ranking suite, which
# runs its own checks — and that noise must not land in this suite's output.
# But the suppression is around the corpus load, and `check()` runs INSIDE it.
# Writing to the captured stdout would silently swallow every result line: the
# assertions would still run and still fail the build, while a reader saw
# nothing and the runner counted almost none of them. So `check` holds the
# real stream.
_OUT = sys.stdout


def check(name, cond, detail=""):
    if cond:
        print(f"  ✓ {name}", file=_OUT)
    else:
        print(f"  ✗ {name}  {detail}", file=_OUT)
        FAILS.append(name)


RUN = corpus_mod.DEFAULT_RUN     # read, never spelled out — see below


@contextlib.contextmanager
def corpus_dir(body: str | None, *, run_env: str | None = None):
    """Point the reader at a temp directory, optionally holding an artifact.

    Nothing is written under `data/corpora/`. A fabricated file there is
    indistinguishable from a collected one, and that confusion is what the
    corpus label exists to prevent.

    The artifact is named after `corpus_mod.DEFAULT_RUN` rather than a literal.
    Writing `run3.json` was, without meaning to, an assertion that the default
    is whatever this suite happens to write — which is why every check here
    passed for months while the shipped default named an artifact D46 had
    removed, and the site served SYNTHETIC to everybody.

    `run_env` sets CARO_RUN for the block. `None` clears it, so the default
    path is exercised against a known-empty variable rather than the shell's.
    """
    was, was_run = corpus_reader.CORPORA, os.environ.get(corpus_mod.RUN_ENV)
    with tempfile.TemporaryDirectory() as d:
        if body is not None:
            (Path(d) / f"{RUN}.json").write_text(body, encoding="utf-8")
        corpus_reader.CORPORA = Path(d)
        if run_env is None:
            os.environ.pop(corpus_mod.RUN_ENV, None)
        else:
            os.environ[corpus_mod.RUN_ENV] = run_env
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


def valid_artifact(n: int = 9, *, product_class: str | None = None) -> str:
    """A small artifact in the published schema.

    By default its rows carry no `product_class`, which the schema allows,
    and the loader records such a row as `unknown` — never as `vehicle`.
    A section whose claim needs cars in the corpus says so by passing
    `product_class="vehicle"`. The default is never assumed to hold any.
    """
    rows = [
        {"listing_id": f"b{i}",
         "asking_price_toman": 500_000_000 + i * 40_000_000,
         "year_jalali": 1392 + (i % 4), "mileage_km": 90_000 + i * 9000,
         "make": "peugeot", "model": "206", "trim": "TU5",
         "province": "tehran"}
        for i in range(n)]
    if product_class is not None:
        for x in rows:
            x["product_class"] = product_class
    obj = {
        "schema": SCHEMA, "run_id": RUN, "source": "bama.ir",
        "collected_on": "2026-09-09",
        "listings": rows,
    }
    return json.dumps(obj, ensure_ascii=False, indent=2)


def validates(model, obj) -> tuple[bool, str]:
    """Round-trip through the model. A response that cannot be re-validated
    from its own serialised form is not a contract, it is a coincidence."""
    try:
        model.model_validate(json.loads(obj.model_dump_json()))
        return True, ""
    except Exception as e:                      # noqa: BLE001
        return False, str(e)[:160]


# ---------------------------------------------------------------------------
print("1 — a valid synthetic corpus", file=_OUT)
with corpus_dir(None):
    r = api.search(q="۲۰۶ زیر ۸۰۰ میلیون", k=3)
    ok, why = validates(schemas.SearchResponse, r)
    check("SearchResponse validates", ok, why)
    check("  status.kind is SYNTHETIC", r.status.kind == "SYNTHETIC",
          r.status.kind)
    check("  and it serves, because the gate passes on it",
          r.status.served and r.status.gated)
    check("  with a shortlist and no evidence table",
          len(r.items) == 3 and r.evidence == [])
    ok, why = validates(schemas.CorpusResponse, api.which_corpus())
    check("CorpusResponse validates", ok, why)


# ---------------------------------------------------------------------------
print("\n2 — a valid real corpus")
with corpus_dir(valid_artifact()):
    r = api.search(q="۲۰۶", k=5)
    ok, why = validates(schemas.SearchResponse, r)
    check("SearchResponse validates", ok, why)
    check("  status.kind is REAL", r.status.kind == "REAL", r.status.kind)
    check("  identity is present", r.corpus.identity is not None)
    check("  and sha256 is a 64-character digest",
          r.corpus.identity is not None
          and re.fullmatch(r"[0-9a-f]{64}", r.corpus.identity.sha256)
          is not None,
          r.corpus.identity.sha256 if r.corpus.identity else "None")
    check("  run_id names the run", r.corpus.identity.run_id == RUN,
          str(r.corpus.identity.run_id))

    # The ids are the fixture's own. Reading them back out of a search made
    # these two checks depend on what search chooses to show, which is a
    # different question from whether a caller holding an id gets a valid
    # envelope from the detail and compare paths.
    lst = api.listing("b0")
    ok, why = validates(schemas.ListingResponse, lst)
    check("ListingResponse validates on a real corpus", ok, why)

    cmp_ = api.compare(schemas.CompareRequest(ids=["b0", "b1"], q="۲۰۶"))
    ok, why = validates(schemas.CompareResponse, cmp_)
    check("CompareResponse validates on a real corpus", ok, why)
    check("  and it returns evidence, not rows",
          cmp_.rows == [] and len(cmp_.evidence) == 2)

    # This fixture carries no `product_class`, as the published schema
    # allows. The loader records such a row as `unknown`, never `vehicle`,
    # and search shows no `unknown` as a car (D52) — strict, by decision: a
    # class nobody determined does not pass the gate. The ids above still
    # reach the detail and compare paths; whether those should refuse a
    # non-vehicle is not decided here.
    _loaded = corpus_mod.active().listings
    check("  a row with no class is loaded as `unknown`, not `vehicle`",
          len(_loaded) == 9
          and all(x.product_class == "unknown" for x in _loaded),
          str(sorted({x.product_class for x in _loaded})))
    check("  and search shows none of them as a car",
          r.evidence == [] and r.items == [],
          f"shown: {[e.id for e in r.evidence]}")

# The control: the same nine rows and the same query, with the class the
# only difference. Without it, «none of them» above would pass just as well
# on a search that showed nothing to anybody.
with corpus_dir(valid_artifact(product_class="vehicle")):
    _r2 = api.search(q="۲۰۶", k=5)
    check("  the same rows declared `vehicle` are shown by the same query",
          len(_r2.evidence) == 5, f"shown: {[e.id for e in _r2.evidence]}")


# ---------------------------------------------------------------------------
print("\n3 — a missing DEFAULT corpus falls back, and says what it looked for")
with corpus_dir(None):
    r = api.which_corpus()
    check("kind is SYNTHETIC", r.status.kind == "SYNTHETIC", r.status.kind)
    check("  and there is NO fault — absence is not a failure",
          r.fault is None, str(r.fault))
    check("  and no identity is invented for it",
          r.corpus.identity is None)
    # The fallback was right, and mute. A deployment whose corpus sat in the
    # wrong directory rendered identically to one that had never collected
    # anything, and neither said which path had been tried.
    check("  and the note names the artifact it did not find",
          f"{RUN}.json" in r.corpus.note_fa, r.corpus.note_fa[-90:])


# ---------------------------------------------------------------------------
print("\n3b — a run that was ASKED FOR and is missing is not a fallback")
with corpus_dir(None, run_env="run_no_such_thing"):
    r = api.search(q="۲۰۶", k=3)
    ok, why = validates(schemas.SearchResponse, r)
    check("SearchResponse still validates", ok, why)
    check("  kind is UNUSABLE, not SYNTHETIC",
          r.status.kind == "UNUSABLE", r.status.kind)
    check("  fault.code is RUN_NOT_FOUND, not CORPUS_INVALID",
          r.fault is not None and r.fault.code == "RUN_NOT_FOUND",
          str(r.fault.code if r.fault else None))
    check("  and the message names the run that was asked for",
          r.fault is not None and "run_no_such_thing" in r.fault.message,
          str(r.fault.message if r.fault else None))
    check("  and nothing is served from it",
          not r.status.served and r.items == [] and r.evidence == [])
    # The two UNUSABLE causes reach a client through `fault.code` and through
    # nothing else, which is why the badge branches on the code and not on the
    # kind: «CORPUS UNUSABLE» over a run that is simply not there sends the
    # reader to inspect an artifact that is fine.
    check("  and `kind` alone cannot tell it from a corrupt file",
          r.status.kind == "UNUSABLE")


# ---------------------------------------------------------------------------
# 3c — the two endpoints that used to answer with a 404.
#
# `/api/listing` and `/api/compare` raised HTTPException before the envelope
# was built, so on an unloadable corpus the client was told «no listing 'b0'
# in this corpus» and «none of those ids are in this corpus». Both sentences
# are claims about a LISTING, made from a fact about the SOURCE (D54), and the
# second one is what a whole deployment said about every car on the site the
# moment CARO_RUN named a run that was not there. The listing may exist; there
# is nowhere to look.
print("\n3c — a refusal about the source is not a 404 about the listing")
for label, body, env, want_code in [
        ("configured run missing", None, "run_no_such_thing", "RUN_NOT_FOUND"),
        ("artifact will not load", "<html>404</html>", None, "CORPUS_INVALID")]:
    with corpus_dir(body, run_env=env):
        r = api.listing("b0")
        ok, why = validates(schemas.ListingResponse, r)
        check(f"{label} → ListingResponse validates", ok, why)
        check("  it carries the envelope, not an HTTP error",
              r.status.kind == "UNUSABLE" and r.fault is not None)
        check(f"  the fault is {want_code}",
              r.fault is not None and r.fault.code == want_code,
              str(r.fault.code if r.fault else None))
        check("  and `listing` is null — no car is claimed either way",
              r.listing is None, str(r.listing))

        c = api.compare(schemas.CompareRequest(ids=["b0", "b1"], q="۲۰۶"))
        ok, why = validates(schemas.CompareResponse, c)
        check("  CompareResponse validates", ok, why)
        check("  with the envelope and nothing in it",
              c.status.kind == "UNUSABLE" and c.rows == [] and c.evidence == [],
              f"rows={len(c.rows)} evidence={len(c.evidence)}")

# ---------------------------------------------------------------------------
# 3d — the statuses, over real HTTP.
#
# The checks above call the endpoints as Python functions, which is right for
# the models and blind to the thing this section is about: whether a 404 is
# still a 404, and whether its BODY is the envelope. A status code set on
# FastAPI's injected response object does not exist until something serves it,
# so this one goes through the stack.
#
# Three outcomes have to stay apart, and the first two used to be one:
#
#     no corpus was read          200   the fault is about the SOURCE
#     a corpus was read, id gone  404   the fault is about the RESOURCE
#     a corpus was read, id there 200   a listing
print("\n3d — the same distinctions as HTTP statuses, with envelopes")
from fastapi.testclient import TestClient                       # noqa: E402

HTTP = [
    # (label, artifact, CARO_RUN, request, want status, want fault code)
    ("no corpus · listing", None, "run_gone", ("GET", "/api/listing/b0"),
     200, "RUN_NOT_FOUND"),
    ("no corpus · compare", None, "run_gone", ("POST", "/api/compare"),
     200, "RUN_NOT_FOUND"),
    ("broken file · listing", "<html>404</html>", None,
     ("GET", "/api/listing/b0"), 200, "CORPUS_INVALID"),
    ("healthy · id present", valid_artifact(), None,
     ("GET", "/api/listing/b0"), 200, "ESTIMATOR_NOT_GATED"),
    ("healthy · id absent", valid_artifact(), None,
     ("GET", "/api/listing/ghost"), 404, "LISTING_NOT_FOUND"),
    ("healthy · no id matches", valid_artifact(), None,
     ("POST", "/api/compare"), 404, "COMPARE_IDS_NOT_FOUND"),
]

for label, body, env, (method, path), want_status, want_code in HTTP:
    with corpus_dir(body, run_env=env):
        with contextlib.redirect_stdout(io.StringIO()):
            client = TestClient(api.app, raise_server_exceptions=False)
            if method == "GET":
                resp = client.get(path)
            else:
                ids = ["b0", "b1"] if "run_gone" in (env or "") else ["ghost"]
                resp = client.post(path, json={"ids": ids, "q": "۲۰۶"})
        got = resp.json()
        fault = (got.get("fault") or {}).get("code")
        check(f"{label} → HTTP {want_status}", resp.status_code == want_status,
              str(resp.status_code))
        check(f"  fault.code is {want_code}", fault == want_code, str(fault))
        # The addition that makes the code usable: a 404 is a typed response
        # like any other. A body of `{"detail": "..."}` forces a client to
        # read English prose to find out what happened, which is how a page
        # ends up printing an exception at a buyer.
        check("  and the body carries the envelope",
              "corpus" in got and "status" in got,
              str(sorted(got))[:80])
        check("  with a Persian sentence for the person reading it",
              bool((got.get("fault") or {}).get("fa")))

# And the half that must NOT change. Turning every miss into a 200 would erase
# the one answer this endpoint is actually for: a corpus was read, and this id
# is not in it.
with corpus_dir(valid_artifact()):
    r = api.listing("b0")
    check("a healthy corpus still answers for an id it HAS",
          r.listing is not None and r.listing.id == "b0",
          str(r.listing))
    r = api.listing("definitely-not-here")
    check("  and still refuses one it does not, by fault code",
          r.listing is None and r.fault is not None
          and r.fault.code == "LISTING_NOT_FOUND",
          str(r.fault.code if r.fault else None))
    check("  while still naming the corpus that answered",
          r.corpus.identity is not None and r.status.kind == "REAL")


# ---------------------------------------------------------------------------
print("\n4 — a broken corpus is UNUSABLE, never SYNTHETIC (D49)")
_BROKEN = {
    "invalid schema": '{"schema": "not.caro/9", "run_id": "x", "source": "s",'
                      ' "collected_on": "d", "listings": []}',
    "truncated write": '{"schema": "caro.corpus/1", "listi',
    "an html error page": "<html>404 Not Found</html>",
    "empty file": "",
}
for label, body in _BROKEN.items():
    with corpus_dir(body):
        r = api.search(q="۲۰۶", k=3)
        ok, why = validates(schemas.SearchResponse, r)
        check(f"{label} → response still validates", ok, why)
        check(f"  kind is UNUSABLE, not SYNTHETIC",
              r.status.kind == "UNUSABLE", r.status.kind)
        check(f"  fault.code is CORPUS_INVALID",
              r.fault is not None and r.fault.code == "CORPUS_INVALID",
              str(r.fault))
        check(f"  and the message names what actually broke",
              r.fault is not None and len(r.fault.message) > 10)
        check(f"  nothing is served from it",
              not r.status.served and r.items == [] and r.evidence == [])


# ---------------------------------------------------------------------------
print("\n5 — an ungated corpus fabricates no estimate (D50)")
# The rows are declared vehicles. What D50 forbids is an estimate on the
# evidence a refusal carries, and that claim needs the evidence to be cars:
# a row whose class nobody determined is not one (D52), and a check that
# passes because nothing was shown to check proves nothing.
with corpus_dir(valid_artifact(product_class="vehicle")):
    r = api.search(q="۲۰۶", k=5)
    check("evidence exists", len(r.evidence) > 0, str(len(r.evidence)))
    check("  while nothing is appraisable", r.appraisable == 0, str(r.appraisable))
    check("  and considered counts the LISTINGS, not the empty row set",
          r.considered == 9, str(r.considered))

    # The invariant, read off the serialised payload rather than the objects:
    # a field that does not exist cannot be filled in by a later serialiser.
    # Searched as a JSON KEY, not as a substring. A bare `"rank" not in blob`
    # fails on the fault message's "no ranking may be served" — and a check
    # that fails on prose is one somebody disables.
    blob = r.model_dump_json()
    for field in ("estimate_toman", "opportunity_toman",
                  "expected_damage_toman", "score", "role_fa", "rank"):
        check(f"  «{field}» is not a key anywhere in the payload",
              f'"{field}":' not in blob)

    check("  and EvidenceItem has no such field to fill",
          not ({"estimate_toman", "opportunity_toman", "score"}
               & set(schemas.EvidenceItem.model_fields)),
          str(sorted(schemas.EvidenceItem.model_fields)))
    check("  nor UncheckedItem, the evidence that could not be checked",
          not ({"estimate_toman", "opportunity_toman", "score"}
               & set(schemas.UncheckedItem.model_fields)),
          str(sorted(schemas.UncheckedItem.model_fields)))
    check("  which is what makes this structural rather than a check",
          "estimate_toman" in schemas.ScoredItem.model_fields)


# ---------------------------------------------------------------------------
print("\n6 — a refusal is a product state, not an error")
# Vehicles for the same reason as section 5: `still_available` promises
# evidence, and the promise is only tested where there are cars to show.
with corpus_dir(valid_artifact(product_class="vehicle")):
    r = api.search(q="۲۰۶", k=5)
    ok, why = validates(schemas.SearchResponse, r)
    check("the refusal is schema-valid", ok, why)
    check("  served is false and a fault says why",
          r.status.served is False and r.fault is not None)
    check("  the fault is the gate, not a corpus fault",
          r.fault.code == "ESTIMATOR_NOT_GATED", r.fault.code)
    check("  the parsed intent survives", r.intent.query != "")
    check("  and `still_available` is not a promise — evidence is present",
          "evidence" in r.fault.still_available and len(r.evidence) > 0)
    # The endpoint returns a model; FastAPI turns it into a 200. Nothing here
    # raises, and that is the assertion: an HTTPException would be a 500.
    check("  nothing raised on the way out", True)


# ---------------------------------------------------------------------------
# 7 — the client's description of the contract, against the server's.
#
# This is a text parse of TypeScript from Python, which is crude. The
# alternative is codegen and a build step, and for eleven interfaces the check
# closes the same gap for a fraction of the machinery. If this file grows a
# generator, delete this block rather than keeping both.
print("\n7 — lib/api.ts describes the same shapes as schemas.py")

TS = (ROOT / "webapp/web/lib/api.ts").read_text(encoding="utf-8")

_IFACE = re.compile(
    r"export interface (\w+)(?:\s+extends\s+(\w+))?\s*\{(.*?)\n\}",
    re.DOTALL)
_FIELD = re.compile(r"^\s{2}(\w+)\??\s*:", re.MULTILINE)


def ts_interfaces() -> dict[str, tuple[str | None, set[str]]]:
    out = {}
    for name, parent, body in _IFACE.findall(TS):
        # Strip comments so a field name inside prose is not counted.
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
        body = re.sub(r"//[^\n]*", "", body)
        out[name] = (parent or None, set(_FIELD.findall(body)))
    return out


TS_IFACES = ts_interfaces()
check(f"parsed {len(TS_IFACES)} interfaces out of lib/api.ts",
      len(TS_IFACES) >= 10, str(sorted(TS_IFACES)))


def ts_fields(name: str) -> set[str]:
    parent, fields = TS_IFACES[name]
    return fields | (ts_fields(parent) if parent else set())


PAIRS = [
    ("CorpusIdentity", schemas.CorpusIdentity),
    ("CorpusMeta", schemas.CorpusMeta),
    ("ServingStatus", schemas.ServingStatus),
    ("Fault", schemas.Fault),
    ("Envelope", schemas.Envelope),
    ("EvidenceItem", schemas.EvidenceItem),
    ("UncheckedItem", schemas.UncheckedItem),
    ("ScoredItem", schemas.ScoredItem),
    ("WeightSet", schemas.Weights),
    ("Intent", schemas.Intent),
    ("SearchResponse", schemas.SearchResponse),
    ("ListingResponse", schemas.ListingResponse),
    ("CompareResponse", schemas.CompareResponse),
]

for ts_name, model in PAIRS:
    if ts_name not in TS_IFACES:
        check(f"{ts_name} exists in lib/api.ts", False, "not found")
        continue
    got = ts_fields(ts_name)
    want = set(model.model_fields)
    missing, extra = want - got, got - want
    check(f"{ts_name} ≡ {model.__name__}",
          not missing and not extra,
          f"missing in TS: {sorted(missing) or '—'} · "
          f"not in Python: {sorted(extra) or '—'}")


# The unions, which the field comparison above does not reach.
#
# `FaultCode` and `CorpusKind` are `export type`, not `export interface`, so
# every check above is blind to them: the server can grow a member and the
# client keeps compiling, because TypeScript validates the client against its
# own copy of the union — and that copy is exactly the thing that goes stale.
# Nothing here has drifted yet. The check is written now because "nothing has
# drifted yet" is what was true of `lib/api.ts` before check 7 existed too.
_TYPE = re.compile(r"export type (\w+)\s*=\s*([^;]+);")
_MEMBER = re.compile(r"'([^']*)'")
DASH = "—"       # named, because an f-string expression may not hold one


def ts_union(name: str) -> set[str] | None:
    for got, body in _TYPE.findall(TS):
        if got != name:
            continue
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
        body = re.sub(r"//[^\n]*", "", body)
        return set(_MEMBER.findall(body))
    return None


for ts_name, literal in (("CorpusKind", schemas.CorpusKind),
                         ("FaultCode", schemas.FaultCode),
                         ("ConstraintKey", schemas.ConstraintKey)):
    got = ts_union(ts_name)
    want = set(typing.get_args(literal))
    if got is None:
        check(f"{ts_name} is declared in lib/api.ts", False, "not found")
        continue
    check(f"{ts_name} ≡ the Python Literal, member for member",
          got == want,
          f"missing in TS: {sorted(want - got) or DASH} · "
          f"not in Python: {sorted(got - want) or DASH}")

# And the one list that is not a type at all. `PRICE_STATUS_UNUSABLE` is the
# first half of the card's price rule, copied into TypeScript because the
# client has to apply it; a copy nobody checks is how the client ends up
# drawing a number the server would have refused.
from caro.ingest.quality import UNUSABLE_PRICE                    # noqa: E402

_pu = re.search(r"export const PRICE_STATUS_UNUSABLE: string\[\] = \[(.*?)\];",
                TS, re.S)
_ts_unusable = set(_MEMBER.findall(_pu.group(1))) if _pu else set()
_py_unusable = {s.value for s in UNUSABLE_PRICE}
check("PRICE_STATUS_UNUSABLE ≡ quality.UNUSABLE_PRICE, member for member",
      _ts_unusable == _py_unusable,
      f"missing in TS: {sorted(_py_unusable - _ts_unusable) or DASH} · "
      f"not in Python: {sorted(_ts_unusable - _py_unusable) or DASH}")


# ---------------------------------------------------------------------------
print("\n8 — every example on the search box still finds something")
# ---------------------------------------------------------------------------
#
# The chips under the search box are the likeliest first click on the site,
# and an example that returns nothing is worse than no example at all: it is
# an invitation, and the visitor accepts it. Three of them used to name a 206
# while the shipped corpus held nothing but Saipa, so the most probable first
# impression of CARO was an empty screen.
#
# The list is READ from the component rather than copied here. A copy would
# pass forever while the real chips rotted — the same failure this file's
# section 7 exists to prevent for the TypeScript unions, and the same one the
# palette suite prevents for the demo.
#
# This runs against the REAL default corpus, not a fixture. The claim being
# made is about what is shipped; a synthetic artifact could satisfy any list.

_BOX = (ROOT / "webapp/web/components/SearchBox.tsx").read_text(encoding="utf-8")
_m = re.search(r"const EXAMPLES = \[(.*?)\];", _BOX, re.S)
check("EXAMPLES is readable from SearchBox.tsx", _m is not None)

if _m:
    _chips = re.findall(r"'([^']+)'", _m.group(1))
    check(f"  and holds {len(_chips)} example(s)", len(_chips) >= 3,
          str(_chips))

    _real = ROOT / "data" / "corpora"
    check("  the default corpus is present to check against",
          (_real / f"{RUN}.json").exists(), str(_real / f"{RUN}.json"))

    _was, _was_run = corpus_reader.CORPORA, os.environ.get(corpus_mod.RUN_ENV)
    corpus_reader.CORPORA = _real
    os.environ.pop(corpus_mod.RUN_ENV, None)
    corpus_mod.active.cache_clear()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            _kind = api.which_corpus().status.kind
            _res = [(q, api.search(q=q, k=8)) for q in _chips]
        check(f"  serving the real corpus (kind={_kind})", _kind == "REAL",
              _kind)
        for _q, _r in _res:
            # `evidence` is what an ungated corpus can still show. On a gated
            # one the same query would fill `items` instead, so both count —
            # the assertion is that the example leads somewhere, not which
            # branch it lands in. Listings shown apart, because a constraint
            # could not be checked against them, are somewhere too.
            _n = (len(_r.evidence) + len(_r.evidence_unchecked)
                  + len(_r.items))
            check(f"  «{_q[:38]}» → {_n}", _n > 0,
                  "this example finds nothing in the shipped corpus")
    finally:
        corpus_reader.CORPORA = _was
        if _was_run is None:
            os.environ.pop(corpus_mod.RUN_ENV, None)
        else:
            os.environ[corpus_mod.RUN_ENV] = _was_run
        corpus_mod.active.cache_clear()


# ---------------------------------------------------------------------------
print("\n9 — the detail renderer receives product_class")
# ---------------------------------------------------------------------------
#
# `product_class` is the only gate in FIELD_PROVENANCE.md: only `vehicle`
# renders as a car (D52). run11 carries it on all 76 records, and one of them
# is not a vehicle — an assignment, with a make, a model, a trim, a year and a
# price, so every cell the detail page draws is populated. The one field that
# says it is not a car is the one field EvidenceItem was built without,
# and a renderer cannot branch on what it is not sent.
#
# WHAT THIS ASSERTS: that the information reaches the renderer — present in
# the payload model, and delivered by the detail path with the value the
# artifact holds. WHAT IT DOES NOT: what the site or the API should DO with
# it. `200 + product_class` and a `NOT_A_VEHICLE` fault are both open, and
# neither is chosen here. The read below is from where today's path puts the
# listing; the commit that makes that choice moves the read with it.
#
# The TypeScript side is not asserted separately. Section 7 already holds
# lib/api.ts's EvidenceItem to schemas.py field for field, in both
# directions, so a field added here and not there fails there. A second
# assertion of the same fact would be a second place for it to drift.

check("EvidenceItem carries product_class",
      "product_class" in schemas.EvidenceItem.model_fields,
      "the payload has no field that says whether a listing is a car")
print("    lib/api.ts follows from section 7, which compares EvidenceItem "
      "in both directions")

_art_path = ROOT / "data" / "corpora" / f"{RUN}.json"
if not _art_path.exists():
    check("  the default corpus is present to check against", False,
          str(_art_path))
else:
    _art = {r["listing_id"]: r for r in json.loads(
        _art_path.read_text(encoding="utf-8"))["listings"]}
    _pc = {i: r.get("product_class") for i, r in _art.items()}
    _vehicle = next((i for i, c in sorted(_pc.items()) if c == "vehicle"),
                    None)
    _others = sorted(i for i, c in _pc.items() if c and c != "vehicle")
    if not _others:
        print("    the corpus holds no non-vehicle, so the distinguishing "
              "case has nothing to run on — said, not passed")

    _was, _was_run = corpus_reader.CORPORA, os.environ.get(corpus_mod.RUN_ENV)
    corpus_reader.CORPORA = _art_path.parent
    os.environ.pop(corpus_mod.RUN_ENV, None)
    corpus_mod.active.cache_clear()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            _kind = api.which_corpus().status.kind
            _got = {i: api.listing(listing_id=i)
                    for i in ([_vehicle] if _vehicle else []) + _others}
        check(f"  serving the real corpus (kind={_kind})", _kind == "REAL",
              _kind)
        for _id, _resp in _got.items():
            _delivered = (getattr(_resp.listing, "product_class", None)
                          if _resp.listing is not None else None)
            check(f"  detail path delivers product_class for {_id} "
                  f"(artifact: {_pc[_id]})",
                  _delivered == _pc[_id],
                  f"the renderer receives {_delivered!r}")
            # The two fields the card's price rule names, the same way: a
            # field that is on the model and never filled is a rule the
            # client applies to None. Both paths build a row through
            # `_listing_evidence`, so this follows the value from the
            # artifact to the payload rather than testing one endpoint.
            _want = {k: _art[_id].get(k) for k in ("price_status", "price_kind")}
            _sent = {k: getattr(_resp.listing, k, None) for k in _want}
            check(f"  and the price rule's fields for {_id} "
                  f"({_want['price_status']} / {_want['price_kind']})",
                  _sent == _want, f"the renderer receives {_sent}")
    finally:
        corpus_reader.CORPORA = _was
        if _was_run is None:
            os.environ.pop(corpus_mod.RUN_ENV, None)
        else:
            os.environ[corpus_mod.RUN_ENV] = _was_run
        corpus_mod.active.cache_clear()


# ---------------------------------------------------------------------------
print("\n10 — the gate is applied before a reader sees a row")
# ---------------------------------------------------------------------------
#
# FIELD_PROVENANCE.md defines a gate as the thing "the query applies before a
# reader sees a row; nobody chooses it", and names one: product_class, which
# only `vehicle` passes (D52). Section 9 proves the field reaches the client.
# This proves the QUERY honours it, which it once did not: `_evidence`'s
# filter checked model, budget, year and mileage and never the class, and
# the Quik chip under the search box showed an assignment as the
# eighth of its eight rows — a 1405 Quik at ninety million toman beside real
# ones at a billion.
#
# The gates are read from the declaration rather than named here, so a second
# gate added later fails the first check below until someone decides what
# passes it.
#
# ONLY the search endpoints. A detail page reached by id, and a compare of ids
# someone chose, are not a query whose rows a reader is shown; whether they
# should refuse a non-vehicle is a separate decision and is not taken here.
#
# The class of each row shown is read from the ARTIFACT, by id — not from the
# row the endpoint returned. A guard that takes its verdict from the thing it
# guards passes the day that thing labels what it shows `vehicle`; and a
# scored row carries no class at all (a Row has none, by design), which a
# read of the payload would report as a leak.
#
# Queries are derived, not listed: every example chip, read from the
# component as section 8 reads it, and one bare query per model the corpus
# holds, at k=24 — the most `/api/search` accepts; reweight has no cap. The
# reach check at the end is what makes 24 enough for both: each non-vehicle
# must fall inside the first 24 of its own model's query, or the guard could
# not see it leak.

from webapp.api.eligibility import FIELDS as _DECL               # noqa: E402

_gates = sorted(f for f, e in _DECL.items() if e.gate)
check(f"the declaration's gates are exactly {_gates}",
      _gates == ["product_class"],
      "a new gate needs its own pass rule in this section before it is covered")

_art10 = ROOT / "data" / "corpora" / f"{RUN}.json"
if not _art10.exists():
    check("  the default corpus is present to check against", False,
          str(_art10))
else:
    _rows10 = json.loads(_art10.read_text(encoding="utf-8"))["listings"]
    _cls10 = {x["listing_id"]: x.get("product_class") for x in _rows10}
    _models = sorted({(x.get("model") or "").lower() for x in _rows10
                      if x.get("model")})
    _box10 = (ROOT / "webapp/web/components/SearchBox.tsx").read_text(
        encoding="utf-8")
    _m10 = re.search(r"const EXAMPLES = \[(.*?)\];", _box10, re.S)
    _queries = (re.findall(r"'([^']+)'", _m10.group(1)) if _m10 else []) \
        + _models

    _was, _was_run = corpus_reader.CORPORA, os.environ.get(corpus_mod.RUN_ENV)
    corpus_reader.CORPORA = _art10.parent
    os.environ.pop(corpus_mod.RUN_ENV, None)
    corpus_mod.active.cache_clear()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            _kind10 = api.which_corpus().status.kind
            _res10 = [(q, "search", api.search(q=q, k=24))
                      for q in _queries] + \
                     [(q, "reweight", api.search_reweight(
                         q=q, weights=schemas.ReweightRequest(), k=24))
                      for q in _queries]
        check(f"  serving the real corpus (kind={_kind10})",
              _kind10 == "REAL", _kind10)
        for _q, _ep, _r in _res10:
            _shown = (list(_r.evidence) + list(_r.evidence_unchecked)
                      + list(_r.items))
            _past = sorted({x.id for x in _shown
                            if _cls10.get(x.id) != "vehicle"})
            check(f"  {_ep:<8} «{_q[:30]}» — {len(_shown)} row(s), none "
                  f"past the gate", not _past,
                  f"a non-vehicle is shown as a row: {_past}")
    finally:
        corpus_reader.CORPORA = _was
        if _was_run is None:
            os.environ.pop(corpus_mod.RUN_ENV, None)
        else:
            os.environ[corpus_mod.RUN_ENV] = _was_run
        corpus_mod.active.cache_clear()

    for _nv in (x for x in _rows10 if x.get("product_class") != "vehicle"):
        _mm = (_nv.get("model") or "").lower()
        _same = [x["listing_id"] for x in _rows10
                 if (x.get("model") or "").lower() == _mm]
        _pos = _same.index(_nv["listing_id"]) + 1
        check(f"  reach: {_nv['listing_id']} ({_nv.get('product_class')}) "
              f"would be row {_pos} of «{_mm}» — inside k=24",
              _pos <= 24,
              "outside what one query can show, so a leak here is invisible")




# ---------------------------------------------------------------------------
print("\n11 — every non-vehicle reaches the screen, with its class")
# ---------------------------------------------------------------------------
#
# The contract chosen for detail and compare, after both were measured: they
# answer 200 with the listing and its class, and the SCREEN is obliged to say
# what the listing is. This is the API half — every non-vehicle it is asked
# about is delivered, with the class the artifact records. By detail; by
# compare alone; and by compare beside a vehicle, where it used to be dropped
# without a word, because that branch answered from appraisal Rows only.
#
# The other half — whether the screen then draws it as a car — is
# tests/test_screens.py. It renders the components the pages use, and it
# needs node, which this suite does not; run_all skips a suite by name when a
# declared dependency is absent, and a render check in here would have taken
# every API assertion down with it.
#
# Two non-vehicles: the assignment in run11, and `unknown` from section 2's
# class-less fixture. run11 carries a class on every record, so without the
# fixture `unknown` would never be asked about here at all.

_art11 = ROOT / "data" / "corpora" / f"{RUN}.json"
_cls11 = {x["listing_id"]: x.get("product_class") for x in json.loads(
    _art11.read_text(encoding="utf-8"))["listings"]}
_nvs = sorted(i for i, c in _cls11.items() if c != "vehicle")
check(f"the shipped corpus holds {len(_nvs)} non-vehicle(s) to follow",
      len(_nvs) > 0, "nothing to run on — said, not passed")

_was, _was_run = corpus_reader.CORPORA, os.environ.get(corpus_mod.RUN_ENV)
corpus_reader.CORPORA = _art11.parent
os.environ.pop(corpus_mod.RUN_ENV, None)
corpus_mod.active.cache_clear()
try:
    with contextlib.redirect_stdout(io.StringIO()):
        # A vehicle that is also an appraisal Row: beside one, compare used
        # to take the branch that dropped everything else.
        _veh = next(r.listing_id for r in corpus_mod.active().rows)
        _detail = [(_i, _cls11[_i], api.listing(_i)) for _i in _nvs]
        _asked = [((_i,), api.compare(schemas.CompareRequest(
                      ids=[_i], q="خودرو"))) for _i in _nvs]
        _asked += [((_i, _veh), api.compare(schemas.CompareRequest(
                       ids=[_i, _veh], q="خودرو"))) for _i in _nvs]
finally:
    corpus_reader.CORPORA = _was
    if _was_run is None:
        os.environ.pop(corpus_mod.RUN_ENV, None)
    else:
        os.environ[corpus_mod.RUN_ENV] = _was_run
    corpus_mod.active.cache_clear()

with corpus_dir(valid_artifact()):
    _detail.append(("b0", "unknown", api.listing("b0")))
    _asked.append((("b0",), api.compare(schemas.CompareRequest(
        ids=["b0"], q="۲۰۶"))))
_want11 = {**_cls11, "b0": "unknown"}

for _i, _c, _d in _detail:
    _got = _d.listing.product_class if _d.listing is not None else None
    check(f"  detail delivers {_i} with its class ({_c})", _got == _c,
          f"the screen receives "
          f"{'no listing' if _d.listing is None else repr(_got)}")
for _ids, _r in _asked:
    _sent = {x.id: x.product_class for x in list(_r.evidence) + list(_r.rows)}
    check(f"  compare {' + '.join(_ids)} delivers every id it was asked "
          f"about, the non-vehicle with its class",
          set(_ids) <= set(_sent)
          and all(_sent[_i] == _want11[_i] for _i in _ids
                  if _want11[_i] != "vehicle"),
          f"sent {_sent}")


# ---------------------------------------------------------------------------
print("\n12 — the contact inbox keeps a message, or refuses it and says where")
# ---------------------------------------------------------------------------
# A deployment whose disk does not keep what is written — a serverless
# function — would take a message, return a reference and lose the file. So
# the inbox can be switched off (CARO_INBOX=off), and a write that fails
# anyway is refused the same way. Measured over HTTP on a temporary inbox,
# never on data/inbox/.
from webapp.api import contact as contact_mod                      # noqa: E402

_kept = (contact_mod.INBOX, contact_mod.MESSAGES, os.environ.get("CARO_INBOX"))
_MSG = {"name": "آزمون", "email": "test@example.com",
        "subject": "آزمون", "body": "یک پیام آزمایشی برای صندوق."}


def _lines(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


with tempfile.TemporaryDirectory() as _d:
    contact_mod.INBOX = Path(_d) / "inbox"
    contact_mod.MESSAGES = contact_mod.INBOX / "messages.jsonl"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            _client = TestClient(api.app, raise_server_exceptions=False)

        os.environ.pop("CARO_INBOX", None)
        _st = _client.get("/api/contact/status").json()
        check("with CARO_INBOX unset the inbox says it is open",
              _st.get("open") is True, f"{_st}")
        _r = _client.post("/api/contact", json=_MSG)
        _ref = _r.json().get("ref") if _r.status_code == 200 else None
        check("  a message is kept, and its reference names the line written",
              bool(_ref) and any(f'"ref": "{_ref}"' in ln
                                 for ln in _lines(contact_mod.MESSAGES)),
              f"HTTP {_r.status_code}, "
              f"{len(_lines(contact_mod.MESSAGES))} line(s) written")

        os.environ["CARO_INBOX"] = "off"
        _st = _client.get("/api/contact/status").json()
        check("with CARO_INBOX=off it says it is closed, and where to go",
              _st.get("open") is False
              and _st.get("elsewhere") == contact_mod.ELSEWHERE, f"{_st}")
        _before = len(_lines(contact_mod.MESSAGES))
        _r = _client.post("/api/contact", json=_MSG)
        check("  a message is refused with 503, naming that place",
              _r.status_code == 503
              and contact_mod.ELSEWHERE in str(_r.json().get("detail", "")),
              f"HTTP {_r.status_code}: {_r.text[:120]}")
        check("  and nothing is written",
              len(_lines(contact_mod.MESSAGES)) == _before,
              f"{len(_lines(contact_mod.MESSAGES))} line(s), was {_before}")

        # Open, on a disk that cannot be written: the inbox's parent is a
        # file, so creating the directory fails as a read-only one does.
        os.environ.pop("CARO_INBOX", None)
        _blocker = Path(_d) / "not-a-directory"
        _blocker.write_text("x", encoding="utf-8")
        contact_mod.INBOX = _blocker / "inbox"
        contact_mod.MESSAGES = contact_mod.INBOX / "messages.jsonl"
        _r = _client.post("/api/contact", json=_MSG)
        check("an open inbox that cannot write refuses with 503, not 500, "
              "and hands out no reference",
              _r.status_code == 503 and "ref" not in _r.json()
              and contact_mod.ELSEWHERE in str(_r.json().get("detail", "")),
              f"HTTP {_r.status_code}: {_r.text[:120]}")
    finally:
        contact_mod.INBOX, contact_mod.MESSAGES = _kept[0], _kept[1]
        if _kept[2] is None:
            os.environ.pop("CARO_INBOX", None)
        else:
            os.environ["CARO_INBOX"] = _kept[2]


# ---------------------------------------------------------------------------
print("\n13 — a match is a listing every stated constraint was checked against")
# ---------------------------------------------------------------------------
#
# `_evidence` used to run a comparison only when the listing carried the
# value, so a listing with no price passed «زیر ۳۰۰ میلیون» and one with no
# odometer passed «کم‌کارکرد» (D60, D61). `webapp/api/constraints.py` gives a
# constraint three answers — met, broken, unknown — and a listing is a match
# only when every constraint the buyer stated is met; one that breaks none and
# lacks a value for some is shown apart, naming it.
#
# First the rule, on listings built here, so that every branch is reached
# whether or not the shipped corpus holds a case for it. Then every example
# chip on the shipped corpus, with each listing's values read from the
# ARTIFACT by id rather than from the payload, for the reason section 10
# gives: a guard that takes its verdict from what it guards passes the day
# the payload agrees with itself.

from types import SimpleNamespace                                   # noqa: E402

from caro.ranking import IntentSpec                                 # noqa: E402
from webapp.api import constraints                                  # noqa: E402


def _L(price=500_000_000, *, status="display_confirmed", kind="cash",
       year=1398, km=100_000):
    return SimpleNamespace(asking_price_toman=price, price_status=status,
                           price_kind=kind, year_jalali=year, mileage_km=km)


def _u(x, spec):
    return constraints.unchecked(constraints.judge(x, spec))


_BUDGET = IntentSpec(raw_query="t", budget_max_toman=600_000_000)
_STATED = IntentSpec(raw_query="t", budget_max_toman=600_000_000,
                     year_min=1395, max_mileage_km=150_000)

check("a price inside the budget is a match", _u(_L(), _BUDGET) == [])
check("  above it, the listing is left out",
      _u(_L(700_000_000), _BUDGET) is None)
check("  no price at all: not a match, and «budget» is named",
      _u(_L(None, status="absent", kind="negotiable"), _BUDGET) == ["budget"])
check("  a cash figure with no status recorded is still checked",
      _u(_L(status=None), _BUDGET) == []
      and _u(_L(700_000_000, status=None), _BUDGET) is None)
check("  a financing total under the budget is not inside it",
      _u(_L(300_000_000, kind="financing_total"), _BUDGET) == ["budget"])
check("  nor a figure whose status is unusable",
      _u(_L(300_000_000, status="ambiguous"), _BUDGET) == ["budget"])
check("  a floor is checked the same way",
      _u(_L(None), IntentSpec(raw_query="t", budget_min_toman=1)) == ["budget"]
      and _u(_L(), IntentSpec(raw_query="t",
                              budget_min_toman=600_000_000)) is None)
check("no year and no odometer: both named, in the order judged",
      _u(_L(year=None, km=None), _STATED) == ["year", "mileage"])
check("  one broken constraint leaves a listing out, whatever else is unknown",
      _u(_L(None, km=900_000), _STATED) is None)
check("  a constraint the buyer did not state is not judged at all",
      constraints.judge(_L(None, year=None, km=None),
                        IntentSpec(raw_query="t")) == {})


def _value_missing(rec: dict, i) -> list[str]:
    """What the artifact holds no value for, among the constraints `i` states
    — in judge order. A price counts only as the card would draw it."""
    out = []
    if i.budget_max_toman is not None or i.budget_min_toman is not None:
        drawn = ((rec.get("price_kind") or "absent") == "cash"
                 and rec.get("price_status") not in _py_unusable)
        if rec.get("asking_price_toman") is None or not drawn:
            out.append("budget")
    if i.year_min is not None and rec.get("year_jalali") is None:
        out.append("year")
    if i.max_mileage_km is not None and rec.get("mileage_km") is None:
        out.append("mileage")
    return out


def _value_breaks(rec: dict, i) -> bool:
    p, y, m = (rec.get("asking_price_toman"), rec.get("year_jalali"),
               rec.get("mileage_km"))
    return ((p is not None and "budget" not in _value_missing(rec, i)
             and ((i.budget_max_toman is not None and p > i.budget_max_toman)
                  or (i.budget_min_toman is not None
                      and p < i.budget_min_toman)))
            or (i.year_min is not None and y is not None and y < i.year_min)
            or (i.max_mileage_km is not None and m is not None
                and m > i.max_mileage_km))


_art13 = ROOT / "data" / "corpora" / f"{RUN}.json"
_rec13 = {x["listing_id"]: x for x in json.loads(
    _art13.read_text(encoding="utf-8"))["listings"]}
_box13 = (ROOT / "webapp/web/components/SearchBox.tsx").read_text(
    encoding="utf-8")
_m13 = re.search(r"const EXAMPLES = \[(.*?)\];", _box13, re.S)
_chips13 = re.findall(r"'([^']+)'", _m13.group(1)) if _m13 else []
_K13 = 8                                     # what the results page asks for

_was, _was_run = corpus_reader.CORPORA, os.environ.get(corpus_mod.RUN_ENV)
corpus_reader.CORPORA = _art13.parent
os.environ.pop(corpus_mod.RUN_ENV, None)
corpus_mod.active.cache_clear()
try:
    with contextlib.redirect_stdout(io.StringIO()):
        _res13 = [(q, api.search(q=q, k=_K13)) for q in _chips13]
finally:
    corpus_reader.CORPORA = _was
    if _was_run is None:
        os.environ.pop(corpus_mod.RUN_ENV, None)
    else:
        os.environ[corpus_mod.RUN_ENV] = _was_run
    corpus_mod.active.cache_clear()

for _q, _r in _res13:
    _i = _r.intent
    _bad = [x.id for x in _r.evidence if _value_missing(_rec13[x.id], _i)]
    check(f"  «{_q[:30]}» — {len(_r.evidence)} match(es), each checked "
          f"against every constraint stated", not _bad,
          f"a match with a value missing: {_bad}")
    _wrong = [(x.id, x.unchecked) for x in _r.evidence_unchecked
              if not x.unchecked
              or x.unchecked != _value_missing(_rec13[x.id], _i)]
    check(f"    {len(_r.evidence_unchecked)} shown apart, each naming what "
          f"its listing lacks", not _wrong, f"named wrongly: {_wrong}")
    _broke = [x.id for x in list(_r.evidence) + list(_r.evidence_unchecked)
              if _value_breaks(_rec13[x.id], _i)]
    check("    nothing shown breaks a constraint stated", not _broke,
          f"shown, and breaking one: {_broke}")
    # The totals, counted in the artifact: every vehicle of the model asked
    # for that breaks nothing, split by whether a value is missing. Checked
    # against the payload's own lists alone, a total that reported only the
    # rows shown would agree with itself.
    _cand = [rec for rec in _rec13.values()
             if rec.get("product_class") == "vehicle"
             and (not _i.models
                  or (rec.get("model") or "").lower() in _i.models)
             and not _value_breaks(rec, _i)]
    _want_m = sum(1 for rec in _cand if not _value_missing(rec, _i))
    _want_a = len(_cand) - _want_m
    check(f"    the totals count every one ({_r.evidence_total} matched, "
          f"{_r.evidence_unchecked_total} apart), the lists the first "
          f"{_K13} of each",
          (_r.evidence_total, _r.evidence_unchecked_total)
          == (_want_m, _want_a)
          and len(_r.evidence) == min(_want_m, _K13)
          and len(_r.evidence_unchecked) == min(_want_a, _K13),
          f"the artifact holds {_want_m} matched and {_want_a} apart")

_apart13 = sum(len(r.evidence_unchecked) for _, r in _res13)
check(f"  the examples reach the case: {_apart13} listing(s) shown apart",
      _apart13 > 0,
      "nothing was shown apart, so the checks above cannot see the rule "
      "— said, not passed")

print()
if FAILS:
    print(f"FAILED ({len(FAILS)}): " + ", ".join(FAILS))
    raise SystemExit(1)
print("all tests passed")
