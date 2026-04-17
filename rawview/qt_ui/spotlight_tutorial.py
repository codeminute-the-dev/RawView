"""Interactive spotlight tutorial: dims the window and highlights UI regions step by step."""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


def _safe_widget_rect(main: QWidget, widget: QWidget | None) -> QRect:
    """Rectangle in main-window coordinates; falls back if the widget is hidden, tiny, or off-screen."""
    fallback = QRect(main.width() // 4, main.height() // 4, main.width() // 2, main.height() // 3)
    if widget is None or not widget.isVisible():
        return fallback
    sz = widget.size()
    if sz.width() < 8 or sz.height() < 8:
        return fallback
    top_left = widget.mapTo(main, QPoint(0, 0))
    r = QRect(top_left, sz)
    main_r = main.rect()
    if not main_r.intersects(r):
        return fallback
    clipped = r.intersected(main_r)
    if clipped.width() < 8 or clipped.height() < 8:
        return fallback
    return clipped


Step = tuple[str, str, Callable[[], QRect], Optional[Callable[[], None]]]


def build_re_tutorial_steps(main: QWidget, *, no_agent: bool = False) -> list[Step]:
    """Title, HTML body, hole rect in main-window coordinates, optional pre-step hook."""

    def central() -> QRect:
        w = main.centralWidget()
        return _safe_widget_rect(main, w)

    def dock_file() -> QRect:
        return _safe_widget_rect(main, getattr(main, "_dock_file", None))

    def dock_fn() -> QRect:
        return _safe_widget_rect(main, getattr(main, "_dock_functions", None))

    def decompiler() -> QRect:
        d = getattr(main, "_decompiler", None)
        return _safe_widget_rect(main, d)

    def dock_agent() -> QRect:
        return _safe_widget_rect(main, getattr(main, "_dock_agent", None))

    def dock_work() -> QRect:
        return _safe_widget_rect(main, getattr(main, "_dock_work", None))

    def dock_ann() -> QRect:
        return _safe_widget_rect(main, getattr(main, "_dock_tools", None))

    def show_decompiler_tab() -> None:
        tabs = getattr(main, "_tabs", None)
        dec = getattr(main, "_decompiler", None)
        if tabs is not None and dec is not None:
            tabs.setCurrentWidget(dec)

    def raise_agent() -> None:
        d = getattr(main, "_dock_agent", None)
        if d is not None:
            d.show()
            d.raise_()

    def raise_work() -> None:
        d = getattr(main, "_dock_work", None)
        if d is not None:
            d.show()
            d.raise_()

    return [
        (
            "Welcome",
            "<p>This short tour highlights the main areas for reverse engineering in RawView.</p>"
            "<p>Use <b>Next</b> to continue, <b>Back</b> to review, or <b>Skip tour</b> to close.</p>",
            central,
            None,
        ),
        (
            "Load a program",
            "<p>The <b>File</b> dock is where you set the path to a binary and press <b>Open</b>.</p>"
            "<p>After load, Ghidra imports the file. Use <b>Run auto-analysis</b> when you want a full pass "
            "on an already opened program.</p>",
            dock_file,
            None,
        ),
        (
            "Functions list",
            "<p>The <b>Functions</b> dock lists symbols Ghidra found. Type in the search box to filter.</p>"
            "<p>Double-click a row to jump the listing and decompiler to that function.</p>",
            dock_fn,
            None,
        ),
        (
            "Center views",
            "<p>The large center area has tabs: <b>Decompiler</b> (pseudocode), <b>Disassembly</b>, "
            "<b>Strings</b>, imports/exports, xrefs, and <b>CFG</b>.</p>"
            "<p>That is the core of manual RE: read code, follow strings, inspect control flow.</p>",
            decompiler,
            show_decompiler_tab,
        ),
        (
            (
                "AI help (Cursor)",
                "<p>This build has <b>no in-app Anthropic agent</b>. Use <b>Cursor chat</b> (or another assistant) "
                "with this project open: you describe goals, the assistant suggests steps, and you drive Ghidra "
                "from RawView’s docks and tabs.</p>"
                "<p>RawView stays the single window for decompile, listing, strings, xrefs, and RE session save/load.</p>",
                dock_work,
                raise_work,
            )
            if no_agent
            else (
                "Agent (optional)",
                "<p>The <b>Agent</b> dock runs an Anthropic tool-using assistant. It can call Ghidra through "
                "the same bridge as the UI: decompile, navigate, rename, search, and more.</p>"
                "<p>You need an API key in <b>File &gt; Settings</b>. The agent shows tool calls and replies in the feed. "
                "It is optional; everything else works offline.</p>",
                dock_agent,
                raise_agent,
            )
        ),
        (
            "Work notes",
            "<p>The <b>Work</b> dock is for your Markdown notes: hypotheses, findings, session log.</p>"
            "<p>Notes live under <b>AppData\\RawView\\work</b>. <b>Save notes to disk</b> writes all tabs immediately. "
            "A separate <b>crash recovery autosave</b> snapshots open tabs every few seconds under "
            "<b>work_recovery</b> so you can recover after a crash or power loss.</p>",
            dock_work,
            raise_work,
        ),
        (
            "Annotations",
            "<p>The bottom <b>Annotations</b> dock is for quick renames and end-of-line comments at the "
            "current address.</p>",
            dock_ann,
            None,
        ),
        (
            "You are set",
            "<p>Tip: use <b>View</b> in the menu bar if a dock is closed. Use <b>View &gt; Show tutorial</b> or "
            "<b>Help &gt; Interactive tutorial</b> to replay this tour.</p>"
            + (
                "<p>Open <b>Cursor</b> (or your editor’s AI) beside this window when you want conversational help; "
                "this RawView build has no built-in cloud agent.</p>"
                if no_agent
                else "<p>For the agent, set <b>ANTHROPIC_API_KEY</b> in Settings when you are ready.</p>"
            ),
            central,
            None,
        ),
    ]


class SpotlightTutorialOverlay(QWidget):
    """Frameless overlay on the main window with a spotlight hole and caption panel."""

    finished = Signal()

    def __init__(self, main_window: QWidget, steps: list[Step]) -> None:
        super().__init__(main_window)
        self._main = main_window
        self._steps = steps
        self._index = 0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")

        self._title = QLabel()
        self._title.setStyleSheet("font-size: 15px; font-weight: bold; color: #c0caf5;")
        self._body = QTextBrowser()
        self._body.setOpenExternalLinks(False)
        self._body.setMaximumHeight(200)
        self._body.setStyleSheet(
            "QTextBrowser { background: #1a1b26; color: #a9b1d6; border: 1px solid #3b4261; "
            "border-radius: 6px; padding: 8px; }"
        )

        self._btn_back = QPushButton("Back")
        self._btn_back.setAutoDefault(False)
        self._btn_back.clicked.connect(self._back)
        self._btn_next = QPushButton("Next")
        self._btn_next.setAutoDefault(False)
        self._btn_next.clicked.connect(self._next)
        self._btn_skip = QPushButton("Skip tour")
        self._btn_skip.setAutoDefault(False)
        self._btn_skip.clicked.connect(self._close)

        row = QHBoxLayout()
        row.addWidget(self._btn_back)
        row.addStretch(1)
        row.addWidget(self._btn_skip)
        row.addWidget(self._btn_next)

        panel = QWidget(self)
        panel.setObjectName("tutorialPanel")
        panel.setStyleSheet(
            "#tutorialPanel { background: rgba(26, 27, 38, 240); border: 1px solid #565f89; border-radius: 8px; }"
        )
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(14, 12, 14, 12)
        pl.addWidget(self._title)
        pl.addWidget(self._body)
        pl.addLayout(row)
        self._panel = panel

        self._apply_step()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._layout_panel()

    def _layout_panel(self) -> None:
        margin = 20
        pw = min(520, self.width() - 2 * margin)
        ph = self._panel.sizeHint().height()
        ph = min(max(ph, 220), self.height() - 2 * margin)
        x = (self.width() - pw) // 2
        y = self.height() - ph - margin
        self._panel.setGeometry(x, y, pw, ph)

    def _hole_rect(self) -> QRect:
        if not self._steps:
            return QRect()
        _title, _body, rect_fn, _pre = self._steps[self._index]
        return rect_fn()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        hole = self._hole_rect()
        pad = 6
        rf = QRectF(hole.adjusted(-pad, -pad, pad, pad))

        outer = QPainterPath()
        outer.addRect(QRectF(self.rect()))
        inner = QPainterPath()
        inner.addRoundedRect(rf, 12.0, 12.0)
        dim = outer.subtracted(inner)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillPath(dim, QColor(15, 17, 22, 200))

        pen = QPen(QColor(122, 162, 247))
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rf, 12.0, 12.0)

    def _apply_step(self) -> None:
        if not self._steps:
            return
        title, body, _rect_fn, pre = self._steps[self._index]
        if pre is not None:
            pre()
        self._title.setText(title)
        self._body.setHtml(body)
        self._btn_back.setEnabled(self._index > 0)
        is_last = self._index >= len(self._steps) - 1
        self._btn_next.setText("Finish" if is_last else "Next")
        self._layout_panel()
        self.update()
        # Tabified docks (Agent + Work): raise_() updates the active tab on the next event-loop tick.
        # Without a deferred refresh, _hole_rect() still sees the previous tab as "visible" and the
        # spotlight targets the wrong region or an empty fallback on the Work step.
        QTimer.singleShot(0, self._sync_after_show)

    def _next(self) -> None:
        if self._index >= len(self._steps) - 1:
            self._close()
            return
        self._index += 1
        self._apply_step()

    def _back(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._apply_step()

    def _close(self) -> None:
        self.hide()
        self.deleteLater()
        self.finished.emit()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.setGeometry(self._main.rect())
        self.raise_()
        self._apply_step()

    def _sync_after_show(self) -> None:
        if not self.isVisible():
            return
        self.setGeometry(self._main.rect())
        self._layout_panel()
        self.update()


def attach_spotlight_tutorial(
    main_window: QWidget, *, mark_complete: bool, no_agent: bool = False
) -> SpotlightTutorialOverlay:
    """Show the RE spotlight tour. When mark_complete, first-run completion is written when the tour ends."""
    steps = build_re_tutorial_steps(main_window, no_agent=no_agent)
    overlay = SpotlightTutorialOverlay(main_window, steps)
    overlay.setParent(main_window)
    overlay.setGeometry(main_window.rect())

    def on_finished() -> None:
        if mark_complete:
            from rawview.qt_ui.first_run import mark_tutorial_complete

            mark_tutorial_complete()

    overlay.finished.connect(on_finished)
    overlay.show()
    return overlay
