#!/usr/bin/env python3
"""Generate src/songlinks/models.py from the API's OpenAPI document.

    curl -sf https://songlinks.io/v1/openapi.json -o tests/openapi.json
    python3 scripts/gen_models.py

One TypedDict per response schema, fields in the API's order and under the API's own JSON names. A TypedDict rather
than a dataclass because the client hands back the parsed JSON as it came: a field the API adds later is simply there,
never a parse error, and a caller can still `json.dumps` an answer to store it. A field the API may leave out is
`NotRequired`; one it may send as null is `X | None`, and the two are different things.

Each field's docstring is the API's own description of it, made into sentences. tests/test_models.py checks the
generated file against the same document, so a regenerated spec that drifts from it fails the build.
"""

from __future__ import annotations

import json
import keyword
import os
import re
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "tests", "openapi.json")
OUT = os.path.join(ROOT, "src", "songlinks", "models.py")
SITE = "https://songlinks.io"
WIDTH = 120

# The schemas a client reads, and their Python names. Two are renamed, as in the TypeScript and Java SDKs: `Record`
# reads as a generic word in a signature, and `Error` would sit beside the SDK's own SonglinksError and invite the
# wrong `except`. The JSON is unchanged. Request-side and FastAPI's validation schemas are left out: the client
# reports a 422 as a SonglinksError.
NAMES = {
    "LookupResponse": "LookupResponse",
    "Query": "Query",
    "Cluster": "Cluster",
    "Record": "LookupRecord",
    "Evidence": "Evidence",
    "ReviewItem": "ReviewItem",
    "Link": "Link",
    "Rejection": "Rejection",
    "Provenance": "Provenance",
    "SongMatch": "SongMatch",
    "SongRecord": "SongRecord",
    "SongBeyond": "SongBeyond",
    "RateLimit": "RateLimit",
    "PersonResponse": "PersonResponse",
    "PersonRecord": "PersonRecord",
    "PersonWork": "PersonWork",
    "WorksPage": "WorksPage",
    "PersonEvent": "PersonEvent",
    "PersonProvenance": "PersonProvenance",
    "BuildRef": "BuildRef",
    "PersonWithdrawnResponse": "PersonWithdrawnResponse",
    "WritersResponse": "WritersResponse",
    "WriterAnswer": "WriterAnswer",
    "WritersSummary": "WritersSummary",
    "VersionResponse": "VersionResponse",
    "Error": "ApiError",
    "RateLimited": "RateLimited",
}

# Where the API's wording names its own query parameters, the Python reader needs the method to call. Keyed by
# (schema, field); everything else is the API's description.
OVERRIDES = {
    ("WorksPage", "next_offset"): "The offset to ask for next, as `Songlinks.person(id, works_offset=...)`, or None "
    "on the last page. `Songlinks.person_works(id)` reads every page for you.",
    ("PersonResponse", "works_list"): "One page of works. For the next page, pass `works_list['next_offset']` to "
    "`Songlinks.person(id, works_offset=...)`, or read them all with `Songlinks.person_works(id)`.",
}


def sentence(text: str) -> str:
    """Make the API's description prose: one line, capitalised, closed, with site-relative links made absolute."""
    t = re.sub(r"\s+", " ", str(text)).strip()
    if not t:
        return t
    t = re.sub(r"\[([^\]]+)\]\((/[^)\s]*)\)", lambda m: f"[{m[1]}]({SITE}{m[2]})", t)
    # The API describes its JSON; a Python reader meets those values as None, True and False.
    t = re.sub(r"\b[Nn]ull\b", "None", t)
    t = re.sub(r"\btrue\b", "True", t)
    t = re.sub(r"\bfalse\b", "False", t)
    t = t[0].upper() + t[1:]
    return t if t[-1] in ".!?" else t + "."


def py_type(prop: dict) -> str:
    if "$ref" in prop:
        return NAMES[prop["$ref"].rsplit("/", 1)[-1]]
    if "anyOf" in prop:
        kinds = [p for p in prop["anyOf"] if p.get("type") != "null"]
        inner = " | ".join(py_type(p) for p in kinds) if kinds else "Any"
        nullable = len(kinds) < len(prop["anyOf"])
        return f"{inner} | None" if nullable else inner
    kind = prop.get("type")
    if kind == "array":
        return f"list[{py_type(prop.get('items', {}))}]"
    if kind == "object":
        extra = prop.get("additionalProperties")
        return f"dict[str, {py_type(extra)}]" if isinstance(extra, dict) and extra else "dict[str, Any]"
    return {"integer": "int", "number": "float", "boolean": "bool", "string": "str"}.get(kind, "Any")


def refs(schema: dict) -> set[str]:
    found = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if "$ref" in node:
                found.add(node["$ref"].rsplit("/", 1)[-1])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return found & NAMES.keys()


