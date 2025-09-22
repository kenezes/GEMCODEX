import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QDialogButtonBox, QMessageBox, QSpinBox, QLabel)
from PySide6.QtCore import Qt

from .utils import get_current_date_str_for_db

class ReplacementDialog(QDialog):
    def __init__(self, db, event_bus, part_data, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.part_data = part_data
        
        self.setWindowTitle("Замена запчасти")
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        part_name = self.part_data.get('part_name', 'Неизвестно')
        part_sku = self.part_data.get('part_sku', 'б/а')

        self.part_label = QLabel(f"{part_name} ({part_sku})")
        self.qty_spinbox = QSpinBox()
        self.qty_spinbox.setRange(1, 1000)
        self.qty_spinbox.setValue(self.part_data.get('installed_qty', 1))
        
        self.reason_edit = QLineEdit()
        self.reason_edit.setPlaceholderText("Например: плановое ТО, поломка")

        form_layout.addRow("Запчасть:", self.part_label)
        form_layout.addRow("Списывается со склада, шт.*:", self.qty_spinbox)
        form_layout.addRow("Причина:", self.reason_edit)

        layout.addLayout(form_layout)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def accept(self):
        qty_to_replace = self.qty_spinbox.value()
        reason = self.reason_edit.text().strip()
        part_id = self.part_data['part_id']
        equipment_id = self.part_data['equipment_id']
        date_str = get_current_date_str_for_db()

        success, message = self.db.perform_replacement(date_str, equipment_id, part_id, qty_to_replace, reason)

        if success:
            QMessageBox.information(self, "Успех", message)
            self.event_bus.emit("parts.changed")
            self.event_bus.emit("replacements.changed")
            self.event_bus.emit("equipment_parts_changed", equipment_id)
            super().accept()
        else:
            QMessageBox.critical(self, "Ошибка", message)

