# Brand BrAIn

A small MCP server that keeps one brand's strategy, rules, approved files and approved claims. An AI tool that has Brand BrAIn added is told to ask it before it writes or designs anything for the brand, and to send it each draft for a check.

MCP (Model Context Protocol) is an open standard. An AI tool that speaks it can call the tools of a server like this one.

The repo is brand-neutral. Your own brand goes in a folder under `brands/`, which git ignores. `examples/alder_pipes/` shows a filled brand for an invented company.

## Set it up in five minutes

You need Python 3.11 or later and an AI tool that runs commands in a folder, such as Claude Code or Codex.

1. Download this repo: `git clone https://github.com/prioric/brand-brain.git`, or download it as a ZIP file from GitHub and unpack it.
2. Open your AI tool in the `brand-brain` folder.
3. Say: "Read SETUP.md and set up Brand BrAIn for me."

The AI tool asks four questions, one at a time: which AI tool you use, whether Python is installed (it checks this itself first), whether Brand BrAIn runs on this computer or as a web address, and what the brand is called. It writes your answers to `brands/setup.md`, installs the one library, fills the brand files from the files you point it to, and adds Brand BrAIn to your AI tool. It asks for your yes before each install or settings change.

To try it on the invented brand first, say: "Read SETUP.md and set up Brand BrAIn with the example." To test a brand folder without any AI tool: `python server.py examples/alder_pipes --check` prints one ready line.

## Who it is for

A brand team at a company that already works inside an AI workspace under its own enterprise contract. Staff, partners and agencies write with AI there every day. The server puts the brand rules inside that workspace, so each AI tool that is set up to call the server reads the same rules. The brand team sees how the rules are used.

## The seven tools

| Tool | What it answers |
|---|---|
| `get_strategy` | What the brand strategy says, for one term or all twelve. Each term comes with its definition and its job. |
| `get_rules` | Which brand rules apply to this job, for this audience and country. Each rule names its source. |
| `find_asset` | Which logo, color, typeface or template to use. Only approved values come back. |
| `get_claims` | Which claims are approved, each with the public page that proves it. Expired claims are left out. |
| `check_draft` | Whether a draft passes: `pass`, `fail` with each broken rule named, or `person_must_look` with the sentences a person must read. |
| `request_exception` | Sends a hard case to the owner of that rule area and returns a ticket number. |
| `usage_report` | How often each tool ran and which rules failed most, for the brand team. |

The server writes every call to `{brand}/log/calls.jsonl`, with the rules version and the result. Set `BRAND_BRAIN_LOG_DIR` to write the log to another folder.

## Strategy file gives AI tools the brand's twelve terms

A brand folder can hold `brand_strategy.json` beside `brand.json`. The template in `brand_template/` lists the twelve terms in order: purpose, mission, vision, values, way of winning, audiences, promise, personality, expressions, structure, narrative and guidelines. Each term carries its definition, its job and an empty `entries` list.

An entry contains its text directly or points to an item in `brand.json`:

```json
{"id": "promise-01", "text": "The sentence itself.", "why": "Why the brand keeps it.", "used_for": "Where it is used."}
{"id": "guidelines-01", "ref": "rules:voice-01"}
```

- An Audiences entry also carries `half`. `people` names who the brand is for. `thought` says what that audience should think.
- A `ref` names a list in `brand.json` and one item in it. The list is `rules`, `claims`, `colors`, `typefaces` or `assets`. A color is named by its hex, such as `colors:#2B4C3F`. A typeface is named by its name.

`get_strategy` reads the file each time it is called, so an edit shows at the next call.

- `get_strategy()` returns all twelve terms. `get_strategy("audiences")` returns one.
- A term with no entries comes back with `"empty": true`.
- A `ref` comes back with the item under `resolved`: its kind, id, value, why and used-for. The value is the rule text, the claim text, the color hex and name, the typeface name or the asset file.
- A `ref` that names no item comes back with `"broken": true`. The answer lists every broken entry under `broken_refs`.
- A term outside the twelve gets an error that lists the twelve.
- A brand folder with no `brand_strategy.json` gets an answer that says the brand has no strategy file.

