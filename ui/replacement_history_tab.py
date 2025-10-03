from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableView,
    QHeaderView,
    QAbstractItemView,
    QDateEdit,
    QComboBox,
    QPushButton,
    QMessageBox,
    QMenu,
    QHBoxLayout,
    QLabel,
    QTabWidget,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex, QDate

from .edit_replacement_dialog import EditReplacementDialog
from .order_dialog import OrderDialog
from .task_dialog import TaskDialog
from .utils import db_string_to_ui_string, qdate_to_db_string, apply_table_compact_style


class ReplacementsTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = [
            "Дата",
            "Оборудование",
            "Запчасть (Наименование)",
            "Артикул",
            "Категория",
            "Кол-во",
            "Причина",
        ]
        self._data = []

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
            if col == 0:
                return db_string_to_ui_string(row_data['date'])
            if col == 1:
                return row_data['equipment_name']
            if col == 2:
                return row_data['part_name']
            if col == 3:
                return row_data['part_sku']
            if col == 4:
                return row_data.get('part_category_name', '')
            if col == 5:
                return str(row_data['qty'])
            if col == 6:
                return row_data['reason']

        if role == Qt.UserRole:
            return row_data['id']

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def load_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()


class OrdersHistoryTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = [
            "Дата поставки",
            "Контрагент",
            "Счёт №",
            "Дата счёта",
            "Адрес доставки",
            "Комментарий",
        ]
        self._data: list[dict] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                base_date = (
                    row.get('delivery_date')
                    or row.get('invoice_date')
                    or (row.get('created_at', '').split(' ')[0] if row.get('created_at') else '')
                )
                return db_string_to_ui_string(base_date)
            if col == 1:
                return row.get('counterparty_name', '')
            if col == 2:
                return row.get('invoice_no', '')
            if col == 3:
                return db_string_to_ui_string(row.get('invoice_date'))
            if col == 4:
                return row.get('delivery_address') or row.get('counterparty_address', '')
            if col == 5:
                return row.get('comment', '')

        if role == Qt.UserRole:
            return row.get('id')

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def load_data(self, rows: list[dict]):
        self.beginResetModel()
        self._data = rows
        self.endResetModel()


class TasksHistoryTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = [
            "Дата",
            "Задача",
            "Оборудование",
            "Исполнитель",
            "Срок",
            "Статус",
            "Комментарий",
        ]
        self._data: list[dict] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                created = row.get('created_at')
                created_date = created.split(' ')[0] if created else None
                return db_string_to_ui_string(created_date)
            if col == 1:
                title = row.get('title') or ''
                if row.get('priority'):
                    return f"[{row['priority']}] {title}"
                return title
            if col == 2:
                return row.get('equipment_name', '')
            if col == 3:
                return row.get('assignee_name', '')
            if col == 4:
                return db_string_to_ui_string(row.get('due_date'))
            if col == 5:
                return row.get('status', '')
            if col == 6:
                return row.get('description', '')

        if role == Qt.UserRole:
            return row.get('id')

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def load_data(self, rows: list[dict]):
        self.beginResetModel()
        self._data = rows
        self.endResetModel()


class KnifeOperationsHistoryModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = [
            "Дата",
            "Время",
            "Комплект",
            "Артикул",
            "Описание",
            "Тип",
        ]
        self._data: list[dict] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return db_string_to_ui_string(row.get('event_date'))
            if col == 1:
                return row.get('event_time') or ''
            if col == 2:
                return row.get('part_name', '')
            if col == 3:
                return row.get('part_sku', '')
            if col == 4:
                entry_type = row.get('entry_type')
                comment = row.get('comment', '') or ''
                if entry_type == 'status':
                    from_status = row.get('from_status') or '—'
                    to_status = row.get('to_status') or '—'
                    base = f"Статус: {from_status} → {to_status}"
                    if comment:
                        base = f"{base} ({comment})"
                    return base
                return comment or '—'
            if col == 5:
                return 'Статус' if row.get('entry_type') == 'status' else 'Заточка'

        if role == Qt.UserRole:
            return row.get('entry_id')

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def load_data(self, rows: list[dict]):
        self.beginResetModel()
        self._data = rows
        self.endResetModel()

    def get_entry(self, row: int) -> dict | None:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None


