import sqlite3
import logging
from pathlib import Path
from typing import Any, Optional
from datetime import date, datetime

class Database:
    """Класс для управления базой данных SQLite."""
    def __init__(self, db_path: str, backup_dir: str):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.conn = None
        self.db_path.parent.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        self._knives_category_id = None

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
            # Кэшируем ID категории "ножи" для производительности
            knives_cat = self.fetchone("SELECT id FROM part_categories WHERE name = 'ножи'")
            if knives_cat:
                self._knives_category_id = knives_cat['id']

        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}", exc_info=True)
            raise

    def disconnect(self):
        """Закрывает соединение с БД."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logging.info("Database connection closed.")

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
                note TEXT
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                counterparty_id INTEGER NOT NULL,
                invoice_no TEXT,
                invoice_date TEXT NOT NULL,
                delivery_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
                status TEXT NOT NULL CHECK(status IN ('создан','в пути','принят','отменён')),
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
        query = "SELECT id, name, sku, qty, min_qty, price FROM parts WHERE qty < min_qty ORDER BY name"
        return self.fetchall(query)

    def get_active_tasks(self):
        """Возвращает незавершенные задачи, отсортированные по приоритету и сроку."""
        query = """
            SELECT t.id, t.title, t.description, t.priority, t.due_date, t.status,
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
            SELECT o.id, c.name as counterparty_name, o.invoice_no, o.invoice_date, o.delivery_date, o.status, o.comment
            FROM orders o
            JOIN counterparties c ON o.counterparty_id = c.id
            WHERE o.status IN ('создан', 'в пути')
            ORDER BY o.delivery_date
        """
        return self.fetchall(query)


    # --- Parts & Categories ---
    def get_all_parts(self):
        query = """
            SELECT p.id, p.name, p.sku, p.qty, p.min_qty, p.price, pc.name as category_name,
                   (SELECT GROUP_CONCAT(eq.name, ', ') FROM equipment_parts ep
                    JOIN equipment eq ON ep.equipment_id = eq.id WHERE ep.part_id = p.id) as equipment_list
            FROM parts p LEFT JOIN part_categories pc ON p.category_id = pc.id
            GROUP BY p.id ORDER BY p.name
        """
        return self.fetchall(query)
    def get_part_by_id(self, part_id): return self.fetchone("SELECT * FROM parts WHERE id = ?", (part_id,))
    
    def _ensure_knife_tracking(self, cursor, part_id, category_id):
        """Проверяет и создает запись для отслеживания ножа."""
        if category_id == self._knives_category_id:
            cursor.execute("INSERT OR IGNORE INTO knife_tracking (part_id) VALUES (?)", (part_id,))
    
    def add_part(self, name, sku, qty, min_qty, price, category_id):
        if not self.conn: return False, "Нет подключения к БД."
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("INSERT INTO parts (name, sku, qty, min_qty, price, category_id) VALUES (?, ?, ?, ?, ?, ?)", 
                               (name, sku, qty, min_qty, price, category_id))
                part_id = cursor.lastrowid
                self._ensure_knife_tracking(cursor, part_id, category_id)
            return True, "Запчасть успешно добавлена."
        except sqlite3.IntegrityError: 
            return False, "Запчасть с таким Наименованием и Артикулом уже существует."

    def update_part(self, part_id, name, sku, qty, min_qty, price, category_id):
        if not self.conn: return False, "Нет подключения к БД."
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE parts SET name=?, sku=?, qty=?, min_qty=?, price=?, category_id=? WHERE id=?", 
                               (name, sku, qty, min_qty, price, category_id, part_id))
                self._ensure_knife_tracking(cursor, part_id, category_id)
            return True, "Данные запчасти обновлены."
        except sqlite3.IntegrityError: 
            return False, "Запчасть с таким Наименованием и Артикулом уже существует."

    def delete_part(self, part_id):
        try:
            if self.fetchone("SELECT 1 FROM equipment_parts WHERE part_id = ?", (part_id,)): return False, "Удаление невозможно: запчасть привязана к оборудованию."
            if self.fetchone("SELECT 1 FROM order_items WHERE part_id = ?", (part_id,)): return False, "Удаление невозможно: запчасть используется в заказах."
            if self.fetchone("SELECT 1 FROM replacements WHERE part_id = ?", (part_id,)): return False, "Удаление невозможно: запчасть используется в истории замен."
            
            if self.fetchone("SELECT 1 FROM knife_tracking WHERE part_id = ?", (part_id,)):
                has_status_log = self.fetchone(
                    "SELECT 1 FROM knife_status_log WHERE part_id = ? LIMIT 1",
                    (part_id,)
                )
                has_sharpen_log = self.fetchone(
                    "SELECT 1 FROM knife_sharpen_log WHERE part_id = ? LIMIT 1",
                    (part_id,)
                )
                if has_status_log or has_sharpen_log:
                    return False, "Удаление невозможно: нож отслеживается. Сначала удалите историю заточек и статусов."
                # Нет истории — безопасно удалить записи отслеживания
                self.execute("DELETE FROM knife_tracking WHERE part_id = ?", (part_id,))
            
            self.execute("DELETE FROM parts WHERE id = ?", (part_id,))
            if self.conn: self.conn.commit()
            return True, "Запчасть удалена."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
        
    def get_part_categories(self): return self.fetchall("SELECT id, name FROM part_categories ORDER BY name")
    def add_part_category(self, name):
        try:
            self.execute("INSERT INTO part_categories (name) VALUES (?)", (name,))
            if self.conn: self.conn.commit()
            return True, "Категория добавлена."
        except sqlite3.IntegrityError: return False, "Категория с таким именем уже существует."
    def update_part_category(self, category_id, name):
        try:
            self.execute("UPDATE part_categories SET name = ? WHERE id = ?", (name, category_id))
            if self.conn: self.conn.commit()
            return True, "Категория переименована."
        except sqlite3.IntegrityError: return False, "Категория с таким именем уже существует."
    def delete_part_category(self, category_id):
        if category_id == self._knives_category_id:
            return False, "Системную категорию 'ножи' нельзя удалить."
        try:
            self.execute("DELETE FROM part_categories WHERE id = ?", (category_id,))
            if self.conn: self.conn.commit()
            return True, "Категория удалена."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"

    # --- Counterparties, Orders, Equipment etc. (existing methods) ---
    def get_all_counterparties(self): return self.fetchall("SELECT * FROM counterparties ORDER BY name")
    def get_counterparty_by_id(self, counterparty_id): return self.fetchone("SELECT * FROM counterparties WHERE id = ?", (counterparty_id,))
    def add_counterparty(self, name, address, contact_person, phone, email, note):
        try:
            self.execute("INSERT INTO counterparties (name, address, contact_person, phone, email, note) VALUES (?, ?, ?, ?, ?, ?)", (name, address, contact_person, phone, email, note))
            if self.conn: self.conn.commit()
            return True, "Контрагент добавлен."
        except sqlite3.IntegrityError: return False, "Контрагент с таким именем уже существует."
    def update_counterparty(self, c_id, name, address, contact_person, phone, email, note):
        try:
            self.execute("UPDATE counterparties SET name=?, address=?, contact_person=?, phone=?, email=?, note=? WHERE id=?", (name, address, contact_person, phone, email, note, c_id))
            if self.conn: self.conn.commit()
            return True, "Данные контрагента обновлены."
        except sqlite3.IntegrityError: return False, "Контрагент с таким именем уже существует."
    def delete_counterparty(self, c_id):
        if self.fetchone("SELECT 1 FROM orders WHERE counterparty_id = ?", (c_id,)): return False, "Удаление невозможно: у контрагента есть заказы."
        try:
            self.execute("DELETE FROM counterparties WHERE id = ?", (c_id,))
            if self.conn: self.conn.commit()
            return True, "Контрагент удален."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def get_all_orders_with_counterparty(self):
        query = """
            SELECT o.id, c.name as counterparty_name, o.invoice_no, o.invoice_date, o.delivery_date, o.created_at, o.status, o.comment
            FROM orders o JOIN counterparties c ON o.counterparty_id = c.id ORDER BY o.created_at DESC
        """
        return self.fetchall(query)
    def get_order_details(self, order_id): return self.fetchone("SELECT * FROM orders WHERE id = ?", (order_id,))
    def get_order_items(self, order_id): return self.fetchall("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    def create_order_with_items(self, order_data, items_data):
        if not self.conn: return False, "Нет подключения к БД."
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute(
                    """INSERT INTO orders (counterparty_id, invoice_no, invoice_date, delivery_date, status, comment)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (order_data['counterparty_id'], order_data['invoice_no'], order_data['invoice_date'],
                     order_data['delivery_date'], order_data['status'], order_data['comment'])
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
                    """UPDATE orders SET counterparty_id=?, invoice_no=?, invoice_date=?, delivery_date=?, status=?, comment=?
                       WHERE id=?""",
                    (order_data['counterparty_id'], order_data['invoice_no'], order_data['invoice_date'],
                     order_data['delivery_date'], order_data['status'], order_data['comment'], order_id)
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
            return True, "Поставка успешно принята, остатки на складе обновлены."
        except sqlite3.Error as e:
            logging.error(f"Ошибка транзакции при приемке поставки: {e}", exc_info=True)
            return False, f"Ошибка транзакции: {e}"
    def get_equipment_categories(self): return self.fetchall("SELECT id, name FROM equipment_categories ORDER BY name")
    def add_equipment_category(self, name):
        try:
            self.execute("INSERT INTO equipment_categories (name) VALUES (?)", (name,))
            if self.conn: self.conn.commit()
            return True, "Категория добавлена."
        except sqlite3.IntegrityError: return False, "Категория с таким именем уже существует."
    def update_equipment_category(self, cat_id, name):
        try:
            self.execute("UPDATE equipment_categories SET name = ? WHERE id = ?", (name, cat_id))
            if self.conn: self.conn.commit()
            return True, "Категория обновлена."
        except sqlite3.IntegrityError: return False, "Категория с таким именем уже существует."
    def delete_equipment_category(self, cat_id):
        if self.fetchone("SELECT 1 FROM equipment WHERE category_id = ?", (cat_id,)): return False, "Удаление невозможно: в категории есть оборудование."
        try:
            self.execute("DELETE FROM equipment_categories WHERE id = ?", (cat_id,))
            if self.conn: self.conn.commit()
            return True, "Категория удалена."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def get_all_equipment(self): return self.fetchall("SELECT id, name, sku, category_id, parent_id FROM equipment ORDER BY name")
    def add_equipment(self, name, sku, category_id, parent_id=None):
        try:
            self.execute("INSERT INTO equipment (name, sku, category_id, parent_id) VALUES (?, ?, ?, ?)", (name, sku, category_id, parent_id))
            if self.conn: self.conn.commit()
            return True, "Оборудование добавлено."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def update_equipment(self, eq_id, name, sku, category_id, parent_id=None):
        try:
            if eq_id and eq_id == parent_id: return False, "Оборудование не может быть родителем для самого себя."
            self.execute("UPDATE equipment SET name=?, sku=?, category_id=?, parent_id=? WHERE id=?", (name, sku, category_id, parent_id, eq_id))
            if self.conn: self.conn.commit()
            return True, "Данные оборудования обновлены."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def delete_equipment(self, eq_id):
        if self.fetchone("SELECT 1 FROM equipment_parts WHERE equipment_id = ?", (eq_id,)): return False, "Удаление невозможно: к оборудованию привязаны запчасти."
        if self.fetchone("SELECT 1 FROM replacements WHERE equipment_id = ?", (eq_id,)): return False, "Удаление невозможно: оборудование фигурирует в истории замен."
        try:
            self.execute("DELETE FROM equipment WHERE id = ?", (eq_id,))
            if self.conn: self.conn.commit()
            return True, "Оборудование удалено."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def get_parts_for_equipment(self, equipment_id):
        query = """
            SELECT ep.id as equipment_part_id, p.id as part_id, p.name as part_name, p.sku as part_sku, ep.installed_qty,
                   (SELECT MAX(r.date) FROM replacements r WHERE r.part_id = p.id AND r.equipment_id = ep.equipment_id) as last_replacement_date
            FROM equipment_parts ep JOIN parts p ON ep.part_id = p.id WHERE ep.equipment_id = ? ORDER BY p.name
        """
        return self.fetchall(query, (equipment_id,))
    def attach_part_to_equipment(self, equipment_id, part_id, qty):
        try:
            self.execute("INSERT INTO equipment_parts (equipment_id, part_id, installed_qty) VALUES (?, ?, ?)", (equipment_id, part_id, qty))
            if self.conn: self.conn.commit()
            return True, "Запчасть успешно привязана."
        except sqlite3.IntegrityError: return False, "Эта запчасть уже привязана к данному оборудованию."
    def detach_part_from_equipment(self, equipment_part_id):
        try:
            self.execute("DELETE FROM equipment_parts WHERE id = ?", (equipment_part_id,))
            if self.conn: self.conn.commit()
            return True, "Запчасть отвязана."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def get_unattached_parts(self, equipment_id):
        query = """
            SELECT p.id, p.name, p.sku, p.qty FROM parts p
            WHERE p.id NOT IN (SELECT part_id FROM equipment_parts WHERE equipment_id = ?) ORDER BY p.name
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
            return True, "Запись о замене обновлена."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def delete_replacement(self, replacement_id):
        try:
            self.execute("DELETE FROM replacements WHERE id = ?", (replacement_id,))
            if self.conn: self.conn.commit()
            return True, "Запись из истории замен удалена."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def get_all_colleagues(self): return self.fetchall("SELECT id, name FROM colleagues ORDER BY name")
    def add_colleague(self, name):
        try:
            self.execute("INSERT INTO colleagues (name) VALUES (?)", (name,))
            if self.conn: self.conn.commit()
            return True, "Сотрудник добавлен."
        except sqlite3.IntegrityError: return False, "Сотрудник с таким именем уже существует."
    def update_colleague(self, colleague_id, name):
        try:
            self.execute("UPDATE colleagues SET name = ? WHERE id = ?", (name, colleague_id))
            if self.conn: self.conn.commit()
            return True, "Имя сотрудника обновлено."
        except sqlite3.IntegrityError: return False, "Сотрудник с таким именем уже существует."
    def delete_colleague(self, colleague_id):
        try:
            self.execute("DELETE FROM colleagues WHERE id = ?", (colleague_id,))
            if self.conn: self.conn.commit()
            return True, "Сотрудник удален."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def get_all_tasks(self):
        query = """
            SELECT t.id, t.title, t.description, t.priority, t.due_date, t.status,
                   c.name as assignee_name, e.name as equipment_name
            FROM tasks t
            LEFT JOIN colleagues c ON t.assignee_id = c.id
            LEFT JOIN equipment e ON t.equipment_id = e.id
            ORDER BY 
                CASE t.priority WHEN 'высокий' THEN 1 WHEN 'средний' THEN 2 WHEN 'низкий' THEN 3 ELSE 4 END, 
                t.due_date
        """
        return self.fetchall(query)
    def get_task_by_id(self, task_id): return self.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
    def add_task(self, title, description, priority, due_date, assignee_id, equipment_id, status):
        try:
            self.execute("INSERT INTO tasks (title, description, priority, due_date, assignee_id, equipment_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (title, description, priority, due_date, assignee_id, equipment_id, status))
            if self.conn: self.conn.commit()
            return True, "Задача создана."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def update_task(self, task_id, title, description, priority, due_date, assignee_id, equipment_id, status):
        try:
            self.execute("UPDATE tasks SET title=?, description=?, priority=?, due_date=?, assignee_id=?, equipment_id=?, status=? WHERE id=?",
                         (title, description, priority, due_date, assignee_id, equipment_id, status, task_id))
            if self.conn: self.conn.commit()
            return True, "Задача обновлена."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def update_task_status(self, task_id, new_status):
        try:
            self.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
            if self.conn: self.conn.commit()
            return True, "Статус задачи обновлен."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
    def delete_task(self, task_id):
        try:
            self.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            if self.conn: self.conn.commit()
            return True, "Задача удалена."
        except sqlite3.Error as e: return False, f"Ошибка базы данных: {e}"
        
    # --- Knives ---
    def get_all_knives_data(self):
        query = """
            SELECT
                p.id, p.name, p.sku, p.qty,
                kt.status,
                kt.last_sharpen_date,
                kt.work_started_at,
                kt.last_interval_days
            FROM parts p
            JOIN part_categories pc ON p.category_id = pc.id
            LEFT JOIN knife_tracking kt ON p.id = kt.part_id
            WHERE pc.name = 'ножи'
        """
        return self.fetchall(query)

    def update_knife_status(self, part_id, new_status, comment=""):
        if not self.conn: return False, "Нет подключения к БД."
        try:
            with self.conn:
                cursor = self.conn.cursor()
                # Убеждаемся, что запись отслеживания существует
                cursor.execute("INSERT OR IGNORE INTO knife_tracking (part_id) VALUES (?)", (part_id,))
                
                cursor.execute("SELECT status, work_started_at FROM knife_tracking WHERE part_id = ?", (part_id,))
                current_state = cursor.fetchone()
                
                if not current_state: # Эта проверка теперь избыточна, но оставим для надежности
                    return False, "Не удалось создать/найти запись об отслеживании ножа."
                
                from_status = current_state['status']
                if from_status == new_status: return True, "Статус не изменился."

                today_str = date.today().isoformat()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if new_status == 'в работе':
                    cursor.execute("UPDATE knife_tracking SET work_started_at = ? WHERE part_id = ?", (today_str, part_id))

                elif new_status == 'затуплен' and from_status == 'в работе' and current_state['work_started_at']:
                    start_date = date.fromisoformat(current_state['work_started_at'])
                    end_date = date.today()
                    interval = (end_date - start_date).days
                    cursor.execute("UPDATE knife_tracking SET last_interval_days = ?, work_started_at = NULL WHERE part_id = ?", (interval, part_id))
                
                cursor.execute("UPDATE knife_tracking SET status = ? WHERE part_id = ?", (new_status, part_id))
                cursor.execute("INSERT INTO knife_status_log (part_id, from_status, to_status, comment, changed_at) VALUES (?, ?, ?, ?, ?)",
                               (part_id, from_status, new_status, comment, timestamp))
                
            return True, "Статус ножа успешно обновлен."
        except Exception as e:
            logging.error(f"Ошибка транзакции при смене статуса ножа: {e}", exc_info=True)
            return False, f"Ошибка транзакции: {e}"

    def sharpen_knives(self, part_ids, sharpen_date, comment=""):
        if not self.conn: return False, "Нет подключения к БД."
        try:
            with self.conn:
                cursor = self.conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for part_id in part_ids:
                    cursor.execute("INSERT OR IGNORE INTO knife_tracking (part_id) VALUES (?)", (part_id,))
                    
                    # Get current status to log the change
                    cursor.execute("SELECT status FROM knife_tracking WHERE part_id = ?", (part_id,))
                    res = cursor.fetchone()
                    from_status = res['status'] if res else 'неизвестно'

                    cursor.execute("""
                        UPDATE knife_tracking 
                        SET status = 'наточен', last_sharpen_date = ?, total_sharpenings = total_sharpenings + 1
                        WHERE part_id = ?
                    """, (sharpen_date, part_id))
                    
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
            return True, "Ножи успешно отправлены на заточку."
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

            return True, "Запись удалена."
        except sqlite3.Error as exc:
            logging.error("Ошибка удаления записи истории заточек", exc_info=True)
            return False, f"Ошибка базы данных: {exc}"

