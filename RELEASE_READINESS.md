# Release readiness review: 0.1.2

Review date: 2026-11-05. Target repository: `cloudtune-soundcloud-provider`.
Scope: this plugin only. No Server, SDK, Runtime or Flutter files were modified.
No Git tags, pushes, releases or package publication were performed.

## A. Confirmed findings

No Critical issue was confirmed. These findings describe the pre-fix source.

| Severity | Finding | Resolution |
| --- | --- | --- |
| High | SoundCloud URL validation accepted embedded credentials and unexpected ports, silently normalized controls, and leaked parser exceptions on malformed input. Search used a separate weaker validator. | Shared parsed URL validation, explicit host/HTTPS/port/path rules and SDK errors; accepted/rejected URL regression tests. |
| High | yt-dlp could write sensitive upstream messages to stderr; chained exceptions and untrusted format IDs could expose signed URLs/tokens in tracebacks or logs. | Private extractor logger, safe error mapping, suppressed raw exception display and no untrusted format metadata in logs. |
| Medium | Encoded/trailing-slash manifest URLs and fragmented/manifest-marked metadata could be selected as DIRECT. Malformed format URLs could crash or be returned. | Conservative format rejection with demonstrated regressions; no speculative HLS inference or probes. |
| Medium | Format headers replaced track headers; malformed headers could erase required headers. | Case-insensitive merge, format overrides, preserve unrelated track requirements. |
| Medium | Infinite numeric durations could crash; invalid negative expiration was advertised. | Reject nonfinite numeric metadata and ignore nonpositive query expiration. |
| Medium | Manual Wheel builder duplicated version/dependency metadata, omitted README/license payload, and mixed a license expression with Metadata-Version 2.3. | Standard Hatchling metadata and license/readme payload; compatibility script delegates to PEP 517. |
| Medium | pip cannot resolve the SDK from public PyPI; uv source configuration does not travel in Wheel metadata. | Explicit pinned SDK source installation for pip/CI. Production Wheel retains the SDK version range, compatible with Manager-provided SDK Wheels. |
| Medium | Existing offline guard broke Windows asyncio socketpair initialization, preventing meaningful async coverage. | Allow only event-loop construction outside the TCP guard; provider/extractor tests retain TCP and DNS guards. |
| Low | Missing CI, contribution/security guidance and incomplete ignores; .python-version selected unverified 3.14. | Add concise repository files and Python 3.12 CI/default. |

After correcting only the test fixture, the original 140 tests recorded
44 failures / 96 passes. Additional pre-fix format regressions recorded
46 failures / 107 passes. The final suite has 154 tests.

## B. Changed and added files

| File | Change and purpose |
| --- | --- |
| `src/cloudtune_soundcloud_provider/provider.py` | URL/format validation, header preservation, safe errors/logging and numeric metadata handling. |
| `tests/conftest.py` | Repair Windows event-loop setup and enforce offline TCP/DNS guards; retain real SDK and mock yt-dlp fixtures. |
| `tests/test_provider.py` | Extend existing regression coverage for conflicting format metadata and network isolation; retain all original tests. |
| `pyproject.toml` | Keep version 0.1.2 as authoritative, standard Hatchling targets/license metadata, development extras, pytest discovery and immutable uv SDK source. |
| `build_wheel.py` | Keep the existing command as a small standard-build wrapper; remove manual ZIP/metadata generation. |
| `.python-version` | Select verified Python 3.12. |
| `requirements-sdk.txt` | Explicit pip source for SDK v0.1.0, pinned to the annotated tag's actual commit. |
| `scripts/verify_wheel.py` | Validate Wheel payload, metadata/version, license and provider registration. |
| `scripts/verify_install.py` | Load the installed entry point and instantiate the real SDK provider; reject accidentally testing src/ instead of site-packages. |
| `.github/workflows/ci.yml` | Push/PR checks for main: Python 3.12, SDK-aware install, offline tests, build/metadata and clean install. No publication. |
| `.gitignore` | Exclude environments, caches, artifacts, credentials and local data. |
| `README.md` | Installation/configuration, verified compatibility boundaries, build/test instructions, upstream limitations and legal notice. |
| `CONTRIBUTING.md` | Small-change/test guidance and privacy rules for fixtures/reports. |
| `SECURITY.md` | Private reporting guidance, sensitive-data handling and exposed-secret response. |
| `RELEASE_NOTES.md` | Reviewable notes for a manual draft GitHub Release. |
| `RELEASE_READINESS.md` | This report and manual release procedure. |

`LICENSE`, `src/cloudtune_soundcloud_provider/__init__.py` and `py.typed` are
unchanged. Local environments, cached source backups/audit data and generated
artifacts remain ignored; they are not release source files.

## C. Playback compatibility

DIRECT progressive HTTP(S) audio still takes precedence over HLS. Existing
progressive format ranking (common compatible containers, then bitrate) and HLS
ranking (AAC/container, then bitrate) are unchanged. SDK methods, capabilities,
provider type, entry point and inherited full-source preview behavior remain.

