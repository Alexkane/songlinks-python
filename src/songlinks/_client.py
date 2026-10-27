"""The Songlinks client: one class over the API's public read endpoints, using only the standard library."""

from __future__ import annotations

import json
import random
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator, Sequence
from typing import Any, cast

from ._errors import PersonWithdrawnError, RateLimitedError, SonglinksError
from ._version import VERSION
from .models import (
    LookupResponse,
    PersonResponse,
    PersonWithdrawnResponse,
    PersonWork,
    SongwritersResponse,
    VersionResponse,
    WritersResponse,
)

WRITERS_MAX = 50
"""The most IPI name numbers `/v1/writers` accepts in one call."""

SONGWRITERS_MAX = 50
"""The most ISRCs `/v1/songwriters` accepts in one call."""

WORKS_PAGE_MAX = 200
"""The most works one person read returns; `Songlinks.person_works` pages through the rest."""

DEFAULT_BASE_URL = "https://songlinks.io"
"""The API's address."""

_RETRYABLE = {429, 503}

_MAX_WAIT_SECONDS = 60.0
"""The longest wait the client sleeps through before retrying; a longer one is raised to the caller at once."""


def normalize_ipi(ipi_name_number: str) -> str:
    """Write an IPI name number the way `Songlinks.writers` answers do, to match the answers to the numbers you sent.

    Spaces and dashes (including the typographic dashes a spreadsheet substitutes) are dropped, and a run of 1 to 11
    digits is padded with leading zeros to 11: `338980326` and `003-389-803 26` both become `00338980326`. Anything
    else is not an IPI name number, and is returned trimmed (to 32 characters), as the API echoes it with status
    `invalid`. A dot is not a separator: `15036818.0` is what a spreadsheet makes of a number read as a float, and
    dropping the dot would turn it into somebody else's number.

    Args:
        ipi_name_number: An IPI name number as you have it, such as `338980326` or `003-389-803-26`.

    Returns:
        The number as 11 digits, such as `00338980326`, or the trimmed input when it is not one.
    """
    # The same reading as the API's own (writer/service.py ipi_key).
    digits = re.sub(r"[\s\-\u2010-\u2015\u2212]", "", ipi_name_number)
    if re.fullmatch(r"[0-9]{1,11}", digits):
        return digits.zfill(11)
    return ipi_name_number.strip()[:32]


def normalize_isrc(isrc: str) -> str:
    """Write an ISRC the way `Songlinks.songwriters` answers do, to match the answers to the ISRCs you sent.

    Spaces and dashes are dropped and letters are upper-cased: `us-mc1-99-59123` and `USMC1 99 59123` both become
    `USMC19959123`. Anything that is then not an ISRC (two letters, three letters or digits, seven digits) is returned
    trimmed (to 32 characters), as the API echoes it with status `invalid`. Only the plain dash `-` is dropped: a
    typographic dash, such as the `–` a spreadsheet may substitute, makes the entry invalid, as it does for the API.

    Args:
        isrc: An ISRC as you have it, such as `USMC19959123` or `US-MC1-99-59123`.

    Returns:
        The ISRC as 12 characters, such as `USMC19959123`, or the trimmed input when it is not one.
    """
    # The same reading as the API's own (writer/work_pages.py isrc_key), character for character, so the answer's
    # `isrc` and this function agree on every input. That is why it is not stricter or kinder than the API: `\d`
    # matches any Unicode digit there too, and the typographic dashes normalize_ipi drops are kept.
    key = re.sub(r"[\s-]", "", isrc).upper()
    if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}\d{7}", key):
        return key
    return isrc.strip()[:32]


def _one_per_entry(method: str, what: str, entries: Sequence[str]) -> None:
    """Refuse an entry the API would read as several: it splits its list on `,`, `;`, line breaks and the text `%2C`."""
    for entry in entries:
        # The edges are trimmed first, as the API trims them, so a line from a Windows file (ending in \r) passes.
        inner = entry.strip()
        if any(c in inner for c in ",;\r\n") or "%2c" in inner.lower():
            raise ValueError(f"{method}() takes one {what} per entry, got {entry!r}")


