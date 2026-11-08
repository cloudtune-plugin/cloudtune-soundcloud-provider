"""Run with a clean environment's Python after installing the release Wheel."""
from importlib.metadata import distribution
from pathlib import Path

import cloudtune_soundcloud_provider
from cloudtune_soundcloud_provider import SoundCloudProvider
from media_provider_sdk import MediaProvider


def main() -> None:
    package = distribution("cloudtune-soundcloud-provider")
    entries = [entry for entry in package.entry_points
               if entry.group == "media_provider.providers" and entry.name == "soundcloud"]
    assert len(entries) == 1
    assert entries[0].load() is SoundCloudProvider
    installed = Path(package.locate_file("cloudtune_soundcloud_provider/__init__.py")).resolve()
    assert installed == Path(cloudtune_soundcloud_provider.__file__).resolve()
    assert "site-packages" in installed.parts, "Expected an installed Wheel, not src/"
    provider = entries[0].load()(settings={}, secrets={})
    assert isinstance(provider, MediaProvider)
    assert provider.provider_type == "SOUNDCLOUD"
    assert provider.capabilities.search and provider.capabilities.stream
    print("Verified installed provider and entry point, version", package.version)


if __name__ == "__main__":
    main()
