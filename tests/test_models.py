"""The generated types against the API's document, and real answers against the types."""

import ast
import json
import pathlib
import sys
import types
import typing

import pytest

from songlinks import models

HERE = pathlib.Path(__file__).parent
SPEC = json.loads((HERE / "openapi.json").read_text())["components"]["schemas"]
sys.path.insert(0, str(HERE.parent / "scripts"))
from gen_models import NAMES  # noqa: E402


def fixture(name: str) -> typing.Any:
    return json.loads((HERE / "fixtures" / name).read_text())


@pytest.mark.parametrize("source", sorted(NAMES))
def test_every_type_matches_its_schema(source: str) -> None:
    cls = getattr(models, NAMES[source])
    schema = SPEC[source]
    assert list(cls.__annotations__) == list(schema["properties"]), "fields, in the API's order"
    assert cls.__required_keys__ == set(schema.get("required", []))


def test_every_type_and_field_has_a_docstring() -> None:
    # The docs are the point of the types: a field without its description is a regression, not a style nit.
    tree = ast.parse(pathlib.Path(models.__file__).read_text())
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        assert ast.get_docstring(cls), cls.name
        body = cls.body[1:]
        for i, node in enumerate(body):
            if isinstance(node, ast.AnnAssign):
                nxt = body[i + 1] if i + 1 < len(body) else None
                assert isinstance(nxt, ast.Expr) and isinstance(nxt.value, ast.Constant), f"{cls.name}.{node.target}"
                text = nxt.value.value
                # A sentence opens with a capital or with a quoted value, such as `model`: ...
                assert (text[0].isupper() or text[0] == "`") and text.rstrip()[-1] in ".!?", f"{cls.name}: {text!r}"
                assert "null" not in text.split(), f"{cls.name}: say None, not null: {text!r}"


def conforms(value: typing.Any, hint: typing.Any, path: str) -> None:
    """Check a parsed answer against a type: every required key present, every value of a declared type."""
    origin = typing.get_origin(hint)
    if origin is typing.NotRequired:
        return conforms(value, typing.get_args(hint)[0], path)
    if origin in (typing.Union, types.UnionType):
        errors = []
        for arm in typing.get_args(hint):
            try:
                return conforms(value, arm, path)
            except AssertionError as err:
                errors.append(str(err))
        raise AssertionError(f"{path}: {value!r} fits none of {hint}: {errors}")
    if hint is type(None):
        assert value is None, path
    elif hint is typing.Any:
        pass
    elif typing.is_typeddict(hint):
        assert isinstance(value, dict), path
        missing = hint.__required_keys__ - value.keys()
        assert not missing, f"{path}: missing {missing}"
        fields = typing.get_type_hints(hint, include_extras=True)
        for key, item in value.items():
            # A key the types don't know is allowed: the API may add fields before the SDK is regenerated.
            if key in fields:
                conforms(item, fields[key], f"{path}.{key}")
    elif origin is list:
        assert isinstance(value, list), path
        for i, item in enumerate(value):
            conforms(item, typing.get_args(hint)[0], f"{path}[{i}]")
    elif origin is dict:
        assert isinstance(value, dict), path
    elif hint is float:
        assert isinstance(value, int | float) and not isinstance(value, bool), path
    else:
        assert isinstance(value, hint) and not (hint is int and isinstance(value, bool)), f"{path}: {value!r}"


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("lookup.json", models.LookupResponse),
        ("lookup-two-persons.json", models.LookupResponse),
        ("person.json", models.PersonResponse),
        ("writers.json", models.WritersResponse),
        ("version.json", models.VersionResponse),
    ],
)
def test_real_answers_fit_the_types(name: str, kind: typing.Any) -> None:
    conforms(fixture(name), kind, name)


def test_conformance_check_catches_a_wrong_answer() -> None:
    # The check above would pass vacuously if it never failed; prove it can.
    answer = fixture("person.json")
    answer["works"] = "many"
    with pytest.raises(AssertionError):
        conforms(answer, models.PersonResponse, "person")
    del answer["person_id"]
    with pytest.raises(AssertionError):
        conforms(answer, models.PersonResponse, "person")
