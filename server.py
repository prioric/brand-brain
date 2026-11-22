"""Brand BrAIn, an MCP server for one brand.

It reads one brand folder (brand.json, and brand_strategy.json when the folder has one) and answers
five questions from an AI tool: what the brand strategy says, which rules apply, which approved file
or value to use, which claims are approved, and whether a draft passes. It writes every call to
log/calls.jsonl itself. The environment variable BRAND_BRAIN_LOG_DIR moves the log to another folder.

Run over stdio, for an AI tool on the same computer:  python server.py my_brand
Run as a web address for an AI workspace:             python server.py my_brand --http
The brand folder is a folder name beside server.py or an absolute path:  python server.py /srv/brands/my_brand
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from collections import Counter
from pathlib import Path

from mcp.server.mcpserver import MCPServer

HERE = Path(__file__).resolve().parent
# The brand folder is a name beside this file or an absolute path.
_ARG = Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "brand_template")
BRAND_DIR = (_ARG if _ARG.is_absolute() else HERE / _ARG).resolve()
BRAND = json.loads((BRAND_DIR / "brand.json").read_text(encoding="utf-8"))
STRATEGY_FILE = BRAND_DIR / "brand_strategy.json"
# The log sits in the brand folder unless BRAND_BRAIN_LOG_DIR names another folder.
LOG_DIR = Path(os.environ["BRAND_BRAIN_LOG_DIR"]) if os.environ.get("BRAND_BRAIN_LOG_DIR") else BRAND_DIR / "log"
NAME = BRAND["brand"]
VERSION = BRAND["rules_version"]

# Roots name folders outside the brand folder, such as a checker's home. Each is resolved from the
# brand folder. A missing root makes every checker that names it answer "checker not available".
ROOTS = {k: (BRAND_DIR / v).resolve() for k, v in BRAND.get("roots", {}).items()}
MISSING_ROOTS = sorted(k for k, v in ROOTS.items() if not v.exists())

# Words that mark a sentence as a product claim, from brand.json "claim_words". A claim sentence must
# match an approved claim. A brand with no claim_words gets no claim test.
CLAIM_WORDS = re.compile(BRAND["claim_words"], re.IGNORECASE) if BRAND.get("claim_words") else None
URL = re.compile(r"https?://\S+|\b[\w.-]+\.(?:com|org|net|io|dev)\b\S*", re.IGNORECASE)
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\b|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
                    re.IGNORECASE)
# Voice marks in a narration script: " / " short pause, " // " long pause, *word* stress, ad-VER-tising.
PAUSE_MARK = re.compile(r"(?<!\S)(//?)(?!\S)")
STRESS_MARK = re.compile(r"\b[A-Za-z]+(?:-[A-Za-z]+)+\b")
EMPH_MARK = re.compile(r"\*([^*\s]+)\*")
PAGE_START = re.compile(r"^\s*<(?:!doctype|html)\b", re.IGNORECASE)
# The twelve terms of a brand strategy, in this order, each with its definition and its job. A brand's
# own brand_strategy.json may repeat them; where it leaves one out, these words are served.
TERMS = {
    "purpose": ("Why the company exists.",
                "It says what the company exists for and what it will not do."),
    "mission": ("Who the company serves, plus the offer.",
                "It tells staff which business the company is in."),
    "vision": ("The world the company wants to help build, and the company's role in it.",
               "It gives people something to aim at."),
    "values": ("Core values are beliefs the company already acts on and keeps at a cost.",
               "It tells staff what to choose when the choice costs something."),
    "way_of_winning": ("The choices by which the company expects to beat competitors. "
                       "Many documents call it the strategy.",
                       "It names the choices the company makes and the ones it turns down."),
    "audiences": ("The people who must recognize the entity, and what each of them should think. "
                  "Most documents call that thought the positioning.",
                  "It says who the brand is for and gives each audience its reasons to pick this brand."),
    "promise": ("What those people can expect.",
                "It creates one clear expectation that the experience can keep or break."),
    "personality": ("The human traits the brand intends to show, in tone and in behavior.",
                    "It makes the brand recognizable by its manner."),
    "expressions": ("Everything a person can sense that the entity intends to be recognized by: the name, the "
                    "logo, the voice, the behaviors, the recognizable product features, a smell, a texture.",
                    "It lets people recognize the brand at once."),
    "structure": ("How the names of the company, its businesses and its products relate.",
                  "It shows people which company stands behind which product."),
    "narrative": ("The story the brand tells about itself: where it comes from, what it stands for and where it "
                  "goes, told as one story.",
                  "It lets staff and partners tell the brand the same way."),
    "guidelines": ("The rules for using the expressions: how the logo, the colors, the type, the pictures and "
                   "the voice are applied.",
                   "It lets everyone who makes something under the name apply the expressions the same way."),
}
# A ref entry points at one item of brand.json: the list it sits in, and the field that names the item.
REF_KINDS = {"rules": "id", "claims": "id", "colors": "hex", "typefaces": "name", "assets": "id"}

STOP = set("a an the and or of to in on for with your you our is are it its that this by from as at be we".split())

server = MCPServer(
    name=f"{NAME} Brand BrAIn",
    instructions=(
        f"Before you write anything that speaks for {NAME}, call get_strategy and follow what it returns. "
        f"Before you write or design anything for {NAME}, call get_rules and get_claims. "
        "Use find_asset for every logo, color and typeface. Call check_draft on the finished text. "
        "On 'fail', fix the draft and check again. On 'person_must_look', tell the user which parts "
        "a person must review. Use request_exception when a rule blocks a real need."
        + (f" Checker not available: root {', '.join(MISSING_ROOTS)} is missing, so drafts go to a person."
           if MISSING_ROOTS else "")
    ),
    version=VERSION,
)


def _log(tool: str, **fields) -> None:
    """The server records each call itself, failures included, with the rule version."""
    LOG_DIR.mkdir(exist_ok=True)
    line = {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "who": os.environ.get("BRAND_BRAIN_USER", "unknown"),
        "tool": tool,
        "rules_version": VERSION,
        **fields,
    }
    with (LOG_DIR / "calls.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def _applies(rule: dict, audience: str, country: str) -> bool:
    a = [x.lower() for x in rule.get("audiences", ["all"])]
    c = [x.lower() for x in rule.get("countries", ["all"])]
    return ("all" in a or audience.lower() in ("all", *a)) and ("all" in c or country.lower() in ("all", *c))


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in STOP and len(w) > 2}


def _live_claims() -> list[dict]:
    """Claims whose end date has not passed."""
    today = dt.date.today().isoformat()
    return [c for c in BRAND.get("claims", []) if not c.get("expires") or c["expires"] >= today]


def _unstress(m: re.Match) -> str:
    """ad-VER-tising becomes advertising. A plain hyphenated word (outside-in) stays as it is."""
    word = m.group(0)
    parts = word.split("-")
    if word.isupper() or not any(p.isupper() and len(p) > 1 for p in parts):
        return word
    joined = "".join(parts).lower()
    return joined.capitalize() if parts[0][:1].isupper() and not parts[0].isupper() else joined


def strip_voice_marks(text: str) -> str:
    """The narration line as a listener hears it, with every voice mark taken out."""
    text = PAUSE_MARK.sub(" ", text)
    text = STRESS_MARK.sub(_unstress, text)
    text = EMPH_MARK.sub(r"\1", text)
    return re.sub(r" {2,}", " ", text).replace(" ,", ",").strip()


def _numbers(text: str) -> set[str]:
    return {n.lower() for n in NUMBER.findall(text)}


def _claim_matches(sentence: str, claim: str) -> bool:
    """A sentence matches a claim when 60% of the claim's words are in it and it adds no number."""
    a, w = _words(claim), _words(sentence)
    return bool(a) and len(a & w) / len(a) >= 0.6 and _numbers(sentence) <= _numbers(claim)


