# 0.1.2

- Preserve progressive DIRECT audio preference and audio-only HLS fallback,
  existing format ranking, SDK entry point and provider methods.
- Reject malformed or unsafe SoundCloud input URLs; safely skip malformed
  formats and reject manifest/fragment metadata when choosing DIRECT streams.
- Preserve required headers by merging track and format headers.
- Withhold raw yt-dlp messages and exception chains from logs/tracebacks.
- Use standard Hatchling packaging, with the SDK installed explicitly from the
  verified v0.1.0 Git commit for pip development and clean-install checks.
- Add offline regression coverage and Python 3.12 CI for tests, Wheel metadata,
  clean installation and provider entry point.

Supported setup: Python 3.12+, SDK 0.1.0 (verified); yt-dlp>=2026.8.19
(review tested 2026.10.26). Other allowed dependency/Python versions have not
been exhaustively tested. See README for SDK provisioning and deployment steps.

Upstream 403/404/502 errors, expired signed URLs and client HLS behavior remain
source/deployment dependent. Full admin upload and authorized DIRECT/HLS playback
must be smoke-tested before changing this draft to a public release.