class ReplacementsHistoryView(QWidget):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self._setup_ui()
        self._load_combobox_data()
        self._connect_events()
        self.refresh_data()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        filters_container = QWidget()
        filters_layout = QHBoxLayout(filters_container)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(16)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())

        self.part_category_combo = QComboBox()
        self.equipment_combo = QComboBox()

        self.delete_button = QPushButton("Удалить выбранные")
        self.delete_button.clicked.connect(self.delete_selected_replacements)

        period_container = QWidget()
        period_container_layout = QVBoxLayout(period_container)
        period_container_layout.setContentsMargins(0, 0, 0, 0)
        period_container_layout.setSpacing(4)
        period_label = QLabel("Период")
        period_label.setStyleSheet("font-weight: 500;")
        period_inputs_layout = QHBoxLayout()
        period_inputs_layout.setContentsMargins(0, 0, 0, 0)
        period_inputs_layout.setSpacing(6)
        period_inputs_layout.addWidget(QLabel("с:"))
        period_inputs_layout.addWidget(self.start_date_edit)
        period_inputs_layout.addWidget(QLabel("по:"))
        period_inputs_layout.addWidget(self.end_date_edit)
        period_container_layout.addWidget(period_label)
        period_container_layout.addLayout(period_inputs_layout)

        def build_filter_block(title: str, widget: QWidget) -> QWidget:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)
            label = QLabel(title)
            label.setStyleSheet("font-weight: 500;")
            container_layout.addWidget(label)
            container_layout.addWidget(widget)
            return container

        filters_layout.addWidget(period_container)
        filters_layout.addWidget(build_filter_block("Категория запчасти", self.part_category_combo))
        filters_layout.addWidget(build_filter_block("Оборудование", self.equipment_combo))
        filters_layout.addStretch()
        filters_layout.addWidget(self.delete_button)

        self.model = ReplacementsTableModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.create_context_menu)
        self.table.doubleClicked.connect(self.edit_selected_replacement)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)

        apply_table_compact_style(self.table)

        main_layout.addWidget(filters_container)
        main_layout.addWidget(self.table)
        self.setLayout(main_layout)
        self.table.selectionModel().selectionChanged.connect(self._update_delete_button_state)
        self._update_delete_button_state()

    def _load_combobox_data(self):
        self.part_category_combo.clear()
        self.part_category_combo.addItem("Все категории", 0)
        for cat in self.db.get_part_categories():
            self.part_category_combo.addItem(cat['name'], cat['id'])

        self.equipment_combo.clear()
        self.equipment_combo.addItem("Все оборудование", 0)
        for eq in self.db.get_all_equipment():
            self.equipment_combo.addItem(eq['name'], eq['id'])

    def _connect_events(self):
        self.start_date_edit.dateChanged.connect(self.refresh_data)
        self.end_date_edit.dateChanged.connect(self.refresh_data)
        self.part_category_combo.currentIndexChanged.connect(self.refresh_data)
        self.equipment_combo.currentIndexChanged.connect(self.refresh_data)
        self.event_bus.subscribe("replacements.changed", self.refresh_data)
        self.event_bus.subscribe("equipment.changed", self._load_combobox_data)
        self.event_bus.subscribe("parts.changed", self._load_combobox_data)

    def refresh_data(self):
        start_date = qdate_to_db_string(self.start_date_edit.date())
        end_date = qdate_to_db_string(self.end_date_edit.date())
        part_category_id = self.part_category_combo.currentData()
        equipment_id = self.equipment_combo.currentData()

        data = self.db.get_all_replacements_filtered(start_date, end_date, part_category_id, equipment_id)
        self.model.load_data(data)

    def _selected_source_indexes(self):
        selection_model = self.table.selectionModel()
        if not selection_model:
            return []
        selected_rows = selection_model.selectedRows()
        return [self.proxy_model.mapToSource(index) for index in selected_rows]

    def get_selected_replacement_ids(self):
        ids = []
        for source_index in self._selected_source_indexes():
            replacement_id = self.model.data(source_index, Qt.UserRole)
            if replacement_id:
                ids.append(replacement_id)
        return ids

    def _update_delete_button_state(self):
        has_selection = bool(self.get_selected_replacement_ids())
        self.delete_button.setEnabled(has_selection)

    def edit_selected_replacement(self):
        ids = self.get_selected_replacement_ids()
        replacement_id = ids[0] if ids else None
        if replacement_id:
            dialog = EditReplacementDialog(self.db, self.event_bus, replacement_id, self)
            dialog.exec()
        else:
            QMessageBox.information(self, "Внимание", "Выберите запись для редактирования.")

    def delete_selected_replacements(self):
        replacement_ids = self.get_selected_replacement_ids()
        if not replacement_ids:
            QMessageBox.warning(self, "Внимание", "Выберите запись для удаления.")
            return

        count = len(replacement_ids)
        if count == 1:
            prompt = (
                "Вы уверены, что хотите удалить выбранную запись из истории?\n\n"
                "<b>Внимание:</b> это действие НЕ вернёт запчасть на склад."
            )
        else:
            prompt = (
                f"Удалить {count} записей из истории замен?\n\n"
                "<b>Внимание:</b> это действие НЕ вернёт запчасти на склад."
            )

        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            prompt,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            success_count = 0
            errors: list[str] = []
            for replacement_id in replacement_ids:
                success, message = self.db.delete_replacement(replacement_id)
                if success:
                    success_count += 1
                else:
                    errors.append(message)

            if success_count:
                self.event_bus.emit("replacements.changed")
                self.refresh_data()
                info_message = (
                    "Удалена запись из истории замен." if success_count == 1 else f"Удалено записей: {success_count}."
                )
                QMessageBox.information(self, "Успех", info_message)

            if errors:
                error_text = "\n".join(dict.fromkeys(errors))
                QMessageBox.critical(self, "Ошибка", error_text)

    def create_context_menu(self, position):
        selected_ids = self.get_selected_replacement_ids()
        if not selected_ids:
            return

        menu = QMenu()
        edit_action = None
        if len(selected_ids) == 1:
            edit_action = menu.addAction("Редактировать")
        delete_action = menu.addAction("Удалить выбранные")

        action = menu.exec(self.table.viewport().mapToGlobal(position))

        if action == edit_action:
            self.edit_selected_replacement()
        elif action == delete_action:
            self.delete_selected_replacements()


