"""Two writers share a name: which one wrote this song?

python examples/which_namesake.py "amy allen" "espresso"
"""

import sys

from songlinks import Songlinks

name, song = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("amy allen", "espresso")
songlinks = Songlinks(user_agent="songlinks-example/1.0")
answer = songlinks.lookup(name, song=song)

match = answer.get("song_match")
if not match or not match.get("candidates"):
    print(f"No one called {name!r} in this answer has a work titled {song!r}.")
    sys.exit()

# song_match names candidates by their `ref` (c1, c2 ...), which is only meaningful inside this one answer.
by_ref = {c["ref"]: c for c in answer.get("candidates", [])}
print(f"{song!r}: {match['match']} title match")
for ref in match["candidates"]:
    person = by_ref[ref]
    print(f"  {person.get('persistent_id') or ref}  {', '.join(person['names'])}  IPI {person['ipi_name_numbers']}")
