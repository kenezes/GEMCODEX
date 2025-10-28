import logging
from urllib.parse import quote
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QToolBar, QTableView, QAbstractItemView,
                             QHeaderView, QMessageBox, QCheckBox, QHBoxLayout, QMenu, QPushButton, QSizePolicy,
                             QLabel, QLineEdit)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QGuiApplication

from .order_dialog import OrderDialog
from ui.utils import (
    apply_table_compact_style,
    build_driver_notification_message,
    db_string_to_ui_string,
)


class OrdersTableModel(QAbstractTableModel):
    """Модель данных для таблицы заказов."""

    COUNTERPARTY_COLUMN = 0
    STATUS_COLUMN = 6
    ACTION_COLUMN = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = [
            "Контрагент",
            "Счёт №",
            "Дата счёта",
            "Дата поставки",
            "Дата создания",
            "Адрес доставки",
            "Статус",
            "Комментарий",
            "",
        ]
        self._data = []
        self._notified_orders: set[int] = set()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row_data = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0: return row_data['counterparty_name']
            if col == 1: return f"{row_data.get('invoice_no', '')}"
            if col == 2: return db_string_to_ui_string(row_data.get('invoice_date'))
            if col == 3: return db_string_to_ui_string(row_data.get('delivery_date'))
            if col == 4: return db_string_to_ui_string(row_data.get('created_at', '').split(' ')[0]) # Только дата
            if col == 5: return row_data.get('delivery_address') or row_data.get('counterparty_address', '')
            if col == 6: return row_data['status']
            if col == 7: return row_data.get('comment', '')

        if role == Qt.TextAlignmentRole and col == self.ACTION_COLUMN:
            return Qt.AlignCenter

        if role == Qt.UserRole:
            return row_data['id']

        if role == Qt.UserRole + 1:
            return row_data

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        if index.column() == self.ACTION_COLUMN:
            return Qt.ItemIsEnabled
        return super().flags(index)

    def load_data(self, data):
        self.beginResetModel()
        self._data = data
        notified_ids = {
            row.get('id')
            for row in data
            if row.get('id') is not None and row.get('driver_notified')
        }
        self._notified_orders = set(notified_ids)
        self.endResetModel()

    def get_row(self, row_index: int) -> dict | None:
        if 0 <= row_index < len(self._data):
            return self._data[row_index]
        return None

    def set_notified(self, order_id: int, notified: bool):
        if order_id is None:
            return
        if notified:
            self._notified_orders.add(order_id)
        else:
            self._notified_orders.discard(order_id)
        for row in self._data:
            if row.get('id') == order_id:
                row['driver_notified'] = 1 if notified else 0
                break

    def is_notified(self, order_id: int) -> bool:
        return order_id in self._notified_orders

class OrdersFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hide_completed = False

    def set_hide_completed(self, hide):
        self._hide_completed = hide
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._hide_completed:
            return True

        index = self.sourceModel().index(source_row, OrdersTableModel.STATUS_COLUMN, source_parent)
        status = self.sourceModel().data(index) or ""
        normalized = str(status).strip().lower().replace('ё', 'е')
        return not any(keyword in normalized for keyword in ("принят", "отменен"))

