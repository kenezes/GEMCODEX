import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QMessageBox, QSplitter, QTreeWidget, QTreeWidgetItem,
                             QTableWidget, QTableWidgetItem, QHeaderView, QToolButton,
                             QLabel, QPlainTextEdit, QStyle, QCheckBox, QMenu)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, QSize

from .equipment_category_manager_dialog import EquipmentCategoryManagerDialog
from .equipment_dialog import EquipmentDialog
from .attach_part_dialog import AttachPartDialog
from .edit_attached_part_dialog import EditAttachedPartDialog
from .replacement_dialog import ReplacementDialog
from .task_dialog import TaskDialog
from .utils import (
    open_part_folder as open_part_folder_fs,
    open_equipment_folder as open_equipment_folder_fs,
    move_part_folder_on_rename,
)

class EquipmentTab(QWidget):
    def __init__(self, db, event_bus, parent=None):
        super().__init__(parent)
        self.db = db
        self.event_bus = event_bus
        self.current_equipment_id = None
        self._comment_updating = False
        self._comment_dirty = False
        self._expanded_components: set[int] = set()
        self._row_parts: list[dict | None] = []
        self.init_ui()
        self.load_tree_data()
        self.update_buttons_state()

        self.event_bus.subscribe('equipment_parts_changed', self.on_equipment_parts_changed)
        self.event_bus.subscribe('parts.changed', self.on_parts_changed)
        self.event_bus.subscribe('equipment.changed', self.load_tree_data)

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # Левая панель (дерево)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        tree_buttons_layout = QHBoxLayout()
        tree_buttons_layout.setSpacing(4)

        icon_size = QSize(24, 24)

        def _create_tool_button(icon: QStyle.StandardPixmap, tooltip: str) -> QToolButton:
            button = QToolButton()
            button.setIcon(self.style().standardIcon(icon))
            button.setToolTip(tooltip)
            button.setAutoRaise(True)
            button.setIconSize(icon_size)
            return button

        self.manage_categories_button = _create_tool_button(QStyle.SP_FileDialogDetailedView, "Управление категориями")
        self.add_equipment_button = _create_tool_button(QStyle.SP_FileDialogNewFolder, "Добавить оборудование")
        self.edit_equipment_button = _create_tool_button(QStyle.SP_FileDialogContentsView, "Редактировать выбранный элемент")
        self.delete_equipment_button = _create_tool_button(QStyle.SP_TrashIcon, "Удалить выбранный элемент")
        self.open_equipment_folder_button = _create_tool_button(QStyle.SP_DirOpenIcon, "Открыть папку оборудования")

        tree_buttons_layout.addWidget(self.manage_categories_button)
        tree_buttons_layout.addWidget(self.add_equipment_button)
        tree_buttons_layout.addWidget(self.edit_equipment_button)
        tree_buttons_layout.addWidget(self.delete_equipment_button)
        tree_buttons_layout.addWidget(self.open_equipment_folder_button)
        tree_buttons_layout.addStretch()

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)

        left_layout.addLayout(tree_buttons_layout)

        self.add_equipment_main_button = QPushButton("Добавить оборудование")
        self.add_equipment_main_button.setCursor(Qt.PointingHandCursor)
        self.add_equipment_main_button.clicked.connect(self.add_equipment)
        left_layout.addWidget(self.add_equipment_main_button)

        self.only_requires_equipment_checkbox = QCheckBox("Только оборудование с требующей замену запчастью")
        self.only_requires_equipment_checkbox.setToolTip(
            "Отображать только те аппараты, у которых есть помеченные как требующие замены запчасти."
        )
        left_layout.addWidget(self.only_requires_equipment_checkbox)
        left_layout.addWidget(self.tree)

        comment_controls_layout = QHBoxLayout()
        self.comment_label = QLabel("Комментарий:")
        self.save_comment_button = _create_tool_button(QStyle.SP_DialogSaveButton, "Сохранить комментарий")
        self.save_comment_button.setEnabled(False)
        comment_controls_layout.addWidget(self.comment_label)
        comment_controls_layout.addStretch()
        comment_controls_layout.addWidget(self.save_comment_button)

        self.comment_edit = QPlainTextEdit()
        self.comment_edit.setPlaceholderText("Введите комментарий к выбранному оборудованию")
        self.comment_edit.setMaximumHeight(100)
        self.comment_edit.setEnabled(False)

        left_layout.addLayout(comment_controls_layout)
        left_layout.addWidget(self.comment_edit)

        # Правая панель (таблица запчастей)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        parts_buttons_layout = QHBoxLayout()
        self.add_part_button = QPushButton("Добавить запчасть")
        parts_buttons_layout.addWidget(self.add_part_button)
        parts_buttons_layout.addStretch()
        
        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(5)
        self.parts_table.setHorizontalHeaderLabels([
            "Наименование",
            "Артикул",
            "Установлено, шт.",
            "Последняя замена",
            "Действия",
        ])
        self.parts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.parts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.parts_table.setContextMenuPolicy(Qt.CustomContextMenu)

        header = self.parts_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)

        self.only_requires_parts_checkbox = QCheckBox("Только требующие замену")
        self.only_requires_parts_checkbox.setToolTip(
            "Скрыть элементы, которые не помечены как требующие замены."
        )
        parts_buttons_layout.addWidget(self.only_requires_parts_checkbox)
        right_layout.addLayout(parts_buttons_layout)
        right_layout.addWidget(self.parts_table)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        left_panel.setMinimumWidth(180)
        splitter.setSizes([240, 760])
        main_layout.addWidget(splitter)

        # Подключения
        self.manage_categories_button.clicked.connect(self.manage_categories)
        self.add_equipment_button.clicked.connect(self.add_equipment)
        self.edit_equipment_button.clicked.connect(self.edit_equipment)
        self.delete_equipment_button.clicked.connect(self.delete_equipment)
        self.tree.currentItemChanged.connect(self.on_tree_selection_changed)
        self.add_part_button.clicked.connect(self.attach_part)
        self.open_equipment_folder_button.clicked.connect(self.open_selected_equipment_folder)
        self.comment_edit.textChanged.connect(self.on_comment_text_changed)
        self.save_comment_button.clicked.connect(self.save_equipment_comment)
        self.only_requires_equipment_checkbox.toggled.connect(self.on_equipment_filter_toggled)
        self.only_requires_parts_checkbox.toggled.connect(self.on_parts_filter_toggled)
        self.parts_table.customContextMenuRequested.connect(self._show_parts_context_menu)

    def update_buttons_state(self):
        selected_item = self.tree.currentItem()
        is_item_selected = selected_item is not None
        item_data = selected_item.data(0, Qt.UserRole) if is_item_selected else {}

        is_category_selected = is_item_selected and item_data.get('type') == 'category'
        is_equipment_selected = is_item_selected and item_data.get('type') == 'equipment'

        self.edit_equipment_button.setEnabled(is_item_selected)
        self.delete_equipment_button.setEnabled(is_item_selected)
        self.add_part_button.setEnabled(is_equipment_selected)
        self.open_equipment_folder_button.setEnabled(is_equipment_selected)

    def on_equipment_filter_toggled(self, checked):
        self.load_tree_data()

    def on_parts_filter_toggled(self, checked):
        if self.current_equipment_id:
            self.load_parts_for_equipment(self.current_equipment_id)
        else:
            self.parts_table.setRowCount(0)

    def load_tree_data(self, *args, **kwargs):
        selected_equipment_id = self.current_equipment_id
        self.tree.clear()
        self.update_comment_panel(None)

        categories = self.db.get_equipment_categories()
        equipment_list = self.db.get_all_equipment()
        filter_active = self.only_requires_equipment_checkbox.isChecked()
        equipment_with_flags = self.db.get_equipment_ids_with_replacement_flag()

        equipment_by_parent = {}
        for eq in equipment_list:
            parent_id = eq['parent_id']
            equipment_by_parent.setdefault(parent_id, []).append(eq)

        for cat in categories:
            cat_item = QTreeWidgetItem(self.tree, [cat['name']])
            cat_item.setData(0, Qt.UserRole, {'type': 'category', 'id': cat['id']})

            top_level_equipment = [
                eq for eq in equipment_list if eq['category_id'] == cat['id'] and eq['parent_id'] is None
            ]

            has_children = False
            for eq in top_level_equipment:
                if self._add_equipment_node(cat_item, eq, equipment_by_parent, equipment_with_flags, filter_active):
                    has_children = True

            if not has_children:
                index = self.tree.indexOfTopLevelItem(cat_item)
                self.tree.takeTopLevelItem(index)

        self.tree.expandAll()

        if selected_equipment_id:
            item = self._find_tree_item_by_equipment_id(selected_equipment_id)
            if item:
                self.tree.setCurrentItem(item)
                self.current_equipment_id = selected_equipment_id
                self.update_comment_panel(item)
                self.load_parts_for_equipment(selected_equipment_id)
            else:
                self.current_equipment_id = None
                self.parts_table.setRowCount(0)
        else:
            self.current_equipment_id = None
            self.parts_table.setRowCount(0)

        self.update_buttons_state()

    def _add_equipment_node(
        self,
        parent_item,
        equipment_data,
        equipment_by_parent,
        equipment_with_flags,
        filter_active,
    ):
        if filter_active and not self._equipment_matches_filter(
            equipment_data['id'], equipment_by_parent, equipment_with_flags
        ):
            return False

        display_text = f"{equipment_data['name']} ({equipment_data['sku'] or 'б/а'})"
        eq_item = QTreeWidgetItem(parent_item, [display_text])
        eq_item.setData(0, Qt.UserRole, {
            'type': 'equipment',
            'id': equipment_data['id'],
            'name': equipment_data['name'],
            'sku': equipment_data.get('sku'),
            'comment': equipment_data.get('comment')
        })

        children = equipment_by_parent.get(equipment_data['id'], [])
        for child in children:
            self._add_equipment_node(eq_item, child, equipment_by_parent, equipment_with_flags, filter_active)

        return True

    def _equipment_matches_filter(self, equipment_id, equipment_by_parent, equipment_with_flags):
        if equipment_id in equipment_with_flags:
            return True

        for child in equipment_by_parent.get(equipment_id, []):
            if self._equipment_matches_filter(child['id'], equipment_by_parent, equipment_with_flags):
                return True

        return False

    def _find_tree_item_by_equipment_id(self, equipment_id):
        if equipment_id is None:
            return None

        def _iter_items(parent):
            count = parent.childCount()
            for index in range(count):
                yield parent.child(index)

        stack = []
        for index in range(self.tree.topLevelItemCount()):
            stack.append(self.tree.topLevelItem(index))

        while stack:
            item = stack.pop()
            item_data = item.data(0, Qt.UserRole) or {}
            if item_data.get('type') == 'equipment' and item_data.get('id') == equipment_id:
                return item
            stack.extend(_iter_items(item))

        return None

    def on_tree_selection_changed(self, current, previous):
        self.update_buttons_state()
        self.update_comment_panel(current)
        if current:
            item_data = current.data(0, Qt.UserRole)
            if item_data and item_data.get('type') == 'equipment':
                self.current_equipment_id = item_data['id']
                self.load_parts_for_equipment(self.current_equipment_id)
            else:
                self.current_equipment_id = None
                self.parts_table.setRowCount(0)
        else:
            self.current_equipment_id = None
            self.parts_table.setRowCount(0)

    def update_comment_panel(self, current_item):
        self._comment_updating = True
        try:
            if not current_item:
                self.comment_edit.clear()
                self.comment_edit.setEnabled(False)
                self.comment_label.setText("Комментарий (выберите оборудование):")
                self.save_comment_button.setEnabled(False)
                self._comment_dirty = False
                return

            item_data = current_item.data(0, Qt.UserRole) or {}
            if item_data.get('type') == 'equipment':
                comment_text = item_data.get('comment') or ""
                self.comment_edit.setPlainText(comment_text)
                self.comment_edit.setEnabled(True)
                self.comment_label.setText("Комментарий:")
                self._comment_dirty = False
                self.save_comment_button.setEnabled(False)
            else:
                self.comment_edit.clear()
                self.comment_edit.setEnabled(False)
                self.comment_label.setText("Комментарий (выберите оборудование):")
                self.save_comment_button.setEnabled(False)
                self._comment_dirty = False
        finally:
            self._comment_updating = False

    def on_comment_text_changed(self):
        if self._comment_updating or not self.comment_edit.isEnabled():
            return
        self._comment_dirty = True
        self.save_comment_button.setEnabled(True)

    def save_equipment_comment(self):
        if not self.current_equipment_id or not self._comment_dirty:
            return

        comment_text = self.comment_edit.toPlainText().strip()
        success, message = self.db.update_equipment_comment(self.current_equipment_id, comment_text)
        if success:
            selected_item = self.tree.currentItem()
            if selected_item:
                item_data = selected_item.data(0, Qt.UserRole) or {}
                item_data['comment'] = comment_text
                selected_item.setData(0, Qt.UserRole, item_data)
            self._comment_dirty = False
            self.save_comment_button.setEnabled(False)
            QMessageBox.information(self, "Комментарий сохранен", message)
        else:
            QMessageBox.critical(self, "Ошибка", message)

    def load_parts_for_equipment(self, equipment_id):
        self.parts_table.setRowCount(0)
        self.parts_table.clearSpans()
        self._row_parts.clear()

        if equipment_id is None:
            return

        part_tree = self._build_part_tree(equipment_id, level=0, parent_equipment_id=None)
        visible_part_ids = self._collect_part_ids(part_tree)
        if visible_part_ids:
            self._expanded_components.intersection_update(visible_part_ids)

        filter_active = self.only_requires_parts_checkbox.isChecked()
        if filter_active:
            part_tree = self._filter_part_tree(part_tree)

        self._populate_parts_table(part_tree)

    def _build_part_tree(self, equipment_id: int, level: int, parent_equipment_id: int | None) -> list[dict]:
        tree: list[dict] = []
        for part in self.db.get_parts_for_equipment(equipment_id):
            component_equipment_id = part.get('component_equipment_id')
            entry: dict = {
                'equipment_part_id': part['equipment_part_id'],
                'part_id': part['part_id'],
                'part_name': part['part_name'],
                'part_sku': part.get('part_sku'),
                'installed_qty': part['installed_qty'],
                'requires_replacement': part.get('requires_replacement'),
                'category_name': part.get('category_name'),
                'last_replacement_date': part.get('last_replacement_date') or '',
                'equipment_id': equipment_id,
                'component_equipment_id': component_equipment_id,
                'level': level,
                'parent_equipment_id': parent_equipment_id,
            }

            children: list[dict] = []
            if component_equipment_id:
                children = self._build_part_tree(component_equipment_id, level + 1, equipment_id)
            entry['children'] = children
            entry['has_descendants'] = bool(children)
            tree.append(entry)
        return tree

    def _collect_part_ids(self, part_tree: list[dict]) -> set[int]:
        ids: set[int] = set()
        for entry in part_tree:
            equipment_part_id = entry.get('equipment_part_id')
            if equipment_part_id:
                ids.add(equipment_part_id)
            ids.update(self._collect_part_ids(entry.get('children', [])))
        return ids

    def _filter_part_tree(self, part_tree: list[dict]) -> list[dict]:
        filtered: list[dict] = []
        for entry in part_tree:
            filtered_children = self._filter_part_tree(entry.get('children', []))
            include_entry = bool(entry.get('requires_replacement'))
            if filtered_children:
                include_entry = True
            if include_entry:
                new_entry = entry.copy()
                new_entry['children'] = filtered_children
                filtered.append(new_entry)
        return filtered

    def _populate_parts_table(self, part_tree: list[dict]):
        current_category = None
        row_index = 0
        part_counter = 1

        for entry in part_tree:
            if entry.get('level', 0) == 0:
                category_name = entry.get('category_name') or 'Без категории'
                if category_name != current_category:
                    row_index = self._insert_category_header(row_index, category_name)
                    current_category = category_name
            row_index, part_counter = self._insert_part_row(entry, row_index, part_counter)

        self.parts_table.resizeColumnsToContents()

    def _insert_category_header(self, row_index: int, category_name: str) -> int:
        self.parts_table.insertRow(row_index)
        header_item = QTableWidgetItem(category_name)
        header_font = header_item.font()
        header_font.setBold(True)
        header_item.setFont(header_font)
        header_item.setFlags(Qt.ItemIsEnabled)
        header_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.parts_table.setItem(row_index, 0, header_item)
        self.parts_table.setSpan(row_index, 0, 1, self.parts_table.columnCount())

        header_row_item = QTableWidgetItem('')
        header_row_item.setFlags(Qt.ItemIsEnabled)
        self.parts_table.setVerticalHeaderItem(row_index, header_row_item)
        self._row_parts.insert(row_index, None)

        return row_index + 1

    def _insert_part_row(self, entry: dict, row_index: int, part_counter: int) -> tuple[int, int]:
        self.parts_table.insertRow(row_index)

        part_copy = entry.copy()
        part_copy['row_type'] = 'part'
        part_copy['children'] = entry.get('children', [])
        part_copy['has_descendants'] = entry.get('has_descendants', False)
        self._row_parts.insert(row_index, part_copy)

        name_item = QTableWidgetItem('')
        name_item.setFlags(Qt.ItemIsEnabled)
        self.parts_table.setItem(row_index, 0, name_item)

        sku_item = QTableWidgetItem(part_copy.get('part_sku') or '')
        sku_item.setFlags(Qt.ItemIsEnabled)
        self.parts_table.setItem(row_index, 1, sku_item)

        qty_item = QTableWidgetItem(str(part_copy.get('installed_qty', '')))
        qty_item.setFlags(Qt.ItemIsEnabled)
        self.parts_table.setItem(row_index, 2, qty_item)

        last_replacement = part_copy.get('last_replacement_date') or ''
        last_item = QTableWidgetItem(last_replacement)
        last_item.setFlags(Qt.ItemIsEnabled)
        self.parts_table.setItem(row_index, 3, last_item)

        requires_button = QPushButton()
        self._update_requires_replacement_button(requires_button, part_copy)
        requires_button.clicked.connect(
            lambda _, p=part_copy, b=requires_button: self.on_requires_replacement_button_clicked(p, b)
        )

        row_number_item = QTableWidgetItem(str(part_counter))
        row_number_item.setTextAlignment(Qt.AlignCenter)
        row_number_item.setFlags(Qt.ItemIsEnabled)
        self.parts_table.setVerticalHeaderItem(row_index, row_number_item)
        part_counter += 1

        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(4)

        icon_size = QSize(18, 18)

        def _create_icon_button(icon: QStyle.StandardPixmap, tooltip: str) -> QPushButton:
            button = QPushButton()
            button.setIcon(self.style().standardIcon(icon))
            button.setIconSize(icon_size)
            button.setToolTip(tooltip)
            button.setCursor(Qt.PointingHandCursor)
            button.setFlat(False)
            button.setFixedSize(30, 26)
            return button

        replace_button = _create_icon_button(QStyle.SP_BrowserReload, 'Заменить запчасть')
        replace_button.clicked.connect(lambda _, p=part_copy: self.replace_part(p))

        detach_button = _create_icon_button(QStyle.SP_DialogCancelButton, 'Удалить привязку запчасти')
        detach_button.clicked.connect(lambda _, p=part_copy: self.detach_part(p))

        folder_button = _create_icon_button(QStyle.SP_DirOpenIcon, 'Открыть папку запчасти')
        folder_button.clicked.connect(
            lambda _, pn=part_copy.get('part_name', ''), sku=part_copy.get('part_sku'): self.open_part_folder_location(pn, sku)
        )

        actions_layout.addWidget(replace_button)
        actions_layout.addWidget(detach_button)
        actions_layout.addWidget(folder_button)
        actions_layout.addStretch()
        actions_layout.addWidget(requires_button)

        self.parts_table.setCellWidget(row_index, 4, actions_widget)

        name_widget = self._create_part_name_widget(part_copy)
        self.parts_table.setCellWidget(row_index, 0, name_widget)

        if part_copy.get('component_equipment_id'):
            self._apply_complex_row_style(row_index, name_widget, actions_widget)

        row_index += 1

        if (
            part_copy.get('children')
            and part_copy.get('equipment_part_id') in self._expanded_components
        ):
            for child in part_copy['children']:
                row_index, part_counter = self._insert_part_row(child, row_index, part_counter)

        return row_index, part_counter

    def _create_part_name_widget(self, part_data: dict) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 0, 0)

        indent_level = max(0, part_data.get('level', 0))
        if indent_level:
            layout.addSpacing(indent_level * 20)

        if part_data.get('component_equipment_id'):
            toggle_button = QToolButton()
            toggle_button.setAutoRaise(True)
            toggle_button.setCheckable(True)
            is_expanded = part_data.get('equipment_part_id') in self._expanded_components
            toggle_button.setChecked(is_expanded)
            toggle_button.setArrowType(Qt.DownArrow if is_expanded else Qt.RightArrow)
            toggle_button.clicked.connect(
                lambda checked, epid=part_data.get('equipment_part_id'): self._toggle_component_expansion(epid, checked)
            )
            layout.addWidget(toggle_button)
        else:
            layout.addSpacing(16)

        name_label = QLabel(part_data.get('part_name', ''))
        layout.addWidget(name_label)
        layout.addStretch()
        return container

    def _toggle_component_expansion(self, equipment_part_id: int, expanded: bool):
        if expanded:
            self._expanded_components.add(equipment_part_id)
        else:
            self._expanded_components.discard(equipment_part_id)

        if self.current_equipment_id:
            self.load_parts_for_equipment(self.current_equipment_id)

    def _apply_complex_row_style(self, row_index: int, name_widget: QWidget, actions_widget: QWidget):
        highlight = QColor('#e3f2fd')
        for column in range(self.parts_table.columnCount()):
            item = self.parts_table.item(row_index, column)
            if item:
                item.setBackground(highlight)
        name_widget.setStyleSheet('background-color: #e3f2fd;')
        actions_widget.setStyleSheet('background-color: #e3f2fd;')

    def _show_parts_context_menu(self, position):
        row = self.parts_table.rowAt(position.y())
        if row < 0 or row >= len(self._row_parts):
            return

        part_data = self._row_parts[row]
        if not part_data:
            return

        menu = QMenu(self)
        edit_action = menu.addAction('Редактировать привязанную запчасть')
        edit_action.triggered.connect(lambda: self._edit_attached_part(part_data))

        component_equipment_id = part_data.get('component_equipment_id')

        if component_equipment_id is not None:
            menu.addSeparator()
            unset_action = menu.addAction('Сделать обычной запчастью')
            if part_data.get('has_descendants'):
                unset_action.setEnabled(False)
            unset_action.triggered.connect(lambda: self._unset_complex_component(part_data))
        else:
            menu.addSeparator()
            set_action = menu.addAction('Сделать сложным компонентом')
            set_action.triggered.connect(lambda: self._set_complex_component(part_data))

        menu.exec(self.parts_table.viewport().mapToGlobal(position))

    def _edit_attached_part(self, part_data: dict):
        equipment_part_id = part_data.get('equipment_part_id')
        equipment_id = part_data.get('equipment_id')
        part_id = part_data.get('part_id')

        if not equipment_part_id or not part_id:
            return

        installed_qty = part_data.get('installed_qty') or 1
        dialog = EditAttachedPartDialog(
            part_data.get('part_name', ''),
            part_data.get('part_sku', ''),
            installed_qty,
            self,
        )

        if not dialog.exec():
            return

        new_name, new_sku, new_qty = dialog.get_values()
        success, message, payload = self.db.update_attached_part(
            equipment_part_id,
            new_name,
            new_sku,
            new_qty,
        )

        if not success:
            QMessageBox.warning(self, 'Редактирование запчасти', message)
            return

        old_name = part_data.get('part_name', '')
        old_sku = part_data.get('part_sku', '')
        if old_name != new_name or old_sku != new_sku:
            move_part_folder_on_rename(old_name, old_sku, new_name, new_sku, self)

        QMessageBox.information(self, 'Редактирование запчасти', message)

        payload = payload or {}
        target_equipment_id = payload.get('equipment_id') or equipment_id
        target_part_id = payload.get('part_id') or part_id
        name_changed = payload.get('name_changed', old_name != new_name or old_sku != new_sku)

        if target_equipment_id:
            self.event_bus.emit('equipment_parts_changed', target_equipment_id)

        if target_part_id:
            self.event_bus.emit('parts.changed')

        if name_changed:
            self.event_bus.emit('equipment.changed')

    def _set_complex_component(self, part_data: dict):
        equipment_part_id = part_data.get('equipment_part_id')
        if not equipment_part_id:
            return

        success, message, _ = self.db.mark_equipment_part_as_complex(equipment_part_id)
        if not success:
            QMessageBox.warning(self, 'Сложный компонент', message)
            return

        QMessageBox.information(self, 'Сложный компонент', message)
        self._expanded_components.add(equipment_part_id)

        parent_equipment_id = part_data.get('equipment_id')
        if parent_equipment_id:
            self.event_bus.emit('equipment_parts_changed', parent_equipment_id)
        self.event_bus.emit('equipment.changed')

        if self.current_equipment_id:
            self.load_parts_for_equipment(self.current_equipment_id)

    def _unset_complex_component(self, part_data: dict):
        equipment_part_id = part_data.get('equipment_part_id')
        part_name = part_data.get('part_name', '')
        if not equipment_part_id:
            return

        reply = QMessageBox.question(
            self,
            'Сложный компонент',
            f"Сделать запчасть '{part_name}' обычной?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        success, message, _ = self.db.unmark_equipment_part_complex(equipment_part_id)
        if not success:
            QMessageBox.warning(self, 'Сложный компонент', message)
            return

        QMessageBox.information(self, 'Сложный компонент', message)
        self._expanded_components.discard(equipment_part_id)

        parent_equipment_id = part_data.get('equipment_id')
        if parent_equipment_id:
            self.event_bus.emit('equipment_parts_changed', parent_equipment_id)
        self.event_bus.emit('equipment.changed')

        if self.current_equipment_id:
            self.load_parts_for_equipment(self.current_equipment_id)

    def manage_categories(self):
        dialog = EquipmentCategoryManagerDialog(self.db, self)
        if dialog.exec():
            self.load_tree_data()
            self.event_bus.emit('equipment.changed')

    def add_equipment(self):
        selected_item = self.tree.currentItem()
        category_id = None
        parent_id = None

        if not selected_item:
            QMessageBox.warning(self, "Внимание", "Сначала выберите категорию или оборудование-родителя.")
            return

        item_data = selected_item.data(0, Qt.UserRole)
        if item_data['type'] == 'category':
            category_id = item_data['id']
        elif item_data['type'] == 'equipment':
            parent_id = item_data['id']
            # Получаем категорию от родителя
            parent_data = self.db.fetchone("SELECT category_id FROM equipment WHERE id=?", (parent_id,))
            if parent_data:
                category_id = parent_data['category_id']
        
        if category_id is None:
            QMessageBox.critical(self, "Ошибка", "Не удалось определить категорию для нового оборудования.")
            return

        dialog = EquipmentDialog(self.db, self.event_bus, category_id=category_id, parent_id=parent_id, parent=self)
        if dialog.exec():
            self.load_tree_data()

    def edit_equipment(self):
        selected_item = self.tree.currentItem()
        if not selected_item: return

        item_data = selected_item.data(0, Qt.UserRole)
        if item_data.get('type') == 'category':
            self.manage_categories()
        elif item_data.get('type') == 'equipment':
            equipment_id = item_data['id']
            dialog = EquipmentDialog(self.db, self.event_bus, equipment_id=equipment_id, parent=self)
            if dialog.exec():
                self.load_tree_data()

    def delete_equipment(self):
        selected_item = self.tree.currentItem()
        if not selected_item: return

        item_data = selected_item.data(0, Qt.UserRole)
        item_type = item_data.get('type')
        item_id = item_data.get('id')
        item_name = selected_item.text(0)

        if item_type == 'category':
            reply = QMessageBox.question(self, "Удаление категории", 
                                       f"Вы уверены, что хотите удалить категорию '{item_name}'?\n"
                                       "Это действие необратимо.",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                success, message = self.db.delete_equipment_category(item_id)
                QMessageBox.information(self, "Результат", message)
                if success: self.load_tree_data()
        
        elif item_type == 'equipment':
            reply = QMessageBox.question(self, "Удаление оборудования",
                                       f"Вы уверены, что хотите удалить оборудование '{item_name}'?\n"
                                       "Все вложенное оборудование также будет удалено. Это действие необратимо.",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                success, message = self.db.delete_equipment(item_id)
                QMessageBox.information(self, "Результат", message)
                if success: self.load_tree_data()

    def attach_part(self):
        if self.current_equipment_id:
            dialog = AttachPartDialog(self.db, self.event_bus, self.current_equipment_id, self)
            dialog.exec()

    def detach_part(self, part_data: dict):
        equipment_part_id = part_data.get('equipment_part_id')
        part_name = part_data.get('part_name', '')
        if not equipment_part_id:
            return

        reply = QMessageBox.question(
            self,
            "Удаление привязки",
            f"Вы уверены, что хотите отвязать запчасть '{part_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        success, message = self.db.detach_part_from_equipment(equipment_part_id)
        QMessageBox.information(self, "Результат", message)
        if not success:
            return

        self._expanded_components.discard(equipment_part_id)
        target_equipment_id = part_data.get('equipment_id') or self.current_equipment_id
        if target_equipment_id:
            self.event_bus.emit("equipment_parts_changed", target_equipment_id)
        self.event_bus.emit('equipment.changed')
        if self.current_equipment_id:
            self.load_parts_for_equipment(self.current_equipment_id)

    def on_requires_replacement_button_clicked(self, part_data, button):
        requires_replacement = bool(part_data.get('requires_replacement'))
        if requires_replacement:
            QMessageBox.information(
                self,
                "Замена уже запланирована",
                "Для этой запчасти уже существует задача на замену. Завершите или отмените её, чтобы снять отметку.",
            )
            return

        self._prompt_create_replacement_task(part_data)

    def _update_requires_replacement_button(self, button, part_data):
        requires = bool(part_data.get('requires_replacement'))
        if requires:
            button.setText("Требует замены")
            button.setStyleSheet(
                "QPushButton { background-color: #dc3545; color: white; }"
                "QPushButton:hover { background-color: #c82333; }"
            )
            button.setToolTip("Запчасть помечена как требующая замены")
        else:
            button.setText("Создать задачу на замену")
            button.setStyleSheet(
                "QPushButton { background-color: #28a745; color: white; }"
                "QPushButton:hover { background-color: #218838; }"
            )
            button.setToolTip("Создайте задачу на замену, чтобы запчасть была помечена")

    def _prompt_create_replacement_task(self, part_data):
        part_name = part_data.get('part_name') or ""
        part_sku = part_data.get('part_sku') or "б/а"
        equipment_id = part_data.get('equipment_id')
        equipment = (
            self.db.fetchone("SELECT name, sku FROM equipment WHERE id = ?", (equipment_id,))
            if equipment_id
            else None
        )

        equipment_name = equipment['name'] if equipment else ""
        equipment_sku = equipment['sku'] if equipment else None
        equipment_sku = equipment_sku or "б/а"

        part_label = f"{part_name} ({part_sku})"
        equipment_label = f"{equipment_name} ({equipment_sku})"

        default_title = f"Замена {part_label} на {equipment_label}"

        reply = QMessageBox.question(
            self,
            "Создать задачу",
            f"Создать задачу «{default_title}»?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply != QMessageBox.Yes:
            return

        preselected_part = {
            'equipment_part_id': part_data.get('equipment_part_id'),
            'part_id': part_data.get('part_id'),
            'qty': part_data.get('installed_qty') or 1,
            'equipment_id': equipment_id,
        }

        dialog = TaskDialog(self.db, self.event_bus, parent=self, preselected_parts=[preselected_part])
        dialog.title_edit.setText(default_title)

        if equipment_id is not None:
            index = dialog.equipment_combo.findData(equipment_id)
            if index != -1:
                dialog.equipment_combo.setCurrentIndex(index)

        dialog.exec()

    def replace_part(self, part_data):
        """Вызывает диалог замены запчасти."""
        dialog = ReplacementDialog(self.db, self.event_bus, part_data, self)
        dialog.exec()

    def open_part_folder_location(self, part_name, part_sku):
        open_part_folder_fs(part_name, part_sku)

    def open_selected_equipment_folder(self):
        selected_item = self.tree.currentItem()
        if not selected_item:
            return

        item_data = selected_item.data(0, Qt.UserRole) or {}
        if item_data.get('type') != 'equipment':
            QMessageBox.information(self, "Папка оборудования", "Выберите оборудование в списке.")
            return

        open_equipment_folder_fs(item_data.get('name'), item_data.get('sku'))

    def on_equipment_parts_changed(self, equipment_id):
        logging.info(f"Event 'equipment_parts_changed' received for equipment_id: {equipment_id}")
        self.load_tree_data()
        if self.current_equipment_id:
            self.load_parts_for_equipment(self.current_equipment_id)

    def on_parts_changed(self):
        if self.current_equipment_id:
            self.load_parts_for_equipment(self.current_equipment_id)

