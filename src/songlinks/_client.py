"""The Songlinks client: one class over the API's public read endpoints, using only the standard library."""

from __future__ import annotations

import json
import random
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
    VersionResponse,
    WritersResponse,
)

WRITERS_MAX = 50
"""The most IPI name numbers `/v1/writers` accepts in one call."""

WORKS_PAGE_MAX = 200
"""The most works one person read returns; `Songlinks.person_works` pages through the rest."""

DEFAULT_BASE_URL = "https://songlinks.io"
"""The API's address."""

_RETRYABLE = {429, 503}


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
                is 2; 0 turns retrying off.
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
            name: A songwriter's full name, such as `mark hoppus`.
            song: The title of a song the writer wrote. When given, the answer's `song_match` says which candidates
                hold a work with that title.
            threshold: How sure the model must be before it joins two records, from 0.5 to 0.99. The API decides
                when it is left out.
            routes: Extra routes to run. `["catalogue"]`, the API's default, also returns records registered under
                another name; `[]` skips that, and the lookup is faster.

        Returns:
            The people the name could be, each with the registrations behind them. Check `answer` first.

        Raises:
            SonglinksError: When the API answers with an error.
        """
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
            works_limit: How many works to return, from 1 to 200.

        Returns:
            The stored person: their registrations, names, IPI name numbers and a page of works.

        Raises:
            PersonWithdrawnError: When the ID has been withdrawn.
            SonglinksError: When the API answers with any other error, such as `not_found`.
        """
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

        Args:
            ipi_name_numbers: The numbers to check; leading zeros may be left off.

        Returns:
            For each number, in the order sent, the stored person who holds it and a status.

        Raises:
            ValueError: When the list is empty or holds more than 50 numbers.
            SonglinksError: When the API answers with an error.
        """
        # A bare string is a Sequence[str] too, and would be sent one digit per number.
        if isinstance(ipi_name_numbers, str):
            raise TypeError("writers() takes a list of IPI name numbers, not one string")
        if not ipi_name_numbers:
            raise ValueError("writers() needs at least one IPI name number")
        if len(ipi_name_numbers) > WRITERS_MAX:
            raise ValueError(f"writers() takes at most {WRITERS_MAX} IPI name numbers per call")
        return cast(WritersResponse, self._get("/v1/writers", {"ipi": ",".join(ipi_name_numbers)}))

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
                retry_after = _parse_retry_after(err.headers.get("Retry-After"))
                if err.code in _RETRYABLE and attempt < self.max_retries:
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
    # "Install Certificates" step is run. When the system gave none and certifi is installed, use certifi's. Only
    # then: certifi replaces the system's list, which would drop a company's own certificates where they exist.
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
    if status == 429:
        return RateLimitedError(message, body, retry_after)
    if status == 410 and "person_id" in b:
        return PersonWithdrawnError(cast(PersonWithdrawnResponse, body))
    # 422 is FastAPI's validation answer, with `detail` rather than `error`.
    code = b["error"] if isinstance(b.get("error"), str) else "invalid_request" if status == 422 else f"http_{status}"
    return SonglinksError(status, code, message, body)


def _parse_retry_after(value: str | None) -> float | None:
    # Only the delta-seconds form: the API never sends an HTTP date, and a value it cannot read is treated as absent.
    try:
        seconds = float(value) if value else None
    except ValueError:
        return None
    return seconds if seconds is not None and seconds >= 0 else None


def _backoff(attempt: int, retry_after: float | None) -> float:
    """Retry-After when the API gives one, capped at a minute; else 0.5 s, 1 s, 2 s ... with jitter."""
    if retry_after is not None:
        return min(retry_after, 60.0)
    return 0.5 * 2.0**attempt * random.uniform(0.75, 1.25)
