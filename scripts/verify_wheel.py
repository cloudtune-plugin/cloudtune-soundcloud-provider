"""Check release Wheel contents, metadata and registration without importing src."""
from configparser import ConfigParser
from email import message_from_bytes
from pathlib import Path
import sys
import tomllib
from zipfile import ZipFile


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    wheels = list((root / "dist").glob("*.whl"))
    assert len(wheels) == 1, "Expected exactly one release Wheel in dist/"
    with ZipFile(wheels[0]) as wheel:
        names = wheel.namelist()
        metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
        assert len(metadata_paths) == 1
        prefix = metadata_paths[0].rsplit("/", 1)[0]
        metadata = message_from_bytes(wheel.read(metadata_paths[0]))
        assert metadata["Name"] == project["name"]
        assert metadata["Version"] == project["version"]
        assert metadata["Requires-Python"] == project["requires-python"]
        assert metadata["License-Expression"] == "MIT"
        assert "SoundCloud" in metadata.get_payload()
        assert any("media-provider-sdk" in value for value in metadata.get_all("Requires-Dist", []))
        assert any("yt-dlp" in value for value in metadata.get_all("Requires-Dist", []))
        entries = ConfigParser()
        entries.read_string(wheel.read(prefix + "/entry_points.txt").decode())
        assert entries["media_provider.providers"]["soundcloud"] == (
            "cloudtune_soundcloud_provider.provider:SoundCloudProvider"
        )
        for filename in ("__init__.py", "provider.py", "py.typed"):
            assert "cloudtune_soundcloud_provider/" + filename in names
        assert any(name.endswith("/licenses/LICENSE") for name in names)
        assert all(name.startswith(("cloudtune_soundcloud_provider/", prefix + "/")) for name in names)
    print("Verified Wheel:", wheels[0].name)


if __name__ == "__main__":
    main()
