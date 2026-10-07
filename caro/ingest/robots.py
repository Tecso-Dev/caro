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

And the gate
------------
`RobotsGate` fetches one origin's robots.txt the first time it is asked,
judges it once, keeps the judgement and a record of what was read, and is
asked before every request to that origin. An adapter owns one gate, and an
execution — one process: a collection run, a round of date_watch, a probe —
builds one adapter, so robots.txt is read once per execution and kept in
memory only. RFC 9309 §2.4 allows a cached copy for a day; a run takes
minutes, and nothing is carried from one run to the next.

What a fetch that did not return a policy means (§2.3.1):

    2xx                      the rules it states; an empty file states none
    2xx that is markup, or   deny_all. A page served where robots.txt
      not UTF-8              should be — a challenge, an application shell
                             — is not a policy, and reading it as an empty
                             one would allow everything. The RFC would parse
                             it; this does not, on purpose.
    429                      deny_all: the source asked us to slow down
    any other 4xx            allow_all: robots.txt is unavailable (§2.3.1.3)
    5xx, no response, a      deny_all: unreachable (§2.3.1.4)
      fetcher that raises,
      no fetcher at all,
      any other status
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Callable, NamedTuple
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


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

class RobotsViolation(RuntimeError):
    """Raised before a request robots.txt does not allow.

    `everything` is set when no request at all may be made, because
    robots.txt could not be read as a policy — as opposed to this one url
    being disallowed. A caller may skip a refused url and go on; nothing
    goes on past `everything`.
    """

    def __init__(self, message: str, *, everything: bool = False):
        super().__init__(message)
        self.everything = everything


RULES, ALLOW_ALL, DENY_ALL = "rules", "allow_all", "deny_all"

_MARKUP = re.compile(r"<html|<!doctype", re.I)


def _judge(status: int | None, body: str) -> tuple[str, str]:
    if not status:
        return DENY_ALL, ("no response: unreachable, so nothing may be "
                          "requested (RFC 9309 §2.3.1.4)")
    if 200 <= status < 300:
        if (body.lstrip("\ufeff \t\r\n").startswith("<")
                or _MARKUP.search(body[:1024])):
            return DENY_ALL, (f"http {status}, but the body is a page, not a "
                              "robots.txt")
        if "\ufffd" in body:
            return DENY_ALL, f"http {status}, but the body is not UTF-8"
        return RULES, f"http {status}: read"
    if status == 429:
        return DENY_ALL, "http 429: asked to slow down, read as unreachable"
    if 400 <= status < 500:
        return ALLOW_ALL, (f"http {status}: unavailable, so no rule applies "
                           "(RFC 9309 §2.3.1.3)")
    if 500 <= status < 600:
        return DENY_ALL, (f"http {status}: unreachable, so nothing may be "
                          "requested (RFC 9309 §2.3.1.4)")
    return DENY_ALL, f"http {status}: not a status this reads"


def _origin(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}".lower()


class RobotsGate:
    """One origin's robots.txt: fetched once, judged, recorded, and asked
    before every request to that origin."""

    def __init__(self, origin: str,
                 fetch: Callable[[str], tuple[int, str]] | None, *,
                 source: str, token: str = PRODUCT_TOKEN,
                 pause: Callable[[], None] | None = None):
        self.origin = _origin(origin)
        self.url = self.origin + "/robots.txt"
        self.source = source
        self.token = token
        self._fetch = fetch
        self._pause = pause
        self._rules: list[Rule] = []
        self.record: dict | None = None     # what was read, once read
        self.text: str | None = None        # the body, when it was a 2xx

    def ensure(self) -> dict:
        """Read robots.txt if it has not been read. Returns the record."""
        if self.record is not None:
            return self.record
        at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        status, body = None, ""
        if self._fetch is None:
            verdict, why = DENY_ALL, ("no robots fetcher was given: nothing "
                                      "was asked, so nothing is allowed")
        else:
            try:
                status, body = self._fetch(self.url)
            except Exception:
                status, body = 0, ""
            body = body if isinstance(body, str) else ""
            verdict, why = _judge(status, body)
        group = n = None
        if verdict == RULES:
            self._rules, group = rules_for(body, self.token)
            n = len(self._rules)
        raw = body.encode("utf-8") if status and 200 <= status < 300 else None
        self.text = body if raw is not None else None
        self.record = {
            "source": self.source, "url": self.url, "token": self.token,
            "fetched_at": at, "http_status": status,
            "bytes": None if raw is None else len(raw),
            "sha256": None if raw is None else hashlib.sha256(raw).hexdigest(),
            "verdict": verdict, "group": group, "rules": n, "why": why,
        }
        # A request like any other, so the same pause follows it.
        if self._fetch is not None and self._pause is not None:
            self._pause()
        return self.record

    def allows(self, url: str) -> bool:
        """The gate's answer for `url`, without raising."""
        if _origin(url) != self.origin:
            return False
        verdict = self.ensure()["verdict"]
        if verdict == DENY_ALL:
            return False
        return verdict == ALLOW_ALL or allowed(self._rules, url)

    def check(self, url: str) -> None:
        """Raise RobotsViolation unless `url` may be requested."""
        if _origin(url) != self.origin:
            raise RobotsViolation(
                f"{url} is not on {self.origin}, the one origin whose "
                "robots.txt this gate reads")
        rec = self.ensure()
        if rec["verdict"] == DENY_ALL:
            raise RobotsViolation(
                f"{self.source}: robots.txt at {self.url} gave no policy "
                f"({rec['why']}); nothing is requested", everything=True)
        if rec["verdict"] == RULES and not allowed(self._rules, url):
            raise RobotsViolation(
                f"{self.source} robots.txt disallows {_target(url)} for "
                f"{self.token}: {url}")


def describe(record: dict | None) -> str:
    """The record on one line: which file, when, which bytes, what it means."""
    if not record:
        return "robots.txt not read"
    s = (f"{record['url']}  {record['fetched_at']}  "
         f"http {record['http_status']}")
    if record["sha256"]:
        s += f"  {record['bytes']} bytes  sha256 {record['sha256']}"
    if record["verdict"] == RULES:
        return s + (f"  -> {record['rules']} rule(s) from group "
                    f"{record['group'] or 'none'}")
    return s + f"  -> {record['verdict']}: {record['why']}"
