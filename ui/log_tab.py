from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
)


class LogTab(QWidget):
    """Вкладка отображения журнала действий пользователей."""

    def __init__(
        self,
        log_file: Path,
        parent: Optional[QWidget] = None,
        backup_handler: Optional[Callable[[], None]] = None,
        backup_icon: Optional[QIcon] = None,
    ) -> None:
        super().__init__(parent)
        self.log_file = Path(log_file)
        self._backup_handler = backup_handler
        self._backup_icon = backup_icon
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self.load_log)

        self._init_ui()
        self.load_log()
        self._timer.start()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        info_label = QLabel(
            "Здесь отображается файл журнала приложения."
            " В журнал добавляются все ключевые действия пользователей."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        controls_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.clicked.connect(self.load_log)
        controls_layout.addWidget(self.refresh_button)

        self.auto_refresh_checkbox = QCheckBox("Автообновление")
        self.auto_refresh_checkbox.setChecked(True)
        self.auto_refresh_checkbox.toggled.connect(self._toggle_auto_refresh)
        controls_layout.addWidget(self.auto_refresh_checkbox)

        open_folder_button = QPushButton("Открыть папку с логами")
        open_folder_button.clicked.connect(self._open_logs_folder)
        controls_layout.addWidget(open_folder_button)

        if self._backup_handler:
            backup_button = QPushButton("Создать бекап")
            if self._backup_icon:
                backup_button.setIcon(self._backup_icon)
            backup_button.setToolTip("Создать резервную копию приложения")
            backup_button.clicked.connect(self._backup_handler)
            controls_layout.addWidget(backup_button)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        self.log_view.setFont(font)
        layout.addWidget(self.log_view)

        path_label = QLabel(f"Текущий файл: {self.log_file.resolve()}")
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(path_label)

    def _toggle_auto_refresh(self, enabled: bool) -> None:
        if enabled:
            self._timer.start()
        else:
            self._timer.stop()

    def _open_logs_folder(self) -> None:
        folder = self.log_file.parent.resolve()
        if not folder.exists():
            QMessageBox.warning(self, "Логи", "Папка с логами ещё не создана.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def load_log(self) -> None:
        if not self.log_file.exists():
            self.log_view.setPlainText("Лог-файл пока не создан.")
            return

        try:
            content = self.log_file.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            QMessageBox.warning(self, "Ошибка", f"Не удалось прочитать лог-файл:\n{exc}")
            return

        lines = content.splitlines()
        max_lines = 1000
        total_lines = len(lines)
        if total_lines > max_lines:
            lines = lines[-max_lines:]
            header = f"Показаны последние {max_lines} строк из {total_lines}.\n"
            text = header + "\n".join(lines)
        else:
            text = "\n".join(lines)

        self.log_view.setPlainText(text)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())
