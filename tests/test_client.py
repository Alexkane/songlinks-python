"""The client against a local HTTP server that answers from a script."""

import http.server
import json
import threading
import urllib.parse
from collections.abc import Iterator
from typing import Any

import pytest

from songlinks import (
    WRITERS_MAX,
    PersonWithdrawnError,
    RateLimitedError,
    Songlinks,
    SonglinksError,
    _client,
)

Reply = tuple[int, dict[str, str], Any]


class Server:
    """Answers each request with the next scripted reply, and records what was asked."""

    def __init__(self) -> None:
        self.replies: list[Reply] = []
        self.requests: list[tuple[str, dict[str, list[str]], dict[str, str]]] = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - the name http.server calls
                url = urllib.parse.urlsplit(self.path)
                outer.requests.append((url.path, urllib.parse.parse_qs(url.query), dict(self.headers)))
                status, headers, body = outer.replies.pop(0)
                data = b"" if body is None else json.dumps(body).encode()
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Iterator[Server]:
    s = Server()
    waits: list[float] = []
    monkeypatch.setattr(_client.time, "sleep", waits.append)
    s.waits = waits  # type: ignore[attr-defined]
    yield s
    s.httpd.shutdown()


def client(server: Server, **kw: Any) -> Songlinks:
    return Songlinks(base_url=server.url, **kw)


def test_lookup_sends_the_name_and_options(server: Server) -> None:
    server.replies.append((200, {}, {"answer": "candidates"}))
    answer = client(server, user_agent="my-app/1.0").lookup("mark hoppus", song="down", threshold=0.8, routes=[])
    assert answer == {"answer": "candidates"}
    path, query, headers = server.requests[0]
    assert path == "/v1/lookup"
    assert query == {"name": ["mark hoppus"], "song": ["down"], "threshold": ["0.8"], "routes": ["none"]}
    assert headers["User-Agent"].startswith("songlinks-python/") and headers["User-Agent"].endswith(" my-app/1.0")


def test_lookup_leaves_unset_options_to_the_api(server: Server) -> None:
    server.replies.append((200, {}, {}))
    client(server).lookup("amy allen")
    assert server.requests[0][1] == {"name": ["amy allen"]}


def test_person_quotes_the_id_and_pages(server: Server) -> None:
    server.replies.append((200, {}, {"person_id": "SLP-1"}))
    client(server).person("SLP/../x", works_offset=200, works_limit=50)
    path, query, _ = server.requests[0]
    assert path == "/v1/person/SLP%2F..%2Fx"
    assert query == {"works_offset": ["200"], "works_limit": ["50"]}


def test_a_merged_id_is_followed(server: Server) -> None:
    server.replies.append((308, {"Location": "/v1/person/SLP-NEW"}, None))
    server.replies.append((200, {}, {"person_id": "SLP-NEW", "redirected_from": "SLP-OLD"}))
    assert client(server).person("SLP-OLD")["redirected_from"] == "SLP-OLD"
    assert [r[0] for r in server.requests] == ["/v1/person/SLP-OLD", "/v1/person/SLP-NEW"]


def test_person_works_reads_every_page_and_stops_when_asked(server: Server) -> None:
    page = lambda items, nxt: (200, {}, {"works_list": {"items": items, "next_offset": nxt}})  # noqa: E731
    server.replies += [page([{"title": "A"}, {"title": "B"}], 2), page([{"title": "C"}], None)]
    assert [w["title"] for w in client(server).person_works("SLP-1", page_size=2)] == ["A", "B", "C"]
    assert [r[1]["works_offset"] for r in server.requests] == [["0"], ["2"]]

    server.requests.clear()
    server.replies += [page([{"title": "A"}], 1)]
    works = client(server).person_works("SLP-1")
    next(works)
    assert len(server.requests) == 1, "a page is fetched only when the loop needs it"


def test_writers_joins_the_list_and_refuses_a_bad_one(server: Server) -> None:
    server.replies.append((200, {}, {"writers": []}))
    client(server).writers(["338980326", "00340247397"])
    assert server.requests[0][1] == {"ipi": ["338980326,00340247397"]}
    with pytest.raises(ValueError):
        client(server).writers([])
    with pytest.raises(ValueError):
        client(server).writers(["1"] * (WRITERS_MAX + 1))
    with pytest.raises(TypeError):
        client(server).writers("00338980326")  # type: ignore[arg-type]
    for bad in ["338980326,00340247397", "338980326;1", "338980326\n1", "338980326%2C1"]:
        with pytest.raises(ValueError):
            client(server).writers([bad])
    with pytest.raises(TypeError):
        client(server).writers([338980326])  # type: ignore[list-item]


def test_writers_accepts_a_line_from_a_windows_file(server: Server) -> None:
    server.replies.append((200, {}, {"writers": []}))
    client(server).writers(["338980326\r"])
    assert len(server.requests) == 1


def test_an_error_carries_the_apis_code(server: Server) -> None:
    server.replies.append((404, {}, {"error": "not_found", "message": "No person with that ID."}))
    with pytest.raises(SonglinksError) as caught:
        client(server).person("SLP-0")
    err = caught.value
    assert (err.status, err.code, err.message, str(err)) == (404, "not_found", "No person with that ID.", err.message)


def test_a_validation_error_is_invalid_request(server: Server) -> None:
    server.replies.append((422, {}, {"detail": [{"msg": "bad"}]}))
    with pytest.raises(SonglinksError) as caught:
        client(server).lookup("x", threshold=2)
    assert (caught.value.code, caught.value.message) == ("invalid_request", "bad")


