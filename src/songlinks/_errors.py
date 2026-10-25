"""The exceptions the client raises when the API answers with an error."""

from __future__ import annotations

from typing import Any

from .models import PersonWithdrawnResponse


class SonglinksError(Exception):
    """Raised when the API answers with an error.

    Branch on `code`, the API's own error code; the message is a sentence meant for people, and its wording may change.

    Attributes:
        status: The HTTP status of the answer, such as 404 or 503.
        code: The API's error code, such as `not_found`, `busy` or `too_many`.
        message: The API's message, or a description of the failure when it sent none.
        body: The answer's body as parsed JSON, or None when it had none.
    """

    def __init__(self, status: int, code: str, message: str, body: Any = None) -> None:
        """Create the exception for one error answer.

        Args:
            status: The HTTP status.
            code: The API's error code.
            message: The API's message, or a description of the failure when it sent none.
            body: The answer's body, or None.
        """
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.body = body


class RateLimitedError(SonglinksError):
    """Raised when the API refuses a request because the caller is over a limit (HTTP 429).

    The client retries these itself, waiting as long as the API asks, and raises this only when its retries run out.

    Attributes:
        retry_after_seconds: How long the API asked the caller to wait, in seconds, or None when it did not say.
    """

    def __init__(self, message: str, body: Any = None, retry_after_seconds: float | None = None) -> None:
        """Create the exception for a 429 answer.

        Args:
            message: The API's message.
            body: The answer's body, or None.
            retry_after_seconds: How long the API asked the caller to wait, or None.
        """
        super().__init__(429, "rate_limited", message, body)
        self.retry_after_seconds = retry_after_seconds


class PersonWithdrawnError(SonglinksError):
    """Raised when a person ID has been withdrawn (HTTP 410).

    The API still answers in full: `body` says when the ID was issued and withdrawn, and gives its history. It is a
    valid answer to keep.

    Attributes:
        body: The API's answer about the withdrawn ID.
    """

    body: PersonWithdrawnResponse

    def __init__(self, body: PersonWithdrawnResponse) -> None:
        """Create the exception for a 410 answer.

        Args:
            body: The API's answer about the withdrawn ID.
        """
        super().__init__(410, "withdrawn", f"Person {body['person_id']} was withdrawn", body)
