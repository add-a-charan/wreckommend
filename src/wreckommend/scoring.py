from datetime import UTC, datetime

from sklearn.metrics.pairwise import cosine_similarity

from wreckommend.lastfm.candidates import LIKED_RATING_THRESHOLD
from wreckommend.lastfm.tags import vectorize_all


def _liked_library_track_ids(conn) -> list[str]:
    rows = conn.execute(
        "SELECT id FROM tracks WHERE user_rating >= ?",
        (LIKED_RATING_THRESHOLD,),
    ).fetchall()
    return [row[0] for row in rows]


def _persist_score(
    conn, candidate_id: str, score: float, nearest_track_id: str
) -> None:
    conn.execute(
        """
        UPDATE candidate_tracks
        SET tag_score = ?, tag_score_nearest_track_id = ?, tag_score_computed_at = ?
        WHERE id = ?
        """,
        (score, nearest_track_id, datetime.now(UTC).isoformat(), candidate_id),
    )


def score_candidates(conn) -> None:
    """Score each candidate by cosine similarity to its single nearest liked
    library track, in a tag-vector space shared by library and candidate
    tracks. Scoring against the nearest liked track (rather than one averaged
    taste profile) preserves distinct niche taste clusters instead of
    blending them into a centroid that scores poorly against all of them."""
    entity_ids, matrix, library_ids, candidate_ids = vectorize_all(conn)

    liked_ids = [tid for tid in _liked_library_track_ids(conn) if tid in library_ids]
    if not liked_ids:
        print("No liked library tracks with usable tags; nothing to score against.")
        return

    total_candidates = conn.execute("SELECT COUNT(*) FROM candidate_tracks").fetchone()[
        0
    ]

    index = {entity_id: i for i, entity_id in enumerate(entity_ids)}
    liked_matrix = matrix[[index[tid] for tid in liked_ids]]

    scored = 0
    with conn:
        for candidate_id in candidate_ids:
            similarities = cosine_similarity(
                matrix[index[candidate_id]], liked_matrix
            ).flatten()
            best = int(similarities.argmax())
            _persist_score(
                conn, candidate_id, float(similarities[best]), liked_ids[best]
            )
            scored += 1

    skipped = total_candidates - scored
    print(
        f"Scored {scored} candidates against {len(liked_ids)} liked tracks "
        f"({skipped} candidates skipped — no usable tags after cleaning)."
    )


def top_candidates(conn, limit: int = 25, offset: int = 0) -> list[tuple]:
    return conn.execute(
        """
        SELECT id, title, artist_name, tag_score, discovered_via, source, preview_url
        FROM candidate_tracks
        WHERE tag_score IS NOT NULL
        ORDER BY tag_score DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