class Songlinks:
    """The Songlinks API client. Create one and reuse it; it holds no connection and is safe to share between threads.

    Example:
        >>> from songlinks import Songlinks
        >>> songlinks = Songlinks(user_agent="my-app/1.0")
        >>> answer = songlinks.lookup("mark hoppus")
        >>> answer["candidates"][0]["persistent_id"]
        'SLP-ZYM7-GD3E-S'
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 2,
        user_agent: str | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        """Create a client.

        Args:
            base_url: The API's address. The default is https://songlinks.io.
            timeout: How long one request may take before it is abandoned, in seconds. The default is 30.
            max_retries: How many times a request is retried after a 429, a 503 or a network failure. The default
                is 2; 0 turns retrying off. An answer asking for a wait longer than a minute is not retried: it is
                raised at once.
            user_agent: Your app's name and version, such as `my-app/1.2`, added to each request's User-Agent after
                the SDK's own.
            ssl_context: The TLS settings to connect with, such as a context trusting a company proxy's certificate.
                The default trusts the system's certificates.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = f"songlinks-python/{VERSION}" + (f" {user_agent}" if user_agent else "")
        self.ssl_context = ssl_context or _default_context()

    def lookup(
        self,
        name: str,
        *,
        song: str | None = None,
        threshold: float | None = None,
        routes: Sequence[str] | None = None,
    ) -> LookupResponse:
        """Look up a songwriter by name.

        Args:
            name: A songwriter's full name, such as `mark hoppus`. A single word, such as `madonna`, is answered with
                `answer` `rejected` (code `single-token`), since one word matches too many people to group.
            song: The title of a song the writer wrote. When given, the answer's `song_match` says which candidates
                hold a work with that title.
            threshold: How sure Songlinks must be before it joins two records into one person, from 0.5 to 0.99.
                Higher joins fewer records and keeps more apart. The API's default is `version()["threshold"]`
                (0.85 today).
            routes: Extra searches to run beside the name match. The one there is, `"catalogue"`, also finds records
                registered under another name that share the writer's catalogue, such as a stage name, and returns
                them in `links`. It runs by default; `[]` skips it, and the lookup is faster.

        Returns:
            The people the name could be, each with the registrations behind them. Check `answer` first.

        Raises:
            ValueError: When the name is empty.
            SonglinksError: When the API answers with an error, such as `invalid_request` for a threshold out of
                range.
        """
        if not name.strip():
            raise ValueError("lookup() needs a name")
        query = {"name": name}
        if song:
            query["song"] = song
        if threshold is not None:
            query["threshold"] = str(threshold)
        if routes is not None:
            # The API reads an empty `routes` as "use the default", so no routes at all is spelt `none`.
            query["routes"] = ",".join(routes) if routes else "none"
        return cast(LookupResponse, self._get("/v1/lookup", query))

    def person(
        self, person_id: str, *, works_offset: int | None = None, works_limit: int | None = None
    ) -> PersonResponse:
        """Read a person by ID, with one page of their works.

        A merged ID is followed to the person it now points at, and the answer's `redirected_from` names the ID you
        asked for.

        Args:
            person_id: A person ID, such as `SLP-ZYM7-GD3E-S`.
            works_offset: The position of the first work to return, from 0. The first page when left out.
            works_limit: How many works to return, from 1 to 200. The API returns 100 when it is left out.

        Returns:
            The stored person: their registrations, names, IPI name numbers and a page of works.

        Raises:
            ValueError: When the person ID is empty.
            PersonWithdrawnError: When the ID has been withdrawn.
            SonglinksError: When the API answers with any other error, such as `not_found` for an unknown ID.
        """
        # An empty ID would ask for /v1/person/, which is a different route and answers a bare 404.
        if not person_id.strip():
            raise ValueError("person() needs a person ID")
        query = {}
        if works_offset is not None:
            query["works_offset"] = str(works_offset)
        if works_limit is not None:
            query["works_limit"] = str(works_limit)
        return cast(PersonResponse, self._get(f"/v1/person/{urllib.parse.quote(person_id, safe='')}", query))

    def person_works(self, person_id: str, page_size: int = WORKS_PAGE_MAX) -> Iterator[PersonWork]:
        """Read every work of a person, in the API's order.

        Pages are requested only as the loop asks for more, so stopping early stops the requests.

        Args:
            person_id: A person ID, such as `SLP-ZYM7-GD3E-S`.
            page_size: How many works to request at a time, from 1 to 200. The default is 200.

        Yields:
            The person's works, one at a time.

        Raises:
            SonglinksError: When the API answers with an error while the works are read.
        """
        offset: int | None = 0
        while offset is not None:
            page = self.person(person_id, works_offset=offset, works_limit=page_size)
            yield from page["works_list"]["items"]
            offset = page["works_list"].get("next_offset")

    def writers(self, ipi_name_numbers: Sequence[str]) -> WritersResponse:
        """Check up to 50 IPI name numbers at once.

        The API refuses a longer list rather than shortening it, and so does this method: for more, call it once for
        each batch of `WRITERS_MAX`.

        The answer has one entry per distinct number, in the order each was first sent, written as 11 digits. Two
        forms of one number (`338980326` and `00338980326`) and repeats come back as one entry, so match answers to
        your list by number, not by position: `normalize_ipi` turns your input into the form the answer uses.

        Args:
            ipi_name_numbers: The numbers to check. Leading zeros may be left off, and spaces and dashes are ignored.

        Returns:
            For each distinct number, the person who holds it and a status, with totals in `summary`.

        Raises:
            TypeError: When given one string rather than a list of them, or an entry that is not a string.
            ValueError: When the list is empty, holds more than 50 numbers, or has an entry holding a comma,
                semicolon, line break or the text `%2C` (which the API would read as several numbers).
            SonglinksError: When the API answers with an error.
        """
        # A bare string is a Sequence[str] too, and would be sent one digit per number.
        if isinstance(ipi_name_numbers, str):
            raise TypeError("writers() takes a list of IPI name numbers, not one string")
        if not ipi_name_numbers:
            raise ValueError("writers() needs at least one IPI name number")
        if len(ipi_name_numbers) > WRITERS_MAX:
            raise ValueError(f"writers() takes at most {WRITERS_MAX} IPI name numbers per call")
        for n in ipi_name_numbers:
            if not isinstance(n, str):
                raise TypeError(
                    f"writers() takes IPI name numbers as text, got {n!r}: an int would lose its leading zeros"
                )
        _one_per_entry("writers", "IPI name number", ipi_name_numbers)
        return cast(WritersResponse, self._get("/v1/writers", {"ipi": ",".join(ipi_name_numbers)}))

    def songwriters(self, isrcs: Sequence[str]) -> SongwritersResponse:
        """Find who wrote up to 50 recordings at once, by ISRC.

        For each recording: the works (songs) it is registered to, the writers registered on each work, and each
        writer's person ID where they have one, which `person()` reads for everything else they wrote. Publishers are
        left out.

        The API refuses a longer list rather than shortening it, and so does this method: for more, call it once for
        each batch of `SONGWRITERS_MAX`.

        The answer has one entry per distinct ISRC, in the order each was first sent, written as 12 characters in
        upper case with no dashes. Two forms of one ISRC (`US-MC1-99-59123` and `usmc19959123`) and repeats come back
        as one entry, so match answers to your list by ISRC, not by position: `normalize_isrc` turns your input into
        the form the answer uses.

        Each entry's `status` is `registered` (its `works` are listed), `unregistered` (no work in the registration
        data names this recording, which is an answer, not an error) or `invalid` (not an ISRC; the entry echoes what
        you sent, and the rest of the list is still answered).

        Args:
            isrcs: The ISRCs to look up, such as `["USMC19959123"]`. Case does not matter, and spaces and dashes are
                ignored.

        Returns:
            For each distinct ISRC, its status and the works it is registered to, with their writers.

        Raises:
            TypeError: When given one string rather than a list of them, or an entry that is not a string.
            ValueError: When the list is empty, holds more than 50 entries (repeats included), or has an entry
                holding a comma, semicolon, line break or the text `%2C` (which the API would read as several ISRCs).
            SonglinksError: When the API answers with an error.
        """
        # A bare string is a Sequence[str] too, and would be sent one character per ISRC.
        if isinstance(isrcs, str):
            raise TypeError("songwriters() takes a list of ISRCs, not one string")
        if not isrcs:
            raise ValueError("songwriters() needs at least one ISRC")
        # The API counts after folding repeats, so it would take a longer list with repeats in it; this counts what
        # was passed, as writers() does, so whether a call is refused never depends on how the API reads the entries.
        if len(isrcs) > SONGWRITERS_MAX:
            raise ValueError(f"songwriters() takes at most {SONGWRITERS_MAX} ISRCs per call")
        for isrc in isrcs:
            if not isinstance(isrc, str):
                raise TypeError(f"songwriters() takes ISRCs as text, got {isrc!r}")
        _one_per_entry("songwriters", "ISRC", isrcs)
        return cast(SongwritersResponse, self._get("/v1/songwriters", {"isrc": ",".join(isrcs)}))

    def version(self) -> VersionResponse:
        """Ask what is serving.

        Returns:
            The API's release, the model and code in use, and the date of the registration data.

        Raises:
            SonglinksError: When the API answers with an error.
        """
        return cast(VersionResponse, self._get("/v1/version", {}))

    def _get(self, path: str, query: dict[str, str]) -> Any:
        url = self.base_url + path + ("?" + urllib.parse.urlencode(query) if query else "")
        request = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": self.user_agent}, method="GET"
        )
        attempt = 0
        while True:
            try:
                # urllib follows the 307/308 a merged person ID answers with, re-sending the same GET.
                with urllib.request.urlopen(request, timeout=self.timeout, context=self.ssl_context) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as err:
                body = _read_json(err)
                retry_after = _retry_after(err.headers.get("Retry-After"), body)
                # A wait longer than a minute (the edge's rate limit asks for up to five) is the caller's to
                # schedule, not something to block on inside one call, so it is raised at once.
                waitable = retry_after is None or retry_after <= _MAX_WAIT_SECONDS
                if err.code in _RETRYABLE and attempt < self.max_retries and waitable:
                    time.sleep(_backoff(attempt, retry_after))
                    attempt += 1
                    continue
                raise _to_error(err.code, body, retry_after) from None
            except urllib.error.URLError as err:
                # A certificate that cannot be checked fails the same way every time, so it is not retried; the note
                # says how to fix the machine, since the usual cause is a Python with no certificates installed.
                if isinstance(err.reason, ssl.SSLCertVerificationError):
                    err.add_note(_CERT_HINT)
                    raise
                if attempt < self.max_retries:
                    time.sleep(_backoff(attempt, None))
                    attempt += 1
                    continue
                raise
            except (TimeoutError, ConnectionError):
                # HTTPError is a URLError and was handled above, so this is a network failure or a timeout:
                # retried like a 503, then re-raised as it was.
                if attempt < self.max_retries:
                    time.sleep(_backoff(attempt, None))
                    attempt += 1
                    continue
                raise


