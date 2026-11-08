# Contributing

Use Python 3.12 and Git. Follow the README installation steps, then run:

```bash
python -m pytest -q
python -m build --wheel
python -m twine check dist/*
python scripts/verify_wheel.py
```

Keep changes small and preserve DIRECT-first, HLS-fallback selection. Demonstrate
stream-selection bugs with an offline regression test before changing behavior.
Tests use the real SDK types and mock yt-dlp; the network guard must remain enabled.
Do not add credentials, real signed CDN URLs, private track links or raw extractor
output to fixtures or bug reports. Use synthetic example domains and values.

The SDK Git source must remain consistent in requirements-sdk.txt and
pyproject.toml. The project version is maintained only in pyproject.toml.

Describe the problem, resulting behavior and checks in pull requests. A real
CloudTune Plugin Manager installation and authorized playback smoke test are
required before a release; CI alone does not verify server/client playback.
Report security issues using SECURITY.md.
