"""Who wrote these recordings? A CSV of ISRCs in, one row per writer out, with the person ID behind each.

    python examples/recording_writers.py recordings.csv > writers.csv

The input is a CSV with an `isrc` column (other columns are passed through). ISRCs are sent 50 at a time, the most
the API takes in one call. A recording with no registered work, or an entry that is not an ISRC, gets one row with
its status and the writer columns empty.
"""

import csv
import sys

from songlinks import SONGWRITERS_MAX, RecordingAnswer, Songlinks, normalize_isrc

songlinks = Songlinks(user_agent="songlinks-example/1.0")
with open(sys.argv[1], newline="") as f:
    rows = list(csv.DictReader(f))

answers: dict[str, RecordingAnswer] = {}
for start in range(0, len(rows), SONGWRITERS_MAX):
    # A blank cell is left out: a batch of nothing but blanks is an error from the API, not an empty answer.
    batch = [row["isrc"].strip() for row in rows[start : start + SONGWRITERS_MAX] if row["isrc"].strip()]
    for recording in songlinks.songwriters(batch)["recordings"] if batch else []:
        answers[recording["isrc"]] = recording

out = csv.writer(sys.stdout)
out.writerow(
    [*(rows[0].keys() if rows else ["isrc"]), "status", "title", "iswc", "writer", "writer_ipi", "role", "person_id"]
)
for row in rows:
    # The answer writes each ISRC as 12 characters, upper case, with repeats merged, so look yours up in that form.
    r = answers.get(normalize_isrc(row["isrc"].strip()))
    status = r["status"] if r else ""
    written = [(work, w) for work in (r.get("works", []) if r else []) for w in work["writers"]]
    if not written:  # unregistered or invalid: one row, the writer columns left empty
        out.writerow([*row.values(), status])
    for work, w in written:
        found = [work.get("title"), work.get("iswc"), w.get("name"), w.get("ipi_name_number"), w["role"]]
        out.writerow([*row.values(), status, *found, w.get("persistent_id")])
