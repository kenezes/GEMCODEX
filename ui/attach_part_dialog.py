import logging
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QMessageBox,
    QAbstractItemView,
    QSpinBox,
    QTabWidget,
    QFormLayout,
    QDateEdit,
    QComboBox,
    QDoubleSpinBox,
    QWidget,
)
from PySide6.QtCore import Qt, QDate, QLocale
from PySide6.QtGui import QStandardItemModel, QStandardItem

from .utils import apply_table_compact_style

class AttachPartDialog(QDialog):
    ALL_CATEGORIES = -1
    UNCATEGORIZED = "__none__"

    def __init__(self, db, event_bus, equipment_id, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.equipment_id = equipment_id
        self.setWindowTitle("Привязка запчасти к оборудованию")
        self.setMinimumSize(720, 520)

        self.layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        self._build_stock_tab()
        self._build_new_part_tab()

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)
        self.layout.addLayout(buttons_layout)

        self.event_bus.subscribe("parts.changed", self.on_parts_changed)
        self.all_parts: list[dict] = []
        self._row_types: list[str] = []
        self._categories: list[dict] = []

        self.load_parts()

    def _build_stock_tab(self):
        self.stock_tab = QWidget()
        tab_layout = QVBoxLayout(self.stock_tab)

        filters_layout = QHBoxLayout()
        filters_layout.addWidget(QLabel("Поиск:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите наименование или артикул...")
        self.search_input.textChanged.connect(self._on_filters_changed)
        filters_layout.addWidget(self.search_input)

        filters_layout.addWidget(QLabel("Категория:"))
        self.category_filter = QComboBox()
        self.category_filter.currentIndexChanged.connect(self._on_filters_changed)
        filters_layout.addWidget(self.category_filter)
        filters_layout.addStretch()
        tab_layout.addLayout(filters_layout)

        self.table_view = QTableView()
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSortingEnabled(False)

        self.table_model = QStandardItemModel(self)
        self.table_model.setHorizontalHeaderLabels(["Наименование", "Артикул", "На складе, шт."])
        self.table_view.setModel(self.table_model)
        apply_table_compact_style(self.table_view)
        tab_layout.addWidget(self.table_view)

        form_layout = QFormLayout()
        self.stock_installed_qty_input = QSpinBox()
        self.stock_installed_qty_input.setMinimum(1)
        self.stock_installed_qty_input.setMaximum(999999)
        self.stock_installed_qty_input.setValue(1)
        form_layout.addRow("Установлено, шт.:", self.stock_installed_qty_input)

        self.stock_comment_input = QLineEdit()
        form_layout.addRow("Комментарий:", self.stock_comment_input)

        self.stock_last_replacement_edit = self._create_optional_date_edit()
        clear_button = QPushButton("Очистить")
        clear_button.setFlat(True)
        clear_button.clicked.connect(lambda: self._clear_date(self.stock_last_replacement_edit))
        date_container = QWidget()
        date_layout = QHBoxLayout(date_container)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(6)
        date_layout.addWidget(self.stock_last_replacement_edit)
        date_layout.addWidget(clear_button)
        date_layout.addStretch()
        form_layout.addRow("Последняя замена:", date_container)

        tab_layout.addLayout(form_layout)

        self.tabs.addTab(self.stock_tab, "Со склада")

    def _build_new_part_tab(self):
        self.new_part_tab = QWidget()
        layout = QVBoxLayout(self.new_part_tab)

        form_layout = QFormLayout()

        self.new_name_input = QLineEdit()
        form_layout.addRow("Наименование*:", self.new_name_input)

        self.new_sku_input = QLineEdit()
        form_layout.addRow("Артикул*:", self.new_sku_input)

        self.new_qty_input = QSpinBox()
        self.new_qty_input.setRange(0, 999999)
        form_layout.addRow("Остаток (на складе):", self.new_qty_input)

        self.new_min_qty_input = QSpinBox()
        self.new_min_qty_input.setRange(0, 999999)
        form_layout.addRow("Минимум (на складе):", self.new_min_qty_input)

        self.new_price_input = QDoubleSpinBox()
        self.new_price_input.setRange(0.0, 999999999.99)
        self.new_price_input.setDecimals(2)
        self.new_price_input.setGroupSeparatorShown(True)
        c_locale = QLocale(QLocale.Language.C)
        c_locale.setNumberOptions(QLocale.NumberOption.RejectGroupSeparator)
        self.new_price_input.setLocale(c_locale)
        form_layout.addRow("Цена:", self.new_price_input)

        self.new_category_combo = QComboBox()
        form_layout.addRow("Категория:", self.new_category_combo)

        self.new_installed_qty_input = QSpinBox()
        self.new_installed_qty_input.setMinimum(1)
        self.new_installed_qty_input.setMaximum(999999)
        self.new_installed_qty_input.setValue(1)
        form_layout.addRow("Установлено, шт.:", self.new_installed_qty_input)

        self.new_comment_input = QLineEdit()
        form_layout.addRow("Комментарий:", self.new_comment_input)

        self.new_last_replacement_edit = self._create_optional_date_edit()
        new_clear_button = QPushButton("Очистить")
        new_clear_button.setFlat(True)
        new_clear_button.clicked.connect(lambda: self._clear_date(self.new_last_replacement_edit))
        new_date_container = QWidget()
        new_date_layout = QHBoxLayout(new_date_container)
        new_date_layout.setContentsMargins(0, 0, 0, 0)
        new_date_layout.setSpacing(6)
        new_date_layout.addWidget(self.new_last_replacement_edit)
        new_date_layout.addWidget(new_clear_button)
        new_date_layout.addStretch()
        form_layout.addRow("Последняя замена:", new_date_container)

        layout.addLayout(form_layout)
        layout.addStretch()

        self.tabs.addTab(self.new_part_tab, "Новая")

    def _create_optional_date_edit(self) -> QDateEdit:
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("dd.MM.yyyy")
        min_date = QDate(1900, 1, 1)
        edit.setMinimumDate(min_date)
        edit.setDate(min_date)
        edit.setSpecialValueText("Не указано")
        return edit

    def _clear_date(self, date_edit: QDateEdit):
        date_edit.setDate(date_edit.minimumDate())

    def _get_date_value(self, date_edit: QDateEdit) -> str | None:
        date_value = date_edit.date()
        if date_value <= date_edit.minimumDate():
            return None
        return date_value.toString("yyyy-MM-dd")

    def _on_filters_changed(self):
        self.filter_parts(self.search_input.text())

    def load_parts(self):
        self._load_part_categories()
        parts = self.db.get_unattached_parts(self.equipment_id)
        self.all_parts = parts
        category_token = self.category_filter.currentData()
        self._display_parts(parts, self.search_input.text(), category_token)

    def _load_part_categories(self):
        categories = self.db.get_part_categories()
        self._categories = categories

        current_filter = self.category_filter.currentData() if hasattr(self, 'category_filter') else self.ALL_CATEGORIES
        if hasattr(self, 'category_filter'):
            self.category_filter.blockSignals(True)
            self.category_filter.clear()
            self.category_filter.addItem("Все категории", self.ALL_CATEGORIES)
            self.category_filter.addItem("Без категории", self.UNCATEGORIZED)
            for cat in categories:
                self.category_filter.addItem(cat['name'], cat['id'])
            index = self.category_filter.findData(current_filter)
            if index != -1:
                self.category_filter.setCurrentIndex(index)
            else:
                self.category_filter.setCurrentIndex(0)
            self.category_filter.blockSignals(False)

        if hasattr(self, 'new_category_combo'):
            current_new = self.new_category_combo.currentData()
            self.new_category_combo.blockSignals(True)
            self.new_category_combo.clear()
            self.new_category_combo.addItem("", None)
            for cat in categories:
                self.new_category_combo.addItem(cat['name'], cat['id'])
            if current_new is not None:
                index_new = self.new_category_combo.findData(current_new)
                if index_new != -1:
                    self.new_category_combo.setCurrentIndex(index_new)
                else:
                    self.new_category_combo.setCurrentIndex(0)
            else:
                self.new_category_combo.setCurrentIndex(0)
            self.new_category_combo.blockSignals(False)

    def filter_parts(self, text=""):
        category_token = self.category_filter.currentData()
        self._display_parts(self.all_parts, text, category_token)

    def _display_parts(self, parts, filter_text="", category_token=None):
        self.table_model.removeRows(0, self.table_model.rowCount())
        self._row_types = []
        filter_text = (filter_text or "").strip().lower()
        selected_category = self.ALL_CATEGORIES if category_token is None else category_token

        current_category_name = None
        for part in parts:
            part_category_id = part.get('category_id')

            if selected_category != self.ALL_CATEGORIES:
                if selected_category == self.UNCATEGORIZED:
                    if part_category_id is not None:
                        continue
                else:
                    if part_category_id != selected_category:
                        continue

            searchable_text = f"{part['name']} {part['sku'] or ''}".lower()
            if filter_text and filter_text not in searchable_text:
                continue

            category_name = part.get('category_name') or "Без категории"
            if category_name != current_category_name:
                header_item = QStandardItem(category_name)
                header_font = header_item.font()
                header_font.setBold(True)
                header_item.setFont(header_font)
                header_item.setFlags(Qt.ItemIsEnabled)

                placeholders = [QStandardItem(""), QStandardItem("")]
                for item in placeholders:
                    item.setFlags(Qt.ItemIsEnabled)

                self.table_model.appendRow([header_item, *placeholders])
                self._row_types.append('header')
                current_category_name = category_name

            row = [
                QStandardItem(part['name']),
                QStandardItem(part['sku'] or ""),
                QStandardItem(str(part['qty']))
            ]
            row[0].setData(part['id'], Qt.UserRole)
            self.table_model.appendRow(row)
            self._row_types.append('part')

        self.table_view.resizeColumnsToContents()
        self._update_vertical_header_numbers()

    def _update_vertical_header_numbers(self):
        part_counter = 1
        for row, row_type in enumerate(self._row_types):
            if row_type == 'header':
                label = ""
            else:
                label = str(part_counter)
                part_counter += 1
            self.table_model.setHeaderData(row, Qt.Vertical, label, Qt.DisplayRole)
            if label:
                self.table_model.setHeaderData(row, Qt.Vertical, Qt.AlignCenter, Qt.TextAlignmentRole)
            else:
                self.table_model.setHeaderData(row, Qt.Vertical, Qt.AlignLeft, Qt.TextAlignmentRole)

    def on_parts_changed(self):
        logging.info("AttachPartDialog received 'parts.changed' signal, reloading parts list.")
        self.load_parts()

    def get_selected_part_id(self):
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if not selected_indexes:
            return None

        item = self.table_model.itemFromIndex(selected_indexes[0])
        return item.data(Qt.UserRole)

    def _accept_stock_part(self):
        part_id = self.get_selected_part_id()
        if part_id is None:
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите запчасть из списка.")
            return

        installed_qty = self.stock_installed_qty_input.value()
        if installed_qty <= 0:
            QMessageBox.warning(self, "Ошибка", "Установленное количество должно быть больше нуля.")
            return

        comment = self.stock_comment_input.text().strip()
        last_replacement = self._get_date_value(self.stock_last_replacement_edit)

        success, message = self.db.attach_part_to_equipment(
            self.equipment_id,
            part_id,
            installed_qty,
            comment,
            last_replacement,
        )

        if success:
            logging.info("Запчасть %s привязана к оборудованию %s", part_id, self.equipment_id)
            self.event_bus.emit("equipment_parts_changed", self.equipment_id)
            super().accept()
        else:
            QMessageBox.warning(self, "Ошибка привязки", message)

    def _accept_new_part(self):
        name = self.new_name_input.text().strip()
        sku = self.new_sku_input.text().strip()

        if not name or not sku:
            QMessageBox.warning(self, "Новая запчасть", "Заполните поля 'Наименование' и 'Артикул'.")
            return

        qty = self.new_qty_input.value()
        min_qty = self.new_min_qty_input.value()
        price = self.new_price_input.value()
        category_id = self.new_category_combo.currentData()

        success, message, part_id = self.db.add_part(name, sku, qty, min_qty, price, category_id)
        if not success:
            QMessageBox.warning(self, "Новая запчасть", message)
            return

        if part_id is None:
            row = self.db.fetchone(
                "SELECT id FROM parts WHERE name = ? AND sku = ?",
                (name, sku),
            )
            part_id = row['id'] if row else None

        if part_id is None:
            QMessageBox.warning(self, "Новая запчасть", "Не удалось определить добавленную запчасть.")
            return

        installed_qty = self.new_installed_qty_input.value()
        comment = self.new_comment_input.text().strip()
        last_replacement = self._get_date_value(self.new_last_replacement_edit)

        success_attach, message_attach = self.db.attach_part_to_equipment(
            self.equipment_id,
            part_id,
            installed_qty,
            comment,
            last_replacement,
        )

        if not success_attach:
            QMessageBox.warning(self, "Привязка запчасти", message_attach)
            return

        self.event_bus.emit("parts.changed")
        self.event_bus.emit("equipment_parts_changed", self.equipment_id)
        super().accept()

    def accept(self):
        current_tab = self.tabs.currentWidget()
        if current_tab is self.stock_tab:
            self._accept_stock_part()
        else:
            self._accept_new_part()

    def closeEvent(self, event):
        self.event_bus.unsubscribe("parts.changed", self.on_parts_changed)
        super().closeEvent(event)

