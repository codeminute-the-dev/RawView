"""Native CFG placeholder using QGraphicsView (no web)."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsTextItem, QGraphicsView, QVBoxLayout, QWidget


class CfgPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        layout.addWidget(self._view)
        self.set_placeholder("Select a function and open the CFG tab after analysis.\n\nNative graph rendering will replace this placeholder.")

    def set_placeholder(self, message: str) -> None:
        self._scene.clear()
        t = QGraphicsTextItem(message)
        t.setDefaultTextColor(QColor("#a9b1d6"))
        self._scene.addItem(t)

    def load_cfg_json(self, data: dict[str, Any]) -> None:
        self._scene.clear()
        note = data.get("note") or data.get("error") or ""
        entry = data.get("entry", "")
        fn = data.get("function", "")
        self._scene.addRect(40, 40, 160, 48, QPen(QColor("#7aa2f7")), QBrush(QColor("#24283b")))
        lbl = QGraphicsTextItem(f"{fn}\n{entry}\n{note}")
        lbl.setDefaultTextColor(QColor("#c0caf5"))
        lbl.setPos(48, 48)
        self._scene.addItem(lbl)
        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-20, -20, 20, 20))
