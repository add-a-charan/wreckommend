import json
from datetime import UTC, datetime
from typing import Callable


def params_key(*parts: str) -> str:
    return "|".join(part.strip().lower() for part in parts)


def get(conn, provider: str, endpoint: str, params_key: str) -> dict | None:
    row = conn.execute(
        """
        SELECT response_json, status FROM api_response_cache
        WHERE provider = ? AND endpoint = ? AND params_key = ?
        """,
        (provider, endpoint, params_key),
    ).fetchone()
    if row is None or row[1] != "ok":
        return None
    return json.loads(row[0])


def put(
    conn,
    provider: str,
    endpoint: str,
    params_key: str,
    response: dict,
    status: str = "ok",
) -> None:
    cache_dict = {
        "provider": provider,
        "endpoint": endpoint,
        "params_key": params_key,
        "response_json": json.dumps(response),
        "status": status,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    sql = """
        INSERT INTO api_response_cache (
            provider, endpoint, params_key, response_json, status, fetched_at
        )
        VALUES (
            :provider, :endpoint, :params_key, :response_json, :status, :fetched_at
        )
        ON CONFLICT(provider, endpoint, params_key) DO UPDATE SET
            response_json = excluded.response_json,
            status = excluded.status,
            fetched_at = excluded.fetched_at
    """
    conn.execute(sql, cache_dict)


def get_or_fetch(
    conn, provider: str, endpoint: str, params: tuple[str, ...], fetch: Callable[[], dict]
) -> dict:
    """Returns the cached response for params, or calls fetch(), caches, and returns it."""
    key = params_key(*params)
    cached = get(conn, provider, endpoint, key)
    if cached is not None:
        return cached

    response = fetch()
    with conn:
        put(conn, provider, endpoint, key, response)
    return response
