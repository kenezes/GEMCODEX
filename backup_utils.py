import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional


def _path_is_relative_to(path: Path, other: Path) -> bool:
    """Return True if *path* is located inside *other* (inclusive)."""

    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def _iter_application_files(app_root: Path, *, exclude: Optional[set[Path]] = None):
    exclude = {p.resolve() for p in (exclude or set())}

    for root, dirs, files in os.walk(app_root):
        root_path = Path(root).resolve()

        if any(_path_is_relative_to(root_path, item) for item in exclude):
            dirs[:] = []
            continue

        dirs[:] = [
            name for name in dirs
            if not any(
                _path_is_relative_to((root_path / name).resolve(), item)
                for item in exclude
            )
        ]

        relative_root = root_path.relative_to(app_root)

        if not files and not dirs:
            yield relative_root, None
            continue

        for file_name in files:
            file_path = root_path / file_name
            if relative_root == Path('.'):
                archive_name = Path(file_name)
            else:
                archive_name = relative_root / file_name
            yield archive_name, file_path


def list_app_backups(backup_dir: Path):
    backup_dir = Path(backup_dir)
    return sorted(backup_dir.glob("app_backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)


def get_latest_backup_time(backup_dir: Path) -> Optional[datetime]:
    backups = list_app_backups(backup_dir)
    if not backups:
        return None
    return datetime.fromtimestamp(backups[0].stat().st_mtime)


def cleanup_old_backups(backup_dir: Path, keep: int = 3):
    backups = list_app_backups(backup_dir)
    for old_backup in backups[keep:]:
        try:
            old_backup.unlink()
        except OSError as exc:  # pragma: no cover - filesystem edge case
            logging.warning("Не удалось удалить старый бекап %s: %s", old_backup, exc)


def create_application_backup(app_root: Path, backup_dir: Path):
    app_root = Path(app_root).resolve()
    backup_dir = Path(backup_dir).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"app_backup_{timestamp}.zip"

    exclude: set[Path] = set()
    if _path_is_relative_to(backup_dir, app_root):
        exclude.add(backup_dir)

    try:
        with TemporaryDirectory() as tmp_dir:
            temp_archive_path = Path(tmp_dir) / archive_name
            with zipfile.ZipFile(temp_archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for archive_name_part, file_path in _iter_application_files(app_root, exclude=exclude):
                    if file_path is None:
                        if archive_name_part == Path('.'):
                            continue
                        directory_name = archive_name_part.as_posix().rstrip('/') + '/'
                        archive.writestr(directory_name, '')
                        continue
                    archive.write(file_path, archive_name_part.as_posix())

            final_path = backup_dir / archive_name
            shutil.move(str(temp_archive_path), final_path)

        cleanup_old_backups(backup_dir)
        return True, f"Резервная копия сохранена:\n{final_path}", final_path
    except Exception as exc:  # pragma: no cover - filesystem edge case
        logging.error("Не удалось создать архив приложения: %s", exc, exc_info=True)
        return False, f"Не удалось создать резервную копию:\n{exc}", None
