"""A stand-in checker for the result-rule tests. Its answer is the first word of the draft."""
import json
import sys

word = open(sys.argv[1], encoding="utf-8").read().split()[0]
if word == "crash":
    sys.exit(3)
if word == "garbage":
    print("this is not json")
    sys.exit(0)
print(json.dumps({"verdict": word, "failures": [{"rule": "stub", "found": word, "fix": "none"}] if word == "fail" else [],
                  "person_must_look": [{"sentence": word, "why": "stub"}] if word == "person_must_look" else []}))
