import asyncio
import logging
import traceback

import pytest
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from media_provider_sdk import (
    MediaProvider, ProviderInvalidResponseError, ProviderItemNotFoundError,
    ProviderSearchError, ProviderSearchResult, ProviderStream, ProviderStreamError,
    ProviderTimeoutError,
)
from cloudtune_soundcloud_provider import SoundCloudProvider

TRACK = "https://soundcloud.com/artist/track"
DIRECT = {"url": "https://cdn.example/audio.mp3", "protocol": "https",
          "ext": "mp3", "acodec": "mp3", "vcodec": "none", "abr": 128,
          "format_id": "http_mp3"}
HLS = {"url": "https://cdn.example/audio.m3u8", "protocol": "m3u8_native",
       "ext": "m4a", "acodec": "mp4a.40.2", "vcodec": "none", "abr": 256,
       "format_id": "hls_aac"}


def resolve(provider, extractor, info):
    extractor.return_value.extract_info.return_value = info
    return asyncio.run(provider.get_stream(TRACK))


@pytest.mark.parametrize("formats,kind,mime", [
    ([DIRECT], "DIRECT", "audio/mpeg"),
    ([HLS], "HLS", "application/vnd.apple.mpegurl"),
    ([HLS, DIRECT], "DIRECT", "audio/mpeg"),
    ([None, 1, "bad", {}, DIRECT], "DIRECT", "audio/mpeg"),
])
def test_resolution_policy(provider, extractor, formats, kind, mime):
    stream = resolve(provider, extractor, {"formats": formats})
    assert isinstance(stream, ProviderStream)
    assert stream.stream_type == kind
    assert stream.mime_type == mime
    assert stream.url == (DIRECT if kind == "DIRECT" else HLS)["url"]
    extractor.return_value.extract_info.assert_called_once_with(TRACK, download=False)


@pytest.mark.parametrize("info", [DIRECT, HLS])
def test_top_level_format(provider, extractor, info):
    assert resolve(provider, extractor, info).url == info["url"]


def test_inspect_all_formats_despite_top_level_hls(provider, extractor):
    stream = resolve(provider, extractor, {**HLS, "formats": [DIRECT, HLS]})
    assert stream.stream_type == "DIRECT"


@pytest.mark.parametrize("formats", [None, [], {}, "bad", [None, 1, {}],
    [{**DIRECT, "protocol": "http_dash_segments"}],
    [{**DIRECT, "ext": "unknown"}],
    [{**DIRECT, "acodec": "none"}],
    [{**DIRECT, "vcodec": "h264"}],
    [{**DIRECT, "protocol": None}],
    [{**DIRECT, "url": "ftp://cdn.example/audio.mp3"}],
])
def test_no_supported_format(provider, extractor, formats):
    with pytest.raises(ProviderStreamError, match="supported audio"):
        resolve(provider, extractor, {"formats": formats})


@pytest.mark.parametrize("url", [
    "https://[broken", "https:/audio.mp3", "https:///audio.mp3",
    "https://cdn.example:bad/audio.mp3", "https://cdn.example/audio\n.mp3",
    "https://user:secret@cdn.example/audio.mp3",
])
@pytest.mark.parametrize("template", [DIRECT, HLS])
def test_malformed_media_url_is_skipped(provider, extractor, url, template):
    with pytest.raises(ProviderStreamError):
        resolve(provider, extractor, {"formats": [{**template, "url": url}]})


@pytest.mark.parametrize("url", ["https://cdn.example/list.m3u8",
    "https://cdn.example/list.m3u8?token=example", "https://cdn.example/list.mpd",
    "https://cdn.example/list%2Em3u8", "https://cdn.example/list.m3u8/",
])
def test_manifest_cannot_be_direct(provider, extractor, url):
    with pytest.raises(ProviderStreamError):
        resolve(provider, extractor, {**DIRECT, "url": url})


def test_fragmented_media_cannot_be_direct(provider, extractor):
    with pytest.raises(ProviderStreamError):
        resolve(provider, extractor, {**DIRECT, "fragments": [{"url": "part.mp3"}]})


