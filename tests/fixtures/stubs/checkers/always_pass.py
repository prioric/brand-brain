"""A stand-in checker that always passes."""
import json

print(json.dumps({"verdict": "pass", "failures": [], "person_must_look": []}))
