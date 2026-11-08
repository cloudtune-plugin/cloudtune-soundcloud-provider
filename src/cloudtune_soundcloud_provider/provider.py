"""CloudTune SoundCloud media provider, using yt-dlp for discovery and playback.

Only use with tracks for which playback and redistribution are authorized.
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
from typing import Any
from urllib.parse import ParseResult, parse_qs, unquote, urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from media_provider_sdk import (
    MediaProvider,
    ProviderCapabilities,
    ProviderError,
    ProviderInvalidResponseError,
    ProviderItemNotFoundError,
    ProviderSearchError,
    ProviderSearchResult,
    ProviderStream,
    ProviderStreamError,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)


class _ExtractorLogger:
    """Do not forward yt-dlp messages: they may contain credentials or URLs."""

    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        logger.debug("SoundCloud extractor reported a warning (details withheld)")

    def error(self, message: str) -> None:
        logger.debug("SoundCloud extractor reported an error (details withheld)")


class SoundCloudProvider(MediaProvider):
    provider_type = "SOUNDCLOUD"
    display_name = "SoundCloud"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(search=True, stream=True, preview=True, lyrics=False)

    @staticmethod
    def _options(**overrides: Any) -> dict[str, Any]:
        options: dict[str, Any] = {
            "logger": _ExtractorLogger(),
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "ignoreconfig": True,
            "socket_timeout": 20,
            "retries": 2,
            "extractor_retries": 2,
        }
        options.update(overrides)
        return options

    async def search(self, query: str, *, limit: int = 20) -> list[ProviderSearchResult]:
        query = query.strip()
        if not query:
            return []
        limit = max(1, min(limit, 30))
        try:
            data = await asyncio.to_thread(self._search_sync, query, limit)
        except DownloadError as exc:
            logger.warning("SoundCloud search extractor failed: %s", type(exc).__name__)
            raise ProviderSearchError("SoundCloud search failed") from None
        except TimeoutError:
            raise ProviderTimeoutError("SoundCloud search timed out") from None
        except ProviderError:
            raise
        except Exception as exc:
            logger.error("SoundCloud search extractor failed unexpectedly: %s", type(exc).__name__)
            raise ProviderSearchError("Unexpected SoundCloud search failure") from None
        if data is None:
            return []
        if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
            raise ProviderInvalidResponseError("SoundCloud search returned invalid entries")
        results: list[ProviderSearchResult] = []
        for item in data["entries"]:
            if not isinstance(item, dict):
                continue
            url = self._canonical_url(item)
            title = self._text(item.get("title"))
            if not url or not title:
                continue
            results.append(ProviderSearchResult(
                provider_item_id=url,
                title=title,
                artist=self._text(item.get("artist") or item.get("uploader")),
                album=self._text(item.get("album")),
                thumbnail_url=self._thumbnail(item),
                duration_seconds=self._integer(item.get("duration")),
                extra={"webpage_url": url, "soundcloud_id": self._text(item.get("id"))},
            ))
        return results[:limit]

    def _search_sync(self, query: str, limit: int) -> dict[str, Any] | None:
        # scsearch is the native SoundCloud search extractor (NOT ytsearch).
        with YoutubeDL(self._options(extract_flat=True, playlistend=limit, ignoreerrors=True)) as ydl:
            data = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
        if data is not None and not isinstance(data, dict):
            raise ProviderInvalidResponseError("Invalid SoundCloud search response")
        return data

    async def get_stream(self, provider_item_id: str) -> ProviderStream:
        return await asyncio.to_thread(self._get_stream_sync, provider_item_id)

    def _get_stream_sync(self, provider_item_id: str) -> ProviderStream:
        url = self._validate_track_url(provider_item_id)
        # Prefer byte-addressable HTTP media. When SoundCloud offers HLS only,
        # explicitly identify it as HLS so the client can use its HLS path.
        options = self._options(noplaylist=True, format="bestaudio/best")
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except DownloadError as exc:
            logger.warning("SoundCloud stream extractor failed: %s", type(exc).__name__)
            raise ProviderStreamError("Unable to resolve SoundCloud stream") from None
        except TimeoutError:
            raise ProviderTimeoutError("SoundCloud stream request timed out") from None
        except ProviderError:
            raise
        except Exception as exc:
            logger.error("SoundCloud stream extractor failed unexpectedly: %s", type(exc).__name__)
            raise ProviderStreamError("Unexpected SoundCloud stream resolution failure") from None

        if not isinstance(info, dict):
            raise ProviderInvalidResponseError("SoundCloud returned invalid track information")
        selected = self._select_progressive(info)
        stream_type = "DIRECT"
        if selected is None:
            selected = self._select_hls(info)
            stream_type = "HLS"
        if selected is None:
            logger.warning("SoundCloud track has no supported direct or HLS audio format")
            raise ProviderStreamError("SoundCloud offers no supported audio stream for this track")
        stream_url = selected["url"]
        # Format headers override track headers case-insensitively without
        # dropping unrelated requirements such as Referer or Authorization.
        merged_headers: dict[str, tuple[str, str]] = {}
        for source in (info.get("http_headers"), selected.get("http_headers")):
            if isinstance(source, dict):
                for key, value in source.items():
                    if value is not None:
                        name = str(key)
                        merged_headers[name.lower()] = (name, str(value))
        headers = dict(merged_headers.values())
        ext = (self._text(selected.get("ext")) or "").lower()
        codec = self._text(selected.get("acodec"))
        protocol = (self._text(selected.get("protocol")) or "").lower()
        mime_type = {
            "m4a": "audio/mp4", "mp4": "audio/mp4", "mp3": "audio/mpeg",
            "aac": "audio/aac", "webm": "audio/webm", "opus": "audio/ogg",
            "ogg": "audio/ogg", "flac": "audio/flac", "wav": "audio/wav",
        }.get(ext)
        if stream_type == "HLS":
            mime_type = "application/vnd.apple.mpegurl"
        elif not mime_type and codec and codec.startswith("mp4a"):
            mime_type = "audio/mp4"
        parsed = parse_qs(urlparse(stream_url).query)
        expires_at_epoch = None
        for key in ("expires", "expire", "exp"):
            try:
                expiration = int(parsed[key][0])
                if expiration > 0:
                    expires_at_epoch = expiration
                    break
            except (KeyError, ValueError, TypeError, IndexError):
                pass
        # HLS filesize describes the *aggregate* audio, not the manifest body.
        # filesize_approx is never safe to advertise as Content-Length.
        length = selected.get("filesize") if stream_type == "DIRECT" else None
        if isinstance(length, bool) or not isinstance(length, int) or length < 0:
            length = None
        logger.info(
            "SoundCloud stream selected: type=%s expires=%s",
            stream_type, expires_at_epoch is not None,
        )
        return ProviderStream(
            url=stream_url,
            mime_type=mime_type,
            expires_at_epoch=expires_at_epoch,
            headers=headers,
            stream_type=stream_type,
            duration_seconds=self._integer(info.get("duration")),
            content_length=length,
            container=self._text(selected.get("container")) or ext or None,
            codec=codec,
            format_id=self._text(selected.get("format_id")),
            extra={"webpage_url": self._canonical_url(info) or url, "source_protocol": protocol},
        )

    @classmethod
    def _select_progressive(cls, info: dict[str, Any]) -> dict[str, Any] | None:
        """Select byte-addressable HTTP audio, never an HLS/DASH manifest.

        yt-dlp may pick an HLS stream as `info.url` even when the formats list
        contains an HTTP progressive alternative, so we inspect all candidates.
        """
        candidates = [info]
        if isinstance(info.get("formats"), list):
            candidates.extend(f for f in info["formats"] if isinstance(f, dict))
        playable: list[dict[str, Any]] = []
        for fmt in candidates:
            parsed_url = cls._parse_http_url(fmt.get("url"))
            if parsed_url is None:
                continue
            protocol = (cls._text(fmt.get("protocol")) or "").lower()
            if protocol not in ("http", "https"):
                continue
            # Decode path escapes for classification only; return the original
            # signed URL unchanged. Two passes also catch double-escaped suffixes.
            path = unquote(unquote(parsed_url.path)).lower().rstrip("/")
            if path.endswith((".m3u8", ".mpd")):
                continue
            if fmt.get("fragments") or fmt.get("manifest_url"):
                continue
            if cls._text(fmt.get("vcodec")) not in (None, "none"):
                continue
            if cls._text(fmt.get("acodec")) == "none":
                continue
            ext = (cls._text(fmt.get("ext")) or "").lower()
            if ext not in ("m4a", "mp4", "mp3", "aac", "webm", "opus", "ogg", "flac", "wav"):
                continue
            playable.append(fmt)
        if not playable:
            return None
        return max(playable, key=lambda f: (
            (cls._text(f.get("ext")) or "").lower() in ("m4a", "mp3", "mp4", "aac"),
            f.get("abr") if isinstance(f.get("abr"), (int, float)) and not isinstance(f.get("abr"), bool) else 0,
        ))

    @classmethod
    def _select_hls(cls, info: dict[str, Any]) -> dict[str, Any] | None:
        """Find an audio-only HLS manifest without mistaking its m4a extension
        for a progressive media file. Prefer AAC/m4a for AVPlayer compatibility.
        """
        candidates = [info]
        if isinstance(info.get("formats"), list):
            candidates.extend(f for f in info["formats"] if isinstance(f, dict))
        playable: list[dict[str, Any]] = []
        for fmt in candidates:
            parsed_url = cls._parse_http_url(fmt.get("url"))
            if parsed_url is None:
                continue
            proto = (cls._text(fmt.get("protocol")) or "").lower()
            # yt-dlp reports m3u8 or m3u8_native depending on extractor/version.
            if proto not in ("m3u8", "m3u8_native"):
                continue
            if cls._text(fmt.get("vcodec")) not in (None, "none"):
                continue
            if cls._text(fmt.get("acodec")) == "none":
                continue
            playable.append(fmt)
        if not playable:
            return None
        return max(playable, key=lambda f: (
            (cls._text(f.get("acodec")) or "").lower().startswith("mp4a"),
            (cls._text(f.get("ext")) or "").lower() in ("m4a", "mp4", "aac"),
            f.get("abr") if isinstance(f.get("abr"), (int, float)) and not isinstance(f.get("abr"), bool) else 0,
        ))

    @staticmethod
    def _parse_http_url(value: Any) -> ParseResult | None:
        if not isinstance(value, str) or not value:
            return None
        # urlparse silently removes some control characters; check first.
        if any(char.isspace() or ord(char) < 32 or 127 <= ord(char) <= 159 for char in value):
            return None
        if "\\" in value or re.search(r"%(?![0-9a-fA-F]{2})", value):
            return None
        decoded = unquote(value)
        if any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in decoded):
            return None
        try:
            parsed = urlparse(value)
            if (parsed.scheme not in ("https", "http") or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.netloc.endswith(":")):
                return None
            # Accessing .port validates its syntax and range.
            parsed.port
            return parsed
        except ValueError:
            return None

    @classmethod
    def _validate_track_url(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ProviderItemNotFoundError("Expected an HTTPS SoundCloud track URL")
        # Preserve the existing convenience of surrounding spaces, but never
        # strip tabs/newlines before validating them.
        value = value.strip(" ")
        parsed = cls._parse_http_url(value)
        if (parsed is None or parsed.scheme != "https" or parsed.port not in (None, 443)
                or parsed.hostname.lower() not in (
                    "soundcloud.com", "www.soundcloud.com", "m.soundcloud.com")):
            raise ProviderItemNotFoundError("Expected an HTTPS SoundCloud track URL")
        parts = unquote(parsed.path)[1:].rstrip("/").split("/")
        # Public tracks have two path segments; private links can append s-TOKEN.
        private_link = len(parts) == 3 and parts[2].startswith("s-") and len(parts[2]) > 2
        if (len(parts) != 2 and not private_link) or not all(parts):
            raise ProviderItemNotFoundError("SoundCloud track URL is invalid")
        if parts[1].lower() in ("sets", "tracks", "likes", "reposts", "albums", "spotlight"):
            raise ProviderItemNotFoundError("SoundCloud track URL is invalid")
        return value

    @classmethod
    def _canonical_url(cls, item: dict[str, Any]) -> str | None:
        for key in ("webpage_url", "original_url", "url"):
            value = item.get(key)
            if isinstance(value, str):
                try:
                    return cls._validate_track_url(value)
                except ProviderItemNotFoundError:
                    continue
        return None

    @staticmethod
    def _text(value: Any) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _integer(value: Any) -> int | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return int(value) if value >= 0 else None

    @classmethod
    def _thumbnail(cls, item: dict[str, Any]) -> str | None:
        direct = cls._text(item.get("thumbnail"))
        if direct:
            return direct
        thumbnails = item.get("thumbnails")
        if isinstance(thumbnails, list):
            for thumb in reversed(thumbnails):
                if isinstance(thumb, dict):
                    value = cls._text(thumb.get("url"))
                    if value:
                        return value
        return None
