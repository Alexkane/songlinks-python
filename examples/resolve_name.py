"""Who is this songwriter? Print each person a name could be, with the evidence.

python examples/resolve_name.py "mark hoppus"
"""

import sys

from songlinks import Songlinks

songlinks = Songlinks(user_agent="songlinks-example/1.0")
answer = songlinks.lookup(sys.argv[1] if len(sys.argv) > 1 else "mark hoppus")

if answer["answer"] == "rejected":
    # Not an error: the API explains why it gave no candidates, such as a name too common to group.
    rejection = answer.get("rejection")
    print("No answer:", rejection["code"] if rejection else "rejected")
    # nearest suggests registered names close to the one asked, when there are any.
    if rejection and rejection.get("nearest"):
        print("Did you mean:", ", ".join(rejection["nearest"]))
    sys.exit()

for person in answer.get("candidates", []):
    # persistent_id is None when no ID has been issued yet, which is common; the records are still the answer.
    pid = person.get("persistent_id") or "(no person ID yet)"
    print(f"{pid}  {', '.join(person['names'])}  {person['works']} works")
    for record in person["records"]:
        print(f"    {record['name']:<30} IPI {record.get('ipi_name_number') or '-':<12} {record['works']} works")
    rules = ", ".join(sorted({e["rule"] for e in person["evidence"]}))
    print(f"    joined by: {rules or 'nothing to join: one record'}")

# Pairs the model would not join are shown apart, never as part of a person.
if answer.get("review"):
    print(f"\n{len(answer['review'])} pair(s) held apart for review.")
