"""Calls each of the seven tools on the Alder Pipes example and checks each answer, then checks the setup files.

Run from the repo folder: python -m pytest. The log goes to a temporary folder, so no test writes into
the example folder.
"""
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parent.parent
EXAMPLE = "examples/alder_pipes"


def body(result) -> dict:
    if getattr(result, "structured_content", None):
        return result.structured_content
    return json.loads(result.content[0].text)


def ask(folder: str, log_dir: Path, *calls: tuple[str, dict]) -> list[dict]:
    """Starts the server on one brand folder and returns the answer to each call, in order."""
    params = StdioServerParameters(command=sys.executable, args=[str(REPO / "server.py"), folder],
                                   env={"BRAND_BRAIN_USER": "test", "PYTHONUTF8": "1",
                                        "BRAND_BRAIN_LOG_DIR": str(log_dir)})

    async def run() -> list[dict]:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as s:
                init = await s.initialize()
                answers = [{"name": init.server_info.name, "instructions": init.instructions or ""}]
                for name, args in calls:
                    answers.append(body(await s.call_tool(name, args)))
                return answers

    return asyncio.run(run())


def test_each_tool_answers_on_the_example(tmp_path):
    (init, strategy, rules, partner_rules, colors, claims, bad, good, partner, ticket, report) = ask(
        EXAMPLE, tmp_path,
        ("get_strategy", {}),
        ("get_rules", {}),
        ("get_rules", {"audience": "partner"}),
        ("find_asset", {"kind": "color"}),
        ("get_claims", {}),
        ("check_draft", {"text": "Alder Pipes joints are leak-proof. A real game-changer."}),
        ("check_draft", {"text": "Alder Pipes fit the first time. Our copper pipes carry a 25 year warranty."}),
        ("check_draft", {"text": "Ask your merchant for Alder Pipes.", "audience": "partner"}),
        ("request_exception", {"what": "Use the old slogan at a trade show", "why": "The stand is printed", "rule_area": "legal"}),
        ("usage_report", {}),
    )
    assert init["name"] == "Alder Pipes Brand BrAIn"
    assert "get_strategy" in init["instructions"] and "check_draft" in init["instructions"]

    terms = {t["term"]: t for t in strategy["terms"]}
    assert len(terms) == 12 and not any(t["empty"] for t in terms.values())
    assert strategy["broken_refs"] == []

    assert [r["id"] for r in rules["rules"]] == ["voice-01", "naming-01", "logo-01"]
    assert "legal-01" in [r["id"] for r in partner_rules["rules"]]
    assert [c["hex"] for c in colors["colors"]] == ["#2B4C3F", "#F2EDE4", "#B5652B"]
    assert [c["id"] for c in claims["claims"]] == ["claim-01", "claim-02"]
    assert claims["expired_and_left_out"] == ["claim-old"]

    assert bad["verdict"] == "fail"
    assert sorted(f["found"] for f in bad["failures"]) == ["game-changer", "leak-proof"]
    assert good["verdict"] == "pass", good
    assert partner["verdict"] == "fail" and partner["failures"][0]["rule"] == "trademark"

    assert ticket["ticket"].startswith("EX-") and ticket["goes_to"] == "the Alder Pipes legal desk"
    row = json.loads((tmp_path / "exceptions.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["ticket"] == ticket["ticket"] and row["who"] == "test"

    assert report["calls"]["check_draft"] == 3 and report["calls"]["get_rules"] == 2
    assert report["check_verdicts"] == {"fail": 2, "pass": 1}
    assert not (REPO / EXAMPLE / "log").exists()


def test_setup_names_the_four_questions_and_the_fill_step():
    text = (REPO / "SETUP.md").read_text(encoding="utf-8")
    questions = re.findall(r"^\d\. \*\*(.+?)\*\*", text.split("## The four questions")[1].split("## ")[0], re.M)
    assert questions == ["Which AI tool are you using?", "Is Python 3.11 or later installed?",
                         "Should Brand BrAIn run on this computer, or as a web address?", "What is the brand called?"]
    for must in ("brands/setup.md", "brands/{folder}/", "brand.json", "brand_strategy.json", "claude mcp add",
                 "codex mcp add", "new session", "mcp==2.3.0"):
        assert must in text, must
    assert "SETUP.md" in (REPO / "README.md").read_text(encoding="utf-8")


def test_git_ignores_a_brand_folder_and_the_answers():
    for path in ("brands/my_brand/brand.json", "brands/setup.md", "SETUP.md"):
        r = subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO)
        assert r.returncode == (1 if path == "SETUP.md" else 0), path


def test_no_public_file_keeps_the_old_name():
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=REPO,
                           capture_output=True, text=True, check=True).stdout.split()
    old = re.compile("|".join(["BRAND" + "_MCP", "brand" + "-mcp", "brand " + "server"]), re.I)
    hits = [f for f in files if (REPO / f).is_file() and old.search((REPO / f).read_text(encoding="utf-8", errors="ignore"))]
    assert hits == []


def test_check_prints_one_ready_line():
    r = subprocess.run([sys.executable, str(REPO / "server.py"), EXAMPLE, "--check"], capture_output=True, text=True)
    assert r.returncode == 0
    assert r.stdout.strip() == "Brand BrAIn ready: Alder Pipes, 5 rules, 2 live claims, 3 colors, with a strategy file."
