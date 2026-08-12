from wreckommend import config
import json
from wreckommend.navidrome.client import SubsonicClient
from pathlib import Path


def build_client() -> SubsonicClient:
    client = SubsonicClient(
        config.URL, config.USER, config.PASSWORD, config.VERSION, config.CLIENT_NAME
    )
    return client


def retrieve_all_albums(client: SubsonicClient):
    albums = []
    offset = 0
    size = 500
    while True:
        page = client.getAlbumList2("alphabeticalByName", size=size, offset=offset)
        batch = page["albumList2"].get("album", [])
        albums.extend(batch)
        if len(batch) < size:
            break
        offset += size
    return albums


def retrieve_all_tracks(client: SubsonicClient):
    albums = retrieve_all_albums(client)
    tracks = []
    for album in albums:
        tracks.extend(client.getAlbum(album["id"])["album"]["song"])
    return tracks


def insert_track(conn, song):
    path = song.get("path")
    replay_gain = song.get("replayGain") or {}
    song_dict = {
        "id": song["id"],
        "title": song.get("title"),
        "album": song.get("album"),
        "album_id": song.get("albumId"),
        "year": song.get("year"),
        "track_number": song.get("track"),
        "disc_number": song.get("discNumber"),
        "duration": song.get("duration"),
        "bpm": song.get("bpm"),
        "bit_rate": song.get("bitRate"),
        "bit_depth": song.get("bitDepth"),
        "sampling_rate": song.get("samplingRate"),
        "channels": song.get("channelCount"),
        "explicit": (1 if song.get("explicitStatus") == "explicit" else 0),
        "play_count": song.get("playCount", 0),
        "user_rating": song.get("userRating"),
        "average_rating": song.get("averageRating"),
        "track_gain": replay_gain.get("trackGain"),
        "track_peak": replay_gain.get("trackPeak"),
        "path": path,
        "musicbrainz_track_id": song.get("musicBrainzId") or None,
        "isrc": (song.get("isrc") or [None])[0],
        "resolved_path": (
            str(Path(config.NAVIDROME_MUSIC_ROOT) / path) if path else None
        ),
        "suffix": song.get("suffix"),
        "content_type": song.get("contentType"),
        "starred_at": song.get("starred"),
        "created": song.get("created"),
        "last_played": song.get("played"),
        "raw_json": json.dumps(song),
    }
    sql = """
        INSERT INTO tracks (
            id,
            title,
            album,
            album_id,
            year,
            track_number,
            disc_number,
            duration,
            bpm,
            bit_rate,
            bit_depth,
            sampling_rate,
            channels,
            explicit,
            play_count,
            user_rating,
            average_rating,
            track_gain,
            track_peak,
            path,
            musicbrainz_track_id,
            isrc,
            resolved_path,
            suffix,
            content_type,
            starred_at,
            created,
            last_played,
            raw_json
        )
        VALUES (
            :id,
            :title,
            :album,
            :album_id,
            :year,
            :track_number,
            :disc_number,
            :duration,
            :bpm,
            :bit_rate,
            :bit_depth,
            :sampling_rate,
            :channels,
            :explicit,
            :play_count,
            :user_rating,
            :average_rating,
            :track_gain,
            :track_peak,
            :path,
            :musicbrainz_track_id,
            :isrc,
            :resolved_path,
            :suffix,
            :content_type,
            :starred_at,
            :created,
            :last_played,
            :raw_json
        )
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            album = excluded.album,
            album_id = excluded.album_id,
            year = excluded.year,
            track_number = excluded.track_number,
            disc_number = excluded.disc_number,
            duration = excluded.duration,
            bpm = excluded.bpm,
            bit_rate = excluded.bit_rate,
            bit_depth = excluded.bit_depth,
            sampling_rate = excluded.sampling_rate,
            channels = excluded.channels,
            explicit = excluded.explicit,
            play_count = excluded.play_count,
            user_rating = excluded.user_rating,
            average_rating = excluded.average_rating,
            track_gain = excluded.track_gain,
            track_peak = excluded.track_peak,
            path = excluded.path,
            musicbrainz_track_id = excluded.musicbrainz_track_id,
            isrc = excluded.isrc,
            resolved_path = excluded.resolved_path,
            suffix = excluded.suffix,
            content_type = excluded.content_type,
            starred_at = excluded.starred_at,
            created = excluded.created,
            last_played = excluded.last_played,
            raw_json = excluded.raw_json
    """
    conn.execute(sql, song_dict)


def insert_track_artists(conn, song):
    for artist in song.get("artists", []):
        # Register new artists in SQL table
        artist_dict = {"id": artist["id"], "name": artist["name"]}
        artist_sql = """
            INSERT INTO artists (
                id,
                name
            )
            VALUES (
                :id,
                :name
            )
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name
        """
        conn.execute(artist_sql, artist_dict)

        # Match artist to the track
        track_artist_dict = {
            "track_id": song["id"],
            "artist_id": artist["id"],
            "role": "artist",
        }
        track_artist_sql = """
            INSERT INTO track_artists (
                track_id,
                artist_id,
                role
            )
            VALUES (
                :track_id,
                :artist_id,
                :role
            )
            ON CONFLICT(track_id, artist_id, role) DO NOTHING
        """
        conn.execute(track_artist_sql, track_artist_dict)

    for artist in song.get("albumArtists", []):
        # Register new artists in SQL table
        artist_dict = {"id": artist["id"], "name": artist["name"]}
        artist_sql = """
            INSERT INTO artists (
                id,
                name
            )
            VALUES (
                :id,
                :name
            )
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name
        """
        conn.execute(artist_sql, artist_dict)

        # Match artist to the track
        track_artist_dict = {
            "track_id": song["id"],
            "artist_id": artist["id"],
            "role": "album_artist",
        }
        track_artist_sql = """
            INSERT INTO track_artists (
                track_id,
                artist_id,
                role
            )
            VALUES (
                :track_id,
                :artist_id,
                :role
            )
            ON CONFLICT(track_id, artist_id, role) DO NOTHING
        """
        conn.execute(track_artist_sql, track_artist_dict)


def insert_track_tags(conn, song):
    for genre in song.get("genres", []):
        track_tag_dict = {
            "entity_type": "library_track",
            "entity_id": song["id"],
            "tag": genre["name"].strip().lower(),
            "weight": 1.0,
            "source": "navidrome",
        }

        track_tag_sql = """
            INSERT INTO track_tags (
                entity_type,
                entity_id,
                tag,
                weight,
                source
            )
            VALUES (
                :entity_type,
                :entity_id,
                :tag,
                :weight,
                :source
            )
            ON CONFLICT(entity_type, entity_id, tag, source) DO UPDATE SET
                weight = excluded.weight
        """
        conn.execute(track_tag_sql, track_tag_dict)


def ingest(conn, tracks):
    for song in tracks:
        insert_track(conn, song)
        insert_track_artists(conn, song)
        insert_track_tags(conn, song)
    conn.commit()
