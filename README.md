# wreckommend

A local-first music recommender and TUI player for [Navidrome](https://www.navidrome.org/) servers. It builds a taste profile from your library ratings, discovers new tracks via Last.fm's similarity graph, scores them against your taste in a shared tag-vector space, and lets you preview and browse everything from a terminal UI.

Everything runs locally against your own Navidrome instance and a local SQLite database — no cloud backend.

## Features implemented

### Data ingestion (Subsonic/Navidrome)
- Pulls the full album/track library from Navidrome via the Subsonic API (`src/wreckommend/subsonic/`).
- Incremental ingest: albums are fingerprinted by song count + duration, so unchanged albums are skipped on re-ingest.
- Stores tracks, albums, artists (with artist/album-artist roles), genres, ratings, and play stats in SQLite.

### Tagging & taste modeling
- Enriches every library track with Last.fm tags (track-level, falling back to artist-level tags when a track has none) — `lastfm/enrich.py`.
- Tag cleaning pipeline (`lastfm/tags.py`): accent/punctuation normalization, synonym folding (e.g. "r&b" → "rnb"), a MusicBrainz genre whitelist to filter noise, plus a manual allowlist for genres MusicBrainz doesn't recognize (regional scenes, "vocaloid", decade tags, etc.).
- MusicBrainz integration to resolve Latin-script aliases for non-Latin artist names, so tag cleaning can distinguish real genre tags from romanized self-tags (`musicbrainz/enrich.py`).
- Library and candidate tracks are vectorized into a shared TF-IDF tag space (`lastfm/tags.py: vectorize_all`).

### Discovery pipeline
- Seeds discovery from artists/tracks the user has rated ≥4 stars; excludes artists already owned or rated ≤2 stars (`lastfm/candidates.py`).
- Two candidate-generation strategies: Last.fm similar-artist → top-tracks, and Last.fm similar-track.
- Each discovered candidate is tagged the same way as library tracks, so it lands in the same vector space.

### Scoring
- Candidates are scored by cosine similarity to their single nearest liked library track (not a blended taste centroid), which preserves distinct niche taste clusters instead of averaging them away (`scoring.py`).
- Results are persisted (`tag_score`, nearest matching track) and queryable via `top-candidates`.

### 30-second previews
- Deezer search + preview-URL fetch for top-scored candidates, with local MP3 download/caching (`deezer/preview.py`). Deezer preview URLs are short-lived, so a fresh URL is always fetched right before download/playback.

### Local playback
- Plays local audio (library tracks or downloaded previews) via the system `mpv` binary, with pause/resume through process suspend/resume rather than restart (`audio/player.py`, `audio/playback.py`).
- Shared `PlaybackMixin` gives any list-based UI single-track play/pause/download-progress state for free.

### Terminal UI (Textual)
- Tabbed app shell with keyboard tab-cycling and a Catppuccin Mocha theme (`app.py`).
- **Discover** tab: side-by-side Playlists module (cover art, pulled live from Navidrome) and Recommendations module (paginated, infinite-scroll candidate list backed by the scoring pipeline; runs discovery+scoring in the background on first load).
- **Albums** tab: full library browse with lazy-loaded cover art, batched infinite scroll, and wrap-around navigation (up from the first album jumps to the true last album and vice versa).
- Album detail screen: track listing with duration/size, ratings, favorite status, and inline playback.
- Responsive layout: horizontal/vertical content layout swaps based on terminal aspect ratio on resize.

### CLI
A full pipeline is drivable outside the TUI via `python -m wreckommend`:

| Command | Purpose |
|---|---|
| `ping` | Check connectivity to the Navidrome server |
| `ingest` | Pull/refresh the library from Navidrome into SQLite |
| `enrich` | Tag library tracks with Last.fm tags |
| `sync-genres` | Refresh the MusicBrainz genre whitelist used for tag cleaning |
| `discover` | Generate candidate tracks from similar artists/tracks |
| `score` | Score candidates against liked library tracks |
| `top-candidates` | List highest-scored candidates |
| `fetch-previews` | Fetch Deezer preview URLs for top candidates |
| `download-previews` | Download preview MP3s to disk |
| `report-top-tags` | Dump raw tag frequency (for stoplist/synonym curation) |
| `nearest` | Find nearest library tracks to a given track by tag similarity |

## Not yet implemented

- **Tracks / Artists / Genres / Folders / Radio Stations tabs** — currently stub placeholders (`ui/tracks.py`, `ui/artists.py`, `ui/genres.py`, `ui/folders.py`, `ui/radiostations.py`).
- **Home tab** — placeholder only, no dashboard content yet.
- Audio-feature-based similarity (e.g. librosa) — recommendations are currently tag-only; a shared library+candidate audio-feature space is planned to complement the tag signal.
- API response cache has no TTL/invalidation strategy — cached Last.fm/MusicBrainz/Deezer responses are kept indefinitely.
- No automated tests yet.
- UI styling (`styles/*.tcss`) is a placeholder pass, not finalized.

## Setup

Requires Python ≥3.11, a running Navidrome server, and `mpv` installed for playback.

Create a `.env` in the project root with:

```
SUBSONIC_URL=
SUBSONIC_USER=
SUBSONIC_PASSWORD=
NAVIDROME_MUSIC_ROOT=
CONTACT_EMAIL=
LASTFM_API_KEY=
```

Optional overrides: `DB_PATH`, `PREVIEW_DIR`, `STREAM_CACHE_DIR` (default under `data/` in the project root).

```
pip install -e .
python -m wreckommend ingest      # pull your library
python -m wreckommend enrich      # tag it via Last.fm
python -m wreckommend sync-genres # refresh MusicBrainz genre whitelist
python -m wreckommend discover    # find candidates
python -m wreckommend score       # score them against your taste

python -m wreckommend.app         # launch the TUI
```