def test_a_withdrawn_person_raises_with_the_apis_answer(server: Server) -> None:
    body = {"person_id": "SLP-W", "state": "withdrawn", "history": []}
    server.replies.append((410, {}, body))
    with pytest.raises(PersonWithdrawnError) as caught:
        client(server).person("SLP-W")
    assert caught.value.body == body and caught.value.code == "withdrawn"


def test_a_503_is_retried_then_succeeds(server: Server) -> None:
    server.replies += [(503, {}, {"error": "busy", "message": "Busy."}), (200, {}, {"ok": 1})]
    assert client(server).version() == {"ok": 1}
    assert len(server.requests) == 2 and 0.375 <= server.waits[0] <= 0.625  # type: ignore[attr-defined]


def test_a_429_waits_retry_after_and_raises_when_retries_run_out(server: Server) -> None:
    limited = (429, {"Retry-After": "7"}, {"error": "rate_limited", "message": "Slow down."})
    server.replies += [limited, limited]
    with pytest.raises(RateLimitedError) as caught:
        client(server, max_retries=1).version()
    assert caught.value.retry_after_seconds == 7.0
    assert server.waits == [7.0]  # type: ignore[attr-defined]


def test_a_wait_longer_than_a_minute_is_raised_at_once(server: Server) -> None:
    server.replies.append((429, {"Retry-After": "3600"}, None))
    with pytest.raises(RateLimitedError) as caught:
        client(server).version()
    assert caught.value.retry_after_seconds == 3600.0 and len(server.requests) == 1


def test_the_edges_429_has_its_wait_only_in_the_body(server: Server) -> None:
    body = {"error": "rate_limited", "message": "Too many", "retry_after_seconds": 300}
    server.replies.append((429, {}, body))
    with pytest.raises(RateLimitedError) as caught:
        client(server).version()
    assert caught.value.retry_after_seconds == 300.0 and len(server.requests) == 1


def test_a_503_asking_for_more_than_a_minute_is_raised_at_once(server: Server) -> None:
    server.replies.append((503, {"Retry-After": "120"}, {"error": "busy", "message": "Busy."}))
    with pytest.raises(SonglinksError) as caught:
        client(server).version()
    assert (caught.value.status, caught.value.code, len(server.requests)) == (503, "busy", 1)


def test_the_header_wins_over_the_body(server: Server) -> None:
    server.replies += [(429, {"Retry-After": "2"}, {"retry_after_seconds": 300}), (200, {}, {})]
    client(server).version()
    assert server.waits == [2.0]  # type: ignore[attr-defined]


def test_a_short_wait_in_the_body_is_waited_out(server: Server) -> None:
    server.replies += [(429, {}, {"retry_after_seconds": 5}), (200, {}, {})]
    client(server).version()
    assert server.waits == [5.0]  # type: ignore[attr-defined]


def test_a_422_says_which_parameter_was_wrong(server: Server) -> None:
    detail = [{"loc": ["query", "threshold"], "msg": "Input should be less than or equal to 0.99"}]
    server.replies.append((422, {}, {"detail": detail}))
    with pytest.raises(SonglinksError) as caught:
        client(server).lookup("x y", threshold=2)
    assert caught.value.message == "threshold: Input should be less than or equal to 0.99"


def test_an_empty_name_or_id_is_refused_before_any_request(server: Server) -> None:
    with pytest.raises(ValueError):
        client(server).lookup(" ")
    with pytest.raises(ValueError):
        client(server).person("")
    assert server.requests == []


def test_normalize_ipi_writes_a_number_the_way_the_answer_does() -> None:
    from songlinks import normalize_ipi

    assert normalize_ipi("338980326") == "00338980326"
    assert normalize_ipi("003-389-803 26") == "00338980326"
    assert normalize_ipi("\t003\u2013389803 26") == "00338980326"  # a tab and an en dash
    assert normalize_ipi(" abc ") == "abc"  # invalid: echoed trimmed, as the API does
    assert normalize_ipi("003\u00a0389\u00a0803\u00a026") == "00338980326"  # non-breaking spaces
    assert normalize_ipi("15036818.0") == "15036818.0"
    assert normalize_ipi("123456789012") == "123456789012"


def test_other_errors_are_not_retried(server: Server) -> None:
    server.replies.append((400, {}, {"error": "bad_request", "message": "No."}))
    with pytest.raises(SonglinksError):
        client(server).version()
    assert len(server.requests) == 1


def test_a_network_failure_is_retried_then_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    monkeypatch.setattr(_client.time, "sleep", waits.append)
    # Nothing listens on port 9 here, so every attempt is refused.
    with pytest.raises(OSError):
        Songlinks(base_url="http://127.0.0.1:9", max_retries=2, timeout=2).version()
    assert len(waits) == 2


def test_a_certificate_failure_is_not_retried_and_says_how_to_fix_it(monkeypatch: pytest.MonkeyPatch) -> None:
    import ssl
    import urllib.error

    calls: list[object] = []

    def refuse(*args: Any, **kw: Any) -> Any:
        calls.append(args)
        raise urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))

    monkeypatch.setattr(_client.urllib.request, "urlopen", refuse)
    with pytest.raises(urllib.error.URLError) as caught:
        Songlinks(max_retries=2).version()
    assert len(calls) == 1
    assert "Install Certificates" in caught.value.__notes__[0]
