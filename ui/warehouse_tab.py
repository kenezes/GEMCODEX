import logging
from typing import Optional, Any
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QPushButton,
    QLineEdit,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QAbstractItemView,
    QHeaderView,
    QMessageBox,
    QMenu,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyle,
    QApplication,
)
from PySide6.QtCore import (Qt, QAbstractTableModel, QModelIndex,
                          Signal, QEvent, QSize)
from PySide6.QtGui import QAction, QIcon, QColor, QFont

from .part_dialog import PartDialog
from .category_manager_dialog import CategoryManagerDialog
from .utils import apply_table_compact_style, open_part_folder


ROW_TYPE_ROLE = Qt.UserRole + 10


class FolderButtonDelegate(QStyledItemDelegate):
    """Рисует кнопку с иконкой папки и обрабатывает клики по ней."""

    clicked = Signal(QModelIndex)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon: Optional[QIcon] = None
        if parent:
            self._icon = parent.style().standardIcon(QStyle.SP_DirIcon)

    def paint(self, painter, option, index):  # type: ignore[override]
        if index.data(ROW_TYPE_ROLE) != 'part':
            super().paint(painter, option, index)
            return

        button_option = QStyleOptionButton()
        button_option.rect = option.rect.adjusted(4, 6, -4, -6)
        button_option.text = ""
        button_option.state = QStyle.State_Enabled
        icon = self._icon or option.widget.style().standardIcon(QStyle.SP_DirIcon)
        button_option.icon = icon
        button_option.iconSize = QSize(16, 16)
        if option.state & QStyle.State_MouseOver:
            button_option.state |= QStyle.State_MouseOver
        option.widget.style().drawControl(QStyle.CE_PushButton, button_option, painter, option.widget)

    def editorEvent(self, event, model, option, index):  # type: ignore[override]
        if index.data(ROW_TYPE_ROLE) != 'part':
            return False
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