def _fill(word: str, draft: Path) -> str:
    word = word.replace("{file}", str(draft)).replace("{brand}", str(BRAND_DIR))
    for k, v in ROOTS.items():
        word = word.replace("{" + k + "}", str(v))
    return word


def run_checkers(kind: str, text: str) -> tuple[list[dict], list[dict], list[str]]:
    """Runs the brand's own checkers for this kind of draft.

    Each checker prints one JSON object: verdict, failures, person_must_look. Any fail makes the
    draft fail. A crash, an answer that is not that JSON, or a missing root sends it to a person.
    """
    commands = BRAND.get("checkers", {}).get(kind, [])
    failures, review, names = [], [], []
    if not commands:
        return failures, review, names
    with tempfile.TemporaryDirectory() as d:
        draft = Path(d) / ("draft.html" if kind == "page" else "draft.txt")
        draft.write_text(text, encoding="utf-8")
        for cmd in commands:
            name = Path(cmd[1]).name if len(cmd) > 1 else cmd[0]
            names.append(name)
            needed = [k for k in MISSING_ROOTS if any("{" + k + "}" in w for w in cmd)]
            if needed:
                review.append({"sentence": "", "why": f"Checker not available: root {', '.join(needed)} is missing."})
                continue
            try:
                p = subprocess.run([sys.executable if w == "python" else _fill(w, draft) for w in cmd],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
                out = json.loads(p.stdout)
                verdict = out["verdict"]
            except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, TypeError) as e:
                review.append({"sentence": "", "why": f"Checker {name} gave no answer a machine can read: {e}"})
                continue
            if verdict == "fail":
                failures.extend(out.get("failures") or [{"rule": name, "found": "", "fix": ""}])
            elif verdict == "person_must_look":
                review.extend(out.get("person_must_look") or [{"sentence": "", "why": f"{name} asks for a person."}])
            elif verdict != "pass":
                review.append({"sentence": "", "why": f"Checker {name} answered {verdict!r}."})
    return failures, review, names


