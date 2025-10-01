import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QToolBar,
    QTableView,
    QAbstractItemView,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QHBoxLayout,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex

from ui.utils import db_string_to_ui_string, apply_table_compact_style
from .knife_sharpen_history_dialog import KnifeSharpenHistoryDialog


def _sharpening_button_style(base_color: str, hover_color: str, pressed_color: str) -> str:
    return (
        "QPushButton {"
        f"background-color: {base_color};"
        "color: white;"
        "border: none;"
        "border-radius: 4px;"
        "padding: 2px 8px;"
        "font-size: 11px;"
        "min-height: 0;"
        "min-width: 0;"
        "}"
        f"QPushButton:hover {{background-color: {hover_color};}}"
        f"QPushButton:pressed {{background-color: {pressed_color};}}"
    )


class SharpeningTableModel(QAbstractTableModel):
    ACTION_COLUMN = 6

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._headers = [
            "Наименование",
            "Артикул",
            "Кол-во (склад)",
            "Последняя заточка",
            "Интервал, дней",
            "Аппарат",
            "Состояния",
        ]
        self._data: list[dict] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return None

        row_data = self._data[index.row()]
        column = index.column()

        if role == Qt.DisplayRole:
            if column == 0:
                return row_data["name"]
            if column == 1:
                return row_data["sku"]
            if column == 2:
                return str(row_data["qty"])
            if column == 3:
                return db_string_to_ui_string(row_data.get("last_sharpen_date"))
            if column == 4:
                last_interval = row_data.get("last_interval_days")
                return str(last_interval) if last_interval is not None else ""
            if column == 5:
                equipment = row_data.get("equipment_list")
                return equipment or ""
            if column == 6:
                sharp_state = row_data.get("sharp_state")
                install_state = row_data.get("installation_state")
                states: list[str] = []
                if sharp_state:
                    states.append("Заточен" if sharp_state == "заточен" else "Затуплен")
                if install_state:
                    states.append("Установлен" if install_state == "установлен" else "Снят")
                return ", ".join(states)

        if role == Qt.UserRole:
            return row_data.get("id")

        if role == Qt.UserRole + 1:
            return row_data

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # type: ignore[override]
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def load_data(self, rows: list[dict]):
        self.beginResetModel()
        self._data = rows
        self.endResetModel()

    def row_payload(self, row: int) -> Optional[dict]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None


class SharpeningActionsWidget(QWidget):
    GREEN_STYLE = _sharpening_button_style("#2e7d32", "#1b5e20", "#134d16")
    RED_STYLE = _sharpening_button_style("#c62828", "#b71c1c", "#8e0000")

    def __init__(self, db, event_bus, part_id: int, sharp_state: str, installation_state: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.part_id = part_id
        self.sharp_state = sharp_state or "затуплен"
        self.installation_state = installation_state or "снят"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(160)

        self.sharp_button = QPushButton(self)
        self.install_button = QPushButton(self)
        for button in (self.sharp_button, self.install_button):
            button.setCursor(Qt.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            button.setMinimumWidth(0)
            button.setFixedHeight(24)
            layout.addWidget(button)

        self.sharp_button.clicked.connect(self.toggle_sharp_state)
        self.install_button.clicked.connect(self.toggle_installation_state)

        self._apply_states()

    def _apply_states(self):
        if self.sharp_state == "заточен":
            self._apply_button_style(self.sharp_button, "Заточен", self.GREEN_STYLE)
        else:
            self._apply_button_style(self.sharp_button, "Затуплен", self.RED_STYLE)

        if self.installation_state == "установлен":
            self._apply_button_style(self.install_button, "Установлен", self.GREEN_STYLE)
        else:
            self._apply_button_style(self.install_button, "Снят", self.RED_STYLE)

    @staticmethod
    def _apply_button_style(button: QPushButton, text: str, style: str):
        button.setText(text)
        button.setStyleSheet(style)

    def toggle_sharp_state(self):
        success, message, payload = self.db.toggle_sharp_state(self.part_id)
        if not success:
            QMessageBox.critical(self, "Ошибка", message)
            return
        self.sharp_state = payload.get("sharp_state", self.sharp_state)
        self.installation_state = payload.get("installation_state", self.installation_state)
        self._apply_states()
        self.event_bus.emit("knives.changed")

    def toggle_installation_state(self):
        success, message, payload = self.db.toggle_installation_state(self.part_id)
        if not success:
            QMessageBox.critical(self, "Ошибка", message)
            return
        self.installation_state = payload.get("installation_state", self.installation_state)
        self.sharp_state = payload.get("sharp_state", self.sharp_state)
        self._apply_states()
        self.event_bus.emit("knives.changed")


class SharpeningTab(QWidget):
    def __init__(self, db, event_bus, main_window):
        super().__init__()
        self.db = db
        self.event_bus = event_bus
        self.main_window = main_window
        self._action_widgets: list[SharpeningActionsWidget] = []

        self.init_ui()
        self.event_bus.subscribe("knives.changed", self.refresh_data)
        self.event_bus.subscribe("parts.changed", self.refresh_data)
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
        self.history_button = QPushButton("История заточек")
        self.refresh_button = QPushButton("Обновить")

        self.toolbar.addWidget(self.history_button)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)
        self.toolbar.addWidget(self.refresh_button)

        self.history_button.clicked.connect(self.show_sharpen_history)
        self.refresh_button.clicked.connect(self.refresh_data)

    def _setup_table(self):
        self.table_model = SharpeningTableModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setSortingEnabled(True)

        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(SharpeningTableModel.ACTION_COLUMN, QHeaderView.ResizeToContents)

        apply_table_compact_style(self.table_view)

        self.proxy_model.layoutChanged.connect(self._populate_action_widgets)
        self.proxy_model.modelReset.connect(self._populate_action_widgets)

    def refresh_data(self):
        logging.info("Обновление данных на вкладке 'Заточка'")
        data = self.db.get_all_sharpening_items()
        self.table_model.load_data(data)
        self._populate_action_widgets()
        self.table_view.resizeColumnToContents(SharpeningTableModel.ACTION_COLUMN)

    def _clear_action_widgets(self):
        for widget in self._action_widgets:
            widget.deleteLater()
        self._action_widgets.clear()

    def _populate_action_widgets(self):
        if not hasattr(self, "table_view"):
            return

        self._clear_action_widgets()

        source_model = self.table_model
        proxy_model = self.proxy_model

        for row in range(source_model.rowCount()):
            payload = source_model.row_payload(row)
            if not payload:
                continue
            source_index = source_model.index(row, SharpeningTableModel.ACTION_COLUMN)
            proxy_index = proxy_model.mapFromSource(source_index)
            if not proxy_index.isValid():
                continue

            widget = SharpeningActionsWidget(
                self.db,
                self.event_bus,
                payload.get("id"),
                payload.get("sharp_state", ""),
                payload.get("installation_state", ""),
                self.table_view,
            )
            self.table_view.setIndexWidget(proxy_index, widget)
            self._action_widgets.append(widget)

    def show_sharpen_history(self):
        dialog = KnifeSharpenHistoryDialog(self.db, self.event_bus, self)
        dialog.exec()
