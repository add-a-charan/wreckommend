from wreckommend import config
from wreckommend.deezer.deezer_client import DeezerClient
from wreckommend.lastfm.lastfm_client import LastfmClient
from wreckommend.musicbrainz.musicbrainz_client import MusicBrainzClient
from wreckommend.subsonic.subsonic_client import SubsonicClient


def build_subsonic_client() -> SubsonicClient:
    return SubsonicClient(
        config.SUBSONIC_URL,
        config.SUBSONIC_USER,
        config.SUBSONIC_PASSWORD,
        config.SUBSONIC_VERSION,
        config.APP_CLIENT_NAME,
    )


def build_lastfm_client() -> LastfmClient:
    return LastfmClient(
        config.LASTFM_URL, config.LASTFM_API_KEY, config.APP_CONTACT_EMAIL
    )


def build_musicbrainz_client() -> MusicBrainzClient:
    return MusicBrainzClient(config.MUSICBRAINZ_URL, config.APP_CONTACT_EMAIL)


def build_deezer_client() -> DeezerClient:
    return DeezerClient(config.DEEZER_URL, config.APP_CONTACT_EMAIL)
