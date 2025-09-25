from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QDialogButtonBox, QMessageBox, QComboBox, QPlainTextEdit)

from .utils import move_equipment_folder_on_rename

class EquipmentDialog(QDialog):
    def __init__(self, db, event_bus, category_id=None, parent_id=None, equipment_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.equipment_id = equipment_id
        self.initial_category_id = category_id
        self.initial_parent_id = parent_id
        self.original_name = None
        self.original_sku = None

        self.setWindowTitle("Редактирование оборудования" if self.equipment_id else "Новое оборудование")
        
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.sku_edit = QLineEdit()
        self.category_combo = QComboBox()
        self.parent_combo = QComboBox()
        self.comment_edit = QPlainTextEdit()
        self.comment_edit.setPlaceholderText("Комментарий об оборудовании")
        self.comment_edit.setMaximumHeight(100)

        form_layout.addRow("Наименование*:", self.name_edit)
        form_layout.addRow("Артикул:", self.sku_edit)
        form_layout.addRow("Категория*:", self.category_combo)
        form_layout.addRow("Родитель:", self.parent_combo)
        form_layout.addRow("Комментарий:", self.comment_edit)

        layout.addLayout(form_layout)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.load_combos()

        if self.equipment_id:
            self.load_data()
        else: # For new equipment
            if self.initial_category_id:
                cat_index = self.category_combo.findData(self.initial_category_id)
                if cat_index != -1: self.category_combo.setCurrentIndex(cat_index)
            if self.initial_parent_id:
                parent_index = self.parent_combo.findData(self.initial_parent_id)
                if parent_index != -1: self.parent_combo.setCurrentIndex(parent_index)


    def load_combos(self):
        # Load categories
        categories = self.db.get_equipment_categories()
        for cat in categories:
            self.category_combo.addItem(cat['name'], cat['id'])
        
        # Load possible parents
        self.parent_combo.addItem("Нет (верхний уровень)", None)
        all_equipment = self.db.get_all_equipment()
        for eq in all_equipment:
            if self.equipment_id and self.equipment_id == eq['id']:
                continue
            self.parent_combo.addItem(f"{eq['name']} ({eq.get('sku') or 'б/а'})", eq['id'])

    def load_data(self):
        data = self.db.fetchone("SELECT * FROM equipment WHERE id = ?", (self.equipment_id,))
        if data:
            self.name_edit.setText(data['name'])
            self.sku_edit.setText(data['sku'] or "")
            self.original_name = data['name']
            self.original_sku = data['sku'] or ""
            self.comment_edit.setPlainText(data.get('comment') or "")
            
            cat_index = self.category_combo.findData(data['category_id'])
            if cat_index != -1: self.category_combo.setCurrentIndex(cat_index)

            parent_id = data.get('parent_id')
            if parent_id:
                parent_index = self.parent_combo.findData(parent_id)
                if parent_index != -1: self.parent_combo.setCurrentIndex(parent_index)
            else:
                self.parent_combo.setCurrentIndex(0)

    def accept(self):
        name = self.name_edit.text().strip()
        sku = self.sku_edit.text().strip() or None
        category_id = self.category_combo.currentData()
        parent_id = self.parent_combo.currentData()

        if not name or category_id is None:
            QMessageBox.warning(self, "Ошибка валидации", "Поля 'Наименование' и 'Категория' обязательны.")
            return

        comment = self.comment_edit.toPlainText().strip()

        if self.equipment_id:
            success, message = self.db.update_equipment(self.equipment_id, name, sku, category_id, parent_id, comment)
        else:
            success, message = self.db.add_equipment(name, sku, category_id, parent_id, comment)

        if success:
            if self.equipment_id:
                move_equipment_folder_on_rename(self.original_name, self.original_sku, name, sku, self)
                self.original_name = name
                self.original_sku = sku or ""
            self.event_bus.emit("equipment.changed")
            super().accept()
        else:
            QMessageBox.critical(self, "Ошибка базы данных", message)

