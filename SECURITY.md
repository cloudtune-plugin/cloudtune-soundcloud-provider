# Security

Security fixes currently target the latest 0.1.x release. Keep yt-dlp updated;
upstream service and extractor changes may require a new tested version.

Use the repository's GitHub Security Advisories "Report a vulnerability" option
for private reports if enabled. Otherwise ask a maintainer to enable private
reporting without posting exploit details or credentials publicly. No dedicated
security email or response-time commitment is established for this project.

Include affected versions and a minimal sanitized reproduction. Never include
cookies, authorization headers, private track tokens or signed CDN URLs. The
provider withholds raw yt-dlp messages; treat returned stream URLs and headers as
sensitive too. It validates SoundCloud input hosts but is not a network sandbox
for the upstream extractor. Operators control network egress and DNS policy.

If a secret is exposed, revoke/rotate it and review Git history and release
assets. Adding a path to .gitignore does not remove existing commits.