class OrdersTab(QWidget):
    """Вкладка для управления заказами."""
    def __init__(self, db, event_bus, main_window):
        super().__init__()
        self.db = db
        self.event_bus = event_bus
        self.main_window = main_window
        self._action_widgets: dict[int, QWidget] = {}

        self.init_ui()
        self.event_bus.subscribe("orders.changed", self.refresh_data)
        self.event_bus.subscribe("counterparties.changed", self.refresh_data) # На случай переименования
        self.event_bus.subscribe("orders.driver_notification_changed", self._on_driver_notification_changed)
        self.refresh_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._setup_toolbar()
        self._setup_table()
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.table_view)

    def _setup_toolbar(self):
        self.toolbar = QToolBar()
        
        self.new_order_button = QPushButton("Новый заказ")
        self.delete_order_button = QPushButton("Удалить")
        self.refresh_button = QPushButton("Обновить")
        
        self.hide_completed_checkbox = QCheckBox("Скрыть завершенные")
        
        self.toolbar.addWidget(self.new_order_button)
        self.toolbar.addWidget(self.delete_order_button)
        self.toolbar.addSeparator()

        driver_layout = QHBoxLayout()
        driver_layout.setContentsMargins(0, 0, 0, 0)
        driver_layout.setSpacing(6)

        driver_container = QWidget()
        driver_container.setLayout(driver_layout)

        driver_label = QLabel("Номер водителя:")
        self.driver_phone_input = QLineEdit()
        self.driver_phone_input.setPlaceholderText("Например, 79991234567")
        self.driver_phone_input.setMaximumWidth(180)
        self.driver_phone_input.setClearButtonEnabled(True)
        self.driver_phone_input.editingFinished.connect(self._persist_driver_phone)
        self._load_driver_phone()

        driver_layout.addWidget(driver_label)
        driver_layout.addWidget(self.driver_phone_input)

        self.toolbar.addWidget(driver_container)
        self.toolbar.addSeparator()

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        spacer.setFixedWidth(20)
        self.toolbar.addWidget(spacer)
        
        self.toolbar.addWidget(self.hide_completed_checkbox)
        
        widget = QWidget() # Spacer
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(widget)
        
        self.toolbar.addWidget(self.refresh_button)

        self.new_order_button.clicked.connect(self.create_new_order)
        self.delete_order_button.clicked.connect(self.delete_selected_order)
        self.refresh_button.clicked.connect(self.refresh_data)
        self.hide_completed_checkbox.stateChanged.connect(self.toggle_hide_completed)

    def _setup_table(self):
        self.base_model = OrdersTableModel()
        self.proxy_model = OrdersFilterProxyModel()
        self.proxy_model.setSourceModel(self.base_model)

        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSortingEnabled(True)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._create_context_menu)
        self.table_view.doubleClicked.connect(self.edit_selected_order)
        self.table_view.verticalHeader().setVisible(False)

        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(OrdersTableModel.ACTION_COLUMN, QHeaderView.Fixed)
        header.setStretchLastSection(False)

        apply_table_compact_style(self.table_view)
        self.table_view.setColumnWidth(OrdersTableModel.ACTION_COLUMN, 320)

        self.proxy_model.layoutChanged.connect(self._populate_action_widgets)
        self.proxy_model.modelReset.connect(self._populate_action_widgets)

    def refresh_data(self):
        logging.info("Обновление данных на вкладке 'Заказы'")
        orders_data = self.db.get_all_orders_with_counterparty()
        self.base_model.load_data(orders_data)
        self._populate_action_widgets()

    def _normalize_driver_phone(self, text: str) -> str:
        digits_only = ''.join(ch for ch in text if ch.isdigit())
        if len(digits_only) == 11 and digits_only.startswith('8'):
            digits_only = '7' + digits_only[1:]
        return digits_only

    def _load_driver_phone(self):
        saved_phone = self.db.get_driver_phone()
        if saved_phone:
            self.driver_phone_input.setText(saved_phone)

    def _persist_driver_phone(self):
        digits_only = self._normalize_driver_phone(self.driver_phone_input.text())
        if digits_only:
            self.driver_phone_input.setText(digits_only)
        else:
            self.driver_phone_input.clear()
        if not self.db.set_driver_phone(digits_only):
            logging.warning("Не удалось сохранить номер водителя.")

    def _store_driver_phone(self, digits_only: str):
        if digits_only:
            self.driver_phone_input.setText(digits_only)
        else:
            self.driver_phone_input.clear()
        if not self.db.set_driver_phone(digits_only):
            logging.warning("Не удалось сохранить номер водителя.")

    def _update_checkbox_state(self, order_id: int, checked: bool):
        widget = self._action_widgets.get(order_id)
        if not widget:
            return
        checkbox = widget.property("notify_checkbox")
        if isinstance(checkbox, QCheckBox):
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)

    def toggle_hide_completed(self, state):
        self.proxy_model.set_hide_completed(state == Qt.Checked)

    def create_new_order(self):
        dialog = OrderDialog(self.db, self.event_bus, parent=self.main_window)
        dialog.exec()

    def get_selected_order_id(self):
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if selected_indexes:
            proxy_index = selected_indexes[0]
            source_index = self.proxy_model.mapToSource(proxy_index)
            return self.base_model.data(source_index, Qt.UserRole)
        return None

    def edit_selected_order(self):
        order_id = self.get_selected_order_id()
        if order_id:
            dialog = OrderDialog(self.db, self.event_bus, order_id=order_id, parent=self.main_window)
            dialog.exec()
        else:
            QMessageBox.information(self, "Информация", "Выберите заказ для редактирования.")
            
    def delete_selected_order(self):
        order_id = self.get_selected_order_id()
        if not order_id:
            QMessageBox.warning(self, "Внимание", "Выберите заказ для удаления.")
            return

        reply = QMessageBox.question(self, "Подтверждение удаления",
                                     "Вы уверены, что хотите удалить этот заказ? Это действие необратимо.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            success, message = self.db.delete_order(order_id)
            if success:
                QMessageBox.information(self, "Успех", "Заказ успешно удален.")
                self.event_bus.emit("orders.changed")
            else:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить заказ: {message}")


    def accept_delivery_for_selected(self):
        order_id = self.get_selected_order_id()
        if order_id:
            self._accept_order(order_id)
        else:
            QMessageBox.information(self, "Информация", "Выберите заказ для приемки.")

    def _create_context_menu(self, position):
        menu = QMenu()
        edit_action = QAction("Редактировать", self)
        delete_action = QAction("Удалить", self) # Новый пункт
        accept_action = QAction("Принять поставку", self)
        
        edit_action.triggered.connect(self.edit_selected_order)
        delete_action.triggered.connect(self.delete_selected_order) # Подключаем
        accept_action.triggered.connect(self.accept_delivery_for_selected)
        
        menu.addAction(edit_action)
        menu.addAction(delete_action) # Добавляем
        menu.addSeparator()
        menu.addAction(accept_action)

        menu.exec(self.table_view.viewport().mapToGlobal(position))

    def _populate_action_widgets(self):
        for widget in self._action_widgets.values():
            if widget:
                widget.deleteLater()
        self._action_widgets.clear()

        for row in range(self.proxy_model.rowCount()):
            proxy_index = self.proxy_model.index(row, OrdersTableModel.ACTION_COLUMN)
            if not proxy_index.isValid():
                continue
            source_index = self.proxy_model.mapToSource(proxy_index)
            order = self.base_model.get_row(source_index.row())
            if not order:
                continue

            widget = self._create_order_actions_widget(order)
            self.table_view.setIndexWidget(proxy_index, widget)
            order_id = order.get('id')
            if order_id is not None:
                self._action_widgets[order_id] = widget

    def _create_order_actions_widget(self, order: dict) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        order_id = order.get('id')

        accept_button = self._create_action_button("Принять", "#2e7d32")
        accept_button.setToolTip("Принять поставку")
        if order_id is not None:
            accept_button.clicked.connect(lambda _, oid=order_id: self._accept_order(oid))
        else:
            accept_button.setEnabled(False)
        layout.addWidget(accept_button)

        invoice_button = self._create_action_button("Счёт")
        invoice_button.setToolTip("Отметить заказ как отправленный")
        self._update_invoice_button_style(invoice_button, order.get('status'))
        if order_id is not None:
            invoice_button.clicked.connect(
                lambda _, oid=order_id, btn=invoice_button: self._mark_order_in_transit(oid, btn)
            )
        else:
            invoice_button.setEnabled(False)
        layout.addWidget(invoice_button)

        notify_checkbox = QCheckBox("Сообщить водителю")
        notify_checkbox.setToolTip("Водитель уведомлён")
        if order_id is not None:
            notify_checkbox.setChecked(self.base_model.is_notified(order_id))
            notify_checkbox.stateChanged.connect(
                lambda state, oid=order_id: self._set_order_notified(oid, state == Qt.Checked)
            )
        else:
            notify_checkbox.setEnabled(False)
        layout.addWidget(notify_checkbox)
        widget.setProperty("notify_checkbox", notify_checkbox)

        phone_button = self._create_action_button("📞", "#0277bd")
        phone_button.setToolTip("Отправить данные водителю")
        if order_id is not None:
            phone_button.clicked.connect(
                lambda _, data=order: self._send_order_to_driver(data)
            )
        else:
            phone_button.setEnabled(False)
        layout.addWidget(phone_button)

        layout.addStretch()
        return widget

    @staticmethod
    def _create_action_button(text: str, background: str | None = None) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedHeight(26)
        styles = [
            "QPushButton {",
            "padding: 4px 8px;",
            "border-radius: 4px;",
            "font-size: 12px;",
        ]
        if background:
            styles.append(f"background-color: {background};")
            styles.append("color: #ffffff;")
            styles.append("border: none;")
        else:
            styles.append("background-color: #e0e0e0;")
            styles.append("color: #000000;")
            styles.append("border: 1px solid #bdbdbd;")
        styles.append("}\n")
        styles.append("QPushButton:disabled { background-color: #f0f0f0; color: #9e9e9e; }")
        button.setStyleSheet("".join(styles))
        return button

    @staticmethod
    def _update_invoice_button_style(button: QPushButton, status: str | None):
        if status in {"в пути", "принят"}:
            button.setStyleSheet(
                """
                QPushButton {
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    background-color: #2e7d32;
                    color: #ffffff;
                    border: none;
                }
                QPushButton:disabled {
                    background-color: #a5d6a7;
                    color: #f5f5f5;
                }
                """
            )
        else:
            button.setStyleSheet(
                """
                QPushButton {
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    background-color: #c62828;
                    color: #ffffff;
                    border: none;
                }
                QPushButton:disabled {
                    background-color: #ef9a9a;
                    color: #fbe9e7;
                }
                """
            )

    def _set_order_notified(self, order_id: int, notified: bool):
        previous_state = self.base_model.is_notified(order_id)
        success, message = self.db.set_order_driver_notified(order_id, notified)
        if not success:
            logging.warning("Не удалось обновить отметку об уведомлении водителя: %s", message)
            self._update_checkbox_state(order_id, previous_state)
            if message:
                QMessageBox.warning(self, "Сообщение водителю", message)
            else:
                QMessageBox.warning(
                    self,
                    "Сообщение водителю",
                    "Не удалось сохранить отметку об уведомлении водителя.",
                )
            return

        self.base_model.set_notified(order_id, notified)
        self.event_bus.emit("orders.driver_notification_changed", order_id, notified)

    def _on_driver_notification_changed(self, order_id: int, notified: bool):
        self.base_model.set_notified(order_id, notified)
        self._update_checkbox_state(order_id, notified)

    def _mark_order_in_transit(self, order_id: int, button: QPushButton):
        success, message = self.db.update_order_status(order_id, 'в пути')
        if success:
            self.event_bus.emit("orders.changed")
            self._update_invoice_button_style(button, 'в пути')
        else:
            QMessageBox.warning(self, "Статус заказа", message)

    def _accept_order(self, order_id: int):
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Принять поставку по этому заказу? Остатки на складе будут увеличены.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.No:
            return

        success, message = self.db.accept_delivery(order_id)
        if success:
            QMessageBox.information(self, "Поставка", message)
            self.event_bus.emit("orders.changed")
            self.event_bus.emit("parts.changed")
        else:
            QMessageBox.warning(self, "Поставка", message)

    def _send_order_to_driver(self, order: dict):
        driver_number_raw = self.driver_phone_input.text().strip()
        digits_only = self._normalize_driver_phone(driver_number_raw)
        if not digits_only:
            QMessageBox.warning(self, "Номер водителя", "Укажите номер водителя, чтобы отправить сообщение.")
            return
        if len(digits_only) < 11:
            QMessageBox.warning(self, "Номер водителя", "Неверный формат номера. Используйте 79XXXXXXXXX.")
            return

        self._store_driver_phone(digits_only)

        order_payload = dict(order)
        order_id = order_payload.get('id')
        if order_id is not None:
            details = self.db.get_order_with_details(order_id)
            if details:
                order_payload.update(details)
                if (not order_payload.get('delivery_address')
                        and details.get('counterparty_id')):
                    counterparty = self.db.get_counterparty_by_id(details['counterparty_id'])
                    if counterparty:
                        default_address = counterparty.get('default_address') or counterparty.get('address')
                        if default_address:
                            order_payload['delivery_address'] = default_address
                        if counterparty.get('address'):
                            order_payload.setdefault('counterparty_address', counterparty['address'])

        message = build_driver_notification_message(order_payload)

        QGuiApplication.clipboard().setText(message)
        logging.info("Скопировано сообщение по заказу #%s для отправки водителю", order.get('id'))

        url = QUrl(f"https://wa.me/{digits_only}?text={quote(message, safe='')}")
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(self, "Открытие WhatsApp", "Не удалось открыть чат WhatsApp.")

        order_id = order.get('id')
        if order_id is not None:
            self._set_order_notified(order_id, True)

