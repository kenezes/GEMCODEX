import sqlite3
import logging
from pathlib import Path
from typing import Any, Optional
from datetime import date, datetime, timedelta
from collections import defaultdict

class Database:
    """Класс для управления базой данных SQLite."""
    def __init__(self, db_path: str, backup_dir: str):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.conn = None
        self.db_path.parent.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        self._knives_category_id = None
        self._sharpening_category_ids: set[int] = set()

    def _log_action(self, message: str):
        """Записывает действие пользователя в журнал."""
        logging.info(f"[ACTION] {message}")

    @staticmethod
    def _normalize_addresses(addresses: list[dict[str, Any]] | list[str] | None) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        if not addresses:
            return normalized

        default_assigned = False
        for entry in addresses:
            if isinstance(entry, str):
                address_text = entry.strip()
                is_default = False
            else:
                address_text = (entry.get("address") or "").strip()
                is_default = bool(entry.get("is_default", False))

            if not address_text:
                continue

            if is_default and default_assigned:
                is_default = False
            elif is_default:
                default_assigned = True

            normalized.append({"address": address_text, "is_default": is_default})

        if normalized and not any(addr["is_default"] for addr in normalized):
            normalized[0]["is_default"] = True

        return normalized

    def _replace_counterparty_addresses(self, cursor: sqlite3.Cursor, counterparty_id: int,
                                         addresses: list[dict[str, Any]]):
        cursor.execute("DELETE FROM counterparty_addresses WHERE counterparty_id = ?", (counterparty_id,))
        default_address = ""

        for entry in addresses:
            cursor.execute(
                "INSERT INTO counterparty_addresses (counterparty_id, address, is_default) VALUES (?, ?, ?)",
                (counterparty_id, entry["address"], 1 if entry.get("is_default") else 0),
            )
            if entry.get("is_default") and not default_address:
                default_address = entry["address"]

        if not default_address and addresses:
            default_address = addresses[0]["address"]

        cursor.execute("UPDATE counterparties SET address = ? WHERE id = ?", (default_address, counterparty_id))

    @staticmethod
    def _format_addresses_for_display(addresses: list[dict[str, Any]]) -> str:
        formatted = []
        for entry in addresses:
            suffix = " (по умолчанию)" if entry.get("is_default") else ""
            formatted.append(f"{entry['address']}{suffix}")
        return "\n".join(formatted)

    def _get_counterparty_addresses_map(self, counterparty_ids: list[int] | None = None) -> dict[int, list[dict[str, Any]]]:
        if counterparty_ids:
            placeholders = ",".join("?" for _ in counterparty_ids)
            query = (
                "SELECT counterparty_id, address, is_default FROM counterparty_addresses "
                f"WHERE counterparty_id IN ({placeholders}) "
                "ORDER BY counterparty_id, is_default DESC, id"
            )
            rows = self.fetchall(query, tuple(counterparty_ids))
        else:
            rows = self.fetchall(
                "SELECT counterparty_id, address, is_default FROM counterparty_addresses "
                "ORDER BY counterparty_id, is_default DESC, id"
            )

        result: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            result[row["counterparty_id"]].append({
                "address": row["address"],
                "is_default": bool(row["is_default"]),
            })
        return result

    def connect(self):
        """Устанавливает соединение с БД и настраивает PRAGMA."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.execute("PRAGMA journal_mode = WAL;")
            self.conn.execute("PRAGMA synchronous = NORMAL;")
            self.conn.execute("PRAGMA busy_timeout = 5000;")
            logging.info(f"Successfully connected to database: {self.db_path}")
            self.run_migrations()
            self._refresh_sharpening_categories()

        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}", exc_info=True)
            raise

    def disconnect(self):
        """Закрывает соединение с БД."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logging.info("Database connection closed.")

    def _refresh_sharpening_categories(self):
        """Обновляет кэш ID категорий, для которых включено отслеживание заточек."""
        self._sharpening_category_ids.clear()
        self._knives_category_id = None
        rows = self.fetchall(
            "SELECT id, name FROM part_categories WHERE name IN ('ножи','утюги')"
        )
        for row in rows:
            cat_id = row["id"]
            self._sharpening_category_ids.add(cat_id)
            if row["name"].lower() == "ножи":
                self._knives_category_id = cat_id

    @staticmethod
    def _combined_status(sharp_state: str, installation_state: str) -> str:
        if sharp_state == "затуплен":
            return "затуплен"
        if installation_state == "установлен":
            return "в работе"
        return "наточен"

    @staticmethod
    def _fallback_sharp_state(stored_state: Optional[str], status: Optional[str]) -> str:
        if stored_state in {"заточен", "затуплен"}:
            return stored_state  # type: ignore[return-value]
        if status == "затуплен":
            return "затуплен"
        return "заточен"

    @staticmethod
    def _fallback_installation_state(stored_state: Optional[str], status: Optional[str]) -> str:
        if stored_state in {"установлен", "снят"}:
            return stored_state  # type: ignore[return-value]
        if status == "в работе":
            return "установлен"
        return "снят"

    def execute(self, query: str, params: tuple = ()) -> Optional[sqlite3.Cursor]:
        """Выполняет один SQL-запрос."""
        try:
            if not self.conn:
                raise sqlite3.Error("Database is not connected.")
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            return cursor
        except sqlite3.Error as e:
            logging.error(f"SQL Error: {e}\nQuery: {query}\nParams: {params}", exc_info=True)
            return None

    def fetchall(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Выполняет запрос и возвращает все строки как список словарей."""
        cursor = self.execute(query, params)
        if cursor:
            return [dict(row) for row in cursor.fetchall()]
        return []

    def fetchone(self, query: str, params: tuple = ()) -> Optional[dict[str, Any]]:
        """Выполняет запрос и возвращает одну строку как словарь."""
        cursor = self.execute(query, params)
        if cursor:
            row = cursor.fetchone()
            return dict(row) if row else None
        return None

    def get_setting(self, key: str, default: str = "") -> str:
        """Возвращает значение настройки приложения."""
        row = self.fetchone("SELECT value FROM app_settings WHERE key = ?", (key,))
        if row and row.get("value") is not None:
            return str(row["value"])
        return default

    def set_setting(self, key: str, value: Optional[str]) -> bool:
        """Сохраняет значение настройки приложения. Если значение None или пустое — удаляет настройку."""
        if not self.conn:
            return False

        try:
            with self.conn:
                cursor = self.conn.cursor()
                if value:
                    cursor.execute(
                        """
                            INSERT INTO app_settings (key, value) VALUES (?, ?)
                            ON CONFLICT(key) DO UPDATE SET value = excluded.value
                        """,
                        (key, value),
                    )
                else:
                    cursor.execute("DELETE FROM app_settings WHERE key = ?", (key,))
            return True
        except sqlite3.Error as exc:
            logging.error("Не удалось сохранить настройку %s: %s", key, exc, exc_info=True)
            return False

    def get_driver_phone(self) -> str:
        """Возвращает сохранённый номер телефона водителя."""
        return self.get_setting("driver_phone", "")

    def set_driver_phone(self, phone: str) -> bool:
        """Сохраняет номер телефона водителя."""
        value = phone.strip()
        return self.set_setting("driver_phone", value if value else None)

    def set_order_driver_notified(self, order_id: int, notified: bool) -> tuple[bool, str]:
        """Фиксирует, что водитель уведомлён по конкретному заказу."""
        if not self.conn:
            return False, "Нет подключения к базе данных."

        try:
            with self.conn:
                self.conn.execute(
                    "UPDATE orders SET driver_notified = ? WHERE id = ?",
                    (1 if notified else 0, order_id),
                )
            return True, ""
        except sqlite3.Error as exc:
            logging.error(
                "Не удалось обновить статус уведомления водителя для заказа %s: %s",
                order_id,
                exc,
                exc_info=True,
            )
            return False, str(exc)

    def run_migrations(self):
        """Применяет миграции к схеме БД."""
        if not self.conn: return
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA user_version;")
        user_version = cursor.fetchone()[0]
        logging.info(f"Current database version: {user_version}")

        if user_version < 1:
            logging.info("Applying migration to version 1...")
            self._apply_migration_v1()
            cursor.execute("PRAGMA user_version = 1;")
            self.conn.commit()
            logging.info("Database migrated to version 1.")
        
        if user_version < 2:
            logging.info("Applying migration to version 2...")
            self._apply_migration_v2()
            cursor.execute("PRAGMA user_version = 2;")
            self.conn.commit()
            logging.info("Database migrated to version 2.")

        if user_version < 3:
            logging.info("Applying migration to version 3...")
            self._apply_migration_v3()
            cursor.execute("PRAGMA user_version = 3;")
            self.conn.commit()
            logging.info("Database migrated to version 3.")
            
        if user_version < 4:
            logging.info("Applying migration to version 4...")
            self._apply_migration_v4()
            cursor.execute("PRAGMA user_version = 4;")
            self.conn.commit()
            logging.info("Database migrated to version 4.")

        if user_version < 5:
            logging.info("Applying migration to version 5...")
            self._apply_migration_v5()
            cursor.execute("PRAGMA user_version = 5;")
            self.conn.commit()
            logging.info("Database migrated to version 5.")

        if user_version < 6:
            logging.info("Applying migration to version 6...")
            self._apply_migration_v6()
            cursor.execute("PRAGMA user_version = 6;")
            self.conn.commit()
            logging.info("Database migrated to version 6.")

        if user_version < 7:
            logging.info("Applying migration to version 7...")
            self._apply_migration_v7()
            cursor.execute("PRAGMA user_version = 7;")
            self.conn.commit()
            logging.info("Database migrated to version 7.")

        if user_version < 8:
            logging.info("Applying migration to version 8...")
            self._apply_migration_v8()
            cursor.execute("PRAGMA user_version = 8;")
            self.conn.commit()
            logging.info("Database migrated to version 8.")

        if user_version < 9:
            logging.info("Applying migration to version 9...")
            self._apply_migration_v9()
            cursor.execute("PRAGMA user_version = 9;")
            self.conn.commit()
            logging.info("Database migrated to version 9.")

        if user_version < 10:
            logging.info("Applying migration to version 10...")
            self._apply_migration_v10()
            cursor.execute("PRAGMA user_version = 10;")
            self.conn.commit()
            logging.info("Database migrated to version 10.")

        if user_version < 11:
            logging.info("Applying migration to version 11...")
            self._apply_migration_v11()
            cursor.execute("PRAGMA user_version = 11;")
            self.conn.commit()
            logging.info("Database migrated to version 11.")

        if user_version < 12:
            logging.info("Applying migration to version 12...")
            self._apply_migration_v12()
            cursor.execute("PRAGMA user_version = 12;")
            self.conn.commit()
            logging.info("Database migrated to version 12.")

        if user_version < 13:
            logging.info("Applying migration to version 13...")
            self._apply_migration_v13()
            cursor.execute("PRAGMA user_version = 13;")
            self.conn.commit()
            logging.info("Database migrated to version 13.")

        if user_version < 14:
            logging.info("Applying migration to version 14...")
            self._apply_migration_v14()
            cursor.execute("PRAGMA user_version = 14;")
            self.conn.commit()
            logging.info("Database migrated to version 14.")

        if user_version < 15:
            logging.info("Applying migration to version 15...")
            self._apply_migration_v15()
            cursor.execute("PRAGMA user_version = 15;")
            self.conn.commit()
            logging.info("Database migrated to version 15.")


    def _apply_migration_v1(self):
        """Схема БД версии 1."""
        if not self.conn: return
        
        script = """
            CREATE TABLE IF NOT EXISTS part_categories (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL COLLATE NOCASE
            );
            CREATE TABLE IF NOT EXISTS parts (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                sku TEXT NOT NULL,
                qty INTEGER NOT NULL DEFAULT 0,
                min_qty INTEGER NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0,
                category_id INTEGER,
                FOREIGN KEY (category_id) REFERENCES part_categories(id) ON DELETE SET NULL,
                UNIQUE(name COLLATE NOCASE, sku COLLATE NOCASE)
            );
            CREATE TABLE IF NOT EXISTS equipment_categories (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL COLLATE NOCASE
            );
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                sku TEXT,
                category_id INTEGER NOT NULL,
                FOREIGN KEY (category_id) REFERENCES equipment_categories(id) ON DELETE RESTRICT
            );
            CREATE TABLE IF NOT EXISTS equipment_parts (
                id INTEGER PRIMARY KEY,
                equipment_id INTEGER NOT NULL,
                part_id INTEGER NOT NULL,
                installed_qty INTEGER NOT NULL DEFAULT 1,
                comment TEXT,
                last_replacement_override TEXT,
                FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE RESTRICT,
                FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
                UNIQUE(equipment_id, part_id)
            );
            CREATE TABLE IF NOT EXISTS counterparties (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                address TEXT,
                contact_person TEXT,
                phone TEXT,
                email TEXT,
                note TEXT,
                driver_note TEXT
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                counterparty_id INTEGER NOT NULL,
                invoice_no TEXT,
                invoice_date TEXT NOT NULL,
                delivery_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
                status TEXT NOT NULL CHECK(status IN ('создан','в пути','принят','отменён')),
                driver_notified INTEGER NOT NULL DEFAULT 0,
                comment TEXT,
                FOREIGN KEY (counterparty_id) REFERENCES counterparties(id) ON DELETE RESTRICT
            );
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                part_id INTEGER,
                name TEXT NOT NULL,
                sku TEXT,
                qty INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE RESTRICT,
                FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS replacements (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                equipment_id INTEGER NOT NULL,
                part_id INTEGER NOT NULL,
                qty INTEGER NOT NULL,
                reason TEXT,
                FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE RESTRICT,
                FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO part_categories (name) VALUES ('ножи');
        """
        if self.conn:
            self.conn.executescript(script)

    def _apply_migration_v2(self):
        """Миграция для добавления иерархии оборудования."""
        script = """
            ALTER TABLE equipment ADD COLUMN parent_id INTEGER REFERENCES equipment(id) ON DELETE CASCADE;
            CREATE INDEX IF NOT EXISTS equipment_parent_id_idx ON equipment(parent_id);
        """
        if self.conn:
            try:
                self.conn.executescript(script)
            except sqlite3.OperationalError as e:
                logging.warning(f"Could not apply migration v2 (may already exist): {e}")

    def _apply_migration_v3(self):
        """Миграция для добавления задач и коллег."""
        script = """
            CREATE TABLE IF NOT EXISTS colleagues (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL COLLATE NOCASE
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT NOT NULL CHECK(priority IN ('низкий','средний','высокий')),
                due_date TEXT,
                assignee_id INTEGER,
                equipment_id INTEGER,
                status TEXT NOT NULL CHECK(status IN ('в работе','выполнена','отменена','на стопе')) DEFAULT 'в работе',
                FOREIGN KEY (assignee_id) REFERENCES colleagues(id) ON DELETE SET NULL,
                FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS tasks_status_priority_due_date_idx ON tasks(status, priority, due_date);
        """
        if self.conn:
            self.conn.executescript(script)

    def _apply_migration_v4(self):
        """Миграция для добавления таблиц отслеживания ножей."""
        script = """
            CREATE TABLE IF NOT EXISTS knife_tracking (
                part_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL CHECK(status IN ('в работе','наточен','затуплен')) DEFAULT 'наточен',
                last_sharpen_date TEXT,
                work_started_at TEXT,
                last_interval_days INTEGER,
                total_sharpenings INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS knife_status_log (
                id INTEGER PRIMARY KEY,
                part_id INTEGER NOT NULL,
                changed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
                from_status TEXT,
                to_status TEXT NOT NULL,
                comment TEXT,
                FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS knife_sharpen_log (
                id INTEGER PRIMARY KEY,
                part_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                comment TEXT,
                FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS knife_tracking_status_idx ON knife_tracking(status);
            CREATE INDEX IF NOT EXISTS knife_status_log_part_id_idx ON knife_status_log(part_id, changed_at DESC);
            CREATE INDEX IF NOT EXISTS knife_sharpen_log_part_id_idx ON knife_sharpen_log(part_id, date DESC);
        """
        if self.conn:
            self.conn.executescript(script)
            # Ретроактивно добавляем отслеживание для существующих ножей
            self.conn.execute("""
                INSERT OR IGNORE INTO knife_tracking (part_id)
                SELECT p.id FROM parts p
                JOIN part_categories pc ON p.category_id = pc.id
                WHERE pc.name = 'ножи';
            """)

    def _apply_migration_v5(self):
        """Миграция для добавления комментария к оборудованию."""
        if not self.conn:
            return

        try:
            self.conn.execute("ALTER TABLE equipment ADD COLUMN comment TEXT;")
        except sqlite3.OperationalError as exc:
            # Столбец уже существует
            logging.warning("Could not add equipment.comment column (maybe already exists): %s", exc)

    def _apply_migration_v6(self):
        """Миграция для добавления даты создания задач."""
        if not self.conn:
            return

        try:
            self.conn.execute("ALTER TABLE tasks ADD COLUMN created_at TEXT;")
        except sqlite3.OperationalError as exc:
            logging.warning("Could not add tasks.created_at column (maybe already exists): %s", exc)
            return

        self.conn.execute(
            "UPDATE tasks SET created_at = COALESCE(created_at, strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))"
        )

    def _apply_migration_v7(self):
        """Миграция для добавления признака необходимости замены запчасти."""
        if not self.conn:
            return

        if not self._ensure_equipment_parts_requires_column(update_schema_version=False):
            logging.warning(
                "Migration v7: не удалось гарантировать наличие столбца equipment_parts.requires_replacement."
            )

    def _apply_migration_v8(self):
        """Миграция для добавления задач на замену и связанных запчастей."""
        if not self.conn:
            return

        cursor = self.conn.cursor()

        try:
            cursor.execute(
                "ALTER TABLE tasks ADD COLUMN is_replacement INTEGER NOT NULL DEFAULT 0;"
            )
        except sqlite3.OperationalError as exc:
            logging.info(
                "Migration v8: колонка tasks.is_replacement уже существует: %s",
                exc,
            )

        try:
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS task_parts (
                    id INTEGER PRIMARY KEY,
                    task_id INTEGER NOT NULL,
                    equipment_part_id INTEGER NOT NULL,
                    part_id INTEGER NOT NULL,
                    qty INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY (equipment_part_id) REFERENCES equipment_parts(id) ON DELETE CASCADE,
                    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
                );
                CREATE INDEX IF NOT EXISTS task_parts_task_id_idx ON task_parts(task_id);
                CREATE INDEX IF NOT EXISTS task_parts_equipment_part_id_idx ON task_parts(equipment_part_id);
                """
            )
        except sqlite3.Error as exc:
            logging.error(
                "Migration v8: ошибка при создании таблицы task_parts: %s",
                exc,
                exc_info=True,
            )

    def _apply_migration_v9(self):
        """Миграция для расширения учёта заточек."""
        if not self.conn:
            return

        cursor = self.conn.cursor()

        try:
            cursor.execute(
                "ALTER TABLE knife_tracking ADD COLUMN sharp_state TEXT CHECK(sharp_state IN ('заточен','затуплен')) DEFAULT 'заточен';"
            )
        except sqlite3.OperationalError as exc:
            logging.info("Migration v9: колонка knife_tracking.sharp_state уже существует: %s", exc)

        try:
            cursor.execute(
                "ALTER TABLE knife_tracking ADD COLUMN installation_state TEXT CHECK(installation_state IN ('установлен','снят')) DEFAULT 'снят';"
            )
        except sqlite3.OperationalError as exc:
            logging.info("Migration v9: колонка knife_tracking.installation_state уже существует: %s", exc)

        cursor.execute(
            """
                UPDATE knife_tracking
                SET sharp_state = CASE status
                        WHEN 'затуплен' THEN 'затуплен'
                        ELSE COALESCE(sharp_state, 'заточен')
                    END,
                    installation_state = CASE status
                        WHEN 'в работе' THEN 'установлен'
                        ELSE COALESCE(installation_state, 'снят')
                    END
            """
        )

        cursor.execute(
            """
                INSERT OR IGNORE INTO knife_tracking (part_id)
                SELECT p.id
                FROM parts p
                JOIN part_categories pc ON p.category_id = pc.id
                WHERE pc.name IN ('ножи','утюги')
            """
        )

    def _apply_migration_v10(self):
        """Добавляет поддержку сложных компонентов оборудования."""
        if not self.conn:
            return

        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                    CREATE TABLE IF NOT EXISTS complex_components (
                        id INTEGER PRIMARY KEY,
                        equipment_part_id INTEGER NOT NULL UNIQUE,
                        equipment_id INTEGER NOT NULL UNIQUE,
                        FOREIGN KEY (equipment_part_id) REFERENCES equipment_parts(id) ON DELETE CASCADE,
                        FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
                    );
                """
            )
        except sqlite3.Error as exc:
            logging.error(
                "Migration v10: ошибка при создании таблицы complex_components: %s",
                exc,
                exc_info=True,
            )

    def _apply_migration_v11(self):
        """Добавляет поддержку нескольких адресов контрагента и адрес доставки в заказе."""
        if not self.conn:
            return

        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
                    CREATE TABLE IF NOT EXISTS counterparty_addresses (
                        id INTEGER PRIMARY KEY,
                        counterparty_id INTEGER NOT NULL,
                        address TEXT NOT NULL,
                        is_default INTEGER NOT NULL DEFAULT 0,
                        FOREIGN KEY (counterparty_id) REFERENCES counterparties(id) ON DELETE CASCADE
                    );
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS counterparty_addresses_counterparty_id_idx"
                " ON counterparty_addresses(counterparty_id)"
            )
        except sqlite3.Error as exc:
            logging.error("Migration v11: ошибка при создании таблицы counterparty_addresses: %s", exc, exc_info=True)

        try:
            cursor.execute("ALTER TABLE orders ADD COLUMN delivery_address TEXT;")
        except sqlite3.OperationalError as exc:
            logging.info("Migration v11: колонка orders.delivery_address уже существует: %s", exc)

        try:
            cursor.execute("SELECT id, address FROM counterparties WHERE address IS NOT NULL AND TRIM(address) <> ''")
            rows = cursor.fetchall()
            for row in rows:
                cursor.execute(
                    "INSERT OR IGNORE INTO counterparty_addresses (counterparty_id, address, is_default) VALUES (?, ?, 1)",
                    (row["id"], row["address"].strip()),
                )
        except sqlite3.Error as exc:
            logging.error("Migration v11: ошибка переноса адресов контрагентов: %s", exc, exc_info=True)

        try:
            cursor.execute(
                """
                    UPDATE orders
                    SET delivery_address = (
                        SELECT COALESCE(c.address, '')
                        FROM counterparties c
                        WHERE c.id = orders.counterparty_id
                    )
                    WHERE delivery_address IS NULL OR delivery_address = '';
                """
            )
        except sqlite3.Error as exc:
            logging.error("Migration v11: ошибка обновления адресов заказов: %s", exc, exc_info=True)

    def _apply_migration_v12(self):
        """Добавляет таблицу периодических работ."""
        if not self.conn:
            return

        cursor = self.conn.cursor()

        try:
            cursor.executescript(
                """
                    CREATE TABLE IF NOT EXISTS periodic_tasks (
                        id INTEGER PRIMARY KEY,
                        title TEXT NOT NULL,
                        equipment_id INTEGER,
                        equipment_part_id INTEGER,
                        period_days INTEGER NOT NULL CHECK(period_days > 0),
                        last_completed_date TEXT,
                        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d', 'now', 'localtime')),
                        FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE SET NULL,
                        FOREIGN KEY (equipment_part_id) REFERENCES equipment_parts(id) ON DELETE SET NULL
                    );
                    CREATE INDEX IF NOT EXISTS periodic_tasks_due_idx
                        ON periodic_tasks(period_days, last_completed_date);
                """
            )
        except sqlite3.Error as exc:
            logging.error("Migration v12: ошибка при создании таблицы periodic_tasks: %s", exc, exc_info=True)

    def _apply_migration_v13(self):
        """Добавляет хранение настроек приложения и отметку уведомления водителя."""
        if not self.conn:
            return

        cursor = self.conn.cursor()

        try:
            cursor.execute("ALTER TABLE orders ADD COLUMN driver_notified INTEGER NOT NULL DEFAULT 0;")
        except sqlite3.OperationalError as exc:
            logging.info("Migration v13: колонка orders.driver_notified уже существует: %s", exc)

        try:
            cursor.execute(
                """
                    CREATE TABLE IF NOT EXISTS app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                """
            )
        except sqlite3.Error as exc:
            logging.error("Migration v13: ошибка при создании таблицы app_settings: %s", exc, exc_info=True)

    def _apply_migration_v14(self):
        """Добавляет дополнительные поля для контрагентов и запчастей оборудования."""
        if not self.conn:
            return

        cursor = self.conn.cursor()

        try:
            cursor.execute("ALTER TABLE counterparties ADD COLUMN driver_note TEXT;")
        except sqlite3.OperationalError as exc:
            logging.info("Migration v14: колонка counterparties.driver_note уже существует: %s", exc)

        try:
            cursor.execute("ALTER TABLE equipment_parts ADD COLUMN comment TEXT;")
        except sqlite3.OperationalError as exc:
            logging.info("Migration v14: колонка equipment_parts.comment уже существует: %s", exc)

        try:
            cursor.execute("ALTER TABLE equipment_parts ADD COLUMN last_replacement_override TEXT;")
        except sqlite3.OperationalError as exc:
            logging.info("Migration v14: колонка equipment_parts.last_replacement_override уже существует: %s", exc)

    def _apply_migration_v15(self):
        """Добавляет поддержку групп аналогов для запчастей."""
        if not self.conn:
            return

        cursor = self.conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS part_analog_groups (
                id INTEGER PRIMARY KEY,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        try:
            cursor.execute(
                "ALTER TABLE parts ADD COLUMN analog_group_id INTEGER REFERENCES part_analog_groups(id)"
            )
        except sqlite3.OperationalError as exc:
            logging.info("Migration v15: колонка parts.analog_group_id уже существует: %s", exc)

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_parts_analog_group ON parts(analog_group_id)"
        )

    def backup_database(self) -> tuple[bool, str]:
        if not self.conn: return False, "Нет подключения к базе данных."
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"app_{timestamp}.db"
        try:
            logging.info(f"Starting backup to {backup_path}...")
            self.conn.execute(f"VACUUM INTO '{backup_path}'")
            logging.info("Backup completed. Now checking integrity...")
            backup_conn = sqlite3.connect(backup_path)
            cursor = backup_conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            backup_conn.close()
            if result and result[0] == "ok":
                logging.info("Integrity check successful.")
                return True, f"Резервная копия успешно создана и проверена:\n{backup_path}"
            else:
                logging.error(f"Integrity check failed: {result}")
                return False, f"Резервная копия создана, но не прошла проверку целостности:\n{result}"
        except sqlite3.Error as e:
            logging.error(f"Database backup failed: {e}", exc_info=True)
            return False, f"Ошибка при создании резервной копии:\n{e}"

    # --- Dashboard Queries ---
    def get_parts_to_order(self):
        """Возвращает запчасти, у которых текущий остаток меньше минимального."""
        query = """
            SELECT
                p.id,
                p.name,
                p.sku,
                p.qty,
                p.min_qty,
                p.price,
                CASE
                    WHEN p.qty <= 0 AND EXISTS (
                        SELECT 1 FROM equipment_parts ep
                        WHERE ep.part_id = p.id AND ep.requires_replacement = 1
                    ) THEN 1
                    ELSE 0
                END AS requires_replacement_flag
            FROM parts p
            WHERE p.qty < p.min_qty
               OR (
                    p.qty <= 0
                    AND EXISTS (
                        SELECT 1 FROM equipment_parts ep
                        WHERE ep.part_id = p.id AND ep.requires_replacement = 1
                    )
                )
            ORDER BY p.name
        """
        return self.fetchall(query)

    def get_active_tasks(self):
        """Возвращает незавершенные задачи, отсортированные по приоритету и сроку."""
        query = """
            SELECT t.id, t.title, t.description, t.priority, t.due_date, t.status,
                   t.is_replacement,
                   e.name as equipment_name, c.name as assignee_name
            FROM tasks t
            LEFT JOIN colleagues c ON t.assignee_id = c.id
            LEFT JOIN equipment e ON t.equipment_id = e.id
            WHERE t.status NOT IN ('выполнена', 'отменена')
            ORDER BY
                CASE t.priority WHEN 'высокий' THEN 1 WHEN 'средний' THEN 2 WHEN 'низкий' THEN 3 ELSE 4 END,
                t.due_date
        """
        return self.fetchall(query)

    def get_active_orders(self):
        """Возвращает заказы со статусом 'создан' или 'в пути'."""
        query = """
            SELECT o.id,
                   o.counterparty_id,
                   c.name as counterparty_name,
                   o.invoice_no,
                   o.invoice_date,
                   o.delivery_date,
                   o.delivery_address,
                   o.status,
                   o.comment,
                   o.driver_notified,
                   c.address as counterparty_address,
                   c.driver_note as counterparty_driver_note
            FROM orders o
            JOIN counterparties c ON o.counterparty_id = c.id
            WHERE o.status IN ('создан', 'в пути')
            ORDER BY o.delivery_date
        """
        return self.fetchall(query)


    # --- Parts & Categories ---
    def get_all_parts(self):
        query = """
            SELECT p.id, p.name, p.sku, p.qty, p.min_qty, p.price, p.category_id,
                   pc.name as category_name,
                   (SELECT GROUP_CONCAT(eq.name, ', ') FROM equipment_parts ep
                    JOIN equipment eq ON ep.equipment_id = eq.id WHERE ep.part_id = p.id) as equipment_list,
                   p.analog_group_id,
                   (
                        SELECT COUNT(*)
                        FROM parts pa
                        WHERE pa.analog_group_id = p.analog_group_id
                    ) as analog_group_size,
                   (
                        SELECT GROUP_CONCAT(
                            pa.name || CASE
                                WHEN pa.sku IS NOT NULL AND pa.sku != '' THEN ' (' || pa.sku || ')'
                                ELSE ''
                            END,
                            ', '
                        )
                        FROM parts pa
                        WHERE pa.analog_group_id = p.analog_group_id AND pa.id != p.id
                    ) as analog_names
            FROM parts p LEFT JOIN part_categories pc ON p.category_id = pc.id
            GROUP BY p.id ORDER BY p.name
        """
        return self.fetchall(query)
    def get_part_by_id(self, part_id): return self.fetchone("SELECT * FROM parts WHERE id = ?", (part_id,))

    def get_equipment_display_for_part(self, part_id: int) -> str:
        """Возвращает строку с перечнем оборудования, к которому привязана запчасть."""
        if not part_id:
            return ""

        rows = self.fetchall(
            """
                SELECT e.name, e.sku
                FROM equipment_parts ep
                JOIN equipment e ON ep.equipment_id = e.id
                WHERE ep.part_id = ?
                ORDER BY e.name
            """,
            (part_id,),
        )

        formatted: list[str] = []
        for row in rows:
            # sqlite3.Row поддерживает доступ как по индексу, так и по ключу.
            name = row["name"] if row else None
            sku = row["sku"] if row else None
            if not name:
                continue
            formatted.append(f"{name} ({sku})" if sku else name)

        return ", ".join(formatted)

    def _ensure_knife_tracking(self, cursor, part_id, category_id):
        """Проверяет и создаёт запись для отслеживания заточки."""
        if category_id is None:
            return

        if category_id not in self._sharpening_category_ids:
            row = cursor.execute(
                "SELECT name FROM part_categories WHERE id = ?",
                (category_id,),
            ).fetchone()
            if not row or row["name"].lower() not in {"ножи", "утюги"}:
                return
            self._sharpening_category_ids.add(category_id)

        cursor.execute("INSERT OR IGNORE INTO knife_tracking (part_id) VALUES (?)", (part_id,))
    
    def add_part(self, name, sku, qty, min_qty, price, category_id):
        if not self.conn:
            return False, "Нет подключения к БД.", None
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute(
                    "INSERT INTO parts (name, sku, qty, min_qty, price, category_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, sku, qty, min_qty, price, category_id),
                )
                part_id = cursor.lastrowid
                self._ensure_knife_tracking(cursor, part_id, category_id)
            self._log_action(
                f"Добавлена запчасть #{part_id}: {name} (артикул: {sku}, остаток: {qty}, минимум: {min_qty}, цена: {price:.2f})"
            )
            return True, "Запчасть успешно добавлена.", part_id
        except sqlite3.IntegrityError:
            return False, "Запчасть с таким Наименованием и Артикулом уже существует.", None

    def update_part(self, part_id, name, sku, qty, min_qty, price, category_id):
        if not self.conn: return False, "Нет подключения к БД."
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE parts SET name=?, sku=?, qty=?, min_qty=?, price=?, category_id=? WHERE id=?",
                               (name, sku, qty, min_qty, price, category_id, part_id))
                self._ensure_knife_tracking(cursor, part_id, category_id)
            self._log_action(
                f"Обновлена запчасть #{part_id}: {name} (артикул: {sku}, остаток: {qty}, минимум: {min_qty}, цена: {price:.2f})"
            )
            return True, "Данные запчасти обновлены."
        except sqlite3.IntegrityError:
            return False, "Запчасть с таким Наименованием и Артикулом уже существует."

    def delete_part(self, part_id):
        if not self.conn:
            return False, "Нет подключения к БД."

        part = self.get_part_by_id(part_id)
        try:
            if self.fetchone("SELECT 1 FROM equipment_parts WHERE part_id = ?", (part_id,)): return False, "Удаление невозможно: запчасть привязана к оборудованию."
            if self.fetchone("SELECT 1 FROM order_items WHERE part_id = ?", (part_id,)): return False, "Удаление невозможно: запчасть используется в заказах."
            if self.fetchone("SELECT 1 FROM replacements WHERE part_id = ?", (part_id,)): return False, "Удаление невозможно: запчасть используется в истории замен."

            deleted_status_rows = deleted_sharpen_rows = deleted_tracking_rows = 0

            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM knife_status_log WHERE part_id = ?", (part_id,))
                deleted_status_rows = cursor.rowcount
                cursor.execute("DELETE FROM knife_sharpen_log WHERE part_id = ?", (part_id,))
                deleted_sharpen_rows = cursor.rowcount
                cursor.execute("DELETE FROM knife_tracking WHERE part_id = ?", (part_id,))
                deleted_tracking_rows = cursor.rowcount
                cursor.execute("DELETE FROM parts WHERE id = ?", (part_id,))
                self._cleanup_orphan_analog_groups(cursor)

            if deleted_status_rows or deleted_sharpen_rows or deleted_tracking_rows:
                self._log_action(
                    f"Удалены записи отслеживания ножа при удалении запчасти #{part_id}."
                )

            if part:
                self._log_action(f"Удалена запчасть #{part_id}: {part['name']} (артикул: {part['sku']})")
            else:
                self._log_action(f"Удалена запчасть #{part_id}")
            return True, "Запчасть удалена."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"

    def get_part_categories(self): return self.fetchall("SELECT id, name FROM part_categories ORDER BY name")
    def add_part_category(self, name):
        try:
            self.execute("INSERT INTO part_categories (name) VALUES (?)", (name,))
            if self.conn: self.conn.commit()
            self._log_action(f"Добавлена категория запчастей: {name}")
            return True, "Категория добавлена."
        except sqlite3.IntegrityError: return False, "Категория с таким именем уже существует."
    def update_part_category(self, category_id, name):
        try:
            self.execute("UPDATE part_categories SET name = ? WHERE id = ?", (name, category_id))
            if self.conn: self.conn.commit()
            self._log_action(f"Обновлена категория запчастей #{category_id}: {name}")
            return True, "Категория переименована."
        except sqlite3.IntegrityError: return False, "Категория с таким именем уже существует."
    def delete_part_category(self, category_id):
        if category_id == self._knives_category_id:
            return False, "Системную категорию 'ножи' нельзя удалить."
        try:
            category = self.fetchone("SELECT name FROM part_categories WHERE id = ?", (category_id,))
            self.execute("DELETE FROM part_categories WHERE id = ?", (category_id,))
            if self.conn: self.conn.commit()
            if category:
                self._log_action(f"Удалена категория запчастей #{category_id}: {category['name']}")
            else:
                self._log_action(f"Удалена категория запчастей #{category_id}")
            return True, "Категория удалена."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"

    # --- Counterparties, Orders, Equipment etc. (existing methods) ---
    def get_all_counterparties(self):
        counterparties = self.fetchall("SELECT * FROM counterparties ORDER BY name")
        addresses_map = self._get_counterparty_addresses_map()

        for counterparty in counterparties:
            addresses = addresses_map.get(counterparty["id"], [])
            counterparty["addresses"] = addresses
            default_address = next((a["address"] for a in addresses if a.get("is_default")), counterparty.get("address", ""))
            counterparty["default_address"] = default_address
            counterparty["address"] = self._format_addresses_for_display(addresses) if addresses else default_address

        return counterparties

    def get_counterparty_by_id(self, counterparty_id):
        counterparty = self.fetchone("SELECT * FROM counterparties WHERE id = ?", (counterparty_id,))
        if not counterparty:
            return None

        addresses_map = self._get_counterparty_addresses_map([counterparty_id])
        addresses = addresses_map.get(counterparty_id, [])
        counterparty["addresses"] = addresses
        default_address = next((a["address"] for a in addresses if a.get("is_default")), counterparty.get("address", ""))
        counterparty["default_address"] = default_address
        counterparty["address"] = self._format_addresses_for_display(addresses) if addresses else default_address
        return counterparty
    def add_counterparty(
        self,
        name,
        address,
        contact_person,
        phone,
        email,
        note,
        driver_note,
        addresses=None,
    ):
        normalized_addresses = self._normalize_addresses(addresses)
        if not normalized_addresses and address:
            normalized_addresses = self._normalize_addresses([address])
        default_address = normalized_addresses[0]["address"] if normalized_addresses else (address or "")

        try:
            if not self.conn:
                return False, "Нет подключения к БД."
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute(
                    (
                        "INSERT INTO counterparties (name, address, contact_person, phone, email, note, driver_note)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)"
                    ),
                    (name, default_address, contact_person, phone, email, note, driver_note),
                )
                counterparty_id = cursor.lastrowid
                if normalized_addresses:
                    self._replace_counterparty_addresses(cursor, counterparty_id, normalized_addresses)
            self._log_action(f"Добавлен контрагент: {name}")
            return True, "Контрагент добавлен."
        except sqlite3.IntegrityError:
            return False, "Контрагент с таким именем уже существует."

    def update_counterparty(
        self,
        c_id,
        name,
        address,
        contact_person,
        phone,
        email,
        note,
        driver_note,
        addresses=None,
    ):
        normalized_addresses = self._normalize_addresses(addresses)
        if not normalized_addresses and address:
            normalized_addresses = self._normalize_addresses([address])
        default_address = normalized_addresses[0]["address"] if normalized_addresses else (address or "")

        try:
            if not self.conn:
                return False, "Нет подключения к БД."
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute(
                    (
                        "UPDATE counterparties SET name=?, address=?, contact_person=?, phone=?, email=?, note=?, driver_note=?"
                        " WHERE id=?"
                    ),
                    (name, default_address, contact_person, phone, email, note, driver_note, c_id),
                )
                if normalized_addresses:
                    self._replace_counterparty_addresses(cursor, c_id, normalized_addresses)
                else:
                    cursor.execute("DELETE FROM counterparty_addresses WHERE counterparty_id = ?", (c_id,))
            self._log_action(f"Обновлён контрагент #{c_id}: {name}")
            return True, "Данные контрагента обновлены."
        except sqlite3.IntegrityError:
            return False, "Контрагент с таким именем уже существует."
    def delete_counterparty(self, c_id):
        if self.fetchone("SELECT 1 FROM orders WHERE counterparty_id = ?", (c_id,)): return False, "Удаление невозможно: у контрагента есть заказы."
        try:
            counterparty = self.fetchone("SELECT name FROM counterparties WHERE id = ?", (c_id,))
            self.execute("DELETE FROM counterparties WHERE id = ?", (c_id,))
            if self.conn: self.conn.commit()
            if counterparty:
                self._log_action(f"Удалён контрагент #{c_id}: {counterparty['name']}")
            else:
                self._log_action(f"Удалён контрагент #{c_id}")
            return True, "Контрагент удален."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def get_all_orders_with_counterparty(self):
        query = """
            SELECT o.id,
                   o.counterparty_id,
                   c.name as counterparty_name,
                   o.invoice_no,
                   o.invoice_date,
                   o.delivery_date,
                   o.delivery_address,
                   o.created_at,
                   o.status,
                   o.comment,
                   o.driver_notified,
                   c.address as counterparty_address,
                   c.driver_note as counterparty_driver_note
            FROM orders o
            JOIN counterparties c ON o.counterparty_id = c.id
            ORDER BY o.created_at DESC
        """
        return self.fetchall(query)

    def get_order_with_details(self, order_id: int):
        query = """
            SELECT o.id,
                   o.counterparty_id,
                   c.name AS counterparty_name,
                   o.invoice_no,
                   o.invoice_date,
                   o.delivery_date,
                   o.delivery_address,
                   o.status,
                   o.comment,
                   o.driver_notified,
                   c.address AS counterparty_address,
                   c.driver_note AS counterparty_driver_note
            FROM orders o
            JOIN counterparties c ON o.counterparty_id = c.id
            WHERE o.id = ?
        """
        return self.fetchone(query, (order_id,))

    def get_completed_orders_history(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        counterparty_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Возвращает историю выполненных заказов с учётом фильтров."""

        base_query = """
            SELECT
                o.id,
                o.counterparty_id,
                c.name AS counterparty_name,
                o.invoice_no,
                o.invoice_date,
                o.delivery_date,
                o.created_at,
                o.delivery_address,
                o.status,
                o.comment,
                o.driver_notified,
                c.address AS counterparty_address,
                c.driver_note AS counterparty_driver_note
            FROM orders o
            JOIN counterparties c ON o.counterparty_id = c.id
            WHERE o.status = 'принят'
        """

        conditions: list[str] = []
        params: list[Any] = []

        if start_date:
            conditions.append(
                "COALESCE(o.delivery_date, o.invoice_date, substr(o.created_at, 1, 10)) >= ?"
            )
            params.append(start_date)

        if end_date:
            conditions.append(
                "COALESCE(o.delivery_date, o.invoice_date, substr(o.created_at, 1, 10)) <= ?"
            )
            params.append(end_date)

        if counterparty_id:
            conditions.append("o.counterparty_id = ?")
            params.append(counterparty_id)

        if conditions:
            base_query += " AND " + " AND ".join(conditions)

        base_query += (
            " ORDER BY "
            "COALESCE(o.delivery_date, o.invoice_date, substr(o.created_at, 1, 10)) DESC, "
            "o.id DESC"
        )

        return self.fetchall(base_query, tuple(params))
    def get_order_details(self, order_id): return self.fetchone("SELECT * FROM orders WHERE id = ?", (order_id,))
    def get_order_items(self, order_id): return self.fetchall("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    def create_order_with_items(self, order_data, items_data):
        if not self.conn: return False, "Нет подключения к БД."
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute(
                    """INSERT INTO orders (counterparty_id, invoice_no, invoice_date, delivery_date, delivery_address, status, comment)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (order_data['counterparty_id'], order_data['invoice_no'], order_data['invoice_date'],
                     order_data['delivery_date'], order_data.get('delivery_address'), order_data['status'], order_data['comment'])
                )
                order_id = cursor.lastrowid
                for item in items_data:
                    part_id, name, sku, qty, price, original_price = item

                    if part_id is not None and price != original_price:
                        cursor.execute("UPDATE parts SET price = ? WHERE id = ?", (price, part_id))

                    cursor.execute(
                        """INSERT INTO order_items (order_id, part_id, name, sku, qty, price)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (order_id, part_id, name, sku, qty, price)
                    )
            self._log_action(
                f"Создан заказ #{order_id} для контрагента #{order_data['counterparty_id']} со статусом '{order_data['status']}'"
            )
            return True, "Заказ успешно создан."
        except sqlite3.Error as e:
            logging.error(f"Ошибка транзакции при создании заказа: {e}", exc_info=True)
            return False, f"Ошибка транзакции: {e}"
    def update_order_with_items(self, order_id, order_data, items_data):
        if not self.conn: return False, "Нет подключения к БД."
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute(
                    """UPDATE orders SET counterparty_id=?, invoice_no=?, invoice_date=?, delivery_date=?, delivery_address=?, status=?, comment=?
                       WHERE id=?""",
                    (order_data['counterparty_id'], order_data['invoice_no'], order_data['invoice_date'],
                     order_data['delivery_date'], order_data.get('delivery_address'), order_data['status'], order_data['comment'], order_id)
                )
                cursor.execute("DELETE FROM order_items WHERE order_id=?", (order_id,))
                for item in items_data:
                    part_id, name, sku, qty, price, original_price = item

                    if part_id is not None and price != original_price:
                        cursor.execute("UPDATE parts SET price = ? WHERE id = ?", (price, part_id))

                    cursor.execute(
                        """INSERT INTO order_items (order_id, part_id, name, sku, qty, price)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (order_id, part_id, name, sku, qty, price)
                    )
            self._log_action(
                f"Обновлён заказ #{order_id} (контрагент #{order_data['counterparty_id']}, статус '{order_data['status']}')"
            )
            return True, "Заказ успешно обновлен."
        except sqlite3.Error as e:
            logging.error(f"Ошибка транзакции при обновлении заказа: {e}", exc_info=True)
            return False, f"Ошибка транзакции: {e}"
    def update_order_status(self, order_id, new_status):
        """Обновляет только статус заказа."""
        try:
            if new_status == 'принят':
                return self.accept_delivery(order_id)

            self.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
            if self.conn: self.conn.commit()
            self._log_action(f"Изменён статус заказа #{order_id} на '{new_status}'")
            return True, "Статус заказа обновлен."
        except sqlite3.Error as e:
            return False, f"Ошибка базы данных: {e}"
    def delete_order(self, order_id):
        """Транзакционно удаляет заказ и связанные с ним позиции."""
        if not self.conn: return False, "Нет подключения к БД."
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
                cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            self._log_action(f"Удалён заказ #{order_id}")
            return True, "Заказ успешно удален."
        except sqlite3.Error as e:
            logging.error(f"Ошибка транзакции при удалении заказа: {e}", exc_info=True)
            return False, f"Ошибка транзакции: {e}"
    def accept_delivery(self, order_id):
        if not self.conn: return False, "Нет подключения к БД."
        order = self.get_order_details(order_id)
        if not order or order['status'] not in ('создан', 'в пути'):
            return False, "Принять поставку можно только для заказов в статусе 'создан' или 'в пути'."
        
        items = self.get_order_items(order_id)
        try:
            with self.conn:
                cursor = self.conn.cursor()
                for item in items:
                    part_id = item['part_id']
                    if not part_id:
                        existing_part = self.fetchone("SELECT id FROM parts WHERE name = ? AND sku = ?", (item['name'], item['sku']))
                        if existing_part:
                            part_id = existing_part['id']
                        else:
                            cursor.execute("INSERT INTO parts (name, sku, price, qty) VALUES (?, ?, ?, 0)", (item['name'], item['sku'], item['price']))
                            part_id = cursor.lastrowid
                            cursor.execute("UPDATE order_items SET part_id = ? WHERE id = ?", (part_id, item['id']))

                    cursor.execute("UPDATE parts SET qty = qty + ? WHERE id = ?", (item['qty'], part_id))
                cursor.execute("UPDATE orders SET status = 'принят' WHERE id = ?", (order_id,))
            self._log_action(f"Принята поставка по заказу #{order_id}. Обновлены остатки по {len(items)} поз. товара")
            return True, "Поставка успешно принята, остатки на складе обновлены."
        except sqlite3.Error as e:
            logging.error(f"Ошибка транзакции при приемке поставки: {e}", exc_info=True)
            return False, f"Ошибка транзакции: {e}"
    def get_equipment_categories(self): return self.fetchall("SELECT id, name FROM equipment_categories ORDER BY name")
    def add_equipment_category(self, name):
        try:
            self.execute("INSERT INTO equipment_categories (name) VALUES (?)", (name,))
            if self.conn: self.conn.commit()
            self._log_action(f"Добавлена категория оборудования: {name}")
            return True, "Категория добавлена."
        except sqlite3.IntegrityError: return False, "Категория с таким именем уже существует."
    def update_equipment_category(self, cat_id, name):
        try:
            self.execute("UPDATE equipment_categories SET name = ? WHERE id = ?", (name, cat_id))
            if self.conn: self.conn.commit()
            self._log_action(f"Обновлена категория оборудования #{cat_id}: {name}")
            return True, "Категория обновлена."
        except sqlite3.IntegrityError: return False, "Категория с таким именем уже существует."
    def delete_equipment_category(self, cat_id):
        if self.fetchone("SELECT 1 FROM equipment WHERE category_id = ?", (cat_id,)): return False, "Удаление невозможно: в категории есть оборудование."
        try:
            category = self.fetchone("SELECT name FROM equipment_categories WHERE id = ?", (cat_id,))
            self.execute("DELETE FROM equipment_categories WHERE id = ?", (cat_id,))
            if self.conn: self.conn.commit()
            if category:
                self._log_action(f"Удалена категория оборудования #{cat_id}: {category['name']}")
            else:
                self._log_action(f"Удалена категория оборудования #{cat_id}")
            return True, "Категория удалена."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def get_all_equipment(self):
        return self.fetchall("SELECT id, name, sku, category_id, parent_id, comment FROM equipment ORDER BY name")

    def add_equipment(self, name, sku, category_id, parent_id=None, comment=None):
        try:
            self.execute(
                "INSERT INTO equipment (name, sku, category_id, parent_id, comment) VALUES (?, ?, ?, ?, ?)",
                (name, sku, category_id, parent_id, comment),
            )
            if self.conn: self.conn.commit()
            self._log_action(f"Добавлено оборудование: {name} (артикул: {sku or 'нет'}, категория #{category_id})")
            return True, "Оборудование добавлено."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def update_equipment(self, eq_id, name, sku, category_id, parent_id=None, comment=None):
        try:
            if eq_id and eq_id == parent_id: return False, "Оборудование не может быть родителем для самого себя."
            self.execute(
                "UPDATE equipment SET name=?, sku=?, category_id=?, parent_id=?, comment=? WHERE id=?",
                (name, sku, category_id, parent_id, comment, eq_id),
            )
            if self.conn: self.conn.commit()
            self._log_action(f"Обновлено оборудование #{eq_id}: {name} (артикул: {sku or 'нет'})")
            return True, "Данные оборудования обновлены."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"

    def update_equipment_comment(self, eq_id: int, comment: str):
        if not self.conn:
            return False, "Нет подключения к БД."

        try:
            self.execute("UPDATE equipment SET comment = ? WHERE id = ?", (comment, eq_id))
            if self.conn:
                self.conn.commit()
            self._log_action(f"Обновлён комментарий оборудования #{eq_id}")
            return True, "Комментарий обновлен."
        except sqlite3.Error as e:
            logging.error("Ошибка обновления комментария оборудования #%s: %s", eq_id, e, exc_info=True)
            return False, f"Ошибка базы данных: {e}"
    def delete_equipment(self, eq_id):
        if self.fetchone("SELECT 1 FROM equipment_parts WHERE equipment_id = ?", (eq_id,)): return False, "Удаление невозможно: к оборудованию привязаны запчасти."
        if self.fetchone("SELECT 1 FROM replacements WHERE equipment_id = ?", (eq_id,)): return False, "Удаление невозможно: оборудование фигурирует в истории замен."
        try:
            equipment = self.fetchone("SELECT name, sku FROM equipment WHERE id = ?", (eq_id,))
            self.execute("DELETE FROM equipment WHERE id = ?", (eq_id,))
            if self.conn: self.conn.commit()
            if equipment:
                self._log_action(f"Удалено оборудование #{eq_id}: {equipment['name']} (артикул: {equipment['sku'] or 'нет'})")
            else:
                self._log_action(f"Удалено оборудование #{eq_id}")
            return True, "Оборудование удалено."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def get_parts_for_equipment(self, equipment_id):
        query = """
            SELECT ep.id as equipment_part_id,
                   ep.equipment_id,
                   p.id as part_id,
                   p.name as part_name,
                   p.sku as part_sku,
                   ep.installed_qty,
                   ep.requires_replacement,
                   ep.comment as part_comment,
                   ep.last_replacement_override,
                   pc.name as category_name,
                   cc.equipment_id AS component_equipment_id,
                   COALESCE(
                       ep.last_replacement_override,
                       (
                           SELECT MAX(r.date)
                           FROM replacements r
                           WHERE r.part_id = p.id AND r.equipment_id = ep.equipment_id
                        )
                   ) as last_replacement_date,
                   p.analog_group_id,
                   (
                        SELECT COUNT(*)
                        FROM parts pa
                        WHERE pa.analog_group_id = p.analog_group_id
                    ) as analog_group_size,
                   (
                        SELECT GROUP_CONCAT(
                            pa.name || CASE
                                WHEN pa.sku IS NOT NULL AND pa.sku != '' THEN ' (' || pa.sku || ')'
                                ELSE ''
                            END,
                            ', '
                        )
                        FROM parts pa
                        WHERE pa.analog_group_id = p.analog_group_id AND pa.id != p.id
                    ) as analog_names
            FROM equipment_parts ep
                JOIN parts p ON ep.part_id = p.id
                LEFT JOIN part_categories pc ON p.category_id = pc.id
                LEFT JOIN complex_components cc ON cc.equipment_part_id = ep.id
            WHERE ep.equipment_id = ?
            ORDER BY pc.name IS NULL, pc.name, p.name
        """
        return self.fetchall(query, (equipment_id,))

    def _cleanup_orphan_analog_groups(self, cursor: sqlite3.Cursor | None = None):
        if not self.conn:
            return

        local_cursor = cursor or self.conn.cursor()
        local_cursor.execute(
            """
            DELETE FROM part_analog_groups
            WHERE id NOT IN (
                SELECT DISTINCT analog_group_id FROM parts WHERE analog_group_id IS NOT NULL
            )
            """
        )

    def set_parts_as_analogs(self, part_ids: list[int]):
        if not self.conn:
            return False, "Нет подключения к базе данных."

        unique_ids = sorted({int(pid) for pid in part_ids if pid})
        if len(unique_ids) < 2:
            return False, "Для создания группы аналогов выберите минимум две запчасти."

        placeholders = ",".join("?" for _ in unique_ids)

        try:
            with self.conn:
                cursor = self.conn.cursor()
                rows = cursor.execute(
                    f"SELECT id, analog_group_id FROM parts WHERE id IN ({placeholders})",
                    tuple(unique_ids),
                ).fetchall()

                if len(rows) != len(unique_ids):
                    found_ids = {row["id"] for row in rows}
                    missing = sorted(set(unique_ids) - found_ids)
                    return False, "Запчасти не найдены: " + ", ".join(map(str, missing))

                old_group_ids = {
                    row["analog_group_id"] for row in rows if row["analog_group_id"] is not None
                }

                cursor.execute(
                    f"UPDATE parts SET analog_group_id = NULL WHERE id IN ({placeholders})",
                    tuple(unique_ids),
                )

                cursor.execute("INSERT INTO part_analog_groups DEFAULT VALUES")
                group_id = cursor.lastrowid

                cursor.execute(
                    f"UPDATE parts SET analog_group_id = ? WHERE id IN ({placeholders})",
                    (group_id, *unique_ids),
                )

                if old_group_ids:
                    for group_id_to_check in old_group_ids:
                        cursor.execute(
                            "DELETE FROM part_analog_groups WHERE id = ? AND NOT EXISTS (SELECT 1 FROM parts WHERE analog_group_id = ?)",
                            (group_id_to_check, group_id_to_check),
                        )

                self._log_action(
                    "Сформирована группа аналогов #%s для запчастей: %s"
                    % (group_id, ", ".join(map(str, unique_ids)))
                )

            return True, "Запчасти объединены в группу аналогов."
        except sqlite3.Error as exc:
            logging.error("Ошибка при создании группы аналогов: %s", exc, exc_info=True)
            return False, f"Ошибка базы данных: {exc}"

    def get_analogs_for_part(self, part_id: int):
        query = """
            SELECT p2.id, p2.name, p2.sku, p2.qty
            FROM parts p1
            JOIN parts p2 ON p1.analog_group_id = p2.analog_group_id
            WHERE p1.id = ? AND p2.id != ?
            ORDER BY p2.name
        """
        return self.fetchall(query, (part_id, part_id))

    def replace_equipment_part_with_analog(self, equipment_part_id: int, new_part_id: int):
        if not self.conn:
            return False, "Нет подключения к базе данных.", {}

        try:
            with self.conn:
                cursor = self.conn.cursor()
                link = cursor.execute(
                    """
                    SELECT equipment_id, part_id
                    FROM equipment_parts
                    WHERE id = ?
                    """,
                    (equipment_part_id,),
                ).fetchone()

                if not link:
                    return False, "Привязка запчасти не найдена.", {}

                if link["part_id"] == new_part_id:
                    return False, "Указанный аналог уже установлен.", {}

                if not cursor.execute(
                    "SELECT 1 FROM parts WHERE id = ?",
                    (new_part_id,),
                ).fetchone():
                    return False, "Аналог не найден.", {}

                analog_pair = cursor.execute(
                    """
                    SELECT 1
                    FROM parts p1
                    JOIN parts p2 ON p1.analog_group_id = p2.analog_group_id
                    WHERE p1.id = ? AND p2.id = ?
                    """,
                    (link["part_id"], new_part_id),
                ).fetchone()

                if not analog_pair:
                    return False, "Выбранная запчасть не является аналогом текущей.", {}

                duplicate = cursor.execute(
                    "SELECT 1 FROM equipment_parts WHERE equipment_id = ? AND part_id = ?",
                    (link["equipment_id"], new_part_id),
                ).fetchone()

                if duplicate:
                    return False, "Аналог уже привязан к данному оборудованию.", {}

                cursor.execute(
                    "UPDATE equipment_parts SET part_id = ?, requires_replacement = 0 WHERE id = ?",
                    (new_part_id, equipment_part_id),
                )

                self._log_action(
                    f"Запчасть #{link['part_id']} заменена на аналог #{new_part_id} на оборудовании #{link['equipment_id']}"
                )

                payload = {
                    "equipment_id": link["equipment_id"],
                    "old_part_id": link["part_id"],
                    "new_part_id": new_part_id,
                }

            return True, "Запчасть заменена на выбранный аналог.", payload
        except sqlite3.Error as exc:
            logging.error(
                "Ошибка при замене запчасти на аналог #%s: %s", equipment_part_id, exc, exc_info=True
            )
            return False, f"Ошибка базы данных: {exc}", {}
    def attach_part_to_equipment(
        self,
        equipment_id,
        part_id,
        qty,
        comment: str | None = None,
        last_replacement: str | None = None,
    ):
        try:
            self.execute(
                """
                INSERT INTO equipment_parts (equipment_id, part_id, installed_qty, comment, last_replacement_override)
                VALUES (?, ?, ?, ?, ?)
                """,
                (equipment_id, part_id, qty, comment or None, last_replacement or None),
            )
            if self.conn: self.conn.commit()
            self._log_action(f"Привязана запчасть #{part_id} к оборудованию #{equipment_id} (количество: {qty})")
            return True, "Запчасть успешно привязана."
        except sqlite3.IntegrityError: return False, "Эта запчасть уже привязана к данному оборудованию."

    def update_equipment_part_comment(self, equipment_part_id: int, comment: str) -> tuple[bool, str]:
        if not self.conn:
            return False, "Нет подключения к БД."

        try:
            self.execute(
                "UPDATE equipment_parts SET comment = ? WHERE id = ?",
                (comment or None, equipment_part_id),
            )
            if self.conn:
                self.conn.commit()
            self._log_action(f"Обновлен комментарий привязанной запчасти #{equipment_part_id}")
            return True, "Комментарий обновлен."
        except sqlite3.Error as exc:
            logging.error(
                "Ошибка обновления комментария запчасти #%s: %s", equipment_part_id, exc, exc_info=True
            )
            return False, f"Ошибка базы данных: {exc}"
    def detach_part_from_equipment(self, equipment_part_id):
        if not self.conn:
            return False, "Нет подключения к БД."

        try:
            with self.conn:
                cursor = self.conn.cursor()
                link = cursor.execute(
                    "SELECT equipment_id, part_id FROM equipment_parts WHERE id = ?",
                    (equipment_part_id,),
                ).fetchone()

                if not link:
                    return False, "Привязка запчасти не найдена."

                component_row = cursor.execute(
                    "SELECT equipment_id FROM complex_components WHERE equipment_part_id = ?",
                    (equipment_part_id,),
                ).fetchone()

                if component_row:
                    component_equipment_id = component_row["equipment_id"]
                    has_children = cursor.execute(
                        "SELECT 1 FROM equipment_parts WHERE equipment_id = ? LIMIT 1",
                        (component_equipment_id,),
                    ).fetchone()
                    if has_children:
                        return False, "Нельзя отвязать сложный компонент, к которому привязаны запчасти."

                    cursor.execute(
                        "DELETE FROM complex_components WHERE equipment_part_id = ?",
                        (equipment_part_id,),
                    )
                    cursor.execute(
                        "DELETE FROM equipment WHERE id = ?",
                        (component_equipment_id,),
                    )

                cursor.execute(
                    "DELETE FROM equipment_parts WHERE id = ?",
                    (equipment_part_id,),
                )

            self._log_action(
                f"Отвязана запчасть #{link['part_id']} от оборудования #{link['equipment_id']}"
            )
            return True, "Запчасть отвязана."
        except sqlite3.Error as e:
            logging.error(
                "Ошибка при отвязке запчасти #%s: %s", equipment_part_id, e, exc_info=True
            )
            return False, f"Ошибка базы данных: {e}"

    def update_attached_part(
        self,
        equipment_part_id: int,
        name: str,
        sku: str,
        installed_qty: int,
        last_replacement_override: str | None = None,
    ):
        """Обновляет данные привязанной запчасти (наименование, артикул, количество, последнюю замену)."""
        if not self.conn:
            return False, "Нет подключения к БД.", {}

        if installed_qty <= 0:
            return False, "Установленное количество должно быть больше нуля.", {}

        last_replacement_value = (last_replacement_override or "").strip() or None

        try:
            with self.conn:
                cursor = self.conn.cursor()
                link = cursor.execute(
                    """
                    SELECT equipment_id, part_id, installed_qty, last_replacement_override
                    FROM equipment_parts
                    WHERE id = ?
                    """,
                    (equipment_part_id,),
                ).fetchone()

                if not link:
                    return False, "Привязка запчасти не найдена.", {}

                part_row = cursor.execute(
                    "SELECT name, sku, qty, min_qty, price, category_id FROM parts WHERE id = ?",
                    (link["part_id"],),
                ).fetchone()

                if not part_row:
                    return False, "Запчасть не найдена.", {}

                cursor.execute(
                    "UPDATE equipment_parts SET installed_qty = ?, last_replacement_override = ? WHERE id = ?",
                    (installed_qty, last_replacement_value, equipment_part_id),
                )

                name_changed = name != part_row["name"] or sku != part_row["sku"]
                if name_changed:
                    cursor.execute(
                        "UPDATE parts SET name = ?, sku = ? WHERE id = ?",
                        (name, sku, link["part_id"]),
                    )
                    cursor.execute(
                        """
                        UPDATE equipment
                        SET name = ?, sku = ?
                        WHERE id IN (
                            SELECT cc.equipment_id
                            FROM complex_components cc
                            JOIN equipment_parts ep ON cc.equipment_part_id = ep.id
                            WHERE ep.part_id = ?
                        )
                        """,
                        (name, sku, link["part_id"]),
                    )

            self._log_action(
                "Обновлена привязанная запчасть #{part_id} к оборудованию #{equipment_id}: "
                "имя '{old_name}' → '{new_name}', артикул '{old_sku}' → '{new_sku}', "
                "количество {old_qty} → {new_qty}, последняя замена '{old_last}' → '{new_last}'".format(
                    part_id=link["part_id"],
                    equipment_id=link["equipment_id"],
                    old_name=part_row["name"],
                    new_name=name,
                    old_sku=part_row["sku"],
                    new_sku=sku,
                    old_qty=link["installed_qty"],
                    new_qty=installed_qty,
                    old_last=link["last_replacement_override"] or "",
                    new_last=last_replacement_value or "",
                )
            )

            return True, "Данные привязанной запчасти обновлены.", {
                "equipment_id": link["equipment_id"],
                "part_id": link["part_id"],
                "name_changed": name_changed,
            }
        except sqlite3.IntegrityError:
            return False, "Запчасть с таким Наименованием и Артикулом уже существует.", {}
        except sqlite3.Error as e:
            logging.error(
                "Ошибка при обновлении привязанной запчасти #%s: %s",
                equipment_part_id,
                e,
                exc_info=True,
            )
            return False, f"Ошибка базы данных: {e}", {}

    def mark_equipment_part_as_complex(self, equipment_part_id: int):
        if not self.conn:
            return False, "Нет подключения к БД.", {}

        try:
            with self.conn:
                cursor = self.conn.cursor()
                part_row = cursor.execute(
                    """
                        SELECT ep.equipment_id, ep.part_id, p.name AS part_name, p.sku AS part_sku,
                               e.category_id
                        FROM equipment_parts ep
                        JOIN parts p ON ep.part_id = p.id
                        JOIN equipment e ON ep.equipment_id = e.id
                        WHERE ep.id = ?
                    """,
                    (equipment_part_id,),
                ).fetchone()

                if not part_row:
                    return False, "Запчасть не найдена.", {}

                existing = cursor.execute(
                    "SELECT equipment_id FROM complex_components WHERE equipment_part_id = ?",
                    (equipment_part_id,),
                ).fetchone()
                if existing:
                    return False, "Запчасть уже является сложным компонентом.", {
                        "equipment_id": existing["equipment_id"],
                    }

                cursor.execute(
                    "INSERT INTO equipment (name, sku, category_id, parent_id, comment) VALUES (?, ?, ?, ?, ?)",
                    (
                        part_row["part_name"],
                        part_row["part_sku"],
                        part_row["category_id"],
                        part_row["equipment_id"],
                        None,
                    ),
                )
                component_equipment_id = cursor.lastrowid

                cursor.execute(
                    "INSERT INTO complex_components (equipment_part_id, equipment_id) VALUES (?, ?)",
                    (equipment_part_id, component_equipment_id),
                )

            self._log_action(
                f"Запчасть #{part_row['part_id']} превращена в сложный компонент для оборудования #{part_row['equipment_id']}"
            )
            return True, "Запчасть отмечена как сложный компонент.", {
                "equipment_id": component_equipment_id,
            }
        except sqlite3.Error as e:
            logging.error(
                "Ошибка при создании сложного компонента на основе связи #%s: %s",
                equipment_part_id,
                e,
                exc_info=True,
            )
            return False, f"Ошибка базы данных: {e}", {}

    def unmark_equipment_part_complex(self, equipment_part_id: int):
        if not self.conn:
            return False, "Нет подключения к БД.", {}

        try:
            with self.conn:
                cursor = self.conn.cursor()
                mapping = cursor.execute(
                    "SELECT equipment_id FROM complex_components WHERE equipment_part_id = ?",
                    (equipment_part_id,),
                ).fetchone()

                if not mapping:
                    return False, "Запчасть не является сложным компонентом.", {}

                component_equipment_id = mapping["equipment_id"]

                has_children = cursor.execute(
                    "SELECT 1 FROM equipment_parts WHERE equipment_id = ? LIMIT 1",
                    (component_equipment_id,),
                ).fetchone()
                if has_children:
                    return False, (
                        "Нельзя преобразовать компонент обратно: к нему привязаны другие запчасти."
                    ), {}

                cursor.execute(
                    "DELETE FROM complex_components WHERE equipment_part_id = ?",
                    (equipment_part_id,),
                )
                cursor.execute(
                    "DELETE FROM equipment WHERE id = ?",
                    (component_equipment_id,),
                )

            self._log_action(
                f"Запчасть-связь #{equipment_part_id} больше не является сложным компонентом"
            )
            return True, "Запчасть преобразована в обычную.", {
                "removed_equipment_id": component_equipment_id,
            }
        except sqlite3.Error as e:
            logging.error(
                "Ошибка при удалении сложного компонента #%s: %s",
                equipment_part_id,
                e,
                exc_info=True,
            )
            return False, f"Ошибка базы данных: {e}", {}

    def get_complex_component_equipment_id(self, equipment_part_id: int) -> Optional[int]:
        row = self.fetchone(
            "SELECT equipment_id FROM complex_components WHERE equipment_part_id = ?",
            (equipment_part_id,),
        )
        if row:
            return row["equipment_id"]
        return None

    def _ensure_equipment_parts_requires_column(self, update_schema_version: bool = True) -> bool:
        """Убеждается, что у таблицы equipment_parts есть колонка requires_replacement."""
        if not self.conn:
            logging.error("Не удалось проверить структуру equipment_parts: нет подключения к БД.")
            return False

        try:
            cursor = self.conn.execute("PRAGMA table_info(equipment_parts);")
            columns = {row[1] for row in cursor.fetchall()}
        except sqlite3.Error as exc:
            logging.error(
                "Не удалось получить информацию о столбцах equipment_parts: %s",
                exc,
                exc_info=True,
            )
            return False

        if "requires_replacement" in columns:
            return True

        try:
            self.conn.execute(
                "ALTER TABLE equipment_parts ADD COLUMN requires_replacement INTEGER NOT NULL DEFAULT 0;"
            )
            self.conn.commit()
            if update_schema_version:
                try:
                    cursor = self.conn.execute("PRAGMA user_version;")
                    current_version = cursor.fetchone()[0]
                    if current_version < 7:
                        self.conn.execute("PRAGMA user_version = 7;")
                        self.conn.commit()
                except sqlite3.Error as exc:
                    logging.warning(
                        "Не удалось обновить user_version после добавления столбца requires_replacement: %s",
                        exc,
                        exc_info=True,
                    )
            logging.info(
                "Столбец equipment_parts.requires_replacement успешно добавлен принудительно."
            )
            return True
        except sqlite3.Error as exc:
            logging.error(
                "Ошибка при добавлении столбца equipment_parts.requires_replacement: %s",
                exc,
                exc_info=True,
            )
            return False

    def set_equipment_part_requires_replacement(self, equipment_part_id: int, requires: bool):
        link = self.fetchone(
            "SELECT equipment_id, part_id FROM equipment_parts WHERE id = ?",
            (equipment_part_id,),
        )
        if not link:
            return False, None, "Привязка запчасти не найдена."

        if not self._ensure_equipment_parts_requires_column():
            return (
                False,
                link.get("equipment_id"),
                "Не удалось подготовить таблицу для сохранения признака замены.",
            )

        try:
            requires_value = 1 if requires else 0
            cursor = self.execute(
                "UPDATE equipment_parts SET requires_replacement = ? WHERE id = ?",
                (requires_value, equipment_part_id),
            )
            if cursor is None:
                return (
                    False,
                    link.get("equipment_id"),
                    "Ошибка базы данных при обновлении признака замены.",
                )

            if self.conn:
                self.conn.commit()

            action = "помечена как требующая замены" if requires else "снята отметка о необходимости замены"
            self._log_action(
                f"Запчасть #{link['part_id']} на оборудовании #{link['equipment_id']} {action}."
            )
            return True, link['equipment_id'], "Статус обновлён."
        except sqlite3.Error as e:
            logging.error(
                "Ошибка обновления признака замены для equipment_part_id=%s: %s",
                equipment_part_id,
                e,
                exc_info=True,
            )
            return False, link['equipment_id'], f"Ошибка базы данных: {e}"

    def _refresh_equipment_parts_flags(self, cursor, equipment_part_ids: set[int]):
        if not equipment_part_ids:
            return

        placeholders = ",".join("?" for _ in equipment_part_ids)
        query = f"""
            SELECT
                ep.id AS equipment_part_id,
                EXISTS (
                    SELECT 1
                    FROM task_parts tp
                    JOIN tasks t ON tp.task_id = t.id
                    WHERE tp.equipment_part_id = ep.id
                      AND t.status NOT IN ('выполнена', 'отменена')
                ) AS has_active_task
            FROM equipment_parts ep
            WHERE ep.id IN ({placeholders})
        """

        cursor.execute(query, tuple(equipment_part_ids))
        rows = cursor.fetchall()
        for row in rows:
            requires = 1 if row[1] else 0
            cursor.execute(
                "UPDATE equipment_parts SET requires_replacement = ? WHERE id = ?",
                (requires, row[0]),
            )

    def _get_equipment_ids_for_part_links(self, cursor, equipment_part_ids: set[int]) -> set[int]:
        if not equipment_part_ids:
            return set()

        placeholders = ",".join("?" for _ in equipment_part_ids)
        cursor.execute(
            f"SELECT DISTINCT equipment_id FROM equipment_parts WHERE id IN ({placeholders})",
            tuple(equipment_part_ids),
        )
        return {row[0] for row in cursor.fetchall() if row[0] is not None}

    def _fetch_task_equipment_part_ids(self, cursor, task_id: int) -> set[int]:
        cursor.execute("SELECT equipment_part_id FROM task_parts WHERE task_id = ?", (task_id,))
        return {row[0] for row in cursor.fetchall() if row[0] is not None}

    def _replace_task_parts(self, cursor, task_id: int, replacement_parts: list[dict], expected_equipment_id: Optional[int]) -> set[int]:
        cursor.execute("DELETE FROM task_parts WHERE task_id = ?", (task_id,))
        inserted_equipment_part_ids: set[int] = set()

        for part in replacement_parts:
            equipment_part_id = part.get('equipment_part_id')
            part_id = part.get('part_id')
            qty = int(part.get('qty', 0) or 0)

            if not equipment_part_id:
                raise ValueError("Для задачи на замену необходимо выбрать запчасти из оборудования.")
            if not part_id:
                raise ValueError("Не удалось определить запчасть для задачи на замену.")
            if qty <= 0:
                raise ValueError("Количество списываемых запчастей должно быть положительным.")

            cursor.execute(
                "SELECT part_id, equipment_id FROM equipment_parts WHERE id = ?",
                (equipment_part_id,),
            )
            link_row = cursor.fetchone()
            if not link_row:
                raise ValueError("Выбранная запчасть больше не привязана к оборудованию.")

            linked_part_id, equipment_id = link_row
            if linked_part_id != part_id:
                raise ValueError("Запчасть и связь с оборудованием не совпадают.")
            if expected_equipment_id and equipment_id != expected_equipment_id:
                raise ValueError("Все запчасти должны относиться к выбранному оборудованию.")

            cursor.execute(
                "INSERT INTO task_parts (task_id, equipment_part_id, part_id, qty) VALUES (?, ?, ?, ?)",
                (task_id, equipment_part_id, part_id, qty),
            )
            inserted_equipment_part_ids.add(equipment_part_id)

        return inserted_equipment_part_ids

    def get_task_parts(self, task_id: int) -> list[dict[str, Any]]:
        query = """
            SELECT
                tp.id,
                tp.task_id,
                tp.part_id,
                tp.qty,
                tp.equipment_part_id,
                p.name AS part_name,
                p.sku AS part_sku,
                ep.equipment_id,
                ep.installed_qty
            FROM task_parts tp
            JOIN parts p ON tp.part_id = p.id
            LEFT JOIN equipment_parts ep ON tp.equipment_part_id = ep.id
            WHERE tp.task_id = ?
        """
        return self.fetchall(query, (task_id,))

    def _fetch_task_parts_for_processing(self, cursor, task_id: int) -> list[dict[str, Any]]:
        cursor.execute(
            """
                SELECT tp.part_id, tp.qty, tp.equipment_part_id, ep.equipment_id
                FROM task_parts tp
                LEFT JOIN equipment_parts ep ON tp.equipment_part_id = ep.id
                WHERE tp.task_id = ?
            """,
            (task_id,),
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_equipment_ids_with_replacement_flag(self) -> set[int]:
        rows = self.fetchall(
            "SELECT DISTINCT equipment_id FROM equipment_parts WHERE requires_replacement = 1"
        )
        flagged: set[int] = {row['equipment_id'] for row in rows}
        if not flagged:
            return set()

        equipment_rows = self.get_all_equipment()
        parent_map = {row['id']: row.get('parent_id') for row in equipment_rows}

        result = set(flagged)
        stack = list(flagged)
        while stack:
            current_id = stack.pop()
            parent_id = parent_map.get(current_id)
            if parent_id and parent_id not in result:
                result.add(parent_id)
                stack.append(parent_id)

        return result
    def get_unattached_parts(self, equipment_id):
        query = """
            SELECT p.id, p.name, p.sku, p.qty, pc.name as category_name, pc.id as category_id
            FROM parts p
                LEFT JOIN part_categories pc ON p.category_id = pc.id
            WHERE p.id NOT IN (SELECT part_id FROM equipment_parts WHERE equipment_id = ?)
            ORDER BY pc.name IS NULL, pc.name, p.name
        """
        return self.fetchall(query, (equipment_id,))
    def perform_replacement(self, date_str, equipment_id, part_id, qty, reason):
        if not self.conn: return False, "Нет подключения к БД."
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("SELECT qty FROM parts WHERE id = ?", (part_id,))
                current_qty_row = cursor.fetchone()
                if not current_qty_row or current_qty_row[0] < qty: return False, "Недостаточно запчастей на складе."
                cursor.execute("UPDATE parts SET qty = qty - ? WHERE id = ?", (qty, part_id))
                cursor.execute("INSERT INTO replacements (date, equipment_id, part_id, qty, reason) VALUES (?, ?, ?, ?, ?)", (date_str, equipment_id, part_id, qty, reason))
                cursor.execute(
                    "UPDATE equipment_parts SET requires_replacement = 0 WHERE equipment_id = ? AND part_id = ?",
                    (equipment_id, part_id),
                )
            self._log_action(
                f"Выполнена замена: запчасть #{part_id} на оборудовании #{equipment_id}, количество {qty}, дата {date_str}, причина: {reason or 'не указана'}"
            )
            return True, "Замена успешно выполнена."
        except sqlite3.Error as e:
            logging.error(f"Ошибка транзакции при замене запчасти: {e}", exc_info=True)
            return False, f"Ошибка транзакции: {e}"
    def get_all_replacements_filtered(self, start_date=None, end_date=None, part_category_id=None, equipment_id=None):
        query = """
            SELECT r.id, r.date, r.qty, r.reason, e.name as equipment_name, p.name as part_name, p.sku as part_sku, pc.name as part_category_name
            FROM replacements r JOIN equipment e ON r.equipment_id = e.id JOIN parts p ON r.part_id = p.id LEFT JOIN part_categories pc ON p.category_id = pc.id
        """
        conditions, params = [], []
        if start_date: conditions.append("r.date >= ?"); params.append(start_date)
        if end_date: conditions.append("r.date <= ?"); params.append(end_date)
        if equipment_id: conditions.append("r.equipment_id = ?"); params.append(equipment_id)
        if part_category_id: conditions.append("p.category_id = ?"); params.append(part_category_id)
        if conditions: query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY r.date DESC"
        return self.fetchall(query, tuple(params))
    def get_replacement_by_id(self, replacement_id): return self.fetchone("SELECT * FROM replacements WHERE id = ?", (replacement_id,))
    def update_replacement(self, replacement_id, date_str, qty, reason):
        try:
            self.execute("UPDATE replacements SET date=?, qty=?, reason=? WHERE id=?", (date_str, qty, reason, replacement_id))
            if self.conn: self.conn.commit()
            self._log_action(
                f"Обновлена запись замены #{replacement_id}: дата {date_str}, количество {qty}, причина: {reason or 'не указана'}"
            )
            return True, "Запись о замене обновлена."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def delete_replacement(self, replacement_id):
        try:
            replacement = self.fetchone("SELECT date, equipment_id, part_id FROM replacements WHERE id = ?", (replacement_id,))
            self.execute("DELETE FROM replacements WHERE id = ?", (replacement_id,))
            if self.conn: self.conn.commit()
            if replacement:
                self._log_action(
                    f"Удалена запись замены #{replacement_id}: дата {replacement['date']}, оборудование #{replacement['equipment_id']}, запчасть #{replacement['part_id']}"
                )
            else:
                self._log_action(f"Удалена запись замены #{replacement_id}")
            return True, "Запись из истории замен удалена."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def get_all_colleagues(self): return self.fetchall("SELECT id, name FROM colleagues ORDER BY name")
    def add_colleague(self, name):
        try:
            self.execute("INSERT INTO colleagues (name) VALUES (?)", (name,))
            if self.conn: self.conn.commit()
            self._log_action(f"Добавлен сотрудник: {name}")
            return True, "Сотрудник добавлен."
        except sqlite3.IntegrityError: return False, "Сотрудник с таким именем уже существует."
    def update_colleague(self, colleague_id, name):
        try:
            self.execute("UPDATE colleagues SET name = ? WHERE id = ?", (name, colleague_id))
            if self.conn: self.conn.commit()
            self._log_action(f"Обновлён сотрудник #{colleague_id}: {name}")
            return True, "Имя сотрудника обновлено."
        except sqlite3.IntegrityError: return False, "Сотрудник с таким именем уже существует."
    def delete_colleague(self, colleague_id):
        try:
            colleague = self.fetchone("SELECT name FROM colleagues WHERE id = ?", (colleague_id,))
            self.execute("DELETE FROM colleagues WHERE id = ?", (colleague_id,))
            if self.conn: self.conn.commit()
            if colleague:
                self._log_action(f"Удалён сотрудник #{colleague_id}: {colleague['name']}")
            else:
                self._log_action(f"Удалён сотрудник #{colleague_id}")
            return True, "Сотрудник удален."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def get_all_tasks(self):
        query = """
            SELECT t.id, t.title, t.description, t.priority, t.due_date, t.status,
                   t.created_at, t.is_replacement,
                   c.name as assignee_name, e.name as equipment_name
            FROM tasks t
            LEFT JOIN colleagues c ON t.assignee_id = c.id
            LEFT JOIN equipment e ON t.equipment_id = e.id
            ORDER BY
                CASE t.priority WHEN 'высокий' THEN 1 WHEN 'средний' THEN 2 WHEN 'низкий' THEN 3 ELSE 4 END,
                t.due_date
        """
        return self.fetchall(query)

    def get_tasks_history(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        assignee_id: int | None = None,
        equipment_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Возвращает задачи со статусом 'выполнена' или 'отменена'."""

        query = """
            SELECT
                t.id,
                t.title,
                t.description,
                t.priority,
                t.due_date,
                t.status,
                t.created_at,
                t.assignee_id,
                t.equipment_id,
                c.name AS assignee_name,
                e.name AS equipment_name
            FROM tasks t
            LEFT JOIN colleagues c ON t.assignee_id = c.id
            LEFT JOIN equipment e ON t.equipment_id = e.id
            WHERE t.status IN ('выполнена', 'отменена')
        """

        conditions: list[str] = []
        params: list[Any] = []

        if start_date:
            conditions.append(
                "COALESCE(t.due_date, substr(t.created_at, 1, 10)) >= ?"
            )
            params.append(start_date)

        if end_date:
            conditions.append(
                "COALESCE(t.due_date, substr(t.created_at, 1, 10)) <= ?"
            )
            params.append(end_date)

        if assignee_id:
            conditions.append("t.assignee_id = ?")
            params.append(assignee_id)

        if equipment_id:
            conditions.append("t.equipment_id = ?")
            params.append(equipment_id)

        if conditions:
            query += " AND " + " AND ".join(conditions)

        query += (
            " ORDER BY COALESCE(t.due_date, substr(t.created_at, 1, 10)) DESC, "
            "t.created_at DESC, t.id DESC"
        )

        return self.fetchall(query, tuple(params))
    def get_task_by_id(self, task_id): return self.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
    def add_task(
        self,
        title,
        description,
        priority,
        due_date,
        assignee_id,
        equipment_id,
        status,
        is_replacement=False,
        replacement_parts: Optional[list[dict[str, Any]]] = None,
    ):
        replacement_parts = replacement_parts or []

        if is_replacement and not equipment_id:
            return False, "Для задачи на замену необходимо выбрать оборудование.", {}
        if is_replacement and not replacement_parts:
            return False, "Добавьте хотя бы одну запчасть для задачи на замену.", {}

        try:
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            events: dict[str, Any] = {}

            if not self.conn:
                raise sqlite3.Error("Нет подключения к базе данных.")

            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute(
                    """
                        INSERT INTO tasks (
                            title, description, priority, due_date, assignee_id, equipment_id, status, created_at, is_replacement
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        title,
                        description,
                        priority,
                        due_date,
                        assignee_id,
                        equipment_id,
                        status,
                        created_at,
                        1 if is_replacement else 0,
                    ),
                )
                task_id = cursor.lastrowid

                affected_equipment_part_ids: set[int] = set()
                if is_replacement:
                    affected_equipment_part_ids = self._replace_task_parts(
                        cursor,
                        task_id,
                        replacement_parts,
                        equipment_id,
                    )
                    self._refresh_equipment_parts_flags(cursor, affected_equipment_part_ids)
                    events['equipment_ids'] = self._get_equipment_ids_for_part_links(
                        cursor, affected_equipment_part_ids
                    )

            self._log_action(
                f"Создана задача: '{title}' (приоритет: {priority}, срок: {due_date or 'не указан'}, назначена на сотрудника #{assignee_id or 'нет'})"
            )
            return True, "Задача создана.", events
        except ValueError as exc:
            return False, str(exc), {}
        except sqlite3.Error as e:
            logging.error("Ошибка при добавлении задачи: %s", e, exc_info=True)
            return False, f"Ошибка базы данных: {e}", {}

    def update_task(
        self,
        task_id,
        title,
        description,
        priority,
        due_date,
        assignee_id,
        equipment_id,
        status,
        is_replacement=False,
        replacement_parts: Optional[list[dict[str, Any]]] = None,
    ):
        replacement_parts = replacement_parts or []

        if is_replacement and not equipment_id:
            return False, "Для задачи на замену необходимо выбрать оборудование.", {}
        if is_replacement and not replacement_parts:
            return False, "Добавьте хотя бы одну запчасть для задачи на замену.", {}

        try:
            if not self.conn:
                raise sqlite3.Error("Нет подключения к базе данных.")

            with self.conn:
                cursor = self.conn.cursor()
                previous_equipment_part_ids = self._fetch_task_equipment_part_ids(cursor, task_id)

                cursor.execute(
                    """
                        UPDATE tasks
                        SET title=?, description=?, priority=?, due_date=?, assignee_id=?, equipment_id=?, status=?, is_replacement=?
                        WHERE id=?
                    """,
                    (
                        title,
                        description,
                        priority,
                        due_date,
                        assignee_id,
                        equipment_id,
                        status,
                        1 if is_replacement else 0,
                        task_id,
                    ),
                )

                affected_equipment_part_ids = set(previous_equipment_part_ids)

                if is_replacement:
                    new_equipment_part_ids = self._replace_task_parts(
                        cursor,
                        task_id,
                        replacement_parts,
                        equipment_id,
                    )
                    affected_equipment_part_ids.update(new_equipment_part_ids)
                else:
                    cursor.execute("DELETE FROM task_parts WHERE task_id = ?", (task_id,))

                self._refresh_equipment_parts_flags(cursor, affected_equipment_part_ids)
                equipment_ids = self._get_equipment_ids_for_part_links(
                    cursor, affected_equipment_part_ids
                )

            self._log_action(
                f"Обновлена задача #{task_id}: '{title}' (приоритет: {priority}, срок: {due_date or 'не указан'}, статус: {status})"
            )
            return True, "Задача обновлена.", {'equipment_ids': equipment_ids}
        except ValueError as exc:
            return False, str(exc), {}
        except sqlite3.Error as e:
            logging.error("Ошибка при обновлении задачи #%s: %s", task_id, e, exc_info=True)
            return False, f"Ошибка базы данных: {e}", {}

    def update_task_status(self, task_id, new_status):
        task = self.get_task_by_id(task_id)
        if not task:
            return False, "Задача не найдена.", {}

        try:
            if not self.conn:
                raise sqlite3.Error("Нет подключения к базе данных.")

            events: dict[str, Any] = {}

            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))

                affected_equipment_part_ids: set[int] = set()
                equipment_ids: set[int] = set()
                parts_changed = False

                if task.get('is_replacement'):
                    parts_rows = self._fetch_task_parts_for_processing(cursor, task_id)
                    affected_equipment_part_ids = {
                        row['equipment_part_id']
                        for row in parts_rows
                        if row.get('equipment_part_id')
                    }
                    equipment_ids = {
                        row['equipment_id']
                        for row in parts_rows
                        if row.get('equipment_id') is not None
                    }

                    if new_status == 'выполнена':
                        for row in parts_rows:
                            cursor.execute("SELECT qty FROM parts WHERE id = ?", (row['part_id'],))
                            qty_row = cursor.fetchone()
                            if not qty_row:
                                raise ValueError("Запчасть для списания не найдена.")
                            if qty_row[0] < row['qty']:
                                raise ValueError("Недостаточно запчастей на складе для списания.")

                        reason = task.get('description') or f"Задача #{task_id}: {task.get('title')}"
                        date_str = date.today().isoformat()

                        for row in parts_rows:
                            cursor.execute(
                                "UPDATE parts SET qty = qty - ? WHERE id = ?",
                                (row['qty'], row['part_id']),
                            )
                            if row.get('equipment_id') is not None:
                                cursor.execute(
                                    "INSERT INTO replacements (date, equipment_id, part_id, qty, reason) VALUES (?, ?, ?, ?, ?)",
                                    (date_str, row['equipment_id'], row['part_id'], row['qty'], reason),
                                )

                        parts_changed = True

                self._refresh_equipment_parts_flags(cursor, affected_equipment_part_ids)

            if equipment_ids:
                events['equipment_ids'] = equipment_ids
            if parts_changed:
                events['parts_changed'] = True
                events['replacements_changed'] = True

            self._log_action(f"Изменён статус задачи #{task_id} на '{new_status}'")
            return True, "Статус задачи обновлен.", events
        except ValueError as exc:
            return False, str(exc), {}
        except sqlite3.Error as e:
            logging.error("Ошибка при изменении статуса задачи #%s: %s", task_id, e, exc_info=True)
            return False, f"Ошибка базы данных: {e}", {}

    def delete_task(self, task_id):
        try:
            if not self.conn:
                raise sqlite3.Error("Нет подключения к базе данных.")

            with self.conn:
                cursor = self.conn.cursor()
                task = cursor.execute("SELECT title FROM tasks WHERE id = ?", (task_id,)).fetchone()
                equipment_part_ids = self._fetch_task_equipment_part_ids(cursor, task_id)
                cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                self._refresh_equipment_parts_flags(cursor, equipment_part_ids)
                equipment_ids = self._get_equipment_ids_for_part_links(cursor, equipment_part_ids)

            if task:
                self._log_action(f"Удалена задача #{task_id}: '{task['title']}'")
            else:
                self._log_action(f"Удалена задача #{task_id}")
            return True, "Задача удалена.", {'equipment_ids': equipment_ids}
        except sqlite3.Error as e:
            logging.error("Ошибка при удалении задачи #%s: %s", task_id, e, exc_info=True)
            return False, f"Ошибка базы данных: {e}", {}

    # --- Periodic Tasks ---
    @staticmethod
    def _compute_next_due_date(last_completed: Optional[str], period_days: int) -> date:
        today = date.today()
        if period_days <= 0:
            return today

        if last_completed:
            try:
                last_date = datetime.strptime(last_completed, "%Y-%m-%d").date()
            except ValueError:
                last_date = today
        else:
            last_date = today

        return last_date + timedelta(days=period_days)

    def _prepare_periodic_task_row(self, row: dict[str, Any]) -> dict[str, Any]:
        period_days = int(row.get('period_days') or 0)
        last_completed = row.get('last_completed_date')
        next_due = self._compute_next_due_date(last_completed, period_days)
        row['next_due_date'] = next_due.isoformat()
        row['days_until_due'] = (next_due - date.today()).days
        return row

    def get_all_periodic_tasks(self) -> list[dict[str, Any]]:
        query = """
            SELECT
                pt.id,
                pt.title,
                pt.period_days,
                pt.last_completed_date,
                pt.equipment_id,
                pt.equipment_part_id,
                e.name AS equipment_name,
                ep.part_id,
                p.name AS part_name,
                p.sku AS part_sku
            FROM periodic_tasks pt
            LEFT JOIN equipment e ON pt.equipment_id = e.id
            LEFT JOIN equipment_parts ep ON pt.equipment_part_id = ep.id
            LEFT JOIN parts p ON ep.part_id = p.id
        """

        rows = [self._prepare_periodic_task_row(row) for row in self.fetchall(query)]
        return sorted(
            rows,
            key=lambda r: (
                r.get('next_due_date') or '',
                (r.get('title') or '').lower(),
            ),
        )

    def get_due_periodic_tasks(self, within_days: int = 7) -> list[dict[str, Any]]:
        tasks = self.get_all_periodic_tasks()
        return [
            task
            for task in tasks
            if task.get('days_until_due') is not None and task['days_until_due'] < within_days
        ]

    def get_periodic_task_by_id(self, task_id: int) -> Optional[dict[str, Any]]:
        query = """
            SELECT
                pt.id,
                pt.title,
                pt.period_days,
                pt.last_completed_date,
                pt.equipment_id,
                pt.equipment_part_id,
                e.name AS equipment_name,
                ep.part_id,
                p.name AS part_name,
                p.sku AS part_sku
            FROM periodic_tasks pt
            LEFT JOIN equipment e ON pt.equipment_id = e.id
            LEFT JOIN equipment_parts ep ON pt.equipment_part_id = ep.id
            LEFT JOIN parts p ON ep.part_id = p.id
            WHERE pt.id = ?
        """

        row = self.fetchone(query, (task_id,))
        return self._prepare_periodic_task_row(row) if row else None

    def _resolve_periodic_target(self, cursor: sqlite3.Cursor, equipment_id: Optional[int], equipment_part_id: Optional[int]) -> Optional[int]:
        resolved_equipment_id = equipment_id

        if equipment_part_id:
            part_row = cursor.execute(
                "SELECT equipment_id, part_id FROM equipment_parts WHERE id = ?",
                (equipment_part_id,),
            ).fetchone()
            if not part_row:
                raise ValueError("Выбранная запчасть больше не привязана к оборудованию.")
            resolved_equipment_id = part_row["equipment_id"]

        if not resolved_equipment_id and not equipment_part_id:
            raise ValueError("Выберите аппарат или запчасть.")

        return resolved_equipment_id

    def add_periodic_task(
        self,
        title: str,
        period_days: int,
        equipment_id: Optional[int],
        equipment_part_id: Optional[int],
        last_completed_date: Optional[str],
    ):
        if not self.conn:
            return False, "Нет подключения к базе данных."

        title = (title or "").strip()
        if not title:
            return False, "Укажите название работы."
        if period_days <= 0:
            return False, "Периодичность должна быть положительным числом."

        try:
            with self.conn:
                cursor = self.conn.cursor()
                resolved_equipment_id = self._resolve_periodic_target(
                    cursor,
                    equipment_id,
                    equipment_part_id,
                )

                cursor.execute(
                    """
                        INSERT INTO periodic_tasks (
                            title,
                            equipment_id,
                            equipment_part_id,
                            period_days,
                            last_completed_date
                        ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        title,
                        resolved_equipment_id,
                        equipment_part_id,
                        period_days,
                        last_completed_date,
                    ),
                )
                task_id = cursor.lastrowid

            self._log_action(
                f"Создана периодическая работа #{task_id}: '{title}' (каждые {period_days} дн.)"
            )
            return True, "Периодическая работа создана."
        except ValueError as exc:
            return False, str(exc)
        except sqlite3.Error as exc:
            logging.error("Ошибка при создании периодической работы: %s", exc, exc_info=True)
            return False, f"Ошибка базы данных: {exc}"

    def update_periodic_task(
        self,
        task_id: int,
        title: str,
        period_days: int,
        equipment_id: Optional[int],
        equipment_part_id: Optional[int],
        last_completed_date: Optional[str],
    ):
        if not self.conn:
            return False, "Нет подключения к базе данных."

        title = (title or "").strip()
        if not title:
            return False, "Укажите название работы."
        if period_days <= 0:
            return False, "Периодичность должна быть положительным числом."

        try:
            with self.conn:
                cursor = self.conn.cursor()
                resolved_equipment_id = self._resolve_periodic_target(
                    cursor,
                    equipment_id,
                    equipment_part_id,
                )

                cursor.execute(
                    """
                        UPDATE periodic_tasks
                        SET title = ?,
                            equipment_id = ?,
                            equipment_part_id = ?,
                            period_days = ?,
                            last_completed_date = ?
                        WHERE id = ?
                    """,
                    (
                        title,
                        resolved_equipment_id,
                        equipment_part_id,
                        period_days,
                        last_completed_date,
                        task_id,
                    ),
                )

            self._log_action(
                f"Обновлена периодическая работа #{task_id}: '{title}' (каждые {period_days} дн.)"
            )
            return True, "Периодическая работа обновлена."
        except ValueError as exc:
            return False, str(exc)
        except sqlite3.Error as exc:
            logging.error("Ошибка при обновлении периодической работы #%s: %s", task_id, exc, exc_info=True)
            return False, f"Ошибка базы данных: {exc}"

    def delete_periodic_tasks(self, task_ids: list[int]):
        if not self.conn:
            return False, "Нет подключения к базе данных."
        if not task_ids:
            return False, "Не выбраны работы для удаления."

        try:
            with self.conn:
                cursor = self.conn.cursor()
                placeholders = ",".join("?" for _ in task_ids)
                titles = cursor.execute(
                    f"SELECT id, title FROM periodic_tasks WHERE id IN ({placeholders})",
                    tuple(task_ids),
                ).fetchall()
                cursor.execute(
                    f"DELETE FROM periodic_tasks WHERE id IN ({placeholders})",
                    tuple(task_ids),
                )

            if titles:
                for row in titles:
                    self._log_action(f"Удалена периодическая работа #{row['id']}: '{row['title']}'")
            else:
                self._log_action(f"Удалены периодические работы: {len(task_ids)} шт.")
            return True, "Работы удалены."
        except sqlite3.Error as exc:
            logging.error("Ошибка при удалении периодических работ: %s", exc, exc_info=True)
            return False, f"Ошибка базы данных: {exc}"

    def _update_periodic_task_completion(
        self,
        task_id: int,
        completion_date: Optional[str],
        log_template: str,
        success_message: str,
    ):
        if not self.conn:
            return False, "Нет подключения к базе данных.", {}

        completion_date = completion_date or date.today().isoformat()

        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE periodic_tasks SET last_completed_date = ? WHERE id = ?",
                    (completion_date, task_id),
                )

            task = self.get_periodic_task_by_id(task_id)
            if not task:
                return False, "Периодическая работа не найдена.", {}

            self._log_action(log_template.format(task_id=task_id, title=task['title']))
            return True, success_message, {
                'next_due_date': task.get('next_due_date'),
                'days_until_due': task.get('days_until_due'),
            }
        except sqlite3.Error as exc:
            logging.error(
                "Ошибка при обновлении даты выполнения периодической работы #%s: %s",
                task_id,
                exc,
                exc_info=True,
            )
            return False, f"Ошибка базы данных: {exc}", {}

    def complete_periodic_task(self, task_id: int, completion_date: Optional[str] = None):
        return self._update_periodic_task_completion(
            task_id,
            completion_date,
            "Отмечено выполнение периодической работы #{task_id}: '{title}'",
            "Дата выполнения обновлена.",
        )

    def cancel_periodic_task(self, task_id: int, completion_date: Optional[str] = None):
        return self._update_periodic_task_completion(
            task_id,
            completion_date,
            "Отменено выполнение периодической работы #{task_id}: '{title}'",
            "Периодическая работа отменена.",
        )

    def pause_periodic_task(self, task_id: int, completion_date: Optional[str] = None):
        return self._update_periodic_task_completion(
            task_id,
            completion_date,
            "Периодическая работа #{task_id} отмечена как остановленная: '{title}'",
            "Периодическая работа поставлена на стоп.",
        )

    # --- Knives / Sharpening ---
    def get_all_sharpening_items(self):
        query = """
            SELECT
                p.id, p.name, p.sku, p.qty,
                kt.status,
                kt.last_sharpen_date,
                kt.work_started_at,
                kt.last_interval_days,
                COALESCE(kt.sharp_state, CASE kt.status WHEN 'затуплен' THEN 'затуплен' ELSE 'заточен' END) AS sharp_state,
                COALESCE(kt.installation_state, CASE kt.status WHEN 'в работе' THEN 'установлен' ELSE 'снят' END) AS installation_state,
                (
                    SELECT GROUP_CONCAT(eq.name, ', ')
                    FROM equipment_parts ep
                    JOIN equipment eq ON ep.equipment_id = eq.id
                    WHERE ep.part_id = p.id
                ) AS equipment_list
            FROM parts p
            JOIN part_categories pc ON p.category_id = pc.id
            LEFT JOIN knife_tracking kt ON p.id = kt.part_id
            WHERE pc.name IN ('ножи', 'утюги')
            ORDER BY p.name
        """
        return self.fetchall(query)

    def get_all_knives_data(self):
        return self.get_all_sharpening_items()

    def toggle_sharp_state(self, part_id: int):
        if not self.conn:
            return False, "Нет подключения к БД.", {}

        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO knife_tracking (part_id) VALUES (?)", (part_id,))
                row = cursor.execute(
                    """
                        SELECT kt.sharp_state, kt.installation_state, kt.status, kt.work_started_at,
                               p.name AS part_name
                        FROM knife_tracking kt
                        JOIN parts p ON p.id = kt.part_id
                        WHERE kt.part_id = ?
                    """,
                    (part_id,),
                ).fetchone()

                if not row:
                    return False, "Не найдена запись отслеживания для выбранного комплекта.", {}

                current_status = row["status"]
                current_sharp = self._fallback_sharp_state(row["sharp_state"], current_status)
                current_install = self._fallback_installation_state(row["installation_state"], current_status)

                new_sharp = "затуплен" if current_sharp == "заточен" else "заточен"
                new_status = self._combined_status(new_sharp, current_install)

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                today_str = date.today().isoformat()

                cursor.execute(
                    """
                        UPDATE knife_tracking
                        SET sharp_state = ?,
                            status = ?,
                            last_sharpen_date = CASE WHEN ? = 'заточен' THEN ? ELSE last_sharpen_date END,
                            total_sharpenings = total_sharpenings + CASE WHEN ? = 'заточен' THEN 1 ELSE 0 END
                        WHERE part_id = ?
                    """,
                    (new_sharp, new_status, new_sharp, today_str, new_sharp, part_id),
                )

                cursor.execute(
                    """
                        INSERT INTO knife_status_log (part_id, from_status, to_status, comment, changed_at)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        part_id,
                        current_sharp,
                        new_sharp,
                        "Состояние заточки изменено вручную",
                        timestamp,
                    ),
                )

                action_text = "Заточен" if new_sharp == "заточен" else "Затуплен"
                cursor.execute(
                    "INSERT INTO knife_sharpen_log (part_id, date, comment) VALUES (?, ?, ?)",
                    (
                        part_id,
                        today_str,
                        f"[Ручное обновление] Состояние заточки: {action_text} (время: {timestamp})",
                    ),
                )

                part_name = row["part_name"]

            action_text = "Заточен" if new_sharp == "заточен" else "Затуплен"
            self._log_action(
                f"Комплект '{part_name}' (#{part_id}) переведён в состояние '{action_text.lower()}'"
            )
            return True, f"Состояние заточки обновлено: {action_text}.", {
                "sharp_state": new_sharp,
                "installation_state": current_install,
            }
        except sqlite3.Error as exc:
            logging.error("Ошибка при изменении состояния заточки: %s", exc, exc_info=True)
            return False, f"Ошибка базы данных: {exc}", {}

    def toggle_installation_state(self, part_id: int):
        if not self.conn:
            return False, "Нет подключения к БД.", {}

        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO knife_tracking (part_id) VALUES (?)", (part_id,))
                row = cursor.execute(
                    """
                        SELECT kt.installation_state, kt.sharp_state, kt.status, kt.work_started_at,
                               kt.last_interval_days, p.name AS part_name
                        FROM knife_tracking kt
                        JOIN parts p ON p.id = kt.part_id
                        WHERE kt.part_id = ?
                    """,
                    (part_id,),
                ).fetchone()

                if not row:
                    return False, "Не найдена запись отслеживания для выбранного комплекта.", {}

                current_status = row["status"]
                current_install = self._fallback_installation_state(row["installation_state"], current_status)
                current_sharp = self._fallback_sharp_state(row["sharp_state"], current_status)

                new_install = "снят" if current_install == "установлен" else "установлен"
                new_status = self._combined_status(current_sharp, new_install)

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                today_str = date.today().isoformat()
                interval_value = None

                if new_install == "установлен":
                    cursor.execute(
                        """
                            UPDATE knife_tracking
                            SET installation_state = ?,
                                status = ?,
                                work_started_at = ?,
                                last_interval_days = last_interval_days
                            WHERE part_id = ?
                        """,
                        (new_install, new_status, today_str, part_id),
                    )
                else:
                    interval_value = None
                    if row["work_started_at"]:
                        try:
                            start_date = date.fromisoformat(row["work_started_at"])
                            interval_value = max((date.today() - start_date).days, 0)
                        except ValueError:
                            interval_value = None

                    cursor.execute(
                        """
                            UPDATE knife_tracking
                            SET installation_state = ?,
                                status = ?,
                                work_started_at = NULL,
                                last_interval_days = CASE WHEN ? IS NULL THEN last_interval_days ELSE ? END
                            WHERE part_id = ?
                        """,
                        (new_install, new_status, interval_value, interval_value, part_id),
                    )

                cursor.execute(
                    """
                        INSERT INTO knife_status_log (part_id, from_status, to_status, comment, changed_at)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        part_id,
                        current_install,
                        new_install,
                        "Состояние установки изменено вручную",
                        timestamp,
                    ),
                )

                install_text = "Установлен" if new_install == "установлен" else "Снят"
                cursor.execute(
                    "INSERT INTO knife_sharpen_log (part_id, date, comment) VALUES (?, ?, ?)",
                    (
                        part_id,
                        today_str,
                        f"[Ручное обновление] Состояние установки: {install_text} (время: {timestamp})",
                    ),
                )

                part_name = row["part_name"]

            install_text = "Установлен" if new_install == "установлен" else "Снят"
            self._log_action(
                f"Комплект '{part_name}' (#{part_id}) переведён в состояние '{install_text.lower()}'"
            )
            return True, f"Состояние установки обновлено: {install_text}.", {
                "installation_state": new_install,
                "sharp_state": current_sharp,
            }
        except sqlite3.Error as exc:
            logging.error("Ошибка при изменении состояния установки: %s", exc, exc_info=True)
            return False, f"Ошибка базы данных: {exc}", {}

    def update_knife_status(self, part_id, new_status, comment=""):
        if not self.conn:
            return False, "Нет подключения к БД."

        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO knife_tracking (part_id) VALUES (?)", (part_id,))

                cursor.execute(
                    "SELECT status, work_started_at, sharp_state, installation_state FROM knife_tracking WHERE part_id = ?",
                    (part_id,),
                )
                current_state = cursor.fetchone()

                if not current_state:
                    return False, "Не удалось создать/найти запись об отслеживании комплекта."

                from_status = current_state['status']
                current_sharp = self._fallback_sharp_state(current_state.get('sharp_state'), from_status)
                current_install = self._fallback_installation_state(current_state.get('installation_state'), from_status)

                if from_status == new_status:
                    self._log_action(
                        f"Попытка изменить статус комплекта #{part_id}, но статус уже '{new_status}'"
                    )
                    return True, "Статус не изменился."

                today_str = date.today().isoformat()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                if new_status == 'в работе':
                    new_install = 'установлен'
                    new_sharp = current_sharp
                    cursor.execute(
                        "UPDATE knife_tracking SET work_started_at = ?, installation_state = ?, status = ? WHERE part_id = ?",
                        (today_str, new_install, new_status, part_id),
                    )
                else:
                    if from_status == 'в работе' and current_state['work_started_at']:
                        try:
                            start_date = date.fromisoformat(current_state['work_started_at'])
                            interval = (date.today() - start_date).days
                            cursor.execute(
                                "UPDATE knife_tracking SET last_interval_days = ? WHERE part_id = ?",
                                (interval, part_id),
                            )
                        except ValueError:
                            logging.warning(
                                "Не удалось вычислить интервал работы для комплекта #%s: некорректная дата %s",
                                part_id,
                                current_state['work_started_at'],
                            )

                    new_install = 'снят'
                    new_sharp = 'затуплен' if new_status == 'затуплен' else 'заточен'
                    cursor.execute(
                        """
                            UPDATE knife_tracking
                            SET status = ?,
                                sharp_state = ?,
                                installation_state = ?,
                                work_started_at = NULL
                            WHERE part_id = ?
                        """,
                        (new_status, new_sharp, new_install, part_id),
                    )

                cursor.execute(
                    "UPDATE knife_tracking SET sharp_state = ?, installation_state = ? WHERE part_id = ?",
                    (new_sharp, new_install, part_id),
                )

                cursor.execute(
                    "INSERT INTO knife_status_log (part_id, from_status, to_status, comment, changed_at) VALUES (?, ?, ?, ?, ?)",
                    (part_id, from_status, new_status, comment, timestamp),
                )

            self._log_action(
                f"Изменён статус комплекта #{part_id} с '{from_status}' на '{new_status}'. Комментарий: {comment or 'нет'}"
            )
            return True, "Статус успешно обновлён."
        except Exception as exc:
            logging.error("Ошибка транзакции при смене статуса комплекта: %s", exc, exc_info=True)
            return False, f"Ошибка транзакции: {exc}"

    def sharpen_knives(self, part_ids, sharpen_date, comment=""):
        if not self.conn: return False, "Нет подключения к БД."
        try:
            with self.conn:
                cursor = self.conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for part_id in part_ids:
                    cursor.execute("INSERT OR IGNORE INTO knife_tracking (part_id) VALUES (?)", (part_id,))

                    # Get current status to log the change
                    cursor.execute(
                        "SELECT status, sharp_state, installation_state FROM knife_tracking WHERE part_id = ?",
                        (part_id,),
                    )
                    res = cursor.fetchone()
                    from_status = res['status'] if res else 'неизвестно'
                    current_status = res['status'] if res else None
                    current_sharp = self._fallback_sharp_state(res['sharp_state'] if res else None, current_status)
                    current_install = self._fallback_installation_state(res['installation_state'] if res else None, current_status)
                    new_status = self._combined_status('заточен', current_install)

                    cursor.execute("""
                        UPDATE knife_tracking
                        SET status = ?,
                            sharp_state = 'заточен',
                            installation_state = ?,
                            last_sharpen_date = ?,
                            total_sharpenings = total_sharpenings + 1
                        WHERE part_id = ?
                    """, (new_status, current_install, sharpen_date, part_id))
                    
                    # Log the sharpening event
                    cursor.execute("INSERT INTO knife_sharpen_log (part_id, date, comment) VALUES (?, ?, ?)",
                                   (part_id, sharpen_date, comment))
                    
                    # Log the status change event
                    if from_status != 'наточен':
                        cursor.execute("""
                            INSERT INTO knife_status_log (part_id, changed_at, from_status, to_status, comment)
                            VALUES (?, ?, ?, ?, ?)""",
                            (part_id, timestamp, from_status, 'наточен', f"Заточка: {comment}".strip())
                        )
            self._log_action(
                f"Заточены комплекты (количество: {len(part_ids)}), дата: {sharpen_date}, комментарий: {comment or 'нет'}"
            )
            return True, "Комплекты успешно отправлены на заточку."
        except Exception as e:
            logging.error(f"Ошибка транзакции при заточке ножей: {e}", exc_info=True)
            return False, f"Ошибка транзакции: {e}"

    def get_knife_sharpen_history(self):
        query = """
            SELECT l.id, l.part_id, l.date, l.comment, p.name AS part_name, p.sku AS part_sku
            FROM knife_sharpen_log l
            JOIN parts p ON l.part_id = p.id
            ORDER BY l.date DESC, l.id DESC
        """
        return self.fetchall(query)

    def get_knife_operations_history(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        part_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Возвращает объединённую историю операций с ножами."""

        query = """
            SELECT *
            FROM (
                SELECT
                    'sharpen' AS entry_type,
                    l.id AS entry_id,
                    l.part_id AS part_id,
                    l.date AS event_date,
                    NULL AS event_time,
                    l.comment AS comment,
                    NULL AS from_status,
                    NULL AS to_status,
                    p.name AS part_name,
                    p.sku AS part_sku
                FROM knife_sharpen_log l
                JOIN parts p ON l.part_id = p.id

                UNION ALL

                SELECT
                    'status' AS entry_type,
                    s.id AS entry_id,
                    s.part_id AS part_id,
                    substr(s.changed_at, 1, 10) AS event_date,
                    substr(s.changed_at, 12, 8) AS event_time,
                    s.comment AS comment,
                    s.from_status AS from_status,
                    s.to_status AS to_status,
                    p.name AS part_name,
                    p.sku AS part_sku
                FROM knife_status_log s
                JOIN parts p ON s.part_id = p.id
            ) AS history
        """

        conditions: list[str] = []
        params: list[Any] = []

        if start_date:
            conditions.append("history.event_date >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("history.event_date <= ?")
            params.append(end_date)

        if part_id:
            conditions.append("history.part_id = ?")
            params.append(part_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += (
            " ORDER BY history.event_date DESC, "
            "COALESCE(history.event_time, '00:00:00') DESC, "
            "history.entry_id DESC"
        )

        rows = self.fetchall(query, tuple(params))

        cleaned_rows: list[dict[str, Any]] = []
        seen_status_entries: set[tuple[Any, ...]] = set()
        phrases_to_remove = [
            "(состояние заточки изменено вручную)",
            "(состояние установки изменено вручную)",
        ]

        for row in rows:
            row_dict = dict(row)
            if row_dict.get('entry_type') == 'status':
                comment = row_dict.get('comment') or ""
                for phrase in phrases_to_remove:
                    comment = comment.replace(phrase, "")
                comment = " ".join(comment.strip().split())
                row_dict['comment'] = comment

                key = (
                    row_dict.get('part_id'),
                    row_dict.get('event_date'),
                    row_dict.get('event_time') or "",
                    row_dict.get('from_status') or "",
                    row_dict.get('to_status') or "",
                    comment,
                )
                if key in seen_status_entries:
                    continue
                seen_status_entries.add(key)

            cleaned_rows.append(row_dict)

        return cleaned_rows

    def delete_knife_sharpen_entry(self, entry_id):
        if not self.conn:
            return False, "Нет подключения к БД."

        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("SELECT part_id FROM knife_sharpen_log WHERE id = ?", (entry_id,))
                row = cursor.fetchone()
                if not row:
                    return False, "Запись не найдена."

                part_id = row["part_id"]
                cursor.execute("DELETE FROM knife_sharpen_log WHERE id = ?", (entry_id,))

                cursor.execute(
                    "SELECT MAX(date) as max_date, COUNT(*) as cnt FROM knife_sharpen_log WHERE part_id = ?",
                    (part_id,),
                )
                stats = cursor.fetchone()
                last_date = stats["max_date"] if stats else None
                total = stats["cnt"] if stats else 0
                cursor.execute(
                    "UPDATE knife_tracking SET last_sharpen_date = ?, total_sharpenings = ? WHERE part_id = ?",
                    (last_date, total, part_id),
                )

            self._log_action(
                f"Удалена запись истории заточек #{entry_id} для комплекта #{part_id}"
            )
            return True, "Запись удалена."
        except sqlite3.Error as exc:
            logging.error("Ошибка удаления записи истории заточек", exc_info=True)
            return False, f"Ошибка базы данных: {exc}"

    def delete_knife_status_entry(self, entry_id: int):
        if not self.conn:
            return False, "Нет подключения к БД."

        try:
            with self.conn:
                cursor = self.conn.cursor()
                row = cursor.execute(
                    "SELECT part_id FROM knife_status_log WHERE id = ?",
                    (entry_id,),
                ).fetchone()
                if not row:
                    return False, "Запись не найдена."

                part_id = row["part_id"]
                cursor.execute("DELETE FROM knife_status_log WHERE id = ?", (entry_id,))

                cursor.execute(
                    """
                        SELECT to_status, changed_at
                        FROM knife_status_log
                        WHERE part_id = ?
                        ORDER BY changed_at DESC
                        LIMIT 1
                    """,
                    (part_id,),
                )
                latest = cursor.fetchone()

                if latest:
                    latest_status = latest["to_status"]
                    changed_at = latest["changed_at"]
                    sharp_state = self._fallback_sharp_state(None, latest_status)
                    installation_state = self._fallback_installation_state(None, latest_status)
                    work_started_at = None
                    if latest_status == "в работе" and changed_at:
                        work_started_at = changed_at.split(" ")[0]
                else:
                    latest_status = "наточен"
                    sharp_state = "заточен"
                    installation_state = "снят"
                    work_started_at = None

                combined_status = latest_status
                if combined_status not in {"в работе", "наточен", "затуплен"}:
                    combined_status = self._combined_status(sharp_state, installation_state)

                cursor.execute(
                    "INSERT OR IGNORE INTO knife_tracking (part_id) VALUES (?)",
                    (part_id,),
                )
                cursor.execute(
                    """
                        UPDATE knife_tracking
                        SET status = ?,
                            sharp_state = ?,
                            installation_state = ?,
                            work_started_at = ?
                        WHERE part_id = ?
                    """,
                    (combined_status, sharp_state, installation_state, work_started_at, part_id),
                )

            self._log_action(
                f"Удалена запись изменения статуса #{entry_id} для комплекта #{part_id}"
            )
            return True, "Запись удалена."
        except sqlite3.Error as exc:
            logging.error("Ошибка удаления записи статуса ножа", exc_info=True)
            return False, f"Ошибка базы данных: {exc}"