def _ref_value(kind: str, item: dict) -> str:
    """The one value an AI tool uses from a referenced item."""
    if kind == "rules":
        return item.get("rule", "")
    if kind == "claims":
        return item.get("claim", "")
    if kind == "colors":
        return " ".join(x for x in (item.get("hex", ""), item.get("name", "")) if x)
    if kind == "typefaces":
        return item.get("name", "")
    return item.get("file") or item.get("url", "")


def _resolve(entry: dict) -> dict:
    """Swaps a ref such as "rules:voice-01" for the item it names. A ref that names no item is marked broken."""
    kind, _, key = entry["ref"].partition(":")
    kind, key = kind.strip().lower(), key.strip()
    field = REF_KINDS.get(kind)
    if field is None:
        return {**entry, "broken": True,
                "why_broken": f"A ref can name rules, claims, colors, typefaces or assets. {kind!r} is none of them."}
    for item in BRAND.get(kind, []):
        if key.lower() in (str(item.get(field, "")).lower(), str(item.get("id", "")).lower()):
            return {**entry, "resolved": {"kind": kind, "id": item.get(field) or item.get("id"),
                                          "value": _ref_value(kind, item),
                                          "why": item.get("why", ""), "used_for": item.get("used_for", "")}}
    return {**entry, "broken": True, "why_broken": f"brand.json has no item {key!r} in {kind}."}


def _strategy_terms(doc: dict) -> dict[str, dict]:
    """The file's terms by key. The file holds them as an object keyed by term or as a list of {term, ...}."""
    raw = doc.get("terms", {})
    if isinstance(raw, list):
        return {str(t.get("term", "")).lower(): t for t in raw if isinstance(t, dict)}
    return {str(k).lower(): v for k, v in raw.items() if isinstance(v, dict)}


