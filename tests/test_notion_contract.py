"""Offline reference adapter contract; no real Notion workspace is exercised."""
import uuid
from validation import STATES, choice, typed, validate_gathered

DATES = ("created", "completed", "canceled", "reopened")


def mock_adapter(fetch, identity, status_map):
    """fetch(kind, full_id, cursor) supplies connector-shaped paginated responses."""
    tickets, unknown = [], []

    def full_id(value):
        return str(uuid.UUID(value))  # never accept a shortened display identifier

    def pages(kind, identifier):
        cursor, seen = None, set()
        while True:
            response = fetch(kind, full_id(identifier), cursor)
            yield from typed(response["results"], list, "notion.results")
            if response["has_more"] is False:
                return
            cursor = response["next_cursor"]
            if not cursor or cursor in seen:
                raise ValueError("notion: pagination did not advance")
            seen.add(cursor)

    def emit(row, block=False):
        raw = row["checked"] if block else row.get("status")
        state = ("done" if raw else "open") if block else status_map.get(raw)
        if state is None:
            unknown.append(f"notion: unknown status {raw!r}")
            state = "open"
        choice(state, STATES, "notion.state")
        identifier = full_id(row["id"])
        dates = {field: row.get(field) for field in DATES}
        tickets.append(dict(id=identifier[:8], source="notion", source_id=identifier,
                            page_id=full_id(identity["page_id"]) if block else identifier,
                            url="https://www.notion.so/" + identifier.replace("-", ""),
                            title=row["title"], raw_status=raw, state=state, **dates,
                            date_availability={field: bool(dates[field]) for field in DATES}))

    def children(identifier):
        for block in pages("children", identifier):
            if block["type"] == "code":
                continue
            if block["type"] == "to_do":
                emit(block, True)
            if block.get("has_children"):
                children(block["id"])

    if "data_source_id" in identity:
        full_id(identity["database_id"])
        for row in pages("query", identity["data_source_id"]):
            emit(row)
    else:
        children(identity["page_id"])
    source = dict(identity, run_id="mock-run", attempted_at="2026-10-06T00:00:00Z",
                  fetched_at="2026-10-06T00:00:00Z" if not unknown else None,
                  status="partial" if unknown else "ok", complete=not unknown,
                  error="; ".join(unknown) or None,
                  date_coverage={field: dict(known=sum(t["date_availability"][field] for t in tickets),
                                             total=len(tickets)) for field in DATES})
    output = {"_run": {"run_id": "mock-run"}, "p": dict(sources={"notion": source},
              tickets=tickets, read=["notion"], errors=unknown)}
    inv = {"projects": [{"key": "p", "nodes": []}]}
    return validate_gathered(output, inv)


def test_notion_adapter_contract():
    uid = lambda n: str(uuid.UUID(int=n))
    calls = []
    def fetch(kind, identifier, cursor):
        calls.append((kind, identifier, cursor))
        return responses[(kind, identifier, cursor)]
    page = lambda rows, more=False, cursor=None: dict(results=rows, has_more=more, next_cursor=cursor)
    row = lambda n, status: dict(id=uid(n), title="Task", status=status, created="2026-10-01")
    identity = dict(database_id=uid(1), data_source_id=uid(2))
    responses = {("query", uid(2), None): page([row(3, "Done")], True, "next"),
                 ("query", uid(2), "next"): page([row(4, "Review")])}
    result = mock_adapter(fetch, identity, {"Done": "done", "Review": "wait"})["p"]
    assert calls == [("query", uid(2), None), ("query", uid(2), "next")]
    assert len(result["tickets"]) == 2, "same short label must retain both full page identities"
    assert [t["state"] for t in result["tickets"]] == ["done", "wait"]
    source = result["sources"]["notion"]
    assert source["database_id"] != source["data_source_id"] and source["complete"]
    assert source["date_coverage"]["created"] == dict(known=2, total=2)
    assert source["date_coverage"]["completed"] == dict(known=0, total=2)
    assert result["tickets"][0]["completed"] is None
    assert not result["tickets"][0]["date_availability"]["completed"]
    responses[("query", uid(2), "next")] = page([row(4, "Unknown")])
    result = mock_adapter(fetch, identity, {"Done": "done"})["p"]
    assert result["tickets"][1]["raw_status"] == "Unknown"
    assert result["errors"] and not result["sources"]["notion"]["complete"]
    responses = {("query", uid(2), None): page([])}
    assert mock_adapter(fetch, identity, {})["p"]["sources"]["notion"]["complete"]
    todo = lambda n, checked, nested=False: dict(id=uid(n), title="Nested", type="to_do",
                                                checked=checked, has_children=nested)
    responses = {("children", uid(1), None): page([dict(id=uid(2), type="toggle", has_children=True)]),
                 ("children", uid(2), None): page([todo(3, False, True)], True, "more"),
                 ("children", uid(2), "more"): page([todo(4, True)]),
                 ("children", uid(3), None): page([todo(5, False)])}
    result = mock_adapter(fetch, dict(page_id=uid(1)), {})["p"]
    assert [t["state"] for t in result["tickets"]] == ["open", "open", "done"]
    assert all(t["page_id"] == uid(1) for t in result["tickets"])
    assert len({t["source_id"] for t in result["tickets"]}) == 3
    # A later-page failure or stuck cursor must not return a complete short list.
    responses[("children", uid(2), "more")] = page([], True, "more")
    try:
        mock_adapter(fetch, dict(page_id=uid(1)), {})
    except ValueError as error:
        assert "pagination" in str(error)
    else:
        raise AssertionError("stuck pagination accepted")
    del responses[("children", uid(2), "more")]
    try:
        mock_adapter(fetch, dict(page_id=uid(1)), {})
    except KeyError:
        pass
    else:
        raise AssertionError("unread later page accepted")
    try:
        mock_adapter(fetch, dict(page_id="short"), {})
    except ValueError:
        pass
    else:
        raise AssertionError("short identity accepted")