The server tells the AI tool to call `get_strategy` before it writes anything that speaks for the brand.

## What `check_draft` tests

Built in, for every brand:

- the brand name, against the ways never to write it;
- banned phrases;
- color values in a text, against the approved palette;
- claim sentences, against the approved claims (a sentence matches a claim when it uses 60% of the claim's words and adds no number; a sentence that adds a number, or matches no claim, goes to a person);
- an optional limit on a word, such as puns on the brand's mascot.

A person judges tone, pictures, layout and logo placement. The server lists these under `not_tested` in every answer. The list also names claims written without any of the brand's claim words, because the claim test cannot find them, so a person reads for them.

Your own checkers plug in on top (see below).

## Set it up by hand

The steps SETUP.md walks an AI tool through, for a person who prefers to do them alone.

```
pip install "mcp==2.3.0"
```

1. Copy `brand_template` to `brands/my_brand`.
2. Fill `brands/my_brand/brand.json`. The `_about` block at its top says what goes in each slot. Fill `brands/my_brand/brand_strategy.json` the same way, or delete it when the brand has no strategy to serve.
3. Test the files: `python server.py brands/my_brand --check` prints one line that begins `Brand BrAIn ready:`. An AI tool on the same computer starts the server itself with `python server.py brands/my_brand`. The brand folder can also be an absolute path, such as `python server.py /srv/brands/my_brand`.
4. Or start it as a web address for an AI workspace: `python server.py brands/my_brand --http`. It answers at `http://127.0.0.1:8000/mcp`. Put it behind your company's own sign-in before anyone outside your network can reach it. The server has no sign-in of its own.
5. Add the server to your AI tool's list of MCP servers. For Claude Code: `claude mcp add -s user brand-brain -- python /full/path/server.py /full/path/brands/my_brand`. For Codex: `codex mcp add brand-brain -- python /full/path/server.py /full/path/brands/my_brand`. Then start a new session of the tool. The server tells the tool to call `get_strategy`, `get_rules` and `get_claims` before it writes, and `check_draft` when it is done.

## Plug in your own checkers

A brand that already has its own checks (a style linter, a design token check) names them in `brand.json`, per kind of draft:

```json
"roots": {"tools": "../../our-brand-tools"},
"checkers": {
  "text": [["python", "{tools}/style_check.py", "{file}"]],
  "page": [["python", "{tools}/design_check.py", "{file}"]],
  "narration": [["python", "{tools}/style_check.py", "{file}"]]
}
```

- `{file}` is the draft, written to a temporary file. `{brand}` is the brand folder. Each name in `roots` stands for that folder, resolved from the brand folder.
- A draft that starts with `<!doctype` or `<html` is checked as a page; anything else as text. The AI tool can name the kind itself. For `narration`, the server first takes out the voice marks of a spoken script: ` / ` and ` // ` for pauses, `*word*` for stress, and syllables in capitals as in `ad-VER-tising`.
- Each checker prints one JSON object:

```json
{"verdict": "fail",
 "failures": [{"rule": "voice", "found": "game-changer", "fix": "Name the firm, the price, the rule."}],
 "person_must_look": []}
```

- Any checker that answers `fail` makes the draft fail. A checker that crashes, prints something other than that JSON, or needs a root that is missing sends the draft to a person, with the reason.

## Test it

```
pip install pytest
python -m pytest
```

The tests start the server the way an AI tool does. `tests/test_example.py` calls each of the seven tools on `examples/alder_pipes/` and checks each answer, and checks that SETUP.md and `.gitignore` match. `tests/test_server_basics.py` runs 15 checks on the empty template, an invented brand (Alder Pipes) and stand-in checkers. `tests/test_strategy.py` runs 6 tests of `get_strategy`: the twelve terms in order, an empty term, an unknown term, a brand with no strategy file, and a small filled strategy with a resolved `ref` of each of the five kinds.

## Build or rent

A company can also rent a brand platform that offers the same kind of service. This repo is for a team that wants the rules in its own files and its own checks in the loop.

## License

Apache-2.0. Made by Prioric (prioric.dev).
