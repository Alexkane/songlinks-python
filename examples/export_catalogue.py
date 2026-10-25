"""Export every work of a person to CSV.

python examples/export_catalogue.py SLP-ZYM7-GD3E-S > works.csv
"""

import csv
import sys

from songlinks import Songlinks

songlinks = Songlinks(user_agent="songlinks-example/1.0")
person_id = sys.argv[1] if len(sys.argv) > 1 else "SLP-ZYM7-GD3E-S"

out = csv.writer(sys.stdout)
out.writerow(["mlc_work_id", "title", "iswc"])
# person_works pages through the API 200 works at a time; nothing here needs to know about pages.
for work in songlinks.person_works(person_id):
    out.writerow([work["mlc_work_id"], work["title"], work.get("iswc") or ""])
