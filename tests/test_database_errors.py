import sqlite3

import pytest

from database import Database


def _create_db(tmp_path):
    db_path = tmp_path / "app.db"
    backup_dir = tmp_path / "backup"
    db = Database(str(db_path), str(backup_dir))
    db.connect()
    return db


def test_execute_raises_on_sql_error(tmp_path):
    db = _create_db(tmp_path)

    with pytest.raises(sqlite3.Error):
        db.execute("THIS IS NOT VALID SQL")


def test_add_equipment_category_duplicate(tmp_path):
    db = _create_db(tmp_path)

    success, message = db.add_equipment_category("Тест")
    assert success, message

    success, message = db.add_equipment_category("Тест")
    assert not success
    assert "существ" in message.lower()
