import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QTextEdit, QDialogButtonBox, QMessageBox)

class CounterpartyDialog(QDialog):
    def __init__(self, db, event_bus, counterparty_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.counterparty_id = counterparty_id

        self.setWindowTitle("Редактирование контрагента" if self.counterparty_id else "Новый контрагент")
        self.setMinimumWidth(400)

        self.layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.address_input = QLineEdit()
        self.contact_person_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.email_input = QLineEdit()
        self.note_input = QTextEdit()
        self.note_input.setAcceptRichText(False)

        form_layout.addRow("Наименование*:", self.name_input)
        form_layout.addRow("Адрес:", self.address_input)
        form_layout.addRow("Контактное лицо:", self.contact_person_input)
        form_layout.addRow("Телефон:", self.phone_input)
        form_layout.addRow("Email:", self.email_input)
        form_layout.addRow("Комментарий:", self.note_input)
        
        self.layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        if self.counterparty_id:
            self.load_data()

    def load_data(self):
        data = self.db.get_counterparty_by_id(self.counterparty_id)
        if data:
            self.name_input.setText(data.get('name', ''))
            self.address_input.setText(data.get('address', ''))
            self.contact_person_input.setText(data.get('contact_person', ''))
            self.phone_input.setText(data.get('phone', ''))
            self.email_input.setText(data.get('email', ''))
            self.note_input.setPlainText(data.get('note', ''))

    def accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка валидации", "Поле 'Наименование' обязательно для заполнения.")
            return

        data = {
            "name": name,
            "address": self.address_input.text().strip(),
            "contact_person": self.contact_person_input.text().strip(),
            "phone": self.phone_input.text().strip(),
            "email": self.email_input.text().strip(),
            "note": self.note_input.toPlainText().strip()
        }

        if self.counterparty_id:
            success, message = self.db.update_counterparty(self.counterparty_id, **data)
            logging.info(f"Обновление контрагента ID {self.counterparty_id}")
        else:
            success, message = self.db.add_counterparty(**data)
            logging.info(f"Добавление нового контрагента '{data['name']}'")

        if success:
            QMessageBox.information(self, "Успех", message)
            logging.info(f"Диалог контрагента ID {self.counterparty_id} завершился успешно.")
            self.event_bus.emit("counterparties.changed")
            super().accept()
        else:
            QMessageBox.warning(self, "Ошибка сохранения", message)
            logging.warning(f"Ошибка сохранения контрагента: {message}")