@pytest.mark.parametrize("protocol", ["m3u8", "m3u8_native"])
def test_hls_protocols(provider, extractor, protocol):
    assert resolve(provider, extractor, {**HLS, "protocol": protocol}).stream_type == "HLS"


def test_missing_metadata_never_infers_hls_from_url(provider, extractor):
    with pytest.raises(ProviderStreamError):
        resolve(provider, extractor, {"url": HLS["url"], "ext": "m4a"})


@pytest.mark.parametrize("ext,mime", [
    ("mp3", "audio/mpeg"), ("m4a", "audio/mp4"), ("mp4", "audio/mp4"),
    ("aac", "audio/aac"), ("webm", "audio/webm"), ("opus", "audio/ogg"),
    ("ogg", "audio/ogg"), ("flac", "audio/flac"), ("wav", "audio/wav"),
])
def test_direct_mime(provider, extractor, ext, mime):
    assert resolve(provider, extractor, {**DIRECT, "ext": ext}).mime_type == mime


def test_existing_format_ranking():
    opus = {**DIRECT, "ext": "opus", "abr": 400}
    mp3 = {**DIRECT, "abr": 64}
    assert SoundCloudProvider._select_progressive({"formats": [opus, mp3]}) is mp3
    aac = {**HLS, "abr": 64}
    other = {**HLS, "acodec": "opus", "ext": "opus", "abr": 400}
    assert SoundCloudProvider._select_hls({"formats": [other, aac]}) is aac


def test_headers_expiration_and_size(provider, extractor):
    fmt = {**DIRECT, "url": DIRECT["url"] + "?expires=1900000000",
           "http_headers": {"User-Agent": "format-agent", "Cookie": "example-cookie"},
           "filesize": 1234, "filesize_approx": 2000}
    stream = resolve(provider, extractor, {"formats": [fmt], "duration": 42.9,
        "http_headers": {"Referer": TRACK, "user-agent": "track-agent", "X-Optional": None}})
    assert stream.headers == {"Referer": TRACK, "User-Agent": "format-agent", "Cookie": "example-cookie"}
    assert stream.expires_at_epoch == 1900000000
    assert stream.content_length == 1234
    assert stream.duration_seconds == 42


@pytest.mark.parametrize("headers", [None, [], "bad"])
def test_malformed_format_headers_preserve_track_headers(provider, extractor, headers):
    stream = resolve(provider, extractor, {"formats": [{**DIRECT, "http_headers": headers}],
                                          "http_headers": {"Referer": TRACK}})
    assert stream.headers == {"Referer": TRACK}


@pytest.mark.parametrize("key", ["expires", "expire", "exp"])
def test_expiration_keys(provider, extractor, key):
    assert resolve(provider, extractor, {**DIRECT, "url": DIRECT["url"] + f"?{key}=1900000000"}).expires_at_epoch == 1900000000


@pytest.mark.parametrize("suffix", ["", "?expires=invalid", "?expires=", "?exp=-1"])
def test_missing_or_invalid_expiration(provider, extractor, suffix):
    assert resolve(provider, extractor, {**DIRECT, "url": DIRECT["url"] + suffix}).expires_at_epoch is None


@pytest.mark.parametrize("size", [None, -1, True, "42", 12.5])
def test_unreliable_sizes_omitted(provider, extractor, size):
    assert resolve(provider, extractor, {**DIRECT, "filesize": size, "filesize_approx": 99}).content_length is None


def test_hls_aggregate_size_omitted(provider, extractor):
    assert resolve(provider, extractor, {**HLS, "filesize": 999}).content_length is None


@pytest.mark.parametrize("url", [TRACK, "https://www.soundcloud.com/artist/track",
    "https://m.soundcloud.com/artist/track", "https://soundcloud.com:443/artist/track",
    TRACK + "?si=example", TRACK + "/s-example", " " + TRACK + " "])
def test_valid_track_url(url):
    assert SoundCloudProvider._validate_track_url(url) == url.strip()


