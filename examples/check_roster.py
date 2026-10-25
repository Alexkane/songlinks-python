"""Check a roster of IPI name numbers: who holds each, and how many works they have.

    python examples/check_roster.py roster.csv > checked.csv

The input is a CSV with an `ipi` column (other columns are passed through). Numbers are sent 50 at a time, the most
the API takes in one call.
"""

import csv
import sys

from songlinks import WRITERS_MAX, Songlinks, WriterAnswer

songlinks = Songlinks(user_agent="songlinks-example/1.0")
with open(sys.argv[1], newline="") as f:
    rows = list(csv.DictReader(f))

answers: dict[str, WriterAnswer] = {}
for start in range(0, len(rows), WRITERS_MAX):
    batch = [row["ipi"].strip() for row in rows[start : start + WRITERS_MAX]]
    for writer in songlinks.writers(batch)["writers"]:
        answers[writer["ipi_name_number"]] = writer

out = csv.DictWriter(sys.stdout, [*rows[0].keys(), "status", "person_id", "name", "works"] if rows else ["ipi"])
out.writeheader()
for row in rows:
    # The API answers with the number in its full 11-digit form, so look it up the same way.
    w = answers.get(row["ipi"].strip().zfill(11))
    if w is None:
        out.writerow(row)
        continue
    out.writerow(
        {**row, "status": w["status"], "person_id": w.get("person_id"), "name": w.get("name"), "works": w.get("works")}
    )
