import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QTextEdit, QDialogButtonBox, QMessageBox, QListWidget,
                             QListWidgetItem, QPushButton, QHBoxLayout, QWidget, QInputDialog,
                             QAbstractItemView)

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
        self.contact_person_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.email_input = QLineEdit()
        self.note_input = QTextEdit()
        self.note_input.setAcceptRichText(False)

        self.address_list = QListWidget()
        self.address_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.address_list.itemDoubleClicked.connect(lambda _: self.edit_selected_address())
        self.address_list.currentItemChanged.connect(lambda *_: self._update_address_buttons_state())

        addresses_container = QWidget()
        addresses_layout = QVBoxLayout(addresses_container)
        addresses_layout.setContentsMargins(0, 0, 0, 0)
        addresses_layout.addWidget(self.address_list)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.add_address_button = QPushButton("Добавить")
        self.add_address_button.clicked.connect(self.add_address)
        self.edit_address_button = QPushButton("Изменить")
        self.edit_address_button.clicked.connect(self.edit_selected_address)
        self.remove_address_button = QPushButton("Удалить")
        self.remove_address_button.clicked.connect(self.remove_selected_address)
        self.default_address_button = QPushButton("Сделать основным")
        self.default_address_button.clicked.connect(self.mark_selected_as_default)

        buttons_layout.addWidget(self.add_address_button)
        buttons_layout.addWidget(self.edit_address_button)
        buttons_layout.addWidget(self.remove_address_button)
        buttons_layout.addWidget(self.default_address_button)

        addresses_layout.addLayout(buttons_layout)

        form_layout.addRow("Наименование*:", self.name_input)
        form_layout.addRow("Адреса:", addresses_container)
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

        self._update_address_buttons_state()

    def load_data(self):
        data = self.db.get_counterparty_by_id(self.counterparty_id)
        if data:
            self.name_input.setText(data.get('name', ''))
            self.contact_person_input.setText(data.get('contact_person', ''))
            self.phone_input.setText(data.get('phone', ''))
            self.email_input.setText(data.get('email', ''))
            self.note_input.setPlainText(data.get('note', ''))
            self._populate_addresses(data)
        else:
            self.address_list.clear()
        self._update_address_buttons_state()

    def _populate_addresses(self, data):
        addresses = data.get('addresses', []) or []
        if not addresses and data.get('default_address'):
            addresses = [{'address': data.get('default_address', ''), 'is_default': True}]

        self.address_list.clear()

        default_item: QListWidgetItem | None = None
        for entry in addresses:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, {
                'address': entry.get('address', ''),
                'is_default': bool(entry.get('is_default')),
            })
            self._update_address_item_text(item)
            self.address_list.addItem(item)
            if entry.get('is_default') and default_item is None:
                default_item = item

        if self.address_list.count():
            self.address_list.setCurrentItem(default_item or self.address_list.item(0))

    def _update_address_item_text(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole) or {}
        text = data.get('address', '')
        item.setText(text)

    def _update_address_buttons_state(self):
        has_selection = self.address_list.currentItem() is not None
        self.edit_address_button.setEnabled(has_selection)
        self.remove_address_button.setEnabled(has_selection)
        self.default_address_button.setEnabled(has_selection)

    def _mark_item_default(self, item: QListWidgetItem | None):
        for idx in range(self.address_list.count()):
            current_item = self.address_list.item(idx)
            data = current_item.data(Qt.UserRole) or {}
            data['is_default'] = current_item is item and item is not None
            current_item.setData(Qt.UserRole, data)
            self._update_address_item_text(current_item)

    def add_address(self):
        text, ok = QInputDialog.getText(self, "Добавить адрес", "Адрес:")
        if not ok:
            return
        text = text.strip()
        if not text:
            return

        was_empty = self.address_list.count() == 0
        item = QListWidgetItem()
        item.setData(Qt.UserRole, {'address': text, 'is_default': was_empty})
        self._update_address_item_text(item)
        self.address_list.addItem(item)
        self.address_list.setCurrentItem(item)
        if was_empty:
            self._mark_item_default(item)
        self._update_address_buttons_state()

    def edit_selected_address(self):
        item = self.address_list.currentItem()
        if not item:
            return
        data = item.data(Qt.UserRole) or {}
        text, ok = QInputDialog.getText(self, "Изменить адрес", "Адрес:", text=data.get('address', ''))
        if not ok:
            return
        new_text = text.strip()
        if not new_text:
            return
        data['address'] = new_text
        item.setData(Qt.UserRole, data)
        self._update_address_item_text(item)

    def remove_selected_address(self):
        item = self.address_list.currentItem()
        if not item:
            return
        row = self.address_list.row(item)
        data = item.data(Qt.UserRole) or {}
        self.address_list.takeItem(row)
        if data.get('is_default') and self.address_list.count():
            self._mark_item_default(self.address_list.item(0))
        if self.address_list.count():
            self.address_list.setCurrentRow(min(row, self.address_list.count() - 1))
        self._update_address_buttons_state()

    def mark_selected_as_default(self):
        item = self.address_list.currentItem()
        if not item:
            return
        self._mark_item_default(item)
        self._update_address_buttons_state()

    def _collect_addresses(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for idx in range(self.address_list.count()):
            item = self.address_list.item(idx)
            data = item.data(Qt.UserRole) or {}
            address_text = data.get('address', '').strip()
            if not address_text:
                continue
            result.append({'address': address_text, 'is_default': bool(data.get('is_default'))})
        return result

    def accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка валидации", "Поле 'Наименование' обязательно для заполнения.")
            return

        addresses = self._collect_addresses()
        default_address = next((a['address'] for a in addresses if a.get('is_default')), addresses[0]['address'] if addresses else '')

        data = {
            "name": name,
            "address": default_address,
            "contact_person": self.contact_person_input.text().strip(),
            "phone": self.phone_input.text().strip(),
            "email": self.email_input.text().strip(),
            "note": self.note_input.toPlainText().strip()
        }

        if self.counterparty_id:
            success, message = self.db.update_counterparty(self.counterparty_id, addresses=addresses, **data)
            logging.info(f"Обновление контрагента ID {self.counterparty_id}")
        else:
            success, message = self.db.add_counterparty(addresses=addresses, **data)
            logging.info(f"Добавление нового контрагента '{data['name']}'")

        if success:
            QMessageBox.information(self, "Успех", message)
            logging.info(f"Диалог контрагента ID {self.counterparty_id} завершился успешно.")
            self.event_bus.emit("counterparties.changed")
            super().accept()
        else:
            QMessageBox.warning(self, "Ошибка сохранения", message)
            logging.warning(f"Ошибка сохранения контрагента: {message}")