def ordered(schemas: dict) -> list[str]:
    # Referenced schemas first, so every annotation names a class that already exists. The file has no
    # `from __future__ import annotations` on purpose: under it, Python 3.11's TypedDict reads NotRequired inside a
    # string annotation as required, and `__required_keys__` would be wrong at runtime.
    seen: list[str] = []

    def visit(name: str) -> None:
        if name in seen:
            return
        for dep in sorted(refs(schemas[name])):
            if dep != name:
                visit(dep)
        seen.append(name)

    for name in NAMES:
        visit(name)
    return seen


def docstring(text: str, indent: str) -> list[str]:
    body = textwrap.wrap(
        text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"'),
        WIDTH - len(indent) - 6,
        break_on_hyphens=False,  # never split YYYY-MM-DD or a hyphenated word across lines
        break_long_words=False,  # nor an escaped backslash, which at a line end would join the lines
    )
    if len(body) == 1:
        return [f'{indent}"""{body[0]}"""']
    return [f'{indent}"""{body[0]}', *(f"{indent}{line}" for line in body[1:]), f'{indent}"""']


def class_docstring(summary: str, attrs: list[str]) -> list[str]:
    lines = textwrap.wrap(
        summary.replace("\\", "\\\\").replace('"""', '\\"\\"\\"'),
        WIDTH - 10,
        break_on_hyphens=False,
        break_long_words=False,
    )
    out = [f'    """{lines[0]}', *(f"    {line}" for line in lines[1:])]
    if attrs:
        out += ["", "    Attributes:"]
        for a in attrs:
            wrapped = textwrap.wrap(
                a.replace("\\", "\\\\").replace('"""', '\\"\\"\\"'),
                WIDTH - 12,
                break_on_hyphens=False,
                break_long_words=False,
            )
            out += [f"        {wrapped[0]}", *(f"            {w}" for w in wrapped[1:])]
    return out + ['    """']


def render(spec: dict) -> str:
    schemas = spec["components"]["schemas"]
    out = [
        '"""The Songlinks API\'s response types, one per schema in its OpenAPI document.',
        "",
        "Each is a `TypedDict`: the client returns the API's JSON as parsed, and these describe it, field for field,",
        "under the API's own names. Generated by scripts/gen_models.py; do not edit by hand.",
        '"""',
        "",
        "from typing import Any, NotRequired, TypedDict",
        "",
        "__all__ = [",
        *(f'    "{NAMES[n]}",' for n in NAMES),
        "]",
    ]
    for source in ordered(schemas):
        schema = schemas[source]
        name = NAMES[source]
        required = set(schema.get("required", []))
        out += ["", "", f"class {name}(TypedDict):"]
        summary = sentence(schema.get("description") or f"The API's {source} schema.")
        # The fields again, as a Google-style Attributes section: help() and most editors read only the class
        # docstring, not the per-field docstrings below it (which pdoc and Pylance do read). One line per field, so
        # the section stays a scannable list.
        attrs = []
        for field, prop in schema.get("properties", {}).items():
            text = OVERRIDES.get((source, field)) or sentence(prop.get("description") or "")
            attrs.append(f"{field} ({attr_kind(prop, field in required)}): {first_sentence(text)}")
        out += class_docstring(summary, attrs)
        for field, prop in schema.get("properties", {}).items():
            if keyword.iskeyword(field) or not field.isidentifier():
                raise SystemExit(f"{source}.{field} cannot be a TypedDict field name; use the functional syntax")
            kind = py_type(prop)
            out += ["", f"    {field}: {kind if field in required else f'NotRequired[{kind}]'}"]
            text = OVERRIDES.get((source, field)) or sentence(prop.get("description") or "")
            if not text:
                raise SystemExit(f"{source}.{field} has no description in the API's document")
            out += docstring(text, "    ")
    return "\n".join(out) + "\n"


def attr_kind(prop: dict, required: bool) -> str:
    return py_type(prop) if required else f"{py_type(prop)}, may be absent"


def first_sentence(text: str) -> str:
    """The Attributes line for a field: its first sentence, or all of it when the sentences list its values.

    A description such as "`person`: one person holds this number. `several`: ... `none`: ..." lists one value per
    sentence; cutting it after the first would read as if `person` were the only value.
    """
    if text.startswith("`") or text.count("`: ") > 1:
        return text
    first = re.split(r"(?<=[.!?]) ", text)[0]
    # An abbreviation would end the "sentence" early, mid-thought; nothing in today's document has one, so this
    # guards a regenerated one rather than handling it.
    if re.search(r"\b(e\.g|i\.e|vs|etc)\.$", first):
        raise SystemExit(f"first sentence ends in an abbreviation, which the Attributes split would cut: {first!r}")
    return first


if __name__ == "__main__":
    with open(SPEC) as f:
        text = render(json.load(f))
    with open(OUT, "w") as f:
        f.write(text)
