"""The official Python SDK for the Songlinks API: find the songwriter behind a name.

    >>> from songlinks import Songlinks
    >>> songlinks = Songlinks(user_agent="my-app/1.0")
    >>> songlinks.lookup("mark hoppus")["candidates"][0]["names"]
    ['MARK HOPPUS']

`Songlinks` is the client. Its answers are the API's JSON as parsed dicts, typed by the classes in `songlinks.models`;
errors are raised as `SonglinksError` and its subclasses.
"""

from ._client import DEFAULT_BASE_URL, WORKS_PAGE_MAX, WRITERS_MAX, Songlinks
from ._errors import PersonWithdrawnError, RateLimitedError, SonglinksError
from ._version import VERSION
from .models import (
    ApiError,
    BuildRef,
    Cluster,
    Evidence,
    Link,
    LookupRecord,
    LookupResponse,
    PersonEvent,
    PersonProvenance,
    PersonRecord,
    PersonResponse,
    PersonWithdrawnResponse,
    PersonWork,
    Provenance,
    Query,
    RateLimit,
    RateLimited,
    Rejection,
    ReviewItem,
    SongBeyond,
    SongMatch,
    SongRecord,
    VersionResponse,
    WorksPage,
    WriterAnswer,
    WritersResponse,
    WritersSummary,
)

__version__ = VERSION

__all__ = [
    "DEFAULT_BASE_URL",
    "VERSION",
    "WORKS_PAGE_MAX",
    "WRITERS_MAX",
    "ApiError",
    "BuildRef",
    "Cluster",
    "Evidence",
    "Link",
    "LookupRecord",
    "LookupResponse",
    "PersonEvent",
    "PersonProvenance",
    "PersonRecord",
    "PersonResponse",
    "PersonWithdrawnError",
    "PersonWithdrawnResponse",
    "PersonWork",
    "Provenance",
    "Query",
    "RateLimit",
    "RateLimited",
    "RateLimitedError",
    "Rejection",
    "ReviewItem",
    "SongBeyond",
    "SongMatch",
    "SongRecord",
    "Songlinks",
    "SonglinksError",
    "VersionResponse",
    "WorksPage",
    "WriterAnswer",
    "WritersResponse",
    "WritersSummary",
]
