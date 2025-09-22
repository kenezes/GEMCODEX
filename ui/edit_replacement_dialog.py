import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QDateEdit, QSpinBox, QLabel,
                             QDialogButtonBox, QMessageBox)
from PySide6.QtCore import QDate
from .utils import db_string_to_qdate, qdate_to_db_string

class EditReplacementDialog(QDialog):
    def __init__(self, db, event_bus, replacement_id, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.replacement_id = replacement_id
        
        self.setWindowTitle("Редактирование записи о замене")
        self.setMinimumWidth(400)
        
        self.layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        
        self.qty_spinbox = QSpinBox()
        self.qty_spinbox.setRange(1, 9999)
        
        self.reason_input = QLineEdit()

        info_label = QLabel(
            "<b>Внимание:</b><br>"
            "Редактирование этой записи не изменяет<br>"
            "остатки запчастей на складе."
        )
        info_label.setStyleSheet("color: #555; margin-bottom: 10px;")

        form_layout.addRow("Дата:", self.date_edit)
        form_layout.addRow("Количество, шт.:", self.qty_spinbox)
        form_layout.addRow("Причина:", self.reason_input)

        self.layout.addWidget(info_label)
        self.layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        self.load_data()

    def load_data(self):
        data = self.db.get_replacement_by_id(self.replacement_id)
        if data:
            self.date_edit.setDate(db_string_to_qdate(data['date']))
            self.qty_spinbox.setValue(data['qty'])
            self.reason_input.setText(data['reason'])
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось загрузить данные о замене.")
            self.reject()

    def accept(self):
        date_str = qdate_to_db_string(self.date_edit.date())
        qty = self.qty_spinbox.value()
        reason = self.reason_input.text().strip()

        success, message = self.db.update_replacement(self.replacement_id, date_str, qty, reason)

        if success:
            QMessageBox.information(self, "Успех", message)
            self.event_bus.emit("replacements.changed")
            super().accept()
        else:
            QMessageBox.warning(self, "Ошибка", message)
