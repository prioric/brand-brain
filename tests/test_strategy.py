"""Tests get_strategy the way an AI tool calls it: over stdio, against folders in this repo.

The empty template, an invented brand with no strategy file (tests/fixtures/example) and the same brand
with a small strategy file (tests/fixtures/strategy). Run from the repo folder: python -m pytest.
The log goes to a temporary folder, so no test writes into a brand folder.
"""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parent.parent
ORDER = ["purpose", "mission", "vision", "values", "way_of_winning", "audiences", "promise", "personality",
         "expressions", "structure", "narrative", "guidelines"]


def body(result) -> dict:
    if getattr(result, "structured_content", None):
        return result.structured_content
    return json.loads(result.content[0].text)


def ask(folder: str | Path, log_dir: Path, *calls: tuple[str, dict]) -> list[dict]:
    """Starts the server on one brand folder and returns the answer to each call, in order."""
    params = StdioServerParameters(command=sys.executable, args=[str(REPO / "server.py"), str(folder)],
                                   env={"BRAND_BRAIN_USER": "test", "PYTHONUTF8": "1",
                                        "BRAND_BRAIN_LOG_DIR": str(log_dir)})

    async def run() -> list[dict]:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as s:
                init = await s.initialize()
                answers = [{"instructions": init.instructions or ""}]
                for name, args in calls:
                    answers.append(body(await s.call_tool(name, args)))
                return answers

    return asyncio.run(run())


def test_template_has_the_twelve_terms_in_order():
    doc = json.loads((REPO / "brand_template" / "brand_strategy.json").read_text(encoding="utf-8"))
    assert list(doc["terms"]) == ORDER
    for key, term in doc["terms"].items():
        assert term["definition"] and term["job"], key
        assert term["entries"] == [], key


def test_empty_template_gives_twelve_empty_terms(tmp_path):
    init, everything, one = ask("brand_template", tmp_path, ("get_strategy", {}),
                                ("get_strategy", {"term": "promise"}))
    assert "get_strategy" in init["instructions"]
    assert [t["term"] for t in everything["terms"]] == ORDER
    assert all(t["empty"] and t["entries"] == [] for t in everything["terms"])
    assert one["terms"] == [{"term": "promise", "definition": "What those people can expect.",
                             "job": "It creates one clear expectation that the experience can keep or break.",
                             "empty": True, "entries": []}]
    assert not (REPO / "brand_template" / "log").exists()


def test_unknown_term_gets_a_plain_error(tmp_path):
    _, answer = ask("brand_template", tmp_path, ("get_strategy", {"term": "tagline"}))
    assert "tagline" in answer["error"]
    assert answer["terms"] == ORDER
    assert all(t in answer["error"] for t in ORDER)


def test_a_term_written_with_spaces_is_found(tmp_path):
    _, answer = ask("brand_template", tmp_path, ("get_strategy", {"term": "Way of winning"}))
    assert [t["term"] for t in answer["terms"]] == ["way_of_winning"]


def test_brand_with_no_strategy_file_gets_a_plain_answer(tmp_path):
    _, answer = ask("tests/fixtures/example", tmp_path, ("get_strategy", {}))
    assert answer["strategy_file"] is None
    assert answer["answer"].startswith("Alder Pipes has no strategy file.")
    assert "terms" not in answer


def test_filled_fixture_comes_back_in_full(tmp_path):
    folder = (REPO / "tests" / "fixtures" / "strategy").resolve()  # an absolute path, as the server allows
    _, answer = ask(folder, tmp_path, ("get_strategy", {"term": "all"}))
    terms = {t["term"]: t for t in answer["terms"]}
    assert [t["term"] for t in answer["terms"]] == ORDER
    assert [k for k, t in terms.items() if not t["empty"]] == [
        "purpose", "audiences", "promise", "expressions", "guidelines"]

    assert terms["purpose"]["entries"] == [{"id": "purpose-01", "text": "Keep water in the pipe for fifty years.",
                                            "why": "Invented for the test.", "used_for": "The about page."}]
    assert [(e["half"], e["text"]) for e in terms["audiences"]["entries"]] == [
        ("people", "Plumbers who fit pipes in new houses."), ("thought", "Alder pipes fit the first time.")]

    resolved = [e["resolved"] for k in ("expressions", "promise", "guidelines")
                for e in terms[k]["entries"] if "resolved" in e]
    assert resolved == [
        {"kind": "assets", "id": "logo-01", "value": "logos/alder-green.svg",
         "why": "The logo in the brand color.", "used_for": "Vans and the site header."},
        {"kind": "colors", "id": "#2B4C3F", "value": "#2B4C3F Alder green",
         "why": "The green of the first van.", "used_for": "Headlines and the logo."},
        {"kind": "typefaces", "id": "Inter", "value": "Inter",
         "why": "It reads well on a phone.", "used_for": "Body text."},
        {"kind": "claims", "id": "claim-01", "value": "Our copper pipes carry a 25 year warranty.",
         "why": "Buyers ask how long a pipe lasts.", "used_for": "Product pages."},
        {"kind": "rules", "id": "voice-01", "value": "Write short sentences a plumber would say on site.",
         "why": "Plumbers buy the pipes.", "used_for": "Every text."},
    ]
    broken = terms["guidelines"]["entries"][1]
    assert broken["broken"] is True and "voice-99" in broken["why_broken"]
    assert answer["broken_refs"] == ["guidelines-02"]
    assert (tmp_path / "calls.jsonl").exists()
    assert not (folder / "log").exists()