_CERT_HINT = (
    "Python could not check the API's certificate. On macOS with Python from python.org, run "
    "'Install Certificates.command' in the Python folder under Applications, or `pip install certifi`."
)


def _default_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    # Python from python.org on macOS ships with no certificates loaded, so every HTTPS call fails until its
    # "Install Certificates" step is run. When the context holds none and certifi is installed, certifi's are added.
    # Adding never removes what the system trusts, so a company's own certificates still work; it runs only then
    # because elsewhere the system's list is the one to trust. (A system that keeps its certificates in a directory,
    # read only when needed, also counts 0 here, and gets certifi's added beside them, which is harmless.)
    if context.cert_store_stats()["x509_ca"] == 0:
        try:
            import certifi

            context.load_verify_locations(certifi.where())
        except ImportError:
            pass
    return context


def _read_json(err: urllib.error.HTTPError) -> Any:
    try:
        return json.loads(err.read())
    except (ValueError, OSError):
        return None


def _to_error(status: int, body: Any, retry_after: float | None) -> SonglinksError:
    b = body if isinstance(body, dict) else {}
    message = b["message"] if isinstance(b.get("message"), str) else f"HTTP {status}"
    # 422 is FastAPI's validation answer: no `error` or `message`, but a `detail` list saying which parameter was
    # wrong and why. Its first entry becomes the message, so threshold=2 reads "threshold: Input should be less than
    # or equal to 0.99" rather than "HTTP 422".
    detail = b.get("detail")
    if status == 422 and isinstance(detail, list) and detail and isinstance(detail[0], dict):
        loc, msg = detail[0].get("loc"), detail[0].get("msg")
        if isinstance(msg, str):
            message = f"{loc[-1]}: {msg}" if isinstance(loc, list) and loc else msg
    if status == 429:
        return RateLimitedError(message, body, retry_after)
    if status == 410 and "person_id" in b:
        return PersonWithdrawnError(cast(PersonWithdrawnResponse, body))
    code = b["error"] if isinstance(b.get("error"), str) else "invalid_request" if status == 422 else f"http_{status}"
    return SonglinksError(status, code, message, body)


def _retry_after(header: str | None, body: Any) -> float | None:
    """The wait the API asked for, in seconds: the Retry-After header, or else the body's `retry_after_seconds`.

    The edge's rate limit answers with the body only (its 429 carries no header), so reading the header alone would
    retry a five-minute limit after half a second. Only the delta-seconds form of the header is read: the API never
    sends an HTTP date.
    """
    try:
        seconds = float(header) if header else None
    except ValueError:
        seconds = None
    if seconds is None and isinstance(body, dict):
        value = body.get("retry_after_seconds")
        seconds = float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
    return seconds if seconds is not None and seconds >= 0 else None


def _backoff(attempt: int, retry_after: float | None) -> float:
    """The API's requested wait when it gives one; else 0.5 s, 1 s, 2 s ... with jitter."""
    if retry_after is not None:
        return retry_after
    return 0.5 * 2.0**attempt * random.uniform(0.75, 1.25)
