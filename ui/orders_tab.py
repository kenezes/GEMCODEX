import logging
from urllib.parse import quote
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QToolBar, QTableView, QAbstractItemView,
                             QHeaderView, QMessageBox, QCheckBox, QHBoxLayout, QMenu, QPushButton, QSizePolicy,
                             QLabel, QLineEdit, QStyledItemDelegate, QStyleOptionButton, QStyle)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex, Signal, QEvent, QUrl, QSize
from PySide6.QtGui import (QAction, QDesktopServices, QGuiApplication, QColor, QPalette,
                         QFont, QPixmap, QPainter, QIcon)

from .order_dialog import OrderDialog
from ui.utils import db_string_to_ui_string, apply_table_compact_style


class ActionButtonDelegate(QStyledItemDelegate):
    """Рисует кнопку с иконкой телефона и обрабатывает клики по ней."""

    PHONE_ICON_SIZE = QSize(18, 18)

    clicked = Signal(QModelIndex)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phone_icon = self._create_phone_icon()

    @staticmethod
    def _create_phone_icon() -> QIcon:
        pixmap = QPixmap(36, 36)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont()
        font.setPointSize(20)
        painter.setFont(font)
        painter.setPen(Qt.white)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "📞")
        painter.end()
        return QIcon(pixmap)

    def paint(self, painter, option, index):  # type: ignore[override]
        button_option = QStyleOptionButton()
        button_option.rect = option.rect.adjusted(4, 6, -4, -6)
        button_option.text = ""
        button_option.state = QStyle.State_Enabled
        palette = QPalette(option.palette)
        is_notified = bool(index.data(Qt.UserRole + 2))
        palette.setColor(QPalette.Button, QColor("#2e7d32") if is_notified else QColor("#c62828"))
        palette.setColor(QPalette.ButtonText, Qt.white)
        button_option.palette = palette
        button_option.icon = self._phone_icon
        button_option.iconSize = self.PHONE_ICON_SIZE
        if option.state & QStyle.State_MouseOver:
            button_option.state |= QStyle.State_MouseOver
        option.widget.style().drawControl(QStyle.CE_PushButton, button_option, painter, option.widget)

    def editorEvent(self, event, model, option, index):  # type: ignore[override]
        if event.type() == QEvent.MouseButtonPress and option.rect.contains(event.pos()):
            if hasattr(event, 'button') and event.button() != Qt.LeftButton:
                return False
            return True
        if event.type() == QEvent.MouseButtonRelease and option.rect.contains(event.pos()):
            if hasattr(event, 'button') and event.button() != Qt.LeftButton:
                return False
            self.clicked.emit(index)
            return True
        return False

class OrdersTableModel(QAbstractTableModel):
    """Модель данных для таблицы заказов."""

    COUNTERPARTY_COLUMN = 0
    STATUS_COLUMN = 6
    NOTIFIED_COLUMN = 8
    ACTION_COLUMN = 9

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
            "Уведомлён",
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
            if col == 8: return ""
            if col == 9: return ""

        if role == Qt.CheckStateRole and col == self.NOTIFIED_COLUMN:
            return Qt.Checked if row_data['id'] in self._notified_orders else Qt.Unchecked

        if role == Qt.TextAlignmentRole and col == self.ACTION_COLUMN:
            return Qt.AlignCenter
        if role == Qt.TextAlignmentRole and col == self.NOTIFIED_COLUMN:
            return Qt.AlignCenter

        if role == Qt.UserRole:
            return row_data['id']

        if role == Qt.UserRole + 1:
            return row_data

        if role == Qt.UserRole + 2 and index.column() == self.ACTION_COLUMN:
            return row_data['id'] in self._notified_orders

        if role == Qt.ToolTipRole and col == self.ACTION_COLUMN:
            return "Сообщить водителю о поставке"

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
        if index.column() == self.NOTIFIED_COLUMN:
            return Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable
        return super().flags(index)

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):
        if not index.isValid():
            return False

        if index.column() == self.NOTIFIED_COLUMN and role == Qt.CheckStateRole:
            order_id = self._data[index.row()].get('id')
            if order_id is None:
                return False

            if value == Qt.Checked:
                if order_id not in self._notified_orders:
                    self._notified_orders.add(order_id)
            else:
                self._notified_orders.discard(order_id)

            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            action_index = self.index(index.row(), self.ACTION_COLUMN)
            self.dataChanged.emit(action_index, action_index, [Qt.DisplayRole, Qt.UserRole + 2])
            return True

        return super().setData(index, value, role)

    def load_data(self, data):
        self.beginResetModel()
        self._data = data
        current_ids = {row.get('id') for row in data if row.get('id') is not None}
        self._notified_orders.intersection_update(current_ids)
        self.endResetModel()

    def get_row(self, row_index: int) -> dict | None:
        if 0 <= row_index < len(self._data):
            return self._data[row_index]
        return None

    def mark_notified(self, order_id: int):
        if order_id in self._notified_orders:
            return
        for row_index, row in enumerate(self._data):
            if row.get('id') == order_id:
                self._notified_orders.add(order_id)
                action_index = self.index(row_index, self.ACTION_COLUMN)
                notified_index = self.index(row_index, self.NOTIFIED_COLUMN)
                self.dataChanged.emit(notified_index, notified_index, [Qt.CheckStateRole])
                self.dataChanged.emit(action_index, action_index, [Qt.DisplayRole, Qt.UserRole + 2])
                break

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
        status = self.sourceModel().data(index)
        return status not in ('принят', 'отменён')

