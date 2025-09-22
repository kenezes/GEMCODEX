from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QPushButton, QLineEdit, QDialogButtonBox, QMessageBox,
                             QInputDialog, QListWidgetItem)
from PySide6.QtCore import Qt

class ColleaguesManagerDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Управление списком коллег")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        buttons_layout = QHBoxLayout()
        add_button = QPushButton("Добавить")
        rename_button = QPushButton("Переименовать")
        delete_button = QPushButton("Удалить")
        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(rename_button)
        buttons_layout.addWidget(delete_button)
        layout.addLayout(buttons_layout)

        close_button = QDialogButtonBox(QDialogButtonBox.Close)
        close_button.rejected.connect(self.reject)
        layout.addWidget(close_button)

        add_button.clicked.connect(self.add_colleague)
        rename_button.clicked.connect(self.rename_colleague)
        delete_button.clicked.connect(self.delete_colleague)
        self.list_widget.itemDoubleClicked.connect(self.rename_colleague)

        self.load_colleagues()

    def load_colleagues(self):
        self.list_widget.clear()
        colleagues = self.db.get_all_colleagues()
        for c in colleagues:
            item = QListWidgetItem(c['name'])
            item.setData(Qt.UserRole, c['id'])
            self.list_widget.addItem(item)

    def add_colleague(self):
        name, ok = QInputDialog.getText(self, "Добавить сотрудника", "Имя:")
        if ok and name.strip():
            success, message = self.db.add_colleague(name.strip())
            if success:
                self.load_colleagues()
            else:
                QMessageBox.warning(self, "Ошибка", message)

    def rename_colleague(self):
        selected_item = self.list_widget.currentItem()
        if not selected_item: return

        old_name = selected_item.text()
        colleague_id = selected_item.data(Qt.UserRole)
        
        new_name, ok = QInputDialog.getText(self, "Переименовать сотрудника", "Новое имя:", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            success, message = self.db.update_colleague(colleague_id, new_name.strip())
            if success:
                self.load_colleagues()
            else:
                QMessageBox.warning(self, "Ошибка", message)

    def delete_colleague(self):
        selected_item = self.list_widget.currentItem()
        if not selected_item: return

        colleague_name = selected_item.text()
        colleague_id = selected_item.data(Qt.UserRole)

        reply = QMessageBox.question(self, "Удаление", f"Вы уверены, что хотите удалить сотрудника '{colleague_name}'?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.db.delete_colleague(colleague_id)
            if success:
                self.load_colleagues()
            else:
                QMessageBox.critical(self, "Ошибка", message)
