"""Starts Brand BrAIn the way an AI tool does and tests every built-in check and the checker slot.

It uses only the folders in this repo: the empty template, an invented brand (Alder Pipes) and stub
checkers. Run from the repo folder: python tests/test_server_basics.py. Exit code 1 on a wrong answer.
"""
import asyncio
import json
import shutil
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parent.parent


def body(result) -> dict:
    if getattr(result, "structured_content", None):
        return result.structured_content
    return json.loads(result.content[0].text)


def server(folder: str) -> StdioServerParameters:
    return StdioServerParameters(command=sys.executable, args=[str(REPO / "server.py"), folder],
                                 env={"BRAND_BRAIN_USER": "test", "PYTHONUTF8": "1"})


async def main() -> int:
    bad = []

    def expect(name: str, ok: bool, detail: str = "") -> None:
        print(("ok   " if ok else "FAIL ") + name + ((" | " + str(detail)[:160]) if detail else ""))
        if not ok:
            bad.append(name)

    async with stdio_client(server("brand_template")) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            tools = sorted(t.name for t in (await s.list_tools()).tools)
            expect("the empty template starts and lists seven tools", len(tools) == 7, ", ".join(tools))

    cases = [
        ("an approved claim passes", "Our copper pipes carry a 25 year warranty.", "pass"),
        ("a claim with a new number goes to a person", "Our copper pipes carry a 30 year warranty.", "person_must_look"),
        ("a wrong brand name fails", "AlderPipes makes copper pipes.", "fail"),
        ("a banned phrase fails", "Every joint is leak-proof.", "fail"),
        ("a color outside the palette fails", "Headlines in #FF0000.", "fail"),
        ("a color in the palette passes", "Headlines in #2B4C3F.", "pass"),
    ]
    async with stdio_client(server("tests/fixtures/example")) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            r = body(await s.call_tool("get_rules", {"topic": "naming"}))
            expect("get_rules returns the naming rule and the names", len(r["rules"]) == 1 and r["names"]["correct"])
            for name, text, want in cases:
                r = body(await s.call_tool("check_draft", {"text": text}))
                expect(name, r["verdict"] == want, r["failures"] or r["person_must_look"])

    stubs = {"pass": "pass", "fail": "fail", "person_must_look": "person_must_look",
             "crash": "person_must_look", "garbage": "person_must_look"}
    async with stdio_client(server("tests/fixtures/stubs")) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            for word, want in stubs.items():
                r = body(await s.call_tool("check_draft", {"text": word + " draft"}))
                expect(f"a checker answering '{word}' beside a pass gives {want}", r["verdict"] == want, r["verdict"])

    async with stdio_client(server("tests/fixtures/missing_root")) as (read, write):
        async with ClientSession(read, write) as s:
            init = await s.initialize()
            r = body(await s.call_tool("check_draft", {"text": "A plain draft."}))
            expect("a missing root gives checker not available",
                   r["verdict"] == "person_must_look" and "not available" in str(r["person_must_look"])
                   and "not available" in (init.instructions or ""))

    for folder in ("brand_template", "tests/fixtures/example", "tests/fixtures/stubs", "tests/fixtures/missing_root"):
        shutil.rmtree(REPO / folder / "log", ignore_errors=True)
    print(f"{len(bad)} failed")
    return 1 if bad else 0


def test_server_basics() -> None:
    """The same checks, for python -m pytest."""
    assert asyncio.run(main()) == 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
