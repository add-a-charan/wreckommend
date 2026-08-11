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
    song_dict = {
        "id": song["id"],
        "title": song["title"],
        "album": song["album"],
        "album_id": song["albumId"],
        "year": song["year"],
        "track_number": song["track"],
        "disc_number": song["discNumber"],
        "duration": song["duration"],
        "bpm": song["bpm"],
        "bit_rate": song["bitRate"],
        "bit_depth": song["bitDepth"],
        "sampling_rate": song["samplingRate"],
        "channels": song["channelCount"],
        "explicit": (1 if song["explicitStatus"] == "explicit" else 0),
        "play_count": song["playCount"],
        "user_rating": song.get("userRating"),
        "average_rating": song.get("averageRating"),
        "track_gain": song["replayGain"]["trackGain"],
        "track_peak": song["replayGain"]["trackPeak"],
        "path": song["path"],
        "musicbrainz_track_id": song.get("musicBrainzId") or None,
        "isrc": (song.get("isrc") or [None])[0],
        "resolved_path": str(Path(config.NAVIDROME_MUSIC_ROOT) / song["path"]),
        "suffix": song["suffix"],
        "content_type": song["contentType"],
        "starred_at": song.get("starred"),
        "created": song["created"],
        "last_played": song["played"],
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
    pass


def insert_track_tags(conn, song):
    pass


def ingest(conn, tracks):
    for song in tracks:
        insert_track(conn, song)
        insert_track_artists(conn, song)
        insert_track_tags(conn, song)
    conn.commit()