@pytest.mark.parametrize("url", [None, 123, "", "not a url", "https://[broken/artist/track",
    "http://soundcloud.com/artist/track", "https://example.com/artist/track",
    "https://soundcloud.com.evil.example/artist/track", "https://evilsoundcloud.com/artist/track",
    "https://evil.soundcloud.com/artist/track", "https://soundc1oud.com/artist/track",
    "https://soundcloud.com@127.0.0.1/artist/track", "https://127.0.0.1/artist/track",
    "https://localhost/artist/track", "https://10.0.0.1/artist/track",
    "https://user:password@soundcloud.com/artist/track", "https://@soundcloud.com/artist/track",
    "https://soundcloud.com:8443/artist/track", "https://soundcloud.com:bad/artist/track",
    "https://soundcloud.com:/artist/track", "https://soundcloud.com/artist/tra\nck",
    "\t" + TRACK, TRACK + "\x00", "https://soundcloud.com/artist/track%0a",
    "https://soundcloud.com/artist/track%zz", "https://soundcloud.com/artist/track\\other",
    "https://soundcloud.com/artist", "https://soundcloud.com/artist/sets/playlist",
    "https://soundcloud.com/artist/likes", "https://soundcloud.com/artist/spotlight",
    TRACK + "/comments", "https://soundcloud.com//artist/track",
])
def test_invalid_track_url(url):
    with pytest.raises(ProviderItemNotFoundError):
        SoundCloudProvider._validate_track_url(url)


def test_invalid_input_does_not_call_extractor(provider, extractor):
    with pytest.raises(ProviderItemNotFoundError):
        asyncio.run(provider.get_stream("https://localhost/artist/track"))
    extractor.assert_not_called()


def test_search_success(provider, extractor):
    extractor.return_value.extract_info.return_value = {"entries": [
        None, {"title": "no URL"}, {"webpage_url": TRACK, "title": " Song ",
        "uploader": "Artist", "album": "Album", "id": "123", "duration": 45.9,
        "thumbnails": [{"url": "https://cdn.example/art.jpg"}]}]}
    results = asyncio.run(provider.search(" ambient ", limit=3))
    assert len(results) == 1
    assert isinstance(results[0], ProviderSearchResult)
    assert results[0].title == "Song" and results[0].artist == "Artist"
    assert results[0].provider_item_id == TRACK
    assert results[0].duration_seconds == 45
    assert results[0].thumbnail_url == "https://cdn.example/art.jpg"
    extractor.return_value.extract_info.assert_called_once_with("scsearch3:ambient", download=False)


@pytest.mark.parametrize("data", [None, {"entries": []}])
def test_empty_search(provider, extractor, data):
    extractor.return_value.extract_info.return_value = data
    assert asyncio.run(provider.search("ambient")) == []


def test_blank_search(provider, extractor):
    assert asyncio.run(provider.search("   ")) == []
    extractor.assert_not_called()


@pytest.mark.parametrize("data", [[], "invalid", {}, {"entries": None}, {"entries": {}}])
def test_invalid_search_metadata(provider, extractor, data):
    extractor.return_value.extract_info.return_value = data
    with pytest.raises(ProviderInvalidResponseError):
        asyncio.run(provider.search("ambient"))


def test_search_discards_malformed_urls(provider, extractor):
    extractor.return_value.extract_info.return_value = {"entries": [
        {"webpage_url": "https://[broken", "title": "bad"},
        {"webpage_url": "https://user:secret@soundcloud.com/artist/track", "title": "bad"},
        {"webpage_url": TRACK, "title": "ok"}]}
    assert len(asyncio.run(provider.search("ambient"))) == 1


@pytest.mark.parametrize("limit,expected", [(0, 1), (50, 30)])
def test_search_limit(provider, extractor, limit, expected):
    extractor.return_value.extract_info.return_value = {"entries": [{"webpage_url": TRACK, "title": "x"}] * 40}
    assert len(asyncio.run(provider.search("ambient", limit=limit))) == expected


@pytest.mark.parametrize("number", [float("inf"), float("-inf"), float("nan"), True, -1, "12"])
def test_malformed_numeric_metadata(provider, extractor, number):
    assert resolve(provider, extractor, {**DIRECT, "duration": number}).duration_seconds is None


@pytest.mark.parametrize("info", [None, [], "invalid"])
def test_invalid_stream_metadata(provider, extractor, info):
    with pytest.raises(ProviderInvalidResponseError):
        resolve(provider, extractor, info)


