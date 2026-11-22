# Set up Brand BrAIn

This file is for the AI tool. The person opens their AI tool in this folder and says: "Read SETUP.md and set up Brand BrAIn for me." The AI tool then follows the steps below in order.

`{repo}` is the folder this file sits in. Write it as a full path in every command, so the commands work from any folder.

When the person only wants to try Brand BrAIn first, use the invented brand in `{repo}/examples/alder_pipes/`: ask questions 1 to 3, skip question 4 and steps 3 to 7, and write `examples/alder_pipes` wherever the steps say `brands/{folder}`.

## How to ask

- Ask one question per message. Wait for the answer before the next one.
- Test what you can test yourself before you ask.
- Ask for a yes before you install anything, change the AI tool's settings or start a program.
- Copy the brand's own words into the brand files. Never write a rule, a claim or a strategy line the person's files or answers do not give.

## The four questions

1. **Which AI tool are you using?** Claude Code, Codex, or another. Claude Code and Codex have tested steps below. Any other tool gets a JSON block that most MCP tools read, and the person hears that this path is untested.

2. **Is Python 3.11 or later installed?** Do not ask first. Run `python --version`, then `python3 --version`, then `py --version`. Use the first command that prints 3.11 or later, and call it `{python}` below. Ask only when all three fail or print an older version. Then tell the person to install Python from python.org, and stop.

3. **Should Brand BrAIn run on this computer, or as a web address?**
   - On this computer: the AI tool starts Brand BrAIn itself, each time a session starts. This is the default.
   - As a web address: Brand BrAIn runs as a small web server at `http://127.0.0.1:8000/mcp`, so an AI workspace can reach it. Say to the person: "Brand BrAIn has no sign-in. Before anyone outside this computer can reach it, put it behind your company's own sign-in."

4. **What is the brand called?** Make the folder name from it: lowercase, words joined by `_`, such as `alder_pipes`. Call it `{folder}` below.

## Then do these steps

1. Write `{repo}/brands/setup.md` with the date and the four answers, in a small table: AI tool, Python command, this computer or web address, brand name, folder.
2. Ask for a yes, then run `{python} -m pip install "mcp==2.3.0"`.
3. Copy `{repo}/brand_template/` to `{repo}/brands/{folder}/`. Git ignores the `brands/` folder, so a company's brand files never land in a commit of this repo.
4. Ask in one message: "Where do the brand's rules, colors, logos and claims live today? Name the files or web pages, or say none." Read what the person names.
5. Fill `{repo}/brands/{folder}/brand.json`. The `_about` block at its top says what goes in each slot. Take each value from the files you read. Where the files say nothing, ask the person, one slot per message, or leave the slot empty. Delete the `_about` block at the end.
   - The test of wrong names is case-sensitive: `Alder pipes` in `names.wrong` fails that spelling and passes `Alder Pipes`.
   - An asset's `file` is a path from the brand folder, or a web address. A file named in the brand's guide may be listed before it is copied in.
   - A rule that fits two areas goes in the area of the person who owns it, such as legal for a word legal asked to drop.
6. Fill `{repo}/brands/{folder}/brand_strategy.json` the same way: copy the strategy lines the person's files hold into each term's `entries`. When the brand has no written strategy, leave every term empty. `{repo}/examples/alder_pipes/` shows both files filled for an invented brand.
7. Show the person what you filled, slot by slot, and ask for a yes.
8. Add Brand BrAIn to the AI tool, after a yes. Use the line for the person's tool and choice:

   | AI tool | On this computer | As a web address |
   |---|---|---|
   | Claude Code | `claude mcp add -s user brand-brain -- {python} {repo}/server.py {repo}/brands/{folder}` | `claude mcp add --transport http brand-brain http://127.0.0.1:8000/mcp` |
   | Codex | `codex mcp add brand-brain -- {python} {repo}/server.py {repo}/brands/{folder}` | `codex mcp add brand-brain --url http://127.0.0.1:8000/mcp` |
   | Another tool (untested) | the JSON block below | the address `http://127.0.0.1:8000/mcp` |

   ```json
   {"mcpServers": {"brand-brain": {"command": "{python}", "args": ["{repo}/server.py", "{repo}/brands/{folder}"]}}}
   ```

   `-s user` makes Claude Code see Brand BrAIn in every folder. Codex always does.

   Codex asks for a yes before each Brand BrAIn call, and refuses every call when it runs with no person to ask, as in `codex exec`. To let Codex call the server without asking, add this line under `[mcp_servers.brand-brain]` in `~/.codex/config.toml`, after the person's yes: `default_tools_approval_mode = "approve"`.

   For a web address, also start the server and leave it running: `{python} {repo}/server.py {repo}/brands/{folder} --http`.
9. Test the brand files: run `{python} {repo}/server.py {repo}/brands/{folder} --check`. A good start prints one line that begins `Brand BrAIn ready:` with the brand name and the count of rules, claims and colors. On an error, show it and fix the brand file it names.
10. Tell the person:
    - "Start a new session of your AI tool. A tool reads its list of servers when a session starts."
    - "In the new session, ask: Use brand-brain. Call get_rules, then check this sentence: {a sentence copied from the brand's own files}."
    - "A person still judges tone, pictures, layout and logo placement. Brand BrAIn tests only what a machine can test."

## When something fails

- `pip` is missing: run `{python} -m ensurepip`, then step 2 again.
- The server says `brand.json` is missing: the folder name in the command is wrong. Check `{repo}/brands/`.
- The server stops on a JSON error: the error names a line in a brand file. Fix that line, then start again.
- `claude mcp add` or `codex mcp add` fails: show the error. Most often the tool may not write its own settings file; the person runs the same line in a terminal.
- The AI tool does not list `brand-brain` in a new session: run `claude mcp list` or `codex mcp list`, and add it again from step 8.
