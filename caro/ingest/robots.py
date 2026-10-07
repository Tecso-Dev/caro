"""
robots.txt, read by RFC 9309 — with a matcher of our own.

Why not the standard library
----------------------------
`urllib.robotparser` compares a rule's path as a literal prefix. Divar's
rules are wildcards — `Disallow: /s/*/*?*q=*`, `Disallow: /my-divar/*` —
and given those rules as transcribed on 2026-09-07, on Python 3.11, offline,
it allowed three of the four urls they disallow (`/s/tehran/light?q=206`,
`?page=2&q=pride`, `/my-divar/bookmarks`) and refused only `/new`. A reader
of robots.txt that errs toward permission hands out permission nobody gave,
and it is worse than none: it makes the guard look present.

What is implemented, and nothing more
-------------------------------------
RFC 9309 §2.2, the part a crawler needs to decide one url:

    groups      found by product token, case-insensitively; several groups
                naming the token are combined; `*` applies only when none
                names it; neither, and no rule applies. Rules before the
                first user-agent line belong to no group and are ignored.
    rules       an empty pattern is no rule. A pattern matches from the
                first octet of the path, query included; `*` is any run of
                characters and a final `$` is the end of the url.
    precedence  the longest matching pattern decides, an allow wins a tie,
                no match is allowed, and /robots.txt is always allowed.
    encoding    octets outside ASCII are percent-encoded as UTF-8 on both
                sides, escapes of unreserved characters are decoded, and a
                literal `*` or `$` in a url is encoded, so only a pattern's
                own `%2A` or `%24` matches one (§2.2.2, §2.2.3).

Fetching robots.txt, and what a failed fetch means, is not this part.
"""

from __future__ import annotations

import re
from typing import NamedTuple
from urllib.parse import quote, urlsplit

# The product token robots.txt groups are matched against. RFC 9309 §2.2.1
# wants it to be a substring of the User-Agent the crawler sends, and it is:
# divar_car.USER_AGENT begins with it, and a test holds the two together.
PRODUCT_TOKEN = "CARO-research"

_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                        "abcdefghijklmnopqrstuvwxyz0123456789-._~")
# Printable ASCII stays as written, `%` included so an escape is not escaped
# twice; everything else is percent-encoded.
_PRINTABLE = "".join(chr(c) for c in range(0x21, 0x7F))
_ESCAPE = re.compile(r"%([0-9A-Fa-f]{2})")
_TOKEN = re.compile(r"[A-Za-z_-]+")


def _canonical(s: str) -> str:
    """One spelling for one path, so a url and a pattern can be compared."""
    def one(m: re.Match) -> str:
        ch = chr(int(m.group(1), 16))
        return ch if ch in _UNRESERVED else "%" + m.group(1).upper()
    return _ESCAPE.sub(one, quote(s, safe=_PRINTABLE))


class Rule(NamedTuple):
    allow: bool
    path: str               # canonical; its length is the rule's specificity
    regex: re.Pattern


def _rule(allow: bool, pattern: str) -> Rule:
    p = _canonical(pattern)
    anchored = p.endswith("$")
    # A `$` anywhere but the end is a character, and a url's `$` is encoded,
    # so the pattern's is too.
    body = (p[:-1] if anchored else p).replace("$", "%24")
    rx = ".*".join(re.escape(piece) for piece in body.split("*"))
    return Rule(allow, p, re.compile(rx + (r"\Z" if anchored else ""), re.S))


def _agent(value: str) -> str:
    """The token a user-agent line names: `*`, or its leading letters, `_`
    and `-` — so `CARO-research/0.3` names `caro-research`. Lower-cased."""
    v = value.strip()
    if v.startswith("*"):
        return "*"
    m = _TOKEN.match(v)
    return m.group(0).lower() if m else ""


def parse(text: str) -> list[tuple[list[str], list[Rule]]]:
    """Every group in file order: the tokens it names, and its rules."""
    groups: list[tuple[list[str], list[Rule]]] = []
    naming = False          # inside a run of user-agent lines
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if not naming:
                groups.append(([], []))
                naming = True
            groups[-1][0].append(_agent(value))
        elif key in ("allow", "disallow"):
            naming = False
            if groups and value:
                groups[-1][1].append(_rule(key == "allow", value))
        # Any other record — Sitemap, Crawl-delay — is not a rule here.
    return groups


def rules_for(text: str,
              token: str = PRODUCT_TOKEN) -> tuple[list[Rule], str | None]:
    """The rules that apply to `token`, and the group they came from."""
    groups = parse(text)
    for want, name in ((token.lower(), token), ("*", "*")):
        hit = [rules for agents, rules in groups if want in agents]
        if hit:
            return [r for rules in hit for r in rules], name
    return [], None


def _target(url: str) -> str:
    parts = urlsplit(url)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return _canonical(path).replace("*", "%2A").replace("$", "%24")


def allowed(rules: list[Rule], url: str) -> bool:
    """Whether `rules` let `url` be requested."""
    if urlsplit(url).path == "/robots.txt":
        return True
    target = _target(url)
    best: Rule | None = None
    for r in rules:
        if not r.regex.match(target):
            continue
        if (best is None or len(r.path) > len(best.path)
                or (len(r.path) == len(best.path) and r.allow)):
            best = r
    return best is None or best.allow
