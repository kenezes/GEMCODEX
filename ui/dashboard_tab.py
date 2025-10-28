import logging
from functools import partial
from urllib.parse import quote

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QTableWidget,
    QHeaderView,
    QAbstractItemView,
    QTableWidgetItem,
    QPushButton,
    QMessageBox,
    QMenu,
    QHBoxLayout,
    QCheckBox,
    QInputDialog,
    QLineEdit,
)
from PySide6.QtGui import QColor, QBrush, QAction, QDesktopServices, QGuiApplication
from PySide6.QtCore import Qt, QUrl

from ui.order_dialog import OrderDialog
from ui.task_dialog import TaskDialog
from ui.utils import build_driver_notification_message, db_string_to_ui_string

class DashboardTab(QWidget):
    def __init__(self, db, event_bus, main_window):
        super().__init__()
        self.db = db
        self.event_bus = event_bus
        self.main_window = main_window
        self._notified_orders: set[int] = set()
        self.init_ui()
        self.connect_events()
        self.refresh_all_tables()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Блок "Запчасти к заказу"
        parts_group = QGroupBox("Запчасти к заказу (Остаток < минимума или требуется замена)")
        parts_layout = QVBoxLayout()
        self.parts_table = self._create_parts_table()
        self.order_parts_button = QPushButton("Заказать выбранные")
        self.order_parts_button.clicked.connect(self.order_selected_parts)
        parts_layout.addWidget(self.parts_table)
        parts_layout.addWidget(self.order_parts_button, alignment=Qt.AlignRight)
        parts_group.setLayout(parts_layout)

        # Блок "Активные задачи"
        tasks_group = QGroupBox("Активные задачи")
        tasks_layout = QVBoxLayout()
        self.tasks_table = self._create_tasks_table()
        self.tasks_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tasks_table.customContextMenuRequested.connect(self.show_tasks_context_menu)
        self.tasks_table.cellDoubleClicked.connect(self.open_task_from_dashboard)
        tasks_layout.addWidget(self.tasks_table)
        tasks_group.setLayout(tasks_layout)

        periodic_group = QGroupBox("Периодические задачи (до выполнения ≤ 7 дней)")
        periodic_layout = QVBoxLayout()
        self.periodic_table = self._create_periodic_table()
        periodic_layout.addWidget(self.periodic_table)
        periodic_group.setLayout(periodic_layout)
        periodic_group.setVisible(False)
        self.periodic_group = periodic_group

        # Блок "Заказы в пути"
        orders_group = QGroupBox("Заказы в пути")
        orders_layout = QVBoxLayout()
        self.orders_table = self._create_orders_table()
        self.orders_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.orders_table.customContextMenuRequested.connect(self.show_orders_context_menu)
        self.orders_table.cellDoubleClicked.connect(self.open_order_from_dashboard)
        orders_layout.addWidget(self.orders_table)
        orders_group.setLayout(orders_layout)

        main_layout.addWidget(parts_group, 1)
        main_layout.addWidget(tasks_group, 1)
        main_layout.addWidget(self.periodic_group, 1)
        main_layout.addWidget(orders_group, 1)

    def _create_parts_table(self):
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Наименование", "Артикул", "Ост.", "Мин.", "Цена", "К заказу"])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        return table

    def _create_tasks_table(self):
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            "Задача",
            "Оборудование",
            "Исполнитель",
            "Срок",
            "Статус",
            "Приоритет",
            "Комментарий",
            "",
        ])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        return table

    def _create_orders_table(self):
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels([
            "Контрагент",
            "Счёт №",
            "Дата счёта",
            "Дата поставки",
            "Статус",
            "Комментарий",
            "",
        ])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        return table

    def _create_periodic_table(self):
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels([
            "Работа",
            "Объект",
            "Период (дн.)",
            "Последняя дата",
            "След. дата",
            "Осталось",
            "",
        ])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        return table

    def connect_events(self):
        self.event_bus.subscribe("parts.changed", self.refresh_parts_table)
        self.event_bus.subscribe("orders.changed", self.refresh_orders_table)
        self.event_bus.subscribe("tasks.changed", self.refresh_tasks_table)
        self.event_bus.subscribe("periodic_tasks.changed", self.refresh_periodic_tasks_table)
        self.event_bus.subscribe(
            "orders.driver_notification_changed",
            self._on_driver_notification_changed,
        )

    def refresh_all_tables(self):
        self.refresh_parts_table()
        self.refresh_tasks_table()
        self.refresh_periodic_tasks_table()
        self.refresh_orders_table()

    def refresh_parts_table(self):
        self.parts_table.setRowCount(0)
        parts = self.db.get_parts_to_order()
        for row, part in enumerate(parts):
            self.parts_table.insertRow(row)

            name_item = QTableWidgetItem(part['name'])
            name_item.setData(Qt.UserRole, part['id'])
            self.parts_table.setItem(row, 0, name_item)

            self.parts_table.setItem(row, 1, QTableWidgetItem(part['sku']))
            self.parts_table.setItem(row, 2, QTableWidgetItem(str(part['qty'])))
            self.parts_table.setItem(row, 3, QTableWidgetItem(str(part['min_qty'])))
            self.parts_table.setItem(row, 4, QTableWidgetItem(f"{part['price']:.2f}"))

            requires_flag = bool(part.get('requires_replacement_flag'))
            base_to_order_qty = max(part['min_qty'] - part['qty'], 0)
            to_order_qty = max(base_to_order_qty, 1) if requires_flag else base_to_order_qty
            to_order_item = QTableWidgetItem(str(to_order_qty))
            if requires_flag:
                note = (
                    "Запчасть помечена как требующая замены, но на складе отсутствует. "
                    "Рекомендуется добавить в заказ."
                )
                name_item.setToolTip(note)
                to_order_item.setToolTip(note)
                to_order_item.setBackground(QColor("#FFF3CD"))
                for col in range(self.parts_table.columnCount()):
                    item = self.parts_table.item(row, col)
                    if item:
                        item.setBackground(QColor("#FFF3CD"))
            elif to_order_qty <= 0:
                to_order_item.setBackground(QColor("#ffcccb"))
            self.parts_table.setItem(row, 5, to_order_item)

    def refresh_tasks_table(self):
        self.tasks_table.setRowCount(0)
        tasks = self.db.get_active_tasks()
        priority_colors = {"высокий": QColor("#FFCCCC"), "средний": QColor("#FFE5CC"), "низкий": QColor("#FFFFCC")}
        for row, task in enumerate(tasks):
            self.tasks_table.insertRow(row)

            title_text = task['title']
            if task.get('is_replacement'):
                title_text = f"[Замена] {title_text}"

            title_item = QTableWidgetItem(title_text)
            title_item.setData(Qt.UserRole, task['id'])
            self.tasks_table.setItem(row, 0, title_item)
            
            self.tasks_table.setItem(row, 1, QTableWidgetItem(task.get('equipment_name', '')))
            self.tasks_table.setItem(row, 2, QTableWidgetItem(task.get('assignee_name', '')))
            self.tasks_table.setItem(row, 3, QTableWidgetItem(db_string_to_ui_string(task.get('due_date'))))
            self.tasks_table.setItem(row, 4, QTableWidgetItem(task['status']))
            self.tasks_table.setItem(row, 5, QTableWidgetItem(task['priority']))
            self.tasks_table.setItem(row, 6, QTableWidgetItem(task.get('description', '')))

            color = priority_colors.get(task['priority'])
            if color:
                for col in range(self.tasks_table.columnCount() - 1):
                    item = self.tasks_table.item(row, col)
                    if item:
                        item.setBackground(QBrush(color))

            self.tasks_table.setCellWidget(row, 7, self._build_task_actions_widget(task))

    def _build_task_actions_widget(self, task: dict) -> QWidget:
        task_id = task.get('id')
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        actions = [
            ("Выполнить", lambda: self.change_task_status(task_id, 'выполнена'), "#2e7d32"),
            ("Отменить", lambda: self.change_task_status(task_id, 'отменена'), "#c62828"),
            ("Стоп", lambda: self.change_task_status(task_id, 'на стопе'), "#f9a825"),
        ]

        for text, handler, color in actions:
            button = self._create_small_button(text, color)
            if task_id is not None:
                button.clicked.connect(handler)
            else:
                button.setEnabled(False)
            layout.addWidget(button)

        layout.addStretch()
        return widget

    def _build_periodic_actions_widget(self, task: dict) -> QWidget:
        task_id = task.get('id')
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        actions = [
            ("Выполнить", 'complete', "#2e7d32"),
            ("Отменить", 'cancel', "#c62828"),
            ("Стоп", 'pause', "#f9a825"),
        ]

        for text, action, color in actions:
            button = self._create_small_button(text, color)
            if task_id is not None:
                button.clicked.connect(lambda _, t_id=task_id, act=action: self._handle_periodic_action(t_id, act))
            else:
                button.setEnabled(False)
            layout.addWidget(button)

        layout.addStretch()
        return widget

    def _handle_periodic_action(self, task_id: int, action: str):
        if not task_id:
            return

        action_map = {
            'complete': self.db.complete_periodic_task,
            'cancel': self.db.cancel_periodic_task,
            'pause': self.db.pause_periodic_task,
        }

        handler = action_map.get(action)
        if not handler:
            logging.warning("Неизвестное действие для периодической работы: %s", action)
            return

        success, message, _ = handler(task_id)
        if success:
            QMessageBox.information(self, "Периодическая работа", message)
            self.event_bus.emit("periodic_tasks.changed")
        else:
            QMessageBox.warning(self, "Периодическая работа", message)

    @staticmethod
    def _create_small_button(text: str, background: str | None = None, *, text_color: str = "#ffffff") -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedHeight(26)
        base_style = [
            "QPushButton {",
            "padding: 4px 8px;",
            "border-radius: 4px;",
            "font-size: 12px;",
        ]

        if background:
            base_style.append(f"background-color: {background};")
            base_style.append(f"color: {text_color};")
            base_style.append("border: none;")
        else:
            base_style.append("background-color: #e0e0e0;")
            base_style.append("color: #000000;")
            base_style.append("border: 1px solid #bdbdbd;")

        base_style.append("}\n")
        base_style.append("QPushButton:disabled { background-color: #f0f0f0; color: #9e9e9e; }")
        button.setStyleSheet("".join(base_style))
        return button

    def _build_order_actions_widget(self, order: dict) -> QWidget:
        order_id = order.get('id')
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        accept_button = self._create_small_button("Принять", "#2e7d32")
        accept_button.setToolTip("Принять поставку")
        if order_id is not None:
            accept_button.clicked.connect(lambda _, o_id=order_id: self._accept_order_from_dashboard(o_id))
        else:
            accept_button.setEnabled(False)
        layout.addWidget(accept_button)

        invoice_button = self._create_small_button("Счёт")
        invoice_button.setToolTip("Отметить заказ как отправленный")
        self._update_invoice_button_style(invoice_button, order.get('status'))
        if order_id is not None:
            invoice_button.clicked.connect(
                lambda _, o_id=order_id, btn=invoice_button: self._mark_order_in_transit(o_id, btn)
            )
        else:
            invoice_button.setEnabled(False)
        layout.addWidget(invoice_button)

        checkbox = QCheckBox("Сообщить водителю")
        checkbox.setToolTip("Водитель уведомлён")
        is_notified = bool(order.get('driver_notified'))
        if order_id is not None and order_id in self._notified_orders:
            is_notified = True
        checkbox.setChecked(is_notified)
        if order_id is not None:
            checkbox.stateChanged.connect(
                lambda state, o_id=order_id: self._set_order_notified(o_id, state == Qt.Checked)
            )
        else:
            checkbox.setEnabled(False)
        layout.addWidget(checkbox)
        widget.setProperty("notify_checkbox", checkbox)

        phone_button = self._create_small_button("📞", "#0277bd")
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

    def _accept_order_from_dashboard(self, order_id: int):
        self.change_order_status(order_id, 'принят')

    def _mark_order_in_transit(self, order_id: int, button: QPushButton):
        if self.change_order_status(order_id, 'в пути'):
            self._update_invoice_button_style(button, 'в пути')

    def _update_order_checkbox(self, order_id: int, checked: bool):
        for row in range(self.orders_table.rowCount()):
            item = self.orders_table.item(row, 0)
            if not item or item.data(Qt.UserRole) != order_id:
                continue
            widget = self.orders_table.cellWidget(row, 6)
            if widget:
                checkbox = widget.property("notify_checkbox")
                if isinstance(checkbox, QCheckBox):
                    checkbox.blockSignals(True)
                    checkbox.setChecked(checked)
                    checkbox.blockSignals(False)
            break

    def _remember_driver_phone(self, digits_only: str):
        if not self.db.set_driver_phone(digits_only):
            logging.warning("Dashboard: не удалось сохранить номер водителя.")
            return

        orders_tab = getattr(self.main_window, 'orders_tab', None)
        driver_input = getattr(orders_tab, 'driver_phone_input', None) if orders_tab else None
        if driver_input:
            driver_input.blockSignals(True)
            driver_input.setText(digits_only)
            driver_input.blockSignals(False)

    def _set_order_notified(self, order_id: int, notified: bool):
        was_notified = order_id in self._notified_orders
        success, message = self.db.set_order_driver_notified(order_id, notified)
        if not success:
            logging.warning("Dashboard: не удалось обновить отметку для заказа %s: %s", order_id, message)
            self._update_order_checkbox(order_id, was_notified)
            if message:
                QMessageBox.warning(self, "Сообщение водителю", message)
            else:
                QMessageBox.warning(
                    self,
                    "Сообщение водителю",
                    "Не удалось сохранить отметку об уведомлении водителя.",
                )
            return

        if notified:
            self._notified_orders.add(order_id)
        else:
            self._notified_orders.discard(order_id)

        self.event_bus.emit("orders.driver_notification_changed", order_id, notified)

    def _send_order_to_driver(self, order: dict):
        phone_number = self._request_driver_phone()
        if not phone_number:
            return

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
        url = QUrl(f"https://wa.me/{phone_number}?text={quote(message, safe='')}")
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(self, "Отправка сообщения", "Не удалось открыть WhatsApp.")

        order_id = order.get('id')
        if order_id is not None:
            self._set_order_notified(order_id, True)

    def _on_driver_notification_changed(self, order_id: int, notified: bool):
        if notified:
            self._notified_orders.add(order_id)
        else:
            self._notified_orders.discard(order_id)
        self._update_order_checkbox(order_id, notified)

    def _request_driver_phone(self) -> str:
        default_value = self.db.get_driver_phone()
        orders_tab = getattr(self.main_window, 'orders_tab', None)
        driver_input = getattr(orders_tab, 'driver_phone_input', None) if orders_tab else None
        if not default_value and driver_input:
            default_value = driver_input.text()

        text, ok = QInputDialog.getText(
            self,
            "Номер водителя",
            "Укажите номер телефона водителя:",
            QLineEdit.Normal,
            default_value,
        )

        if not ok:
            return ""

        digits_only = ''.join(ch for ch in text if ch.isdigit())
        if not digits_only:
            QMessageBox.warning(self, "Номер водителя", "Номер телефона не указан.")
            return ""

        if len(digits_only) == 11 and digits_only.startswith('8'):
            digits_only = '7' + digits_only[1:]

        if len(digits_only) < 11:
            QMessageBox.warning(self, "Номер водителя", "Укажите номер в формате 79XXXXXXXXX.")
            return ""

        self._remember_driver_phone(digits_only)
        return digits_only

    def open_task_from_dashboard(self, row: int, column: int):
        item = self.tasks_table.item(row, 0)
        if not item:
            return
        task_id = item.data(Qt.UserRole)
        if not task_id:
            return

        dialog = TaskDialog(self.db, self.event_bus, task_id=task_id, parent=self.main_window)
        dialog.exec()

    def open_order_from_dashboard(self, row: int, column: int):
        item = self.orders_table.item(row, 0)
        if not item:
            return
        order_id = item.data(Qt.UserRole)
        if not order_id:
            return

        dialog = OrderDialog(self.db, self.event_bus, order_id=order_id, parent=self.main_window)
        dialog.exec()

    def refresh_orders_table(self):
        self.orders_table.setRowCount(0)
        orders = self.db.get_active_orders()
        self._notified_orders = {
            order['id']
            for order in orders
            if order.get('id') is not None and order.get('driver_notified')
        }
        for row, order in enumerate(orders):
            self.orders_table.insertRow(row)

            cp_item = QTableWidgetItem(order['counterparty_name'])
            cp_item.setData(Qt.UserRole, order['id'])
            self.orders_table.setItem(row, 0, cp_item)

            self.orders_table.setItem(row, 1, QTableWidgetItem(order.get('invoice_no', '')))
            self.orders_table.setItem(row, 2, QTableWidgetItem(db_string_to_ui_string(order.get('invoice_date'))))
            self.orders_table.setItem(row, 3, QTableWidgetItem(db_string_to_ui_string(order.get('delivery_date'))))
            self.orders_table.setItem(row, 4, QTableWidgetItem(order['status']))
            self.orders_table.setItem(row, 5, QTableWidgetItem(order.get('comment', '')))

            self.orders_table.setCellWidget(row, 6, self._build_order_actions_widget(order))

    def refresh_periodic_tasks_table(self):
        tasks = self.db.get_due_periodic_tasks()
        self.periodic_group.setVisible(bool(tasks))
        table = self.periodic_table
        table.setRowCount(0)

        for row, task in enumerate(tasks):
            table.insertRow(row)

            title = task.get('title') or ""
            subject = self._format_periodic_subject(task)
            period_days = str(task.get('period_days') or "")
            last_date = db_string_to_ui_string(task.get('last_completed_date'))
            next_due = db_string_to_ui_string(task.get('next_due_date'))
            days_text = self._format_days_until_due(task.get('days_until_due'))

            values = [title, subject, period_days, last_date, next_due, days_text]

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, task.get('id'))
                table.setItem(row, col, item)

            days_until = task.get('days_until_due')
            color = None
            if days_until is not None:
                if days_until < 0:
                    color = QColor("#ffcdd2")
                elif days_until <= 3:
                    color = QColor("#fff3cd")

            if color:
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    if item:
                        item.setBackground(QBrush(color))

            table.setCellWidget(row, 6, self._build_periodic_actions_widget(task))

        table.resizeColumnsToContents()

    @staticmethod
    def _format_periodic_subject(task: dict) -> str:
        equipment_name = task.get('equipment_name') or ""
        part_name = task.get('part_name')
        part_sku = task.get('part_sku')

        if part_name:
            part_display = part_name
            if part_sku:
                part_display = f"{part_display} ({part_sku})"
            if equipment_name:
                return f"{equipment_name} → {part_display}"
            return part_display

        return equipment_name or "—"

    @staticmethod
    def _format_days_until_due(days_until_due):
        if days_until_due is None:
            return "—"
        if days_until_due < 0:
            return f"Просрочено на {abs(days_until_due)} дн."
        if days_until_due == 0:
            return "Сегодня"
        return f"{days_until_due} дн."

    def order_selected_parts(self):
        selected_rows = sorted(list(set(item.row() for item in self.parts_table.selectedItems())))
        if not selected_rows:
            QMessageBox.warning(self, "Внимание", "Выберите запчасти для создания заказа.")
            return
            
        initial_items = []
        for row in selected_rows:
            part_item = self.parts_table.item(row, 0)
            part_id = part_item.data(Qt.UserRole) if part_item else None
            if not part_id:
                continue

            part = self.db.get_part_by_id(part_id)
            table_qty_item = self.parts_table.item(row, 5)
            try:
                to_order_qty = int(table_qty_item.text()) if table_qty_item else 0
            except (TypeError, ValueError):
                to_order_qty = 0

            if to_order_qty <= 0:
                calculated_default = max(part['min_qty'] - part['qty'], 0)
                if calculated_default <= 0:
                    reply = QMessageBox.warning(
                        self,
                        "Внимание",
                        f"Запчасть '{part['name']}' не требует заказа.\nВсе равно добавить в заказ?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    if reply == QMessageBox.No:
                        continue
                    to_order_qty = 1
                else:
                    to_order_qty = calculated_default

            initial_items.append({
                'part_id': part['id'],
                'name': part['name'],
                'sku': part['sku'],
                'qty': to_order_qty if to_order_qty > 0 else 1,
                'price': part['price'],
            })

        if not initial_items: return
        order_dialog = OrderDialog(self.db, self.event_bus, parent=self.main_window, initial_items=initial_items)
        order_dialog.exec()

    def show_tasks_context_menu(self, position):
        row = self.tasks_table.rowAt(position.y())
        if row < 0: return

        task_id = self.tasks_table.item(row, 0).data(Qt.UserRole)
        menu = QMenu()
        status_menu = menu.addMenu("Изменить статус")
        
        statuses = ['в работе', 'выполнена', 'отменена', 'на стопе']
        for status in statuses:
            action = status_menu.addAction(status)
            action.triggered.connect(partial(self.change_task_status, task_id, status))
            
        menu.exec(self.tasks_table.viewport().mapToGlobal(position))

    def change_task_status(self, task_id, new_status):
        success, message, events = self.db.update_task_status(task_id, new_status)
        if success:
            self._handle_task_events(events)
            self.event_bus.emit("tasks.changed")
        else:
            QMessageBox.critical(self, "Ошибка", message)

    def _handle_task_events(self, events: dict):
        equipment_ids = set(events.get('equipment_ids', []))
        for equipment_id in equipment_ids:
            self.event_bus.emit("equipment_parts_changed", equipment_id)

        if events.get('parts_changed'):
            self.event_bus.emit("parts.changed")
        if events.get('replacements_changed'):
            self.event_bus.emit("replacements.changed")

    def show_orders_context_menu(self, position):
        row = self.orders_table.rowAt(position.y())
        if row < 0: return

        order_id = self.orders_table.item(row, 0).data(Qt.UserRole)
        menu = QMenu(self)
        status_menu = menu.addMenu("Изменить статус")
        
        statuses = ['создан', 'в пути', 'принят', 'отменён']
        for status in statuses:
            action = status_menu.addAction(status)
            action.triggered.connect(partial(self.change_order_status, order_id, status))

        menu.addSeparator()
        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(partial(self.delete_order_from_dashboard, order_id))
        menu.addAction(delete_action)
            
        menu.exec(self.orders_table.viewport().mapToGlobal(position))

    def change_order_status(self, order_id, new_status):
        # Особый случай для приемки
        if new_status == 'принят':
            reply = QMessageBox.question(self, "Подтверждение",
                                       "Приемка поставки пополнит остатки на складе. Продолжить?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No:
                return False
            success, message = self.db.accept_delivery(order_id)
        else:
            success, message = self.db.update_order_status(order_id, new_status)

        if success:
            self.event_bus.emit("orders.changed")
            if new_status == 'принят':
                self.event_bus.emit("parts.changed")
            return True
        else:
            QMessageBox.critical(self, "Ошибка", message)
        return False

    def delete_order_from_dashboard(self, order_id):
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

