# songlinks

[![PyPI](https://img.shields.io/pypi/v/songlinks.svg)](https://pypi.org/project/songlinks/)
[![ci](https://github.com/Alexkane/songlinks-python/actions/workflows/ci.yml/badge.svg)](https://github.com/Alexkane/songlinks-python/actions/workflows/ci.yml)
[![licence: MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

**Find the songwriter behind a name.** The official Python SDK for [Songlinks](https://songlinks.io).

One songwriter is rarely one record. They're registered under different spellings, under several IPI name numbers, or
with no number at all. Songlinks groups those registrations into one person, shows the evidence for every join, and
keeps apart the ones it isn't sure of.

- **Free, with no key and no sign-up.**
- **Typed end to end.** Your editor knows every field of every answer, with a description of each, taken from the
  API's own description of itself.
- **Light.** The standard library, on Python 3.11 and later, plus `certifi` on macOS, used only when Python has no
  certificates of its own.
- **Built for real apps.** Clear errors, automatic retries when the API is busy, and long lists paged for you.

> **New to this?** Skip to [Your first program, step by step](#your-first-program-step-by-step): it starts from
> installing the language and ends with a working answer. The [words used here](#the-words-used-here) are explained too.

```sh
pip install git+https://github.com/Alexkane/songlinks-python
```

Not on PyPI yet; once it is, `pip install songlinks` will do the same.

## Thirty seconds

```python
from songlinks import Songlinks

songlinks = Songlinks(user_agent="my-app/1.0")

answer = songlinks.lookup("mark hoppus")
if answer["answer"] == "rejected":  # for example a one-word name, which matches too many people
    raise SystemExit(f"no answer: {answer['rejection']['code']}")
candidate = answer["candidates"][0]
print(candidate["persistent_id"], candidate["names"], candidate["works"])
# SLP-ZYM7-GD3E-S ['MARK HOPPUS'] 302

person = songlinks.person("SLP-ZYM7-GD3E-S", works_limit=3)
print([w["title"] for w in person["works_list"]["items"]])
# ['I MISS YOU', 'ALL THE SMALL THINGS', 'DOWN']

check = songlinks.writers(["00338980326", "00340247397"])
print([(w["name"], w["person_id"]) for w in check["writers"]])
# [('MARK HOPPUS', 'SLP-ZYM7-GD3E-S'), ('TRAVIS L BARKER', 'SLP-MG23-XM9B-Y')]
```

Every person has a page you can link to, such as [songlinks.io/person/SLP-ZYM7-GD3E-S](https://songlinks.io/person/SLP-ZYM7-GD3E-S).
It shows the registrations behind the person and what each join rests on.

> **Beta.** Unverified machine output, from a dated snapshot of registration data (a lookup's or a person's
> `provenance["mlc_snapshot"]` gives its date, and `version()` gives the current one). Some answers are wrong and some are incomplete. Not for rights or royalty decisions.

### More

```python
# Which of several writers with the same name wrote a song? Pass one of their songs.
answer = songlinks.lookup("amy allen", song="espresso")
print(answer["song_match"]["match"], answer["song_match"]["candidates"])
# exact ['c1']: the candidate whose "ref" is "c1" is the Amy Allen credited on that song

# Every work of a person, paged for you.
for work in songlinks.person_works("SLP-ZYM7-GD3E-S"):
    print(work["title"])
```

## Your first program, step by step

Never called an API from code before? This takes about five minutes.

**Before you start**, you need two things:

- **A terminal**, where you type commands. On a Mac, open Terminal (in Applications, then Utilities). On Windows, open
  PowerShell from the Start menu. Type each command below on its own line and press Enter after it.
- **A plain-text editor** for code, such as the free [Visual Studio Code](https://code.visualstudio.com). A word
  processor (Word, or TextEdit in its usual mode) adds formatting that stops code from running.
1. **Install Python** 3.11 or later from [python.org](https://www.python.org/downloads/), and **Git** from
   [git-scm.com](https://git-scm.com/downloads) (on a Mac, the first `git` command offers to install it: say yes).
   Check they worked by typing `python3 --version` (on Windows, `py --version`) and `git --version`.
2. **Make a folder for your project**, with its own Python environment (a "venv": a private copy of Python for this
   project, so what you install here stays here), and add the SDK to it.

   On a Mac or Linux:

   ```sh
   mkdir songlinks-test
   cd songlinks-test
   python3 -m venv .venv
   source .venv/bin/activate
   pip install git+https://github.com/Alexkane/songlinks-python
   ```

   On Windows, in PowerShell:

   ```powershell
   mkdir songlinks-test
   cd songlinks-test
   py -m venv .venv
   .venv\Scripts\activate
   pip install git+https://github.com/Alexkane/songlinks-python
   ```

   If PowerShell refuses to run `activate`, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then
   try again. (Once the SDK is on PyPI, `pip install songlinks` will do the same as the last line.)

   **Each time you open a new terminal**, go back into the folder and activate the environment again (`cd
   songlinks-test`, then the `activate` line) before running your program.
3. **Create a file** called `first.py` in the `songlinks-test` folder, in your editor, with this in it:

   ```python
   import sys

   from songlinks import Songlinks

   songlinks = Songlinks(user_agent="my-first-test/1.0")
   answer = songlinks.lookup(sys.argv[1] if len(sys.argv) > 1 else "mark hoppus")

   if answer["answer"] == "rejected":
       print("No answer, because:", answer["rejection"]["code"])
   else:
       for person in answer["candidates"]:
           print(person.get("persistent_id") or "(no person ID yet)", ", ".join(person["names"]), f"(works: {person['works']})")
   ```

   `user_agent` names your program to the API, so a problem can be traced to it; any short name will do.
   `sys.argv[1]` is the name you type after `first.py` in the next step.
4. **Run it**, from the same folder, with any songwriter's full name:

   ```sh
   python first.py "mark hoppus"
   ```

   You should see `SLP-ZYM7-GD3E-S MARK HOPPUS (works: 302)`.

   **Keep the quotes** around the name: without them, only the first word is sent.

   **What you might see instead:**
   - **Several lines.** The name could belong to more than one person, so each possible person gets a line.
   - **`(no person ID yet)`.** Songlinks found the registrations but hasn't given that person an ID yet. That is
     normal, and the rest of the line is still the answer.
   - **`No answer, because: single-token`.** The name is one word, such as `madonna`, which matches too many people.
     Use the full name.
   - **`No answer, because: no-match`.** Nothing registered is close to that name. Check the spelling.

From here, the [examples](#examples) do real jobs: download one from the
[examples folder on GitHub](https://github.com/Alexkane/songlinks-python/tree/main/examples) into your folder and
run it the same way. [Reading an answer](#reading-an-answer) explains what comes back, and the
[words used here](#the-words-used-here) are explained just below.

## The words used here

Music-publishing words, which you'll meet in the answers:

- **Songwriter registration**: when a song is written, its publisher registers it so royalties reach the people who
  wrote it. Each registration names the writers, as typed by whoever filed it. One songwriter can therefore appear
  under several spellings, and two different songwriters can share a name.
- **Record**: one of those registered writer entries: a name as it was typed, with its IPI name number if it has one,
  and the songs (works) registered under it.
- **IPI name number**: an 11-digit number that identifies a songwriter or publisher to collecting societies, such as
  `00338980326`. Many records have none, and one person can have several.
  [More about IPI name numbers](https://songlinks.io/guides/ipi-name-numbers).
- **Work**: a song as a composition (the melody and lyrics), as opposed to a particular recording of it.
- **ISWC**: the international code for a work, such as `T0719661581`. Not every registered work has one.
- **Person** and **person ID**: Songlinks groups the records it judges to be one human into a person and gives them a
  person ID, such as `SLP-ZYM7-GD3E-S`. Every person has a page, such as
  [songlinks.io/person/SLP-ZYM7-GD3E-S](https://songlinks.io/person/SLP-ZYM7-GD3E-S).
- **Candidate**: what a lookup by name returns: the records that name reaches, grouped into people for that one
  question. A candidate usually matches one person ID, but it is worked out fresh each time.
- **Evidence**: why two records were grouped: the same IPI name number, or a judgement that they are the same person
  (for example, the same co-writers and publishers).
- **Rejected**: a lookup that gave no candidates, with a reason, such as a one-word name (`madonna`) that matches too
  many people to group. It is an answer, not an error.

Programming words:

- **API**: a service that programs talk to over the internet. The Songlinks API answers questions such as "who is
  this songwriter?".
- **SDK**: this library. It does the talking to the API for you, so your code calls a function instead of building
  web requests by hand.
- **Rate limit**: the most requests the API accepts from one internet address in a stretch of time: about 100 every
  5 minutes, or 20 from VPNs and cloud servers. Over it, the SDK tells you how long to wait.
- **venv**: a private copy of Python for one project, so what you install there doesn't affect anything else.
- **pip**: the tool that downloads Python libraries, such as this one, into your venv.

## Checking a whole roster?

The API answers one name at a time, which suits an app. If you administer a catalogue, send us the writers instead.
For each one we send back every registration we can group to them, across spellings, stage names and more than one IPI
name number, with the evidence behind each join and the records we deliberately left out. See
[bulk songwriter lookup](https://songlinks.io/bulk-songwriter-lookup), or write to alex@songlinks.to.

## Examples

Runnable scripts for the jobs people use Songlinks for, each under 40 lines. Copy one and change it:

| Script | What it does |
| --- | --- |
| [`resolve_name.py`](examples/resolve_name.py) | Every person a name could be, with their registrations and what joined them. |
| [`which_namesake.py`](examples/which_namesake.py) | Two writers share a name: which one wrote this song? |
| [`check_roster.py`](examples/check_roster.py) | A CSV of IPI name numbers in, the same CSV out with who holds each and their works. |
| [`export_catalogue.py`](examples/export_catalogue.py) | Every work of a person, as CSV. |

```sh
python examples/check_roster.py roster.csv > checked.csv
```

The examples are type-checked with the package, so one that misreads a field fails the build.

## What it covers

| Method | API | What it answers |
| --- | --- | --- |
| `lookup(name, *, song=, threshold=, routes=)` | `GET /v1/lookup` | The people a songwriter's name could be. A `song` the writer wrote says which of them wrote it. |
| `person(id, *, works_offset=, works_limit=)` | `GET /v1/person/{id}` | One person: their registrations, names, IPI name numbers and a page of works. |
| `person_works(id, page_size=200)` | `GET /v1/person/{id}` | Every work of a person, as an iterator over the pages. |
| `writers(ipi_name_numbers)` | `GET /v1/writers` | Up to 50 IPI name numbers checked at once: the stored person behind each. |
| `version()` | `GET /v1/version` | What is serving: the release, the model and the date of the registration data. |

Answers are the API's JSON, parsed into ordinary dicts and lists, under the API's own field names. Store one with
`json.dumps`. Their types are in `songlinks.models` and exported from `songlinks` (`LookupResponse`, `PersonResponse`,
`Cluster`, `WritersResponse` and the rest). Two are renamed: the API's `Record` is `LookupRecord` and its `Error` is
`ApiError`. A field marked `NotRequired` may be absent; one typed `X | None` may be present and None. Read the first
with `.get()`.

### Reading an answer

A **person** and a **candidate** are different things: see [the words used here](#the-words-used-here).

- **A lookup candidate is not a stored person.** It is the lookup's own grouping, made for the name you asked.
  `persistent_id` is the stored person when there is exactly one. A candidate whose records belong to more than one
  stored person has no `persistent_id` and lists them in `stored_persons`. Read each record's own `persistent_id`.
- **A candidate can count more works than its person.** "mark hoppus" reaches two registrations, 302 works between
  them; the person `SLP-ZYM7-GD3E-S` holds one of them as theirs (294 works) and lists the other as `possible`.
  `person()` is the authority on what an ID holds.
- **None is ordinary.** Many records have no person ID yet.
- **Match a writers check by number, not position.** Repeats and two forms of one number come back as one entry, as
  11 digits. `normalize_ipi()` turns your input into the same form.
- **Person IDs can be prerelease.** A prerelease ID may stop resolving, or point at a different person, without notice.
  Check `prerelease` before you store one.

## Errors and retries

Every non-success answer raises a `SonglinksError` with the HTTP `status`, the API's `code` (its `error` field, the
one to branch on), a `message` for people, and the response `body`.

```python
from songlinks import PersonWithdrawnError, RateLimitedError, SonglinksError

# Continuing from the code above, where `songlinks` was created.
person_id = "SLP-0000-0000-0"  # an ID no one holds, to see the not-found branch
try:
    songlinks.person(person_id)
except PersonWithdrawnError as err:
    print("withdrawn", err.body)  # a 410, and a valid answer to keep
except RateLimitedError as err:
    print("retry in", err.retry_after_seconds, "s")
except SonglinksError as err:
    if err.code == "not_found":  # a 404, such as for SLP-0000-0000-0
        print("no person with that ID")
    else:
        print(err.status, err.code, err.message)
```

- **Retried automatically:** `429` and `503` answers and network failures, up to `max_retries` times (default 2).
  When the API asks for a wait (in a `Retry-After` header or the body's `retry_after_seconds`) of a minute or less,
  the client waits that long; otherwise it backs off from half a second.
- **Raised at once:** a requested wait longer than a minute, for you to schedule (`retry_after_seconds` on a 429).
- **Never retried:** any other error.
- **Merged person IDs** are followed to the person they now point at, and the answer's `redirected_from` names the
  ID you asked for.

## Options

```python
Songlinks(
    base_url="https://songlinks.io",  # the default
    timeout=30.0,  # seconds, per request
    max_retries=2,  # 0 turns retrying off
    user_agent="my-app/1.2",  # appended to songlinks-python/<version>
)
```

A client holds no connection and no state between calls, so one can be shared across threads.

## Fair use

The API is free and open. It allows about 100 requests per 5 minutes from one address, across every endpoint, and 20
from VPNs, proxies and hosting providers, which includes most cloud servers. Please send a `user_agent` that names your
app, keep to one request at a time per user action, and cache answers you reuse. Over the limit, the SDK raises a
`RateLimitedError` whose `retry_after_seconds` is the most you need to wait; for a whole roster, see
[bulk songwriter lookup](https://songlinks.io/bulk-songwriter-lookup).

## Links

- [API reference](https://songlinks.io/v1/docs), with every endpoint runnable from the page.
- [How Songlinks decides](https://songlinks.io/about): what a person ID is, and how registrations are grouped.
- [MCP server](https://songlinks.io/mcp-server): the same answers inside Claude or any MCP client.
- Something wrong in an answer? [Open an issue](https://github.com/Alexkane/songlinks-python/issues), or write to
  alex@songlinks.to.

## Development

```sh
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check . && .venv/bin/mypy   # lint, docstrings included, and strict types
.venv/bin/pytest                            # unit tests against a local server, and the docs' examples
SONGLINKS_LIVE=1 .venv/bin/pytest tests/test_live.py   # the same calls against songlinks.io
.venv/bin/pdoc songlinks -o docs            # the API documentation, as HTML
```

The types are generated: `curl -sf https://songlinks.io/v1/openapi.json -o tests/openapi.json`, then
`python3 scripts/gen_models.py`. `tests/test_models.py` fails if they drift from the document.
