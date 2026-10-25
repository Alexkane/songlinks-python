# songlinks

[![PyPI](https://img.shields.io/pypi/v/songlinks.svg)](https://pypi.org/project/songlinks/)
[![ci](https://github.com/Alexkane/songlinks-python/actions/workflows/ci.yml/badge.svg)](https://github.com/Alexkane/songlinks-python/actions/workflows/ci.yml)
[![licence: MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

**Find the songwriter behind a name.** The official Python SDK for [Songlinks](https://songlinks.io).

One songwriter is rarely one record. They're registered under different spellings, under several IPI name numbers, or
with no number at all. Songlinks groups those registrations into one person, shows the evidence for every join, and
keeps apart the ones it isn't sure of.

- **Free, with no key and no sign-up.**
- **Typed end to end.** Every answer is described by a `TypedDict` generated from the API's own OpenAPI document, so
  your editor and mypy know every field.
- **No dependencies.** The standard library only, on Python 3.11 and later.
- **Built to be called from real apps.** Typed errors, retries that honour `Retry-After`, and paging done for you.

```sh
pip install songlinks
```

## Thirty seconds

```python
from songlinks import Songlinks

songlinks = Songlinks(user_agent="my-app/1.0")

answer = songlinks.lookup("mark hoppus")
best = answer["candidates"][0]
print(best["persistent_id"], best["names"], best["works"])
# SLP-ZYM7-GD3E-S ['MARK HOPPUS'] 302

person = songlinks.person("SLP-ZYM7-GD3E-S", works_limit=3)
print([w["title"] for w in person["works_list"]["items"]])
# ['I MISS YOU', 'ALL THE SMALL THINGS', 'DOWN']

check = songlinks.writers(["00338980326", "00340247397"])
# one entry per IPI name number: MARK HOPPUS (SLP-ZYM7-GD3E-S), TRAVIS L BARKER (SLP-MG23-XM9B-Y)
```

Every person has a page you can link to, such as [songlinks.io/person/SLP-ZYM7-GD3E-S](https://songlinks.io/person/SLP-ZYM7-GD3E-S).
It shows the registrations behind the person and what each join rests on.

> **Beta.** Unverified machine output, from a dated snapshot of registration data (every answer's `mlc_snapshot`
> gives its date). Some answers are wrong and some are incomplete. Not for rights or royalty decisions.

### More

```python
# Which of several writers with the same name wrote a song? Pass one of their songs.
answer = songlinks.lookup("amy allen", song="espresso")
print(answer["song_match"]["match"], answer["song_match"]["candidates"])
# exact ['c1']: the Amy Allen credited on that song

# Every work of a person, paged for you.
for work in songlinks.person_works("SLP-ZYM7-GD3E-S"):
    print(work["title"])
```

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

- **A lookup candidate is not a stored person.** It is the lookup's own grouping, made for the name you asked.
  `persistent_id` is the stored person when there is exactly one. A candidate whose records belong to more than one
  stored person has no `persistent_id` and lists them in `stored_persons`. Read each record's own `persistent_id`.
- **None is ordinary.** Many records have no person ID yet.
- **Person IDs can be prerelease.** A prerelease ID may stop resolving, or point at a different person, without notice.
  Check `prerelease` before you store one.

## Errors and retries

Every non-success answer raises a `SonglinksError` with the HTTP `status`, the API's `code` (its `error` field, the
one to branch on), a `message` for people, and the response `body`.

```python
from songlinks import PersonWithdrawnError, RateLimitedError, SonglinksError

try:
    songlinks.person("SLP-0000-0000-0")
except PersonWithdrawnError as err:
    print("withdrawn", err.body)  # a 410, and a valid answer to keep
except RateLimitedError as err:
    print("retry in", err.retry_after_seconds, "s")
except SonglinksError as err:
    print(err.status, err.code, err.message)
```

- **Retried automatically:** `429` and `503` answers and network failures, up to `max_retries` times (default 2). A
  `Retry-After` header is honoured, up to a minute; otherwise it backs off from half a second.
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

The API is free and open. Please send a `user_agent` that names your app, keep to one request at a time per user
action, and cache answers you reuse. A burst of lookups may be rate-limited.

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
