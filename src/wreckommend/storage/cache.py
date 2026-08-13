import json
from datetime import datetime, timezone


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
        "fetched_at": datetime.now(timezone.utc).isoformat(),
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
