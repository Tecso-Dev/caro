"""What one listing says to each constraint the buyer stated.

On a corpus no estimator has cleared, search answers from the listings
directly (`_evidence` in main.py), and until this module its filter ran a
comparison only when the listing carried the value: a listing with no price
passed «زیر ۳۰۰ میلیون», and one with no odometer passed «کم‌کارکرد». D60 and
D61 recorded it as the buyer's constraints failing open where the gate fails
closed. Measured on run11 with the five examples under the search box, at the
k=8 the results page asks for: of the 36 rows drawn as «آگهی‌های منطبق», 3
were there only because a value was missing — two of the four rows answering
«پراید زیر ۳۰۰ میلیون», both listings whose price is «توافقی».

So a constraint has three answers for a listing, not two:

    met       the listing carries the value, and the value satisfies it
    broken    the listing carries the value, and it does not
    unknown   the listing carries no value to check it against

A listing is a match only when every constraint the buyer stated is met. One
that breaks any is left out. One that breaks none and cannot be checked
against some is neither: it is shown apart, with what could not be checked
named, and never under a heading that calls it a match.
"""

from __future__ import annotations

from typing import Literal

from caro.ingest.quality import UNUSABLE_PRICE

Verdict = Literal["met", "broken", "unknown"]

_UNUSABLE = frozenset(s.value for s in UNUSABLE_PRICE)


def asking_price(x) -> int | None:
    """The amount the site shows as this listing's asking price, or None.

    The rule is `askingPrice()` in webapp/web/lib/format.ts, which is the rule
    FIELD_PROVENANCE.md states for a price on a card: a figure whose kind is
    not `cash`, or whose status is unusable, is not an asking price, and the
    card says what it is instead of drawing it. A budget is checked against
    the same figure the card draws, so a financing total — which reads like a
    bargain beside real prices — is unknown to the budget, not inside it. On
    run11 no listing carries such a figure: its two non-cash prices carry no
    amount at all. The rule is here so that the next corpus is held to it
    too.

    Both fields null is the appraisal-row case the card also allows: a row
    that was scored passed both checks in eligibility before it got here.
    """
    status = getattr(x, "price_status", None)
    kind = getattr(x, "price_kind", None)
    if kind is not None and kind != "cash":
        return None
    if status is not None and status in _UNUSABLE:
        return None
    return x.asking_price_toman


def judge(x, spec) -> dict[str, Verdict]:
    """Each constraint the buyer stated, and what this listing says to it.

    Keyed by the names the payload carries in `UncheckedItem.unchecked`. A
    constraint the buyer did not state is absent, not `met`: there is nothing
    to report about it.
    """
    out: dict[str, Verdict] = {}

    if spec.budget_max_toman is not None or spec.budget_min_toman is not None:
        p = asking_price(x)
        if p is None:
            out["budget"] = "unknown"
        elif ((spec.budget_max_toman is not None and p > spec.budget_max_toman)
              or (spec.budget_min_toman is not None
                  and p < spec.budget_min_toman)):
            out["budget"] = "broken"
        else:
            out["budget"] = "met"

    if spec.year_min is not None:
        y = x.year_jalali
        out["year"] = ("unknown" if y is None
                       else "broken" if y < spec.year_min else "met")

    if spec.max_mileage_km is not None:
        m = x.mileage_km
        out["mileage"] = ("unknown" if m is None
                          else "broken" if m > spec.max_mileage_km else "met")

    return out


def unchecked(verdicts: dict[str, Verdict]) -> list[str] | None:
    """None if any constraint is broken; otherwise what could not be checked,
    in the order the constraints were judged — empty for a match."""
    if "broken" in verdicts.values():
        return None
    return [k for k, v in verdicts.items() if v == "unknown"]
