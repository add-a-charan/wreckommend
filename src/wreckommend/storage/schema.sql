PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tracks (
    id TEXT PRIMARY KEY,

    title TEXT NOT NULL,
    album TEXT,
    album_id TEXT,


    year INTEGER,
    track_number INTEGER,
    disc_number INTEGER,

    duration INTEGER,
    bpm INTEGER,


    bit_rate INTEGER,
    bit_depth INTEGER,
    sampling_rate INTEGER,
    channels INTEGER,

    explicit INTEGER,

    play_count INTEGER DEFAULT 0,
    user_rating INTEGER,
    average_rating INTEGER,

    track_gain REAL,
    track_peak REAL,

    path TEXT,

    musicbrainz_track_id TEXT,
    isrc TEXT,
    resolved_path TEXT,
    suffix TEXT,
    content_type TEXT,
    starred_at TEXT,

    created TEXT,
    last_played TEXT,

    raw_json TEXT 
);

CREATE TABLE IF NOT EXISTS track_tags (
    entity_type TEXT CHECK(entity_type IN ('library_track', 'candidate_track')),
    entity_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    source TEXT NOT NULL,
    PRIMARY KEY (entity_type, entity_id, tag, source)
);

CREATE TABLE IF NOT EXISTS artists (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS track_artists (
    track_id TEXT NOT NULL,
    artist_id TEXT NOT NULL,
    role TEXT CHECK(role IN ('artist', 'album_artist')) NOT NULL,

    PRIMARY KEY (track_id, artist_id, role),

    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS api_response_cache (
    provider TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    params_key TEXT NOT NULL,
    response_json TEXT NOT NULL,
    status TEXT NOT NULL,
    fetched_at TEXT NOT NULL,

    PRIMARY KEY (provider, endpoint, params_key)
);