@pytest.mark.parametrize("operation", ["search", "stream"])
@pytest.mark.parametrize("failure,error_type", [
    (DownloadError("HTTP 403: https://cdn.example/a?token=DO_NOT_LOG"), None),
    (DownloadError("HTTP 404"), None), (DownloadError("HTTP 502"), None),
    (TimeoutError("secret timeout detail"), ProviderTimeoutError),
    (RuntimeError("unexpected secret detail"), None),
])
def test_extractor_errors_are_safe(provider, extractor, operation, failure, error_type, caplog):
    extractor.return_value.extract_info.side_effect = failure
    expected = error_type or (ProviderSearchError if operation == "search" else ProviderStreamError)
    with caplog.at_level(logging.DEBUG), pytest.raises(expected) as caught:
        asyncio.run(provider.search("ambient") if operation == "search" else provider.get_stream(TRACK))
    formatted = "".join(traceback.format_exception(caught.value)) + caplog.text
    assert "DO_NOT_LOG" not in formatted
    assert "unexpected secret detail" not in formatted
    assert "secret timeout detail" not in formatted
    assert "SoundCloud" in str(caught.value)


def test_ytdlp_internal_logging_is_safe(caplog, capsys):
    with caplog.at_level(logging.DEBUG):
        with YoutubeDL(SoundCloudProvider._options()) as ydl:
            ydl.report_warning("Cookie: DO_NOT_LOG")
            with pytest.raises(DownloadError):
                ydl.report_error("https://cdn.example/a?token=DO_NOT_LOG")
    assert "DO_NOT_LOG" not in caplog.text + capsys.readouterr().err
    assert "extractor" in caplog.text.lower()


def test_format_metadata_is_not_logged(provider, extractor, caplog):
    with caplog.at_level(logging.INFO):
        resolve(provider, extractor, {**DIRECT, "format_id": "https://cdn.example/?token=DO_NOT_LOG",
                "http_headers": {"Authorization": "DO_NOT_LOG"}})
    assert "DO_NOT_LOG" not in caplog.text


def test_real_sdk_contract_and_preview(provider, extractor):
    assert isinstance(provider, MediaProvider)
    assert provider.provider_type == "SOUNDCLOUD"
    assert provider.capabilities.search and provider.capabilities.stream and provider.capabilities.preview
    extractor.return_value.extract_info.return_value = DIRECT
    assert isinstance(asyncio.run(provider.get_preview_stream(TRACK)), ProviderStream)


@pytest.mark.parametrize("metadata", [
    {"manifest_url": "https://cdn.example/manifest.m3u8"},
    {"ext": "m3u8"},
    {"url": "https://cdn.example/list%252Em3u8"},
])
def test_conflicting_manifest_metadata_cannot_be_direct(provider, extractor, metadata):
    with pytest.raises(ProviderStreamError):
        resolve(provider, extractor, {**DIRECT, **metadata})


@pytest.mark.parametrize("template", [DIRECT, HLS])
@pytest.mark.parametrize("field,value", [
    ("protocol", []), ("ext", {}), ("acodec", "none"), ("vcodec", "h264"),
])
def test_unsupported_format_metadata(provider, extractor, template, field, value):
    if template is HLS and field == "ext":
        # HLS protocol is authoritative; the media extension can be absent.
        assert resolve(provider, extractor, {**template, field: value}).stream_type == "HLS"
    else:
        with pytest.raises(ProviderStreamError):
            resolve(provider, extractor, {**template, field: value})


def test_offline_guard_blocks_tcp():
    import socket
    with socket.socket() as connection, pytest.raises(AssertionError, match="network"):
        connection.connect(("127.0.0.1", 9))


def test_options_preserve_bounded_retries_and_ignore_user_config():
    options = SoundCloudProvider._options()
    assert options["ignoreconfig"] is True
    assert options["skip_download"] is True
    assert options["retries"] == options["extractor_retries"] == 2
    assert options["socket_timeout"] == 20



def test_offline_guard_blocks_dns():
    import socket
    with pytest.raises(AssertionError, match="network"):
        socket.getaddrinfo("example.com", 443)
