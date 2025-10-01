import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, QComboBox,
    QDateEdit, QDialogButtonBox, QMessageBox, QHBoxLayout, QPushButton,
    QTableView, QHeaderView, QAbstractItemView, QGroupBox, QInputDialog
)
from PySide6.QtCore import Qt, QDate, QAbstractTableModel, QModelIndex

from .utils import qdate_to_db_string, apply_table_compact_style
from .part_selection_dialog import PartSelectionDialog
from .manual_part_dialog import ManualPartDialog

class OrderItemsTableModel(QAbstractTableModel):
    """Модель данных для таблицы позиций в заказе."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ["Наименование", "Артикул", "Кол-во", "Цена", "Сумма"]
        # item: [part_id, name, sku, qty, price, original_price]
        self._items = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        item = self._items[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0: return item[1] # name
            if col == 1: return item[2] # sku
            if col == 2: return item[3] # qty
            if col == 3: return f"{item[4]:.2f}" # price
            if col == 4: return f"{item[3] * item[4]:.2f}" # sum
        
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None
    
    def flags(self, index):
        # Разрешаем редактирование для колонок "Кол-во" и "Цена"
        if index.column() in [2, 3]:
            return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return super().flags(index)

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.EditRole and index.isValid():
            row = index.row()
            col = index.column()
            item = self._items[row]
            
            # Колонка 2: Количество
            if col == 2:
                try:
                    qty = int(value)
                    if qty > 0:
                        item[3] = qty
                        self.dataChanged.emit(index, index.siblingAtColumn(4)) # Обновить сумму
                        return True
                except ValueError:
                    return False

            # Колонка 3: Цена
            if col == 3:
                try:
                    price = round(float(str(value).replace(',', '.')), 2)
                    if price >= 0:
                        item[4] = price
                        self.dataChanged.emit(index, index.siblingAtColumn(4)) # Обновить сумму
                        return True
                except (ValueError, TypeError):
                    return False
        return False

    def add_item(self, item_data):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self._items.append(item_data)
        self.endInsertRows()

    def remove_item(self, row):
        if 0 <= row < self.rowCount():
            self.beginRemoveRows(QModelIndex(), row, row)
            self._items.pop(row)
            self.endRemoveRows()

    def get_items(self):
        return self._items

    def load_items(self, items):
        self.beginResetModel()
        self._items = items
        self.endResetModel()

class OrderDialog(QDialog):
    """Диалоговое окно для создания и редактирования заказа."""

    def __init__(self, db, event_bus, order_id=None, parent=None, initial_items=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.order_id = order_id
        self.is_edit_mode = self.order_id is not None
        self._counterparty_addresses: dict[int, list[dict]] = {}
        self._pending_delivery_address: str | None = None

        title = "Редактировать заказ" if self.is_edit_mode else "Новый заказ"
        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)
        
        self.init_ui()
        self.load_combobox_data()
        
        if self.is_edit_mode:
            self.load_order_data()
        elif initial_items:
             # Загружаем предзаполненные данные с дашборда
            formatted_items = [[item['part_id'], item['name'], item['sku'], item['qty'], item['price'], item['price']] for item in initial_items]
            self.items_table_model.load_items(formatted_items)


    def init_ui(self):
        main_layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.counterparty_combo = QComboBox()
        self.counterparty_combo.currentIndexChanged.connect(self._on_counterparty_changed)
        self.address_combo = QComboBox()
        self.address_combo.setPlaceholderText("Выберите адрес")
        self.invoice_no_edit = QLineEdit()
        self.invoice_date_edit = QDateEdit(QDate.currentDate())
        self.invoice_date_edit.setCalendarPopup(True)
        self.delivery_date_edit = QDateEdit(QDate.currentDate())
        self.delivery_date_edit.setCalendarPopup(True)
        self.status_combo = QComboBox()
        self.comment_edit = QTextEdit()
        self.comment_edit.setFixedHeight(60)

        form_layout.addRow("Контрагент*:", self.counterparty_combo)
        form_layout.addRow("Адрес доставки:", self.address_combo)
        form_layout.addRow("Счёт №*:", self.invoice_no_edit)
        form_layout.addRow("Дата счёта:", self.invoice_date_edit)
        form_layout.addRow("Дата поставки:", self.delivery_date_edit)
        form_layout.addRow("Статус:", self.status_combo)
        form_layout.addRow("Комментарий:", self.comment_edit)
        main_layout.addLayout(form_layout)

        items_group = QGroupBox("Позиции заказа")
        items_layout = QVBoxLayout()
        
        items_buttons_layout = QHBoxLayout()
        add_from_warehouse_btn = QPushButton("Добавить из склада")
        add_from_warehouse_btn.clicked.connect(self.add_item_from_warehouse)
        add_manually_btn = QPushButton("Добавить вручную")
        add_manually_btn.clicked.connect(self.add_item_manually)
        remove_item_btn = QPushButton("Удалить позицию")
        remove_item_btn.clicked.connect(self.remove_selected_item)
        items_buttons_layout.addWidget(add_from_warehouse_btn)
        items_buttons_layout.addWidget(add_manually_btn)
        items_buttons_layout.addStretch()
        items_buttons_layout.addWidget(remove_item_btn)

        self.items_table_model = OrderItemsTableModel()
        self.items_table_view = QTableView()
        self.items_table_view.setModel(self.items_table_model)
        self.items_table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.items_table_view.horizontalHeader().setStretchLastSection(True)
        self.items_table_view.verticalHeader().setVisible(False)
        apply_table_compact_style(self.items_table_view)
        self.items_table_view.setEditTriggers(QAbstractItemView.DoubleClicked)
        
        items_layout.addLayout(items_buttons_layout)
        items_layout.addWidget(self.items_table_view)
        items_group.setLayout(items_layout)
        main_layout.addWidget(items_group)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def load_combobox_data(self):
        try:
            counterparties = self.db.get_all_counterparties()
            self.counterparty_combo.blockSignals(True)
            self.counterparty_combo.clear()
            self._counterparty_addresses.clear()
            for cp in counterparties:
                cp_id = cp['id']
                self.counterparty_combo.addItem(cp['name'], userData=cp_id)
                self._counterparty_addresses[cp_id] = cp.get('addresses', [])
            self.counterparty_combo.blockSignals(False)
            if self.counterparty_combo.count() > 0:
                self.counterparty_combo.setCurrentIndex(0)
            else:
                self._update_address_combo()
        except Exception as e:
            logging.error(f"Не удалось загрузить контрагентов: {e}")
        self.status_combo.addItems(['создан', 'в пути', 'принят', 'отменён'])

    def _on_counterparty_changed(self, _index=None):
        self._update_address_combo()

    def _update_address_combo(self):
        counterparty_id = self.counterparty_combo.currentData()
        addresses = self._counterparty_addresses.get(counterparty_id, [])
        selected_address = self._pending_delivery_address

        self.address_combo.blockSignals(True)
        self.address_combo.clear()

        default_index = -1
        for idx, entry in enumerate(addresses):
            address_text = entry.get('address', '')
            self.address_combo.addItem(address_text, address_text)
            if entry.get('is_default') and default_index == -1:
                default_index = idx

        if selected_address:
            index = self.address_combo.findData(selected_address)
            if index == -1 and selected_address.strip():
                self.address_combo.addItem(selected_address, selected_address)
                index = self.address_combo.findData(selected_address)
            if index >= 0:
                self.address_combo.setCurrentIndex(index)
            elif default_index >= 0:
                self.address_combo.setCurrentIndex(default_index)
        elif default_index >= 0:
            self.address_combo.setCurrentIndex(default_index)
        elif addresses:
            self.address_combo.setCurrentIndex(0)

        self.address_combo.blockSignals(False)
        self.address_combo.setEnabled(bool(addresses) or bool(self.address_combo.currentText().strip()))
        self._pending_delivery_address = None

    def load_order_data(self):
        try:
            order_data = self.db.get_order_details(self.order_id)
            if not order_data:
                QMessageBox.critical(self, "Ошибка", "Заказ не найден."); self.reject(); return

            self._pending_delivery_address = order_data.get('delivery_address')
            target_index = self.counterparty_combo.findData(order_data['counterparty_id'])
            if target_index != -1:
                self.counterparty_combo.setCurrentIndex(target_index)
            else:
                self.counterparty_combo.setCurrentIndex(0 if self.counterparty_combo.count() else -1)
                self._update_address_combo()
            self.invoice_no_edit.setText(order_data['invoice_no'])
            self.invoice_date_edit.setDate(QDate.fromString(order_data['invoice_date'], 'yyyy-MM-dd'))
            self.delivery_date_edit.setDate(QDate.fromString(order_data['delivery_date'], 'yyyy-MM-dd'))
            self.status_combo.setCurrentText(order_data['status'])
            self.comment_edit.setText(order_data['comment'] or "")
            
            raw_items = self.db.get_order_items(self.order_id)
            # [part_id, name, sku, qty, price, original_price]
            items = [[i['part_id'], i['name'], i['sku'], i['qty'], i['price'], i['price']] for i in raw_items]
            self.items_table_model.load_items(items)
        except Exception as e:
            logging.error(f"Ошибка загрузки данных заказа ID {self.order_id}: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные заказа: {e}"); self.reject()

    def add_item_from_warehouse(self):
        dialog = PartSelectionDialog(self.db, self)
        if dialog.exec():
            part = dialog.get_selected_part()
            if part:
                qty, ok = QInputDialog.getInt(self, "Количество", "Введите количество:", 1, 1, 99999)
                if ok and qty > 0:
                    item_data = [part['id'], part['name'], part['sku'], qty, part['price'], part['price']]
                    self.items_table_model.add_item(item_data)
    
    def add_item_manually(self):
        try:
            dialog = ManualPartDialog(self)
            if dialog.exec():
                part_data = dialog.get_data()
                if part_data:
                    item_data = [None, part_data['name'], part_data['sku'], part_data['qty'], part_data['price'], part_data['price']]
                    self.items_table_model.add_item(item_data)
        except Exception as e:
            logging.error(f"Ошибка при открытии диалога ручного добавления: {e}", exc_info=True)
            QMessageBox.critical(self, "Критическая ошибка", 
                                 f"Не удалось открыть диалог добавления запчасти.\n"
                                 f"Ошибка: {e}\n\n"
                                 "Проверьте лог-файл для подробностей.")

    def remove_selected_item(self):
        selected_rows = self.items_table_view.selectionModel().selectedRows()
        if selected_rows:
            self.items_table_model.remove_item(selected_rows[0].row())

    def accept(self):
        if self.validate_input():
            self.save_data()
            super().accept()

    def validate_input(self):
        if self.counterparty_combo.currentIndex() == -1:
            QMessageBox.warning(self, "Ошибка валидации", "Необходимо выбрать контрагента."); return False
        if not self.invoice_no_edit.text().strip():
            QMessageBox.warning(self, "Ошибка валидации", "Поле 'Счёт №' обязательно для заполнения."); return False
        if not self.items_table_model.get_items():
            QMessageBox.warning(self, "Ошибка валидации", "Заказ должен содержать хотя бы одну позицию."); return False
        return True

    def save_data(self):
        order_data = {
            "counterparty_id": self.counterparty_combo.currentData(),
            "invoice_no": self.invoice_no_edit.text().strip(),
            "invoice_date": qdate_to_db_string(self.invoice_date_edit.date()),
            "delivery_date": qdate_to_db_string(self.delivery_date_edit.date()),
            "delivery_address": (self.address_combo.currentData() if self.address_combo.currentData() is not None else self.address_combo.currentText()).strip(),
            "status": self.status_combo.currentText(),
            "comment": self.comment_edit.toPlainText().strip()
        }
        items_data = self.items_table_model.get_items()
        
        # Определяем, изменились ли цены
        prices_changed = any(item[4] != item[5] for item in items_data if item[0] is not None)

        if self.is_edit_mode:
            success, message = self.db.update_order_with_items(self.order_id, order_data, items_data)
        else:
            success, message = self.db.create_order_with_items(order_data, items_data)

        if success:
            QMessageBox.information(self, "Успех", message)
            self.event_bus.emit("orders.changed")
            if prices_changed:
                self.event_bus.emit("parts.changed") # Отправляем сигнал, т.к. цены могли измениться
        else:
            QMessageBox.critical(self, "Ошибка базы данных", message)

