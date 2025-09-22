import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox,
    QDialogButtonBox
)
from PySide6.QtCore import Qt

class CategoryManagerDialog(QDialog):
    """Диалоговое окно для управления категориями запчастей."""

    def __init__(self, db_conn, parent=None):
        super().__init__(parent)
        self.db = db_conn
        self.setWindowTitle("Управление категориями запчастей")
        self.setMinimumWidth(400)
        
        self.changes_made = False

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.edit_category)

        buttons_layout = QHBoxLayout()
        add_btn = QPushButton("Добавить")
        add_btn.clicked.connect(self.add_category)
        edit_btn = QPushButton("Редактировать")
        edit_btn.clicked.connect(self.edit_category)
        delete_btn = QPushButton("Удалить")
        delete_btn.clicked.connect(self.delete_category)

        buttons_layout.addWidget(add_btn)
        buttons_layout.addWidget(edit_btn)
        buttons_layout.addWidget(delete_btn)
        buttons_layout.addStretch()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Close)
        self.button_box.rejected.connect(self.reject)
        
        layout.addWidget(self.list_widget)
        layout.addLayout(buttons_layout)
        layout.addWidget(self.button_box)

        self.load_categories()

    def load_categories(self):
        self.list_widget.clear()
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT id, name FROM part_categories ORDER BY name COLLATE NOCASE")
            for cat_id, name in cursor.fetchall():
                item = QListWidgetItem(name)
                item.setData(Qt.UserRole, cat_id)
                self.list_widget.addItem(item)
        except Exception as e:
            logging.error(f"Не удалось загрузить категории запчастей: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить категории: {e}")

    def add_category(self):
        text, ok = QInputDialog.getText(self, "Новая категория", "Введите наименование:")
        if ok and text.strip():
            try:
                cursor = self.db.conn.cursor()
                cursor.execute("INSERT INTO part_categories (name) VALUES (?)", (text.strip(),))
                self.db.conn.commit()
                self.changes_made = True
                self.load_categories()
            except Exception as e:
                self.db.conn.rollback()
                logging.error(f"Ошибка добавления категории '{text}': {e}")
                QMessageBox.warning(self, "Ошибка", f"Не удалось добавить категорию.\nВозможно, она уже существует.")
    
    def edit_category(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "Действие", "Выберите категорию для редактирования.")
            return

        cat_id = current_item.data(Qt.UserRole)
        old_name = current_item.text()

        if old_name.lower() == 'ножи':
            QMessageBox.warning(self, "Запрещено", "Системную категорию 'ножи' нельзя переименовать.")
            return

        text, ok = QInputDialog.getText(self, "Редактировать категорию", "Новое наименование:", text=old_name)
        if ok and text.strip() and text.strip() != old_name:
            try:
                cursor = self.db.conn.cursor()
                cursor.execute("UPDATE part_categories SET name = ? WHERE id = ?", (text.strip(), cat_id))
                self.db.conn.commit()
                self.changes_made = True
                self.load_categories()
            except Exception as e:
                self.db.conn.rollback()
                logging.error(f"Ошибка переименования категории ID {cat_id}: {e}")
                QMessageBox.warning(self, "Ошибка", f"Не удалось переименовать категорию.\nВозможно, имя уже занято.")

    def delete_category(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "Действие", "Выберите категорию для удаления.")
            return

        cat_id = current_item.data(Qt.UserRole)
        name = current_item.text()
        
        if name.lower() == 'ножи':
            QMessageBox.warning(self, "Запрещено", "Системную категорию 'ножи' нельзя удалить.")
            return

        reply = QMessageBox.question(self, "Подтверждение",
            f"Вы уверены, что хотите удалить категорию '{name}'?\n"
            "Все запчасти в этой категории останутся без категории.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                cursor = self.db.conn.cursor()
                cursor.execute("DELETE FROM part_categories WHERE id = ?", (cat_id,))
                self.db.conn.commit()
                self.changes_made = True
                self.load_categories()
            except Exception as e:
                self.db.conn.rollback()
                logging.error(f"Ошибка удаления категории ID {cat_id}: {e}")
                QMessageBox.warning(self, "Ошибка", f"Не удалось удалить категорию: {e}")
    
    def reject(self):
        # Если были изменения, выходим со статусом Accepted, чтобы родитель мог обновиться
        if self.changes_made:
            self.accept()
        else:
            super().reject()
