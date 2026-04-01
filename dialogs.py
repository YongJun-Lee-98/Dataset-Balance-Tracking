from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QLineEdit,
)


class TextInputDialog(QDialog):
    def __init__(
        self,
        parent,
        title: str,
        label: str,
        initial_value: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(360, 120)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(label, self))

        self._line_edit = QLineEdit(self)
        self._line_edit.setText(initial_value)
        self._line_edit.selectAll()
        layout.addWidget(self._line_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> str:
        return self._line_edit.text()

    @classmethod
    def get_value(
        cls,
        parent,
        title: str,
        label: str,
        initial_value: str = "",
    ) -> tuple[str, bool]:
        dialog = cls(parent, title, label, initial_value)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return dialog.value(), accepted


class MultilineTextDialog(QDialog):
    def __init__(
        self,
        parent,
        title: str,
        label: str,
        initial_value: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(420, 320)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(label, self))

        self._editor = QPlainTextEdit(self)
        self._editor.setPlainText(initial_value)
        layout.addWidget(self._editor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> str:
        return self._editor.toPlainText()

    @classmethod
    def get_value(
        cls,
        parent,
        title: str,
        label: str,
        initial_value: str = "",
    ) -> tuple[str, bool]:
        dialog = cls(parent, title, label, initial_value)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return dialog.value(), accepted


class JsonPreviewDialog(QDialog):
    def __init__(self, parent, title: str, json_text: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 520)

        layout = QVBoxLayout(self)
        editor = QPlainTextEdit(self)
        editor.setPlainText(json_text)
        editor.setReadOnly(True)
        layout.addWidget(editor)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


def confirm_action(parent, title: str, text: str, informative_text: str | None = None) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    if informative_text:
        box.setInformativeText(informative_text)
    box.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    box.setDefaultButton(QMessageBox.StandardButton.No)
    return box.exec() == QMessageBox.StandardButton.Yes