class OrdersHistoryView(QWidget):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self._setup_ui()
        self._load_counterparties()
        self._connect_events()
        self.refresh_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        filters_container = QWidget()
        filters_layout = QHBoxLayout(filters_container)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(16)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())

        self.counterparty_combo = QComboBox()

        def build_filter_block(title: str, widget: QWidget) -> QWidget:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)
            label = QLabel(title)
            label.setStyleSheet("font-weight: 500;")
            container_layout.addWidget(label)
            container_layout.addWidget(widget)
            return container

        period_container = QWidget()
        period_layout = QVBoxLayout(period_container)
        period_layout.setContentsMargins(0, 0, 0, 0)
        period_layout.setSpacing(4)
        period_label = QLabel("Период")
        period_label.setStyleSheet("font-weight: 500;")
        period_inputs = QHBoxLayout()
        period_inputs.setContentsMargins(0, 0, 0, 0)
        period_inputs.setSpacing(6)
        period_inputs.addWidget(QLabel("с:"))
        period_inputs.addWidget(self.start_date_edit)
        period_inputs.addWidget(QLabel("по:"))
        period_inputs.addWidget(self.end_date_edit)
        period_layout.addWidget(period_label)
        period_layout.addLayout(period_inputs)

        filters_layout.addWidget(period_container)
        filters_layout.addWidget(build_filter_block("Контрагент", self.counterparty_combo))
        filters_layout.addStretch()

        self.delete_button = QPushButton("Удалить выбранные")
        self.delete_button.clicked.connect(self.delete_selected_orders)
        filters_layout.addWidget(self.delete_button)

        self.model = OrdersHistoryTableModel(self)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        self.table = QTableView(self)
        self.table.setModel(self.proxy_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self.open_selected_order)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        apply_table_compact_style(self.table)

        layout.addWidget(filters_container)
        layout.addWidget(self.table)
        self.table.selectionModel().selectionChanged.connect(self._update_delete_button_state)
        self._update_delete_button_state()

    def _load_counterparties(self):
        self.counterparty_combo.blockSignals(True)
        self.counterparty_combo.clear()
        self.counterparty_combo.addItem("Все контрагенты", 0)
        for counterparty in self.db.get_all_counterparties():
            self.counterparty_combo.addItem(counterparty['name'], counterparty['id'])
        self.counterparty_combo.blockSignals(False)

    def _connect_events(self):
        self.start_date_edit.dateChanged.connect(self.refresh_data)
        self.end_date_edit.dateChanged.connect(self.refresh_data)
        self.counterparty_combo.currentIndexChanged.connect(self.refresh_data)
        self.event_bus.subscribe("orders.changed", self.refresh_data)
        self.event_bus.subscribe("counterparties.changed", self._load_counterparties)

    def refresh_data(self):
        start_date = qdate_to_db_string(self.start_date_edit.date())
        end_date = qdate_to_db_string(self.end_date_edit.date())
        counterparty_id = self.counterparty_combo.currentData()
        data = self.db.get_completed_orders_history(start_date, end_date, counterparty_id)
        self.model.load_data(data)

    def _selected_source_indexes(self):
        selection_model = self.table.selectionModel()
        if not selection_model:
            return []
        return [self.proxy_model.mapToSource(index) for index in selection_model.selectedRows()]

    def _selected_order_ids(self):
        ids = []
        for source_index in self._selected_source_indexes():
            order_id = self.model.data(source_index, Qt.UserRole)
            if order_id:
                ids.append(order_id)
        return ids

    def _update_delete_button_state(self):
        self.delete_button.setEnabled(bool(self._selected_order_ids()))

    def delete_selected_orders(self):
        order_ids = self._selected_order_ids()
        if not order_ids:
            QMessageBox.information(self, "Удаление заказов", "Не выбрано ни одного заказа.")
            return

        if len(order_ids) == 1:
            prompt = "Удалить выбранный заказ из истории?"
        else:
            prompt = f"Удалить {len(order_ids)} заказов из истории?"

        reply = QMessageBox.question(
            self,
            "Удаление заказов",
            prompt,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        success_count = 0
        errors: list[str] = []
        for order_id in order_ids:
            success, message = self.db.delete_order(order_id)
            if success:
                success_count += 1
            else:
                errors.append(message)

        if success_count:
            self.event_bus.emit("orders.changed")
            self.refresh_data()
            summary = (
                "Заказ удалён." if success_count == 1 else f"Удалено заказов: {success_count}."
            )
            QMessageBox.information(self, "Готово", summary)

        if errors:
            error_text = "\n".join(dict.fromkeys(errors))
            QMessageBox.critical(self, "Ошибка", error_text)

    def open_selected_order(self, index: QModelIndex | None = None):
        if index is not None and index.model() is self.proxy_model:
            source_index = self.proxy_model.mapToSource(index)
        else:
            selected = self._selected_source_indexes()
            source_index = selected[0] if selected else None

        if source_index is None:
            QMessageBox.information(self, "Просмотр заказа", "Выберите запись для просмотра.")
            return

        order_id = self.model.data(source_index, Qt.UserRole)
        if not order_id:
            QMessageBox.warning(self, "Просмотр заказа", "Не удалось определить идентификатор заказа.")
            return

        dialog = OrderDialog(self.db, self.event_bus, order_id, self)
        if dialog.exec():
            self.refresh_data()

    def _show_context_menu(self, position):
        order_ids = self._selected_order_ids()
        if not order_ids:
            return

        menu = QMenu(self)
        open_action = None
        if len(order_ids) == 1:
            open_action = menu.addAction("Открыть")
        delete_action = menu.addAction("Удалить выбранные")

        action = menu.exec(self.table.viewport().mapToGlobal(position))
        if action == open_action:
            self.open_selected_order()
        elif action == delete_action:
            self.delete_selected_orders()


class TasksHistoryView(QWidget):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self._setup_ui()
        self._load_filters()
        self._connect_events()
        self.refresh_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        filters_container = QWidget()
        filters_layout = QHBoxLayout(filters_container)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(16)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())

        self.assignee_combo = QComboBox()
        self.equipment_combo = QComboBox()

        def block(title: str, widget: QWidget) -> QWidget:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)
            label = QLabel(title)
            label.setStyleSheet("font-weight: 500;")
            container_layout.addWidget(label)
            container_layout.addWidget(widget)
            return container

        period_container = QWidget()
        period_layout = QVBoxLayout(period_container)
        period_layout.setContentsMargins(0, 0, 0, 0)
        period_layout.setSpacing(4)
        period_label = QLabel("Период")
        period_label.setStyleSheet("font-weight: 500;")
        period_inputs = QHBoxLayout()
        period_inputs.setContentsMargins(0, 0, 0, 0)
        period_inputs.setSpacing(6)
        period_inputs.addWidget(QLabel("с:"))
        period_inputs.addWidget(self.start_date_edit)
        period_inputs.addWidget(QLabel("по:"))
        period_inputs.addWidget(self.end_date_edit)
        period_layout.addWidget(period_label)
        period_layout.addLayout(period_inputs)

        filters_layout.addWidget(period_container)
        filters_layout.addWidget(block("Исполнитель", self.assignee_combo))
        filters_layout.addWidget(block("Оборудование", self.equipment_combo))
        filters_layout.addStretch()

        self.delete_button = QPushButton("Удалить выбранные")
        self.delete_button.clicked.connect(self.delete_selected_tasks)
        filters_layout.addWidget(self.delete_button)

        self.model = TasksHistoryTableModel(self)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        self.table = QTableView(self)
        self.table.setModel(self.proxy_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self.open_selected_task)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        apply_table_compact_style(self.table)

        layout.addWidget(filters_container)
        layout.addWidget(self.table)
        self.table.selectionModel().selectionChanged.connect(self._update_delete_button_state)
        self._update_delete_button_state()

    def _load_filters(self):
        self.assignee_combo.blockSignals(True)
        self.assignee_combo.clear()
        self.assignee_combo.addItem("Все", 0)
        for colleague in self.db.get_all_colleagues():
            self.assignee_combo.addItem(colleague['name'], colleague['id'])
        self.assignee_combo.blockSignals(False)

        self.equipment_combo.blockSignals(True)
        self.equipment_combo.clear()
        self.equipment_combo.addItem("Все", 0)
        for equipment in self.db.get_all_equipment():
            self.equipment_combo.addItem(equipment['name'], equipment['id'])
        self.equipment_combo.blockSignals(False)

    def _connect_events(self):
        self.start_date_edit.dateChanged.connect(self.refresh_data)
        self.end_date_edit.dateChanged.connect(self.refresh_data)
        self.assignee_combo.currentIndexChanged.connect(self.refresh_data)
        self.equipment_combo.currentIndexChanged.connect(self.refresh_data)
        self.event_bus.subscribe("tasks.changed", self.refresh_data)
        self.event_bus.subscribe("equipment.changed", self._load_filters)

    def refresh_data(self):
        start_date = qdate_to_db_string(self.start_date_edit.date())
        end_date = qdate_to_db_string(self.end_date_edit.date())
        assignee_id = self.assignee_combo.currentData()
        equipment_id = self.equipment_combo.currentData()
        rows = self.db.get_tasks_history(start_date, end_date, assignee_id, equipment_id)
        self.model.load_data(rows)

    def _selected_source_indexes(self):
        selection_model = self.table.selectionModel()
        if not selection_model:
            return []
        return [self.proxy_model.mapToSource(index) for index in selection_model.selectedRows()]

    def _selected_task_ids(self):
        ids = []
        for source_index in self._selected_source_indexes():
            task_id = self.model.data(source_index, Qt.UserRole)
            if task_id:
                ids.append(task_id)
        return ids

    def _update_delete_button_state(self):
        self.delete_button.setEnabled(bool(self._selected_task_ids()))

    def delete_selected_tasks(self):
        task_ids = self._selected_task_ids()
        if not task_ids:
            QMessageBox.information(self, "Удаление задач", "Не выбрано ни одной записи.")
            return

        if len(task_ids) == 1:
            prompt = "Удалить выбранную задачу из истории?"
        else:
            prompt = f"Удалить {len(task_ids)} задач из истории?"

        reply = QMessageBox.question(
            self,
            "Удаление задач",
            prompt,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        success_count = 0
        aggregated_events = {
            'equipment_ids': set(),
            'parts_changed': False,
            'replacements_changed': False,
        }
        errors: list[str] = []

        for task_id in task_ids:
            success, message, events = self.db.delete_task(task_id)
            if success:
                success_count += 1
                equipment_ids = events.get('equipment_ids', [])
                if equipment_ids:
                    aggregated_events['equipment_ids'].update(equipment_ids)
                if events.get('parts_changed'):
                    aggregated_events['parts_changed'] = True
                if events.get('replacements_changed'):
                    aggregated_events['replacements_changed'] = True
            else:
                errors.append(message)

        if success_count:
            self._emit_task_side_effects(aggregated_events)
            self.event_bus.emit("tasks.changed")
            self.refresh_data()
            summary = "Задача удалена." if success_count == 1 else f"Удалено задач: {success_count}."
            QMessageBox.information(self, "Готово", summary)

        if errors:
            error_text = "\n".join(dict.fromkeys(errors))
            QMessageBox.critical(self, "Ошибка", error_text)

    def _emit_task_side_effects(self, events: dict):
        equipment_ids = set(events.get('equipment_ids', []))
        for equipment_id in equipment_ids:
            self.event_bus.emit("equipment_parts_changed", equipment_id)
        if events.get('parts_changed'):
            self.event_bus.emit("parts.changed")
        if events.get('replacements_changed'):
            self.event_bus.emit("replacements.changed")

    def open_selected_task(self, index: QModelIndex | None = None):
        if index is not None and index.model() is self.proxy_model:
            source_index = self.proxy_model.mapToSource(index)
        else:
            selected = self._selected_source_indexes()
            source_index = selected[0] if selected else None

        if source_index is None:
            QMessageBox.information(self, "Просмотр задачи", "Выберите запись для просмотра.")
            return

        task_id = self.model.data(source_index, Qt.UserRole)
        if not task_id:
            QMessageBox.warning(self, "Просмотр задачи", "Не удалось определить идентификатор задачи.")
            return

        dialog = TaskDialog(self.db, self.event_bus, task_id, self)
        if dialog.exec():
            self.refresh_data()

    def _show_context_menu(self, position):
        task_ids = self._selected_task_ids()
        if not task_ids:
            return

        menu = QMenu(self)
        open_action = None
        if len(task_ids) == 1:
            open_action = menu.addAction("Открыть")
        delete_action = menu.addAction("Удалить выбранные")

        action = menu.exec(self.table.viewport().mapToGlobal(position))
        if action == open_action:
            self.open_selected_task()
        elif action == delete_action:
            self.delete_selected_tasks()


class KnifeOperationsHistoryView(QWidget):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self._setup_ui()
        self._load_parts()
        self._connect_events()
        self.refresh_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        filters_container = QWidget()
        filters_layout = QHBoxLayout(filters_container)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(16)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())

        self.part_combo = QComboBox()

        def block(title: str, widget: QWidget) -> QWidget:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)
            label = QLabel(title)
            label.setStyleSheet("font-weight: 500;")
            container_layout.addWidget(label)
            container_layout.addWidget(widget)
            return container

        period_container = QWidget()
        period_layout = QVBoxLayout(period_container)
        period_layout.setContentsMargins(0, 0, 0, 0)
        period_layout.setSpacing(4)
        period_label = QLabel("Период")
        period_label.setStyleSheet("font-weight: 500;")
        period_inputs = QHBoxLayout()
        period_inputs.setContentsMargins(0, 0, 0, 0)
        period_inputs.setSpacing(6)
        period_inputs.addWidget(QLabel("с:"))
        period_inputs.addWidget(self.start_date_edit)
        period_inputs.addWidget(QLabel("по:"))
        period_inputs.addWidget(self.end_date_edit)
        period_layout.addWidget(period_label)
        period_layout.addLayout(period_inputs)

        filters_layout.addWidget(period_container)
        filters_layout.addWidget(block("Комплект", self.part_combo))
        filters_layout.addStretch()

        self.delete_button = QPushButton("Удалить выбранные")
        self.delete_button.clicked.connect(self.delete_selected_entries)
        filters_layout.addWidget(self.delete_button)

        self.model = KnifeOperationsHistoryModel(self)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        self.table = QTableView(self)
        self.table.setModel(self.proxy_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        apply_table_compact_style(self.table)

        layout.addWidget(filters_container)
        layout.addWidget(self.table)
        self.table.selectionModel().selectionChanged.connect(self._update_delete_button_state)
        self._update_delete_button_state()

    def _load_parts(self):
        self.part_combo.blockSignals(True)
        self.part_combo.clear()
        self.part_combo.addItem("Все", 0)
        for part in self.db.get_all_sharpening_items():
            display = part.get('name') or f"ID {part.get('id')}"
            sku = part.get('sku')
            if sku:
                display = f"{display} ({sku})"
            self.part_combo.addItem(display, part.get('id'))
        self.part_combo.blockSignals(False)

    def _connect_events(self):
        self.start_date_edit.dateChanged.connect(self.refresh_data)
        self.end_date_edit.dateChanged.connect(self.refresh_data)
        self.part_combo.currentIndexChanged.connect(self.refresh_data)
        self.event_bus.subscribe("knives.changed", self.refresh_data)
        self.event_bus.subscribe("parts.changed", self._load_parts)

    def refresh_data(self):
        start_date = qdate_to_db_string(self.start_date_edit.date())
        end_date = qdate_to_db_string(self.end_date_edit.date())
        part_id = self.part_combo.currentData()
        rows = self.db.get_knife_operations_history(start_date, end_date, part_id)
        self.model.load_data(rows)
        self._update_delete_button_state()

    def _selected_source_indexes(self):
        selection_model = self.table.selectionModel()
        if not selection_model:
            return []
        return [self.proxy_model.mapToSource(index) for index in selection_model.selectedRows()]

    def _selected_entries(self):
        entries: list[dict] = []
        for source_index in self._selected_source_indexes():
            entry = self.model.get_entry(source_index.row())
            if entry:
                entries.append(entry)
        return entries

    def _update_delete_button_state(self):
        self.delete_button.setEnabled(bool(self._selected_entries()))

    def delete_selected_entries(self):
        entries = self._selected_entries()
        if not entries:
            QMessageBox.information(self, "Удаление записей", "Не выбрано ни одной записи.")
            return

        type_labels = {
            'sharpen': 'заточек',
            'status': 'изменений статуса',
        }
        counts: dict[str, int] = {}
        for entry in entries:
            label = type_labels.get(entry.get('entry_type'), 'записей')
            counts[label] = counts.get(label, 0) + 1

        summary_parts = [f"{count} {label}" for label, count in counts.items()]
        summary = ", ".join(summary_parts)
        prompt = f"Удалить выбранные записи ({summary})?"

        reply = QMessageBox.question(
            self,
            "Удаление истории",
            prompt,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        success_count = 0
        errors: list[str] = []
        for entry in entries:
            entry_type = entry.get('entry_type')
            entry_id = entry.get('entry_id')
            if not entry_id:
                continue

            if entry_type == 'status':
                success, message = self.db.delete_knife_status_entry(entry_id)
            else:
                success, message = self.db.delete_knife_sharpen_entry(entry_id)

            if success:
                success_count += 1
            else:
                errors.append(message)

        if success_count:
            self.event_bus.emit("knives.changed")
            self.refresh_data()
            info = "Запись удалена." if success_count == 1 else f"Удалено записей: {success_count}."
            QMessageBox.information(self, "Готово", info)

        if errors:
            error_text = "\n".join(dict.fromkeys(errors))
            QMessageBox.critical(self, "Ошибка", error_text)

    def _show_context_menu(self, position):
        entries = self._selected_entries()
        if not entries:
            return

        menu = QMenu(self)
        delete_action = menu.addAction("Удалить выбранные")
        action = menu.exec(self.table.viewport().mapToGlobal(position))
        if action == delete_action:
            self.delete_selected_entries()


class ReplacementHistoryTab(QWidget):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget(self)
        layout.addWidget(self.tab_widget)

        self.replacements_view = ReplacementsHistoryView(self.db, self.event_bus, self)
        self.tab_widget.addTab(self.replacements_view, "Замены")

        self.orders_view = OrdersHistoryView(self.db, self.event_bus, self)
        self.tab_widget.addTab(self.orders_view, "Заказы")

        self.knives_view = KnifeOperationsHistoryView(self.db, self.event_bus, self)
        self.tab_widget.addTab(self.knives_view, "Заточка")

        self.tasks_view = TasksHistoryView(self.db, self.event_bus, self)
        self.tab_widget.addTab(self.tasks_view, "Задачи")