class WarehouseTab(QWidget):
    ALL_CATEGORIES = -1
    UNCATEGORIZED = "__none__"

    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.init_ui()
        self.refresh_data()
        self.event_bus.subscribe('parts.changed', self.refresh_data)
        self.event_bus.subscribe('equipment_parts_changed', self.refresh_data)
        self.event_bus.subscribe('replacements.changed', self.refresh_data)
        logging.info("Subscribed WarehouseTab to 'parts.changed', 'equipment_parts_changed', 'replacements.changed'")

    def init_ui(self):
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        categories_panel = QWidget()
        categories_layout = QVBoxLayout(categories_panel)
        categories_layout.setContentsMargins(0, 0, 0, 0)
        categories_layout.setSpacing(6)

        categories_header = QHBoxLayout()
        categories_header.setContentsMargins(0, 0, 0, 0)
        categories_header.setSpacing(4)
        categories_label = QLabel("Категории")
        categories_label.setStyleSheet("font-weight: 500;")
        categories_header.addWidget(categories_label)
        categories_header.addStretch()
        self.category_button = QPushButton("Категории...")
        self.category_button.clicked.connect(self.manage_categories)
        categories_header.addWidget(self.category_button)
        categories_layout.addLayout(categories_header)

        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderHidden(True)
        self.category_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.category_tree.currentItemChanged.connect(self._on_category_selection_changed)
        categories_layout.addWidget(self.category_tree)

        splitter.addWidget(categories_panel)

        content_panel = QWidget()
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(6)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по наименованию/артикулу...")
        self.search_input.textChanged.connect(self.filter_data)
        control_layout.addWidget(self.search_input)
        control_layout.addStretch()
        add_button = QPushButton("Добавить запчасть")
        add_button.clicked.connect(self.add_part)
        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.refresh_data)
        control_layout.addWidget(add_button)
        control_layout.addWidget(refresh_button)
        content_layout.addLayout(control_layout)

        self.table_view = QTableView()
        self.table_model = TableModel()
        self.table_view.setModel(self.table_model)
        self._setup_table()
        content_layout.addWidget(self.table_view)

        splitter.addWidget(content_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        categories_panel.setMinimumWidth(220)

    def _setup_table(self):
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.doubleClicked.connect(self.edit_part_from_table)
        self.table_view.clicked.connect(self._on_table_clicked)
        
        # Автоширина колонок
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        header.resizeSection(0, 260)
        header.resizeSection(1, 140)
        header.resizeSection(2, 90)
        header.resizeSection(3, 100)
        header.resizeSection(4, 120)
        header.resizeSection(5, 160)
        header.resizeSection(6, 200)

        apply_table_compact_style(self.table_view)

        self.folder_delegate = FolderButtonDelegate(self.table_view)
        self.folder_delegate.clicked.connect(self.open_part_folder_from_table)
        self.table_view.setItemDelegateForColumn(TableModel.FOLDER_COLUMN, self.folder_delegate)
        self.table_view.setColumnWidth(TableModel.FOLDER_COLUMN, 100)

    def load_categories(self):
        current_selection = self._get_selected_category_token()
        categories = self.db.get_part_categories()
        lookup = {cat['id']: cat['name'] for cat in categories}
        self.table_model.set_category_lookup(lookup)

        items_map: dict[Any, QTreeWidgetItem] = {}
        self.category_tree.blockSignals(True)
        self.category_tree.clear()

        all_item = QTreeWidgetItem(["Все категории"])
        all_item.setData(0, Qt.UserRole, self.ALL_CATEGORIES)
        self.category_tree.addTopLevelItem(all_item)
        items_map[self.ALL_CATEGORIES] = all_item

        uncategorized_item = QTreeWidgetItem(["Без категории"])
        uncategorized_item.setData(0, Qt.UserRole, self.UNCATEGORIZED)
        self.category_tree.addTopLevelItem(uncategorized_item)
        items_map[self.UNCATEGORIZED] = uncategorized_item

        for cat in categories:
            item = QTreeWidgetItem([cat['name']])
            item.setData(0, Qt.UserRole, cat['id'])
            self.category_tree.addTopLevelItem(item)
            items_map[cat['id']] = item

        target = items_map.get(current_selection)
        if target is None:
            target = all_item
        self.category_tree.setCurrentItem(target)
        self.category_tree.blockSignals(False)

    def refresh_data(self, *args, **kwargs):
        logging.info("Refreshing warehouse data...")
        self.load_categories()
        parts_data = self.db.get_all_parts()
        part_ids = [part.get('id') for part in parts_data if part.get('id')]
        equipment_links = self.db.get_equipment_links_for_parts(part_ids)
        for part in parts_data:
            part_id = part.get('id')
            part['equipment_links'] = equipment_links.get(part_id, [])
        self.table_model.set_parts(parts_data)
        self.filter_data() # Применяем фильтры после обновления
        logging.info("Warehouse data refreshed.")

    def open_part_folder_from_table(self, index: QModelIndex):
        row_data = self.table_model.get_row(index.row())
        if not row_data:
            return
        name = row_data.get('name', '')
        sku = row_data.get('sku', '')
        open_part_folder(name or '', sku or '')

    def filter_data(self):
        search_text = self.search_input.text()
        category_token = self._get_selected_category_token()

        self.table_model.set_filters(search_text, category_token)

    def add_part(self):
        dialog = PartDialog(self.db, self.event_bus, parent=self)
        if dialog.exec():
            self.refresh_data()

    def edit_part_from_table(self, index: QModelIndex):
        part_id = self.table_model.get_id_from_index(index)
        if part_id is not None:
            dialog = PartDialog(self.db, self.event_bus, part_id=part_id, parent=self)
            if dialog.exec():
                self.refresh_data()

    def _on_table_clicked(self, index: QModelIndex):
        if not index.isValid():
            return

        row_type = self.table_model.get_row_type(index.row())
        if row_type != 'part':
            return

        part_id = self.table_model.get_id_from_index(index)
        part = self.table_model.get_row(index.row()) or {}

        if index.column() == 0 and part.get('equipment_links') and isinstance(part_id, int):
            self.table_model.toggle_part_expansion(part_id)

    def delete_part(self, part_id):
        part = self.db.get_part_by_id(part_id)
        if not part:
            QMessageBox.warning(self, "Ошибка", "Запчасть не найдена.")
            return

        reply = QMessageBox.question(self, "Удаление запчасти",
            f"Вы уверены, что хотите удалить запчасть '{part['name']} ({part['sku']})'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            success, message = self.db.delete_part(part_id)
            if success:
                QMessageBox.information(self, "Успех", message)
                self.event_bus.emit('parts.changed')
            else:
                QMessageBox.warning(self, "Ошибка удаления", message)

    def manage_categories(self):
        dialog = CategoryManagerDialog(self.db, self)
        if dialog.exec():
            self.event_bus.emit('parts.changed') # Обновляем всё, так как категории могли измениться

    def _get_selected_category_token(self) -> Any:
        item = self.category_tree.currentItem()
        if not item:
            return self.ALL_CATEGORIES
        value = item.data(0, Qt.UserRole)
        if value is None:
            return self.UNCATEGORIZED
        return value

    def _on_category_selection_changed(self, current, previous):
        self.filter_data()

    def show_context_menu(self, pos):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return

        row = index.row()
        if self.table_model.get_row_type(row) != 'part':
            return

        part_id = self.table_model.get_id_from_index(index)
        if part_id is None:
            return

        menu = QMenu(self)

        selected_rows = [
            idx.row()
            for idx in self.table_view.selectionModel().selectedRows()
            if self.table_model.get_row_type(idx.row()) == 'part'
        ]
        if row not in selected_rows:
            selected_rows.append(row)

        selected_part_ids = self.table_model.get_part_ids_from_rows(selected_rows)
        unique_part_ids = sorted(set(selected_part_ids))

        if len(unique_part_ids) >= 2:
            analogs_action = QAction("Сделать аналогами", self)
            analogs_action.triggered.connect(lambda: self.make_parts_analogs(unique_part_ids))
            menu.addAction(analogs_action)
            menu.addSeparator()

        edit_action = QAction("Редактировать", self)
        edit_action.triggered.connect(lambda: self.edit_part_from_table(index))
        menu.addAction(edit_action)

        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(lambda: self.delete_part(part_id))
        menu.addAction(delete_action)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def make_parts_analogs(self, part_ids: list[int]):
        success, message = self.db.set_parts_as_analogs(part_ids)
        if success:
            QMessageBox.information(self, "Аналоги", message)
            self.event_bus.emit('parts.changed')
            self.refresh_data()
        else:
            QMessageBox.warning(self, "Аналоги", message)


class TableModel(QAbstractTableModel):
    FOLDER_COLUMN = 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = ['Наименование', 'Артикул', 'Остаток, шт.', 'Минимум, шт.', 'Цена', 'Категория', 'Оборудование', '']
        self._raw_parts: list[dict] = []
        self._rows: list[dict] = []
        self._search_text: str = ""
        self._category_id: Any = WarehouseTab.ALL_CATEGORIES
        self._category_lookup: dict[Any, str] = {}
        self._analog_color_cache: dict[int, QColor] = {}
        self._expanded_parts: set[int] = set()
        style = QApplication.style()
        self._arrow_collapsed = style.standardIcon(QStyle.SP_ArrowRight)
        self._arrow_expanded = style.standardIcon(QStyle.SP_ArrowDown)

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row_entry = self._rows[index.row()]
        row_type = row_entry.get('row_type')
        column = index.column()

        if role == ROW_TYPE_ROLE:
            return row_type

        if row_type == 'category':
            if role == Qt.DisplayRole and column == 0:
                return row_entry.get('category_name', '')
            if role == Qt.FontRole:
                font = QFont()
                font.setBold(True)
                return font
            if role == Qt.BackgroundRole:
                return QColor('#f5f5f5')
            if role == Qt.TextAlignmentRole:
                return Qt.AlignLeft | Qt.AlignVCenter
            return None

        if row_type == 'equipment':
            equipment = row_entry.get('equipment', {})
            if role == Qt.DisplayRole:
                if column == 0:
                    return f"↳ {equipment.get('equipment_name', '')}"
                if column == 1:
                    return equipment.get('equipment_sku') or 'б/а'
                if column == 2:
                    return equipment.get('installed_qty')
                if column == 3:
                    return equipment.get('last_replacement_date') or ''
                if column == 4:
                    return equipment.get('equipment_comment') or ''
                return ""
            if role == Qt.TextAlignmentRole:
                if column == 2:
                    return Qt.AlignCenter
                if column == self.FOLDER_COLUMN:
                    return Qt.AlignCenter
            if role == Qt.BackgroundRole:
                return QColor('#fafafa')
            return None

        part = row_entry.get('part', {})
        analog_group_id = part.get('analog_group_id')
        analog_group_size = part.get('analog_group_size') or 0

        if role == Qt.DisplayRole:
            if column == 0:
                return part.get('name')
            if column == 1:
                return part.get('sku')
            if column == 2:
                return part.get('qty')
            if column == 3:
                return part.get('min_qty')
            if column == 4:
                return f"{part.get('price', 0):.2f}"
            if column == 5:
                return part.get('category_name')
            if column == 6:
                return part.get('equipment_list', 'нет')
            if column == self.FOLDER_COLUMN:
                return ""

        if role == Qt.DecorationRole and column == 0:
            part_id = part.get('id')
            if part.get('equipment_links') and isinstance(part_id, int):
                return self._arrow_expanded if part_id in self._expanded_parts else self._arrow_collapsed

        if role == Qt.UserRole:
            return part.get('id')

        if role == Qt.UserRole + 1:
            return part

        if role == Qt.TextAlignmentRole:
            if column in (2, 3, 4):
                return Qt.AlignCenter
            if column == self.FOLDER_COLUMN:
                return Qt.AlignCenter

        if role == Qt.BackgroundRole and analog_group_id and analog_group_size and analog_group_size > 1:
            return self._get_analog_color(int(analog_group_id))

        if role == Qt.ToolTipRole:
            if column == self.FOLDER_COLUMN:
                return "Открыть папку запчасти"
            analog_names = part.get('analog_names')
            if analog_names and column in (0, 1):
                return f"Аналоги: {analog_names}"

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._headers[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        if self._rows[index.row()].get('row_type') == 'category':
            return Qt.ItemIsEnabled
        return super().flags(index)

    def set_parts(self, parts: list[dict]):
        self._raw_parts = parts or []
        current_ids = {part.get('id') for part in self._raw_parts if isinstance(part.get('id'), int)}
        self._expanded_parts.intersection_update(current_ids)
        self._rebuild_rows()

    def set_category_lookup(self, lookup: dict[Any, str]):
        self._category_lookup = lookup or {}
        self._rebuild_rows()

    def set_filters(self, search_text: str, category_id: Any):
        self._search_text = (search_text or "").lower()
        self._category_id = category_id
        self._rebuild_rows()

    def get_id_from_index(self, index: QModelIndex):
        if not index.isValid():
            return None
        row_entry = self._rows[index.row()]
        if row_entry.get('row_type') != 'part':
            return None
        part = row_entry.get('part') or {}
        return part.get('id')

    def get_row(self, row: int):
        if 0 <= row < len(self._rows):
            row_entry = self._rows[row]
            if row_entry.get('row_type') == 'part':
                return row_entry.get('part')
        return None

    def get_row_type(self, row: int):
        if 0 <= row < len(self._rows):
            return self._rows[row].get('row_type')
        return None

    def get_part_ids_from_rows(self, rows: list[int]) -> list[int]:
        ids: list[int] = []
        for row in rows:
            if 0 <= row < len(self._rows):
                entry = self._rows[row]
                if entry.get('row_type') == 'part':
                    part = entry.get('part') or {}
                    part_id = part.get('id')
                    if isinstance(part_id, int):
                        ids.append(part_id)
        return ids

    def toggle_part_expansion(self, part_id: int):
        row_index = self._find_row_index(part_id)
        if row_index is None:
            return

        if part_id in self._expanded_parts:
            self._collapse_part(row_index)
            self._expanded_parts.remove(part_id)
            self.dataChanged.emit(self.index(row_index, 0), self.index(row_index, 0))
        else:
            self._expanded_parts.add(part_id)
            self._expand_part(row_index)
            self.dataChanged.emit(self.index(row_index, 0), self.index(row_index, 0))

    def _rebuild_rows(self):
        rows = self._build_rows(include_expanded=True)

        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def _build_rows(self, include_expanded: bool) -> list[dict]:
        filtered: list[dict] = []
        for part in self._raw_parts:
            if not self._matches_category(part):
                continue
            if self._search_text:
                name = str(part.get('name') or '').lower()
                sku = str(part.get('sku') or '').lower()
                if self._search_text not in name and self._search_text not in sku:
                    continue
            filtered.append(part)

        filtered.sort(key=lambda item: (
            (item.get('category_name') or '').lower(),
            (item.get('name') or '').lower(),
        ))

        rows: list[dict] = []
        current_category: Optional[str] = None

        for part in filtered:
            category_name = part.get('category_name') or ''
            if category_name != current_category:
                label = category_name if category_name else 'Без категории'
                rows.append({'row_type': 'category', 'category_name': label})
                current_category = category_name
            rows.append({'row_type': 'part', 'part': part})
            part_id = part.get('id')
            if include_expanded and isinstance(part_id, int) and part_id in self._expanded_parts:
                for equipment in part.get('equipment_links') or []:
                    rows.append({
                        'row_type': 'equipment',
                        'equipment': equipment,
                        'parent_part_id': part_id,
                    })
        return rows

    def _find_row_index(self, part_id: int) -> Optional[int]:
        for idx, entry in enumerate(self._rows):
            if entry.get('row_type') == 'part':
                part = entry.get('part') or {}
                if part.get('id') == part_id:
                    return idx
        return None

    def _expand_part(self, row_index: int):
        part = self.table_row_to_part(row_index)
        if not part:
            return
        equipment_links = part.get('equipment_links') or []
        if not equipment_links:
            return

        insert_position = row_index + 1
        count = len(equipment_links)
        self.beginInsertRows(QModelIndex(), insert_position, insert_position + count - 1)
        inserts = [{
            'row_type': 'equipment',
            'equipment': equipment,
            'parent_part_id': part.get('id'),
        } for equipment in equipment_links]
        self._rows[insert_position:insert_position] = inserts
        self.endInsertRows()

    def _collapse_part(self, row_index: int):
        part = self.table_row_to_part(row_index)
        if not part:
            return

        remove_from = row_index + 1
        remove_to = remove_from - 1
        while remove_to + 1 < len(self._rows):
            entry = self._rows[remove_to + 1]
            if entry.get('row_type') != 'equipment':
                break
            if entry.get('parent_part_id') != part.get('id'):
                break
            remove_to += 1

        if remove_to < remove_from:
            return

        self.beginRemoveRows(QModelIndex(), remove_from, remove_to)
        del self._rows[remove_from:remove_to + 1]
        self.endRemoveRows()

    def table_row_to_part(self, row_index: int) -> Optional[dict]:
        if 0 <= row_index < len(self._rows):
            entry = self._rows[row_index]
            if entry.get('row_type') == 'part':
                return entry.get('part')
        return None

    def _matches_category(self, part: dict) -> bool:
        if self._category_id == WarehouseTab.ALL_CATEGORIES:
            return True
        part_category = part.get('category_id')
        if self._category_id == WarehouseTab.UNCATEGORIZED:
            return part_category in (None, "", 0)
        return part_category == self._category_id

    def _get_analog_color(self, group_id: int) -> QColor:
        color = self._analog_color_cache.get(group_id)
        if color is None:
            hue = (abs(group_id * 47) % 360)
            base_color = QColor.fromHsv(hue, 80, 255)
            color = base_color.lighter(160)
            self._analog_color_cache[group_id] = color
        return color

