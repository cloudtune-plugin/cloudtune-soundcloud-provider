# CloudTune SoundCloud Provider

A standalone SoundCloud source provider plugin for **CloudTune Media Provider Server**, built with Python and [yt-dlp](https://github.com/yt-dlp/yt-dlp).

The plugin searches SoundCloud tracks and resolves playable audio sources for CloudTune. It integrates through the Media Provider SDK and does not require changes to the CloudTune Server or Flutter client.

**Current version:** `0.1.2` · **License:** MIT

## Features

- Search SoundCloud tracks by keyword using yt-dlp's `scsearchN:` extractor.
- Return track metadata when available: title, artist, album, artwork, duration, and track URL.
- Resolve audio sources without downloading audio files.
- Prefer supported progressive HTTP(S) audio (**DIRECT**), falling back to audio-only HLS (**HLS**) when no suitable progressive format is available.
- Return required HTTP request headers and URL expiration information when available.
- Integrate with CloudTune through the `media_provider.providers` entry point.
- Support the SDK's Preview interface by resolving the source audio; the plugin itself does not trim preview duration.

The plugin does **not** implement authentication, cookie configuration, OAuth, lyrics, audio transcoding, or its own streaming proxy.

## Quick start

### Requirements

- Python **3.12 or newer** (CI and release checks target Python 3.12; newer versions are not verified).
- Git, for installing the SDK from its source repository.
- CloudTune Media Provider SDK **0.1.0** (verified against commit `2db38c876bd43b841948b5b999c8c4f22af99cfb`).
- `yt-dlp>=2026.8.19` (release review used `2026.10.26`).

**Important:** The Media Provider SDK is not available from public PyPI as of this release review. Install the SDK before installing the plugin, or provide a compatible SDK Wheel through the CloudTune Plugin Manager. FFmpeg is not required by this plugin.

### Install from source

Clone the repository and enter its directory:

```bash
git clone https://github.com/cloudtune-music/cloudtune-soundcloud-provider.git
cd cloudtune-soundcloud-provider
```

The clone URL above assumes the repository will be published under `cloudtune-music`. Replace it with your actual repository URL if different.

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

Or on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the pinned SDK source and the plugin with development tools:

```bash
python -m pip install -r requirements-sdk.txt
python -m pip install -e ".[dev]"
python -m pip check
```

The repository also defines a uv-specific SDK source in `pyproject.toml`. This setting is **not** read by pip or embedded in the built Wheel. The pip and uv source references target the same verified SDK commit. `uv sync --extra dev` is an alternative, but it was not independently exercised during the release review.

## Install in CloudTune Media Provider Server

CloudTune discovers this plugin using the following Python entry point:

```toml
[project.entry-points."media_provider.providers"]
soundcloud = "cloudtune_soundcloud_provider.provider:SoundCloudProvider"
```

### Option A: Install through Plugin Manager

1. Obtain a built Wheel from a verified GitHub Release, when available, or build one locally using the instructions below.
2. Ensure the Server's plugin worker installer has access to compatible Media Provider SDK and Runtime support Wheels, and can resolve the `yt-dlp` dependency.
3. Upload `cloudtune_soundcloud_provider-0.1.2-py3-none-any.whl` through the Server's admin Plugin Manager.
4. Enable the installed plugin.
5. Create a source provider configuration with type `SOUNDCLOUD`.
6. Use empty configuration objects: `settings={}` and `secrets={}`. This plugin does not consume provider-specific settings or secrets.
7. Test searching and playing tracks you are authorized to access.

**Note:** Installing the SDK in the Server's main Python environment does not automatically install it into an isolated plugin worker. The worker must receive its own compatible SDK dependencies.

### Option B: Install a built Wheel manually

In the intended Python environment, with this repository's `requirements-sdk.txt` available:

```bash
python -m pip install -r requirements-sdk.txt
python -m pip install dist/cloudtune_soundcloud_provider-0.1.2-py3-none-any.whl
python -m pip check
python scripts/verify_install.py
```

A standalone Wheel installation into an empty environment will not automatically locate the SDK on public PyPI. The SDK must be supplied separately through its Git source, an operator-managed package index, or a compatible local Wheel.

## Supported SoundCloud URLs

The provider accepts HTTPS track URLs on:

- `soundcloud.com`
- `www.soundcloud.com`
- `m.soundcloud.com`

Supported paths include ordinary two-segment public track links and supported private track links using `/s-TOKEN`. The default HTTPS port and explicit port `443` are accepted.

The provider does **not** resolve `on.soundcloud.com` short links, playlist/collection URLs, embedded credentials, non-HTTPS URLs, or arbitrary ports. A syntactically valid track URL does not guarantee that SoundCloud will permit playback.

## Audio delivery behavior

| Available source | Selected playback type | Notes |
| --- | --- | --- |
| Supported progressive HTTP(S) audio | `DIRECT` | Preferred when available |
| Audio-only HLS, without suitable progressive audio | `HLS` | Uses the upstream HLS manifest |
| No supported audio format | Resolution error | No invented fallback URL |

For HLS, the plugin reports `application/vnd.apple.mpegurl` as the MIME type. Returned request headers must be forwarded by the downstream playback/proxy implementation when required.

The plugin resolves URLs; it does not probe every returned URL or guarantee that a later request will succeed. CloudTune Server and the client remain responsible for handling manifests, segments, proxying, and playback lifecycle.

## Build a Wheel

Install the development dependencies as described above, then run:

```bash
python -m build --wheel
python -m twine check dist/*
python scripts/verify_wheel.py
```

Expected artifact:

```text
dist/cloudtune_soundcloud_provider-0.1.2-py3-none-any.whl
```

Packaging uses **Hatchling**. The legacy `build_wheel.py` is retained as a compatibility wrapper around the standard build; it does not construct custom Wheel metadata. Avoid mixing artifacts from different versions in `dist/`.

## Run tests

The test suite uses mocked yt-dlp responses and SDK types, and does not require live SoundCloud access.

```bash
python -m pytest -q
```

To run the complete local packaging checks:

```bash
python -m pytest -q
python -m build --wheel
python -m twine check dist/*
python scripts/verify_wheel.py
```

For an installation check, use a **separate clean virtual environment**, install the pinned SDK and built plugin Wheel, and run:

```bash
python -m pip check
python scripts/verify_install.py
```

The repository includes GitHub Actions CI for pushes and pull requests to `main`. CI is intended to run offline unit tests, build and validate the Wheel, and verify package installation and provider entry-point discovery. CI does not automatically publish a package or create a Release.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidance and [RELEASE_READINESS.md](RELEASE_READINESS.md) for release verification details.

## Download and releases

When a verified release is published, download the Wheel from [GitHub Releases](../../releases) and install it through CloudTune's Plugin Manager.

The presence of this link does not imply that a public release has already been published. Check the release page for available artifacts and compatibility notes.

## Known limitations and troubleshooting

### HTTP 403, 404, or 502 after stream resolution

SoundCloud or its CDN may reject a URL after yt-dlp has resolved it. URLs may expire or be restricted by geography, permissions, or upstream changes. Resolve the track again rather than persisting signed media URLs indefinitely. A CDN error does not necessarily mean that the track has been deleted.

### HLS playback failures

HLS requires the downstream Server/client pipeline to handle the manifest, segments, redirects, and necessary HTTP headers. This provider does not include an HLS proxy, transcoder, or FFmpeg packager.

### Some tracks are unavailable

Private, premium, DRM-protected, login-required, region-restricted, or preview-only content may not be playable. This plugin does not bypass authentication or access restrictions.

### yt-dlp extraction failures

SoundCloud may change its API or media formats. Update yt-dlp in the **plugin worker environment**, then rerun tests and deployment playback checks. The provider does not introduce unlimited automatic retries.

### Windows installation paths

Very long Windows paths may prevent isolated plugin environment creation, including `WinError 206` during environment setup. Prefer a short runtime directory path when testing on Windows.

### Logging and security

Signed CDN URLs, cookies, authentication tokens, and sensitive request headers should not be shared in logs, bug reports, or public issues. The provider limits upstream error details to avoid exposing sensitive URLs.

For security reports, see [SECURITY.md](SECURITY.md).

## Contributing

Bug reports and pull requests are welcome. Please include a reproducible example, relevant non-sensitive logs, and tests for behavior changes when possible.

Before opening a pull request:

```bash
python -m pytest -q
python -m build --wheel
python -m twine check dist/*
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for additional guidance.

## Legal notice

This is an independent, unofficial plugin. It is **not affiliated with, sponsored by, or endorsed by SoundCloud**.

Use this software only to access and play content for which you have appropriate rights or authorization, and comply with SoundCloud's terms and applicable laws. The ability to resolve a media URL does not grant permission to download, redistribute, or commercially exploit the underlying audio.

## License

Copyright © 2026 CloudTune Music.

The source code is licensed under the [MIT License](LICENSE). The license applies to this plugin's code, **not** to third-party audio content.