Intentional changes reject unsafe/malformed input and conflicting stream
metadata, merge required headers, ignore invalid expiration/numeric values and
withhold sensitive upstream diagnostics. A manifest with inconsistent metadata
now produces a supported alternative or a clear provider error instead of an
incorrect DIRECT stream. URLs returned by the extractor are preserved verbatim.
No FFmpeg, proxy, transcoding, new runtime dependency or per-request media probe
was added. The existing 20-second socket timeout and bounded retries remain.

## D. Packaging and installation

Wheel: `cloudtune_soundcloud_provider-0.1.2-py3-none-any.whl`.
Source distribution: `cloudtune_soundcloud_provider-0.1.2.tar.gz`.

Clean installation was verified with Python 3.12, SDK 0.1.0 from the fixed Git
commit and yt-dlp 2026.10.26, using the README's two-step pip workflow. The package
imports, dependencies pass `pip check`, and `soundcloud` loads from the installed
Wheel as a `MediaProvider` subclass. A bare pip installation without an SDK source
is not supported; this limitation is explicit rather than hidden in uv config.

The real local Server Wheel validator accepted the artifact. The Server's
unchanged package installer and environment verifier passed with local SDK and
Runtime 0.1.0 support Wheels in a separately created short-path environment.
Full `ensure_environment` creation was attempted but blocked before plugin
installation by Windows MAX_PATH (`WinError 206`); extended path notation also
failed in this host's bundled pip. This does not count as a successful full
Plugin Manager deployment. The Server files were only read/imported, with
bytecode writes disabled; all generated validation files stayed in this repo.

## E. Validation

- `python -m pytest -q`: **154 passed, 0 failed, 0 skipped** (offline).
- `python -m build --wheel`: passed.
- `python -m build`: passed, including a Wheel built from the source distribution.
- `python -m twine check dist/*`: passed for Wheel and source distribution.
- `python scripts/verify_wheel.py`: passed.
- Clean environment Wheel import, entry point and `pip check`: passed.
- Actual local Server Wheel validator: passed.
- Actual local Server installer/verifier with SDK/Runtime Wheels: passed in a
  separately created short-path environment.
- Complete Manager environment creation: blocked by Windows path/tooling limits.
- GitHub-hosted Actions: configured but not executed here.
- Real SoundCloud playback/admin upload: not performed; tests use synthetic data.
- Other Python versions, all allowed SDK/yt-dlp versions and uv sync: not tested.

## F. Public repository audit and readiness

Source/configuration/documentation patterns were inspected for private keys,
known token shapes, credential assignments, real signed SoundCloud CDN URLs,
personal paths and internal configuration. No confirmed secret or personal path
was found in the public source candidates. URLs/tokens/passwords in tests are
synthetic rejected-input/redaction fixtures, not live credentials. No local
configuration/database was selected for release.

Virtual environments, caches and build artifacts exist locally and are ignored.
A temporary Git metadata directory under ignored `.cache/` verified the actual
ignore rules for 14 representative environment, artifact, credential, log and
local-database paths. The real working directory has no `.git`; original commit
history is unavailable and **has not been audited**. A final staged diff review
is required before the initial public push. If another existing repository has
history, audit it separately; .gitignore cannot remove historical secrets.

**Ready for source review on GitHub; not yet cleared for a final public binary
release.** Remaining acceptance items: run the hosted CI, use a short/supported
runtime path and verify full Plugin Manager activation, then smoke-test authorized
DIRECT and HLS tracks on the intended Server/client deployment. CDN 403/404/502
responses remain upstream limitations, not guarantees this plugin can eliminate.
No version bump is made because this is the requested unreleased 0.1.2 source
preparation. If 0.1.2 has already been distributed elsewhere, do not overwrite an
existing release: decide on a patch version before publishing these changes.

## G. Manual release commands (not executed)

Run in this repository after creating the empty GitHub repository. Replace
`YOUR_GITHUB_OWNER` with the intended user/organization. Review the staged diff
for secrets before committing/pushing. The file list excludes all local artifacts.

```bash
git init -b main
git add -- .github .gitignore .python-version CONTRIBUTING.md LICENSE README.md RELEASE_NOTES.md RELEASE_READINESS.md SECURITY.md build_wheel.py pyproject.toml requirements-sdk.txt scripts src tests
git diff --cached --check
git diff --cached
git commit -m "Prepare SoundCloud provider v0.1.2 for release"
git remote add origin https://github.com/YOUR_GITHUB_OWNER/cloudtune-soundcloud-provider.git
git push -u origin main
```

After the remaining acceptance items pass and the final artifacts are rebuilt:

```bash
git tag -a v0.1.2 -m "SoundCloud provider v0.1.2"
git push origin v0.1.2
gh release create v0.1.2 dist/cloudtune_soundcloud_provider-0.1.2-py3-none-any.whl dist/cloudtune_soundcloud_provider-0.1.2.tar.gz --draft --verify-tag --title "v0.1.2" --notes-file RELEASE_NOTES.md
```

These commands create a **draft** release. Review the attached artifacts and
release notes before manually publishing it. No PyPI publication is configured.

## References

- [uv dependency sources](https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-sources): source configuration is specific to uv.
- [Python packaging metadata](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/): standard project/build metadata.
- [yt-dlp SoundCloud extractor](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/soundcloud.py): upstream implementation; installed version was inspected separately.