class OrdersTab(QWidget):
    """Вкладка для управления заказами."""
    def __init__(self, db, event_bus, main_window):
        super().__init__()
        self.db = db
        self.event_bus = event_bus
        self.main_window = main_window
        
        self.init_ui()
        self.event_bus.subscribe("orders.changed", self.refresh_data)
        self.event_bus.subscribe("counterparties.changed", self.refresh_data) # На случай переименования
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
        self.edit_order_button = QPushButton("Редактировать")
        self.delete_order_button = QPushButton("Удалить") # Новая кнопка
        self.accept_delivery_button = QPushButton("Принять поставку")
        self.refresh_button = QPushButton("Обновить")
        
        self.hide_completed_checkbox = QCheckBox("Скрыть завершенные")
        
        self.toolbar.addWidget(self.new_order_button)
        self.toolbar.addWidget(self.edit_order_button)
        self.toolbar.addWidget(self.delete_order_button) # Добавляем кнопку
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.accept_delivery_button)
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
        self.edit_order_button.clicked.connect(self.edit_selected_order)
        self.delete_order_button.clicked.connect(self.delete_selected_order) # Подключаем сигнал
        self.accept_delivery_button.clicked.connect(self.accept_delivery_for_selected)
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
        header.setStretchLastSection(False)

        apply_table_compact_style(self.table_view)

        self.action_delegate = ActionButtonDelegate(self.table_view)
        self.action_delegate.clicked.connect(self._handle_action_button)
        self.table_view.setItemDelegateForColumn(OrdersTableModel.ACTION_COLUMN, self.action_delegate)
        self.table_view.setColumnWidth(OrdersTableModel.NOTIFIED_COLUMN, 110)
        self.table_view.setColumnWidth(OrdersTableModel.ACTION_COLUMN, 72)

    def refresh_data(self):
        logging.info("Обновление данных на вкладке 'Заказы'")
        orders_data = self.db.get_all_orders_with_counterparty()
        self.base_model.load_data(orders_data)
        self.table_view.resizeColumnToContents(OrdersTableModel.ACTION_COLUMN)
        current_width = self.table_view.columnWidth(OrdersTableModel.ACTION_COLUMN)
        if current_width < 72:
            self.table_view.setColumnWidth(OrdersTableModel.ACTION_COLUMN, 72)
        self.table_view.resizeColumnToContents(OrdersTableModel.NOTIFIED_COLUMN)
        notified_width = self.table_view.columnWidth(OrdersTableModel.NOTIFIED_COLUMN)
        if notified_width < 100:
            self.table_view.setColumnWidth(OrdersTableModel.NOTIFIED_COLUMN, 100)

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
            reply = QMessageBox.question(self, "Подтверждение",
                                       "Принять поставку по этому заказу? Остатки на складе будут увеличены.",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                success, message = self.db.accept_delivery(order_id)
                if success:
                    QMessageBox.information(self, "Успех", message)
                    self.event_bus.emit("orders.changed")
                    self.event_bus.emit("parts.changed")
                else:
                    QMessageBox.warning(self, "Внимание", message)
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

    def _handle_action_button(self, proxy_index: QModelIndex):
        source_index = self.proxy_model.mapToSource(proxy_index)
        row_data = self.base_model.get_row(source_index.row())
        if not row_data:
            return

        driver_number_raw = self.driver_phone_input.text().strip()
        digits_only = ''.join(ch for ch in driver_number_raw if ch.isdigit())
        if not digits_only:
            QMessageBox.warning(self, "Номер водителя", "Укажите номер водителя, чтобы отправить сообщение.")
            return
        if len(digits_only) == 11 and digits_only.startswith('8'):
            digits_only = '7' + digits_only[1:]

        invoice_date = db_string_to_ui_string(row_data.get('invoice_date'))
        invoice_line = f"Счет №{row_data.get('invoice_no', '')}"
        if invoice_date:
            invoice_line = f"{invoice_line} от {invoice_date}"

        address = row_data.get('delivery_address') or row_data.get('counterparty_address') or ""
        message = (
            "Привет, можно забирать:\n"
            f"{row_data.get('counterparty_name', '')}\n"
            f"{invoice_line}\n"
            f"Адрес: {address}"
        )

        QGuiApplication.clipboard().setText(message)
        logging.info("Скопировано сообщение по заказу #%s для отправки водителю", row_data.get('id'))

        url = QUrl(f"https://wa.me/{digits_only}?text={quote(message, safe='')}")
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(self, "Открытие WhatsApp", "Не удалось открыть чат WhatsApp.")
        order_id = row_data.get('id')
        if order_id is not None:
            self.base_model.mark_notified(order_id)

