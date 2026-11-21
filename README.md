# Brand server

A small MCP server that keeps one brand's rules, approved files and approved claims. A company's own AI tools ask it before they write or design anything for the brand, and send it each draft for a check.

MCP (Model Context Protocol) is an open standard. An AI tool that speaks it can call the tools of a server like this one.

The repo is brand-neutral. You fill in your own brand in `brand_template/brand.json`.

## Who it is for

A brand team at a company that already works inside an AI workspace under its own enterprise contract. Staff, partners and agencies write with AI there every day. The server puts the brand rules inside that workspace, so each AI tool reads the same rules and the brand team sees how the rules are used.

## The six tools

| Tool | What it answers |
|---|---|
| `get_rules` | Which brand rules apply to this job, for this audience and country. Each rule names its source. |
| `find_asset` | Which logo, color, typeface or template to use. Only approved values come back. |
| `get_claims` | Which claims are approved, each with the public page that proves it. Expired claims are left out. |
| `check_draft` | Whether a draft passes: `pass`, `fail` with each broken rule named, or `person_must_look` with the sentences a person must read. |
| `request_exception` | Sends a hard case to the owner of that rule area and returns a ticket number. |
| `usage_report` | How often each tool ran and which rules failed most, for the brand team. |

The server writes every call to `{brand}/log/calls.jsonl`, with the rules version and the result.

## What `check_draft` tests

Built in, for every brand:

- the brand name, against the ways never to write it;
- banned phrases;
- color values in a text, against the approved palette;
- claim sentences, against the approved claims (a sentence matches a claim when it uses 60% of the claim's words and adds no number);
- an optional limit on a word, such as puns on the brand's mascot.

A person judges tone, pictures, layout and logo placement. The server lists these under `not_tested` in every answer. It also lists claims written without any of the brand's claim words, because those slip past the claim test.

Your own checkers plug in on top (see below).

## Set it up

You need Python 3.11 or later.

```
pip install "mcp==2.3.0"
```

1. Copy `brand_template` to a folder named after your brand, such as `my_brand`.
2. Fill `my_brand/brand.json`. The `_about` block at its top says what goes in each slot.
3. Start the server for an AI tool on the same computer: `python server.py my_brand`.
4. Or start it as a web address for an AI workspace: `python server.py my_brand --http`. Put it behind your company's own sign-in before anyone outside your network can reach it. The server has no sign-in of its own.
5. Add the server to your AI tool's list of MCP servers. The server tells the tool to call `get_rules` and `get_claims` before it writes, and `check_draft` when it is done.

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
python tests/test_server_basics.py
```

It starts the server the way an AI tool does and runs 14 checks on the empty template, an invented brand (Alder Pipes) and stand-in checkers.

## Build or rent

A company can also rent a brand platform that offers the same kind of service. This repo is for a team that wants the rules in its own files and its own checks in the loop.

## License

Apache-2.0. Made by Prioric (prioric.dev).
