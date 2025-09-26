from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QDateEdit, 
                             QLineEdit, QDialogButtonBox, QLabel)
from PySide6.QtCore import QDate

from .utils import qdate_to_db_string

class SharpenKnivesDialog(QDialog):
    def __init__(self, selected_items_count, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Отправить комплекты на заточку")

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.info_label = QLabel(f"Выбрано комплектов для заточки: <b>{selected_items_count}</b> шт.")
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.comment_edit = QLineEdit()

        form_layout.addRow(self.info_label)
        form_layout.addRow("Дата заточки:", self.date_edit)
        form_layout.addRow("Комментарий:", self.comment_edit)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)

    def get_data(self):
        return {
            "date": qdate_to_db_string(self.date_edit.date()),
            "comment": self.comment_edit.text().strip()
        }
