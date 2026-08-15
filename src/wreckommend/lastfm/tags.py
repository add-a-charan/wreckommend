import re
import unicodedata

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_WHITESPACE = re.compile(r"\s+")
_JOINER = re.compile(r"[\s\-]+")


def strip_accents(text: str) -> str:
    result = []
    for ch in text:
        # Check that the tag is in latin script before normalizing
        # if it isn't in latin, leave the tag alone to prevent data loss
        base = unicodedata.normalize("NFKD", ch)[0]
        result.append(base if base.isascii() else ch)
    return "".join(result)


def strip_punctuation(text: str) -> str:
    return "".join(ch for ch in text if ch.isalnum() or ch.isspace() or ch in "-&")


def unify_separators(text: str) -> str:
    text = _WHITESPACE.sub(" ", text).strip()
    return _JOINER.sub("_", text)


def normalize(text: str) -> str:
    text = text.lower()
    text = strip_accents(text)
    text = strip_punctuation(text)
    text = unify_separators(text)
    return text


# Add tags/genres that exist but are not recognized by musicbrainz but still add signal
ALLOWLIST_RAW = {
    "rap",
    "alternative",
    "indie",
    "rnb",
    "alternative rnb",
    "video game music",
    "soundtrack",
    "16-bit",
    "female vocalists",
    "male vocalists",
    "atlanta",
    "los angeles",
    "houston",
    "ohio",
    "new york",
    "east coast",
    "west coast",
    "beast coast",
    "texas",
    "vocaloid",
    "shoegaze",
}

_ALLOWLIST = {normalize(tag) for tag in ALLOWLIST_RAW}

_DECADE_PATTERN = re.compile(r"^(19|20)?\d0s$")


# Look into synonym folding but for now this may work
SYNONYMS_RAW = {
    "r&b": "rnb",
    "rhythm and blues": "rnb",
    "alternative r&b": "alternative rnb",
    "electronique": "electronic",
    "synth pop": "synthpop",
    "alt-pop": "alternative pop",
    "vgm": "video game music",
    "video game": "video game music",
    "game soundtrack": "video game music",
    "ost": "soundtrack",
    "female vocalist": "female vocalists",
    "male vocalist": "male vocalists",
}

_SYNONYMS = {normalize(k): normalize(v) for k, v in SYNONYMS_RAW.items()}


def load_artist_names(conn) -> set[str]:
    # useful for catching and removing romanized self-tags
    # for example a "Camellia" tag on a track かめりあ(Camellia)
    rows = conn.execute("SELECT DISTINCT name, latin_name FROM artists").fetchall()
    names = set()
    for name, latin_name in rows:
        names.add(normalize(name))
        if latin_name:
            names.add(normalize(latin_name))
    return names


def load_genre_whitelist(conn) -> set[str]:
    rows = conn.execute("SELECT name FROM musicbrainz_genres").fetchall()
    return {normalize(name) for (name,) in rows}


def canonicalize(tag: str) -> str:
    normalized = normalize(tag)
    return _SYNONYMS.get(normalized, normalized)


def is_allowed_tag(
    canonical: str, artist_names: set[str], genre_whitelist: set[str]
) -> bool:
    if canonical in artist_names:
        return False
    return (
        canonical in genre_whitelist
        or canonical in _ALLOWLIST
        or bool(_DECADE_PATTERN.match(canonical))
    )


def clean_tag(
    tag: str, artist_names: set[str], genre_whitelist: set[str]
) -> str | None:
    canonical = canonicalize(tag)
    if is_allowed_tag(canonical, artist_names, genre_whitelist):
        return canonical
    return None


# Retrieve the raw top tags for stoplist/synonym curation
def report_top_tags(conn, limit: int = 200) -> list[tuple[str, int]]:
    return conn.execute(
        """
        SELECT tag, COUNT(*) AS n
        FROM track_tags
        WHERE entity_type = 'library_track'
        GROUP BY tag
        ORDER BY n DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def get_cleaned_library_tags(conn) -> dict[str, dict[str, float]]:
    """entity_id -> {canonical_tag: summed_weight}"""
    artist_names = load_artist_names(conn)
    genre_whitelist = load_genre_whitelist(conn)
    rows = conn.execute(
        "SELECT entity_id, tag, weight FROM track_tags WHERE entity_type = 'library_track'"
    ).fetchall()

    cleaned: dict[str, dict[str, float]] = {}
    for entity_id, tag, weight in rows:
        canonical = clean_tag(tag, artist_names, genre_whitelist)
        if canonical is None:
            continue
        track_tags = cleaned.setdefault(entity_id, {})
        track_tags[canonical] = track_tags.get(canonical, 0.0) + weight
    return cleaned


# Navidrome and Lastfm weights work differently, where Navidrome is sort of just a binary thing
# while Lastfm is an actual measure of the tag's popularity. So this value will probably need to change
# a lot until we find an actual strategy for making the weights comparable.
_REPEAT_SCALE = 20


def _document_for_track(tag_weights: dict[str, float]) -> str:
    words = []
    for tag, weight in tag_weights.items():
        repeats = max(1, round(weight * _REPEAT_SCALE))
        words.extend([tag] * repeats)
    return " ".join(words)


def build_corpus(cleaned: dict[str, dict[str, float]]) -> tuple[list[str], list[str]]:
    """Returns (entity_ids, documents), in matching order."""
    entity_ids = list(cleaned.keys())
    documents = [_document_for_track(cleaned[entity_id]) for entity_id in entity_ids]
    return entity_ids, documents


def vectorize_library(conn):
    """Returns (entity_ids, vectorizer, matrix) for all library tracks."""
    cleaned = get_cleaned_library_tags(conn)
    entity_ids, documents = build_corpus(cleaned)

    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(documents)
    return entity_ids, vectorizer, matrix


def nearest_tracks(
    entity_ids: list[str], matrix, target_entity_id: str, top_n: int = 10
) -> list[tuple[str, float]]:
    idx = entity_ids.index(target_entity_id)
    similarities = cosine_similarity(matrix[idx], matrix).flatten()
    ranked = sorted(
        ((entity_ids[i], score) for i, score in enumerate(similarities) if i != idx),
        key=lambda pair: pair[1],
        reverse=True,
    )
    return ranked[:top_n]


def _track_label(conn, track_id: str) -> str:
    row = conn.execute(
        """
        SELECT t.title, a.name
        FROM tracks t
        JOIN artists a ON a.id = (
            SELECT ta.artist_id FROM track_artists ta
            WHERE ta.track_id = t.id AND ta.role = 'artist'
            ORDER BY ta.rowid LIMIT 1
        )
        WHERE t.id = ?
        """,
        (track_id,),
    ).fetchone()
    if row is None:
        return track_id
    title, artist = row
    return f"{artist} - {title}"


def print_nearest(
    conn, entity_ids: list[str], matrix, target_entity_id: str, top_n: int = 10
) -> None:
    print(f"Nearest to: {_track_label(conn, target_entity_id)}")
    for entity_id, score in nearest_tracks(entity_ids, matrix, target_entity_id, top_n):
        print(f"  {score:.3f}  {_track_label(conn, entity_id)}")
