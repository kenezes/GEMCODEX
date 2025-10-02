import os
import sys
import zipfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backup_utils import (
    cleanup_old_backups,
    create_application_backup,
)


def _create_file(path: Path, content: str = "data"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_create_application_backup_excludes_backup_dir(tmp_path: Path):
    app_root = tmp_path / "app"
    backup_dir = app_root / "backup"
    logs_dir = app_root / "logs"
    nested_dir = app_root / "nested" / "deep"

    _create_file(app_root / "config.ini", "example")
    _create_file(logs_dir / "app.log", "log")
    _create_file(nested_dir / "data.txt", "payload")

    # Existing backup that should not end up inside the new archive
    _create_file(backup_dir / "old_backup.zip", "zip content")

    success, message, archive_path = create_application_backup(app_root, backup_dir)

    assert success, message
    assert archive_path.exists()

    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        assert "config.ini" in names
        assert "logs/app.log" in names
        assert "nested/deep/data.txt" in names
        assert all(not name.startswith("backup/") for name in names)


def test_cleanup_old_backups_removes_excess(tmp_path: Path):
    backup_dir = tmp_path
    paths: list[Path] = []
    for idx in range(5):
        archive = backup_dir / f"app_backup_20240101_00000{idx}.zip"
        _create_file(archive, str(idx))
        paths.append(archive)

    # Touch files to simulate different modification times
    for idx, archive in enumerate(paths):
        os.utime(archive, (idx + 1, idx + 1))

    cleanup_old_backups(backup_dir, keep=2)

    remaining = sorted(backup_dir.glob("app_backup_*.zip"))
    assert len(remaining) == 2
    # The newest two files should remain (last ones)
    assert remaining[-2:] == paths[-2:]