@server.tool()
def get_strategy(term: str = "all") -> dict:
    """Return what the brand strategy says, for one term or all twelve.

    Call it before you write anything that speaks for the brand.
    term: purpose, mission, vision, values, way_of_winning, audiences, promise, personality,
    expressions, structure, narrative, guidelines, or all.
    Each term comes with its definition and its job. A term with no entries comes back with "empty": true.
    An Audiences entry has half: people names who the brand is for, thought says what they should think.
    An entry that points at brand.json (ref) comes back with the item under "resolved": its kind, id,
    value, why and used_for. A ref that names no item comes back with "broken": true.
    """
    wanted = term.strip().lower().replace(" ", "_").replace("-", "_") or "all"
    if wanted != "all" and wanted not in TERMS:
        _log("get_strategy", term=term, returned=0, error="unknown term")
        return {"brand": NAME, "error": f"A brand strategy has no term {term!r}. "
                f"Ask for all, or for one of the twelve terms: {', '.join(TERMS)}.", "terms": list(TERMS)}
    if not STRATEGY_FILE.exists():
        _log("get_strategy", term=term, returned=0, error="no strategy file")
        return {"brand": NAME, "rules_version": VERSION, "strategy_file": None,
                "answer": f"{NAME} has no strategy file. The brand folder holds no brand_strategy.json. "
                          "Use get_rules, get_claims and find_asset for what the brand has approved."}
    try:
        found = _strategy_terms(json.loads(STRATEGY_FILE.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        _log("get_strategy", term=term, returned=0, error="unreadable strategy file")
        return {"brand": NAME, "error": f"A machine cannot read brand_strategy.json as JSON: {e}"}

    out, broken = [], []
    for key in (TERMS if wanted == "all" else [wanted]):
        here = found.get(key, {})
        entries = [_resolve(e) if isinstance(e, dict) and e.get("ref") else e for e in here.get("entries", [])]
        broken += [e.get("id", e["ref"]) for e in entries if isinstance(e, dict) and e.get("broken")]
        out.append({"term": key, "definition": here.get("definition") or TERMS[key][0],
                    "job": here.get("job") or TERMS[key][1], "empty": not entries, "entries": entries})
    _log("get_strategy", term=term, returned=sum(len(t["entries"]) for t in out), broken=len(broken))
    return {"brand": NAME, "rules_version": VERSION, "strategy_file": STRATEGY_FILE.name,
            "terms": out, "broken_refs": broken}


@server.tool()
def get_rules(topic: str = "all", audience: str = "staff", country: str = "all", include_old: bool = False) -> dict:
    """Return the brand rules for one job.

    topic: positioning, voice, logo, color, type, naming, legal, or all.
    audience: staff, partner, agency, or all. Partners and agencies also get the trademark rules.
    include_old: also return rules from older sources that the live brand portal has replaced.
    Each rule names its source, so the reader knows where it comes from and how old it is.
    """
    rules = [
        r for r in BRAND["rules"]
        if (topic.lower() == "all" or r["area"].lower() == topic.lower())
        and _applies(r, audience, country)
        and (include_old or r.get("status", "current") == "current")
    ]
    _log("get_rules", topic=topic, audience=audience, country=country, returned=len(rules))
    return {
        "brand": NAME,
        "rules_version": VERSION,
        "read_on": BRAND.get("read_on"),
        "rules": rules,
        "names": BRAND.get("names", {}) if topic.lower() in ("all", "naming") else {},
        "legal_lines": BRAND.get("legal_lines", []) if topic.lower() in ("all", "legal") else [],
    }


@server.tool()
def find_asset(query: str = "", kind: str = "any") -> dict:
    """Return approved logos, colors and typefaces that match the query.

    kind: logo, wordmark, icon, template, color, typeface, or any.
    Use only what this returns. A color or logo from memory may be out of date.
    """
    q = query.lower().strip()
    k = kind.lower()

    def hit(item: dict) -> bool:
        return not q or any(q in str(v).lower() for v in item.values())

    out = {"brand": NAME, "rules_version": VERSION, "assets": [], "colors": [], "typefaces": []}
    if k in ("any", "logo", "wordmark", "icon", "template"):
        out["assets"] = [a for a in BRAND.get("assets", []) if hit(a) and k in ("any", a.get("kind", "").lower())]
    if k in ("any", "color"):
        out["colors"] = [c for c in BRAND.get("colors", []) if hit(c)]
    if k in ("any", "typeface"):
        out["typefaces"] = [t for t in BRAND.get("typefaces", []) if hit(t)]
    _log("find_asset", query=query, kind=kind,
         returned=len(out["assets"]) + len(out["colors"]) + len(out["typefaces"]))
    return out


@server.tool()
def get_claims(topic: str = "") -> dict:
    """Return the approved product claims, each with the public page that states it.

    Use these claims in their own words. A claim outside this list needs a brand owner's yes.
    """
    q = topic.lower().strip()
    claims = [c for c in _live_claims() if not q or q in c["claim"].lower()]
    expired = [c["id"] for c in BRAND.get("claims", []) if c not in _live_claims()]
    _log("get_claims", topic=topic, returned=len(claims))
    return {"brand": NAME, "rules_version": VERSION, "claims": claims, "expired_and_left_out": expired}


@server.tool()
def check_draft(text: str, kind: str = "auto", audience: str = "staff", country: str = "all") -> dict:
    """Test a draft against the rules a machine can test.

    kind: auto, text, page, narration, external or internal. auto treats a draft that starts with
    <!doctype or <html as a page and anything else as text. narration is a spoken script: its voice
    marks (/ and // pauses, *stress*, ad-VER-tising) are taken out before the check. external and
    internal are text; internal skips the banned phrases marked for external use only.
    The brand's own checkers (brand.json "checkers") run after the built-in tests.
    audience: who wrote it: staff, partner or agency. Partner and agency drafts also meet the trademark rules.
    Returns verdict "pass", "fail" or "person_must_look".
    fail: a wrong brand name, a banned phrase, or a color outside the palette. Each failure names its rule.
    person_must_look: the text makes a claim that matches no approved claim, or uses a limited word
    (brand.json "word_limit", such as puns on the brand's animal) more often than the brand allows.
    Tone, pictures and layout are never tested here; a person judges them.
    """
    failures, review = [], []
    k = kind.lower()
    family = ("page" if PAGE_START.match(text) else "text") if k == "auto" else (
        k if k in ("page", "narration") else "text")
    if family == "narration":
        text = "\n".join(strip_voice_marks(line) for line in text.splitlines())
    bare = URL.sub(" ", text)
    if family == "page":
        # Names, phrases and claims are read in the words a visitor sees, never in the code.
        bare = re.sub(r"(?s)<!--.*?-->|<(script|style)\b.*?</\1>|<[^>]+>", " ", bare)

    for wrong in BRAND.get("names", {}).get("wrong", []):
        for m in re.finditer(r"(?<![\w.])" + re.escape(wrong) + r"(?![\w.])", bare):
            failures.append({"rule": "naming", "found": m.group(0),
                             "fix": "Use one of: " + ", ".join(BRAND["names"].get("correct", [])[:4])})
            break
    if audience.lower() in ("partner", "agency"):
        for pat in BRAND.get("names", {}).get("partner_patterns", []):
            m = re.search(pat["pattern"], bare)
            if m:
                failures.append({"rule": pat["rule"], "found": m.group(0), "fix": pat["fix"]})
    for b in BRAND.get("banned_phrases", []):
        if b.get("skip_kind") == kind.lower():
            continue
        if re.search(r"(?<!\w)" + re.escape(b["phrase"]) + r"(?!\w)", bare, re.IGNORECASE):
            failures.append({"rule": "banned phrase", "found": b["phrase"], "fix": b.get("why", "")})
    palette = {c["hex"].upper() for c in BRAND.get("colors", [])}
    # On a page, a brand's own page checker owns the color rules, which know where a value may sit.
    if palette and not (family == "page" and BRAND.get("checkers", {}).get("page")):
        for h in sorted({x.upper() for x in HEX.findall(text)} - palette):
            failures.append({"rule": "color", "found": h, "fix": "Use a color that find_asset returns."})

    limit = BRAND.get("word_limit")
    if limit:
        puns = [w for w in re.findall(limit["pattern"], bare, re.IGNORECASE) if w.lower() != NAME.lower()]
        if len(puns) > limit["max"]:
            review.append({"sentence": ", ".join(puns[:6]),
                           "why": limit.get("why", f"More than {limit['max']} of these words in one piece.")})

    for sentence in re.split(r"(?<=[.!?])\s+|\n+", bare):
        s = sentence.strip()
        if not s or not CLAIM_WORDS or not CLAIM_WORDS.search(s):
            continue
        if not any(_claim_matches(s, c["claim"]) for c in _live_claims()):
            review.append({"sentence": s[:200], "why": "This reads as a product claim and matches no approved claim."})

    more_fail, more_review, checkers = run_checkers(family, text)
    failures += more_fail
    review += more_review

    verdict = "fail" if failures else ("person_must_look" if review else "pass")
    _log("check_draft", kind=kind, family=family, checkers=checkers, country=country, chars=len(text), verdict=verdict,
         failed_rules=[f["rule"] for f in failures], review_count=len(review))
    return {
        "brand": NAME,
        "rules_version": VERSION,
        "verdict": verdict,
        "checked_as": family,
        "failures": failures,
        "person_must_look": review,
        "machine_tested": ["brand name use", "banned phrases", "color values"]
        + ([limit.get("name", "limited words")] if limit else [])
        + (["claims against the approved list"] if CLAIM_WORDS else []) + checkers,
        "not_tested": ["tone of voice", "pictures", "layout", "logo placement", "claims without a claim word"],
    }


@server.tool()
def request_exception(what: str, why: str, rule_area: str = "") -> dict:
    """Send a hard case to the brand owner of one rule area. Returns a ticket id.

    what: the thing you want to do. why: the real need behind it.
    """
    ticket = "EX-" + uuid.uuid4().hex[:8]
    LOG_DIR.mkdir(exist_ok=True)
    with (LOG_DIR / "exceptions.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ticket": ticket, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "who": os.environ.get("BRAND_BRAIN_USER", "unknown"), "what": what, "why": why,
            "rule_area": rule_area, "rules_version": VERSION, "status": "open",
        }, ensure_ascii=False) + "\n")
    _log("request_exception", ticket=ticket, rule_area=rule_area)
    owners = BRAND.get("owners", {})
    owner = owners.get(rule_area.lower(), owners.get("default", "the brand team"))
    return {"ticket": ticket, "status": "open", "goes_to": owner,
            "next": "Hold this part of the draft until a person answers the ticket."}


