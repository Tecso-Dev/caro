"""The SYNTHETIC corpus: generated, with the truth known.

The site serves it when there is no real corpus on disk and none was named
(`webapp/api/corpus.py`), and the ranking suite measures ranking on it. It is
built here, in the package, because both need it and only one of them is a
test. The site used to get it by importing `tests/test_ranking.py`, which ran
every check in that file on the way and ended in `SystemExit` when one was
red: under uvicorn, every request that needed a corpus then answered a bare
500, including the two UNUSABLE states whose whole job is to say what went
wrong (measured on 2026-10-06). Of that file the site used three values, all
built by its first hundred lines; nothing after them changed any of the
three, and none of its code ran at request time. Those lines are this module.

A corpus where the thesis is TRUE by construction: some cars are cheap
because they are damaged. If ranking cannot separate "cheap and sound" from
"cheap and wrecked", it deserves to lose.

Every random draw comes from one generator seeded with `SEED`, in one order,
so every process builds the same corpus: the same rows, the same split, the
same estimator and the same verdict from the acceptance gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from caro.appraisal import (
    ComparableQuantiles, GlobalQuantiles, LogLinearQuantiles, MarketEstimator,
    Row, cluster_temporal_split, run_benchmark,
)
from caro.ranking import RankingPipeline, Ranker, RuleIntentParser

SEED = 11

MODELS = {"pride": 20.4, "206": 21.0, "tiba": 20.6, "pars": 21.2,
          "207": 21.35, "quik": 20.75}
SIGMA = 0.16


def true_mu(m, year, km):
    return MODELS[m] + 0.06 * (year - 1395) - 0.0000012 * km


def make_corpus(n: int = 1800, rng=None) -> list[Row]:
    """`n` listings, drawn from `rng` — a fresh generator seeded with `SEED`
    when none is given, so the corpus never depends on what drew before it."""
    if rng is None:
        rng = np.random.default_rng(SEED)
    rows = []
    for i in range(n):
        m = list(MODELS)[i % len(MODELS)]
        year = int(rng.integers(1392, 1403))
        km = float(rng.integers(15_000, 280_000))
        clean = float(np.exp(rng.normal(true_mu(m, year, km), SIGMA)))

        # 30% of cars carry damage. A damaged car is discounted in the ASKING
        # price by less than the damage actually costs the buyer — which is
        # exactly why the cheapest listing is usually the worst buy.
        risk = float(rng.beta(1.4, 6.0))
        damaged = risk > 0.25
        asking = clean * (1 - 0.55 * risk) if damaged else clean * float(
            rng.normal(1.0, 0.03))

        rows.append(Row(
            listing_id=f"l{i}", cluster_id=f"c{i}",
            first_seen_ordinal=int(rng.integers(0, 100)),
            model_key=m, year_jalali=year, mileage_km=km,
            asking_price_toman=float(asking),
            features={
                "risk": risk,
                "ownership_risk": float(rng.beta(2, 5)),
                "liquidity": 0.8 if m in ("pride", "206") else 0.4,
                "has_accident": 1.0 if risk > 0.45 else 0.0,
                "_clean_value": clean,
            }))
    return rows


def true_utility(r: Row) -> float:
    """What the buyer actually gains: the car's real worth, minus what they
    pay, minus what the damage will cost them. The ranker never sees this."""
    clean = r.features["_clean_value"]
    damage_cost = clean * 0.85 * r.features["risk"]
    return clean - r.asking_price_toman - damage_cost


@dataclass(frozen=True)
class Synthetic:
    """The corpus and what was built on it."""

    rows: list                  # every generated listing
    split: object               # caro.appraisal.Split — train and test
    baselines: dict             # the two estimators the candidate must beat
    estimator: MarketEstimator  # benchmarked against them
    ok: bool                    # the acceptance gate's verdict
    why: list                   # and, when it is False, its reasons
    pipeline: RankingPipeline   # parses and ranks with that estimator
    pool: list                  # the test half: what is searched and ranked


@lru_cache(maxsize=1)
def build() -> Synthetic:
    """The corpus, its split, the two baselines, the estimator benchmarked
    against them with the gate's verdict, and the pipeline that ranks with
    it. Built once per process."""
    rows = make_corpus()
    split = cluster_temporal_split(rows, test_fraction=0.30)
    baselines = {
        "global-quantiles": run_benchmark(GlobalQuantiles(), split,
                                          name="global-quantiles"),
        "comparable-quantiles": run_benchmark(ComparableQuantiles(), split,
                                              name="comparable-quantiles"),
    }
    estimator = MarketEstimator(LogLinearQuantiles())
    ok, why = estimator.benchmark(split, baselines, name="log-linear-ridge")
    return Synthetic(
        rows=rows, split=split, baselines=baselines, estimator=estimator,
        ok=ok, why=why,
        pipeline=RankingPipeline(RuleIntentParser(), Ranker(estimator)),
        pool=split.test)
