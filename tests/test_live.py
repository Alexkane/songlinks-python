"""The same calls against songlinks.io. Run with SONGLINKS_LIVE=1; skipped otherwise, so CI never depends on it."""

import os

import pytest

from songlinks import Songlinks

pytestmark = pytest.mark.skipif(os.environ.get("SONGLINKS_LIVE") != "1", reason="set SONGLINKS_LIVE=1")
HOPPUS = "SLP-ZYM7-GD3E-S"


@pytest.fixture(scope="module")
def songlinks() -> Songlinks:
    return Songlinks(user_agent="songlinks-python-tests")


def test_lookup(songlinks: Songlinks) -> None:
    answer = songlinks.lookup("mark hoppus")
    assert answer["answer"] == "candidates"
    assert any(c.get("persistent_id") == HOPPUS for c in answer.get("candidates", []))


def test_person_and_every_work(songlinks: Songlinks) -> None:
    person = songlinks.person(HOPPUS, works_limit=3)
    assert len(person["works_list"]["items"]) == 3
    works = list(songlinks.person_works(HOPPUS, page_size=100))
    assert len(works) == person["works_list"]["total"]


def test_writers_and_version(songlinks: Songlinks) -> None:
    check = songlinks.writers(["00338980326"])
    assert check["writers"][0].get("person_id") == HOPPUS
    assert songlinks.version()["version"]