@server.tool()
def usage_report() -> dict:
    """Return how often each tool ran and which rules failed most. For the brand team."""
    path = LOG_DIR / "calls.jsonl"
    calls, verdicts, failed = Counter(), Counter(), Counter()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            calls[row["tool"]] += 1
            if row["tool"] == "check_draft":
                verdicts[row["verdict"]] += 1
                failed.update(row.get("failed_rules", []))
    return {"brand": NAME, "calls": dict(calls), "check_verdicts": dict(verdicts),
            "most_failed_rules": failed.most_common(10)}


@server.resource(f"brand://{BRAND_DIR.name}/rules", mime_type="application/json")
def all_rules() -> str:
    """Every rule of the brand as one JSON document."""
    return json.dumps(BRAND, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    if "--check" in sys.argv:
        # A quick test for a person: read the brand files, print one line, stop. No AI tool needed.
        strategy = "with a strategy file" if STRATEGY_FILE.exists() else "with no strategy file"
        print(f"Brand BrAIn ready: {NAME or '(no brand name yet)'}, {len(BRAND.get('rules', []))} rules, "
              f"{len(_live_claims())} live claims, {len(BRAND.get('colors', []))} colors, {strategy}."
              + (f" Missing roots: {', '.join(MISSING_ROOTS)}." if MISSING_ROOTS else ""))
        sys.exit(0)
    server.run("streamable-http" if "--http" in sys.argv else "stdio")
