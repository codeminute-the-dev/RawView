"""Startup splash while RawView loads configuration and starts Ghidra."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRegion,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rawview.qt_ui.branding import app_icon_png_path


# Opaque panel color (matches gradient mid-stop). Transparent QLabel styles cause
# "ghost" frames on Windows when text/layout changes over the frameless splash.
_SPLASH_PANEL = "#1a1b26"


def _opaque_label(w: QWidget) -> None:
    """Ensure stylesheet background is actually painted (avoids stale text on Windows)."""
    w.setAutoFillBackground(True)


class BootSplash(QWidget):
    def __init__(self, *, no_agent: bool = False) -> None:
        super().__init__()
        self.setFixedSize(560, 400)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen
        )
        # Do not use WA_TranslucentBackground here: on Windows it uses a layered window and
        # partial updates + transparent child styles often leave "ghost" frames of old UI.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(0)

        # Top: icon + titles
        top = QHBoxLayout()
        top.setSpacing(20)

        self._icon = QLabel()
        self._icon.setFixedSize(120, 120)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet(f"background-color: {_SPLASH_PANEL}; border-radius: 12px;")
        _opaque_label(self._icon)
        ip = QPixmap(str(app_icon_png_path()))
        if not ip.isNull():
            self._icon.setPixmap(
                ip.scaled(
                    112,
                    112,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self._icon.setText("◆")
            self._icon.setStyleSheet(
                f"color: #7aa2f7; font-size: 48px; background-color: {_SPLASH_PANEL}; border-radius: 12px;"
            )

        titles = QVBoxLayout()
        titles.setSpacing(6)
        self._title = QLabel("RawView")
        tf = QFont()
        tf.setPointSize(26)
        tf.setBold(True)
        self._title.setFont(tf)
        self._title.setStyleSheet(f"color: #c0caf5; background-color: {_SPLASH_PANEL};")
        _opaque_label(self._title)

        self._subtitle = QLabel("Reverse engineering workstation")
        self._subtitle.setStyleSheet(f"color: #7aa2f7; font-size: 14px; background-color: {_SPLASH_PANEL};")
        _opaque_label(self._subtitle)

        tag_txt = (
            "Ghidra headless · manual RE (use Cursor for AI)"
            if no_agent
            else "Ghidra headless · optional Claude agent"
        )
        tag = QLabel(tag_txt)
        tag.setStyleSheet(f"color: #565f89; font-size: 11px; background-color: {_SPLASH_PANEL};")
        _opaque_label(tag)

        titles.addWidget(self._title)
        titles.addWidget(self._subtitle)
        titles.addWidget(tag)
        titles.addStretch()

        top.addWidget(self._icon, alignment=Qt.AlignmentFlag.AlignTop)
        top.addLayout(titles, stretch=1)

        outer.addLayout(top)

        self._status = QLabel("Starting...")
        self._status.setWordWrap(True)
        self._status.setMinimumHeight(52)
        self._status.setStyleSheet(
            f"color: #a9b1d6; font-size: 13px; background-color: {_SPLASH_PANEL}; padding-top: 12px;"
        )
        _opaque_label(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)  # busy
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._bar.setStyleSheet(
            """
            QProgressBar { border: 0; border-radius: 8px; background: #24283b; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #7aa2f7, stop:1 #bb9af7); border-radius: 8px; }
            """
        )

        btn_style = (
            "QPushButton { background: #414868; color: #c0caf5; padding: 10px 18px; border-radius: 12px; "
            "font-size: 13px; }"
            "QPushButton:hover { background: #565f89; }"
        )
        self._btn_download_java = QPushButton("Download JDK")
        self._btn_download_java.setToolTip(
            "Download Eclipse Temurin OpenJDK 21 (Adoptium) into AppData; no administrator install."
        )
        self._btn_download_java.setVisible(False)
        self._btn_download = QPushButton("Download Ghidra")
        self._btn_download.setVisible(False)
        self._btn_settings = QPushButton("Open settings...")
        self._btn_settings.setVisible(False)
        self._btn_continue = QPushButton("Open RawView")
        self._btn_continue.setVisible(False)
        btn_close_style = (
            "QPushButton { background: transparent; color: #565f89; padding: 10px 14px; border-radius: 12px; "
            "font-size: 13px; border: 1px solid #3b4261; }"
            "QPushButton:hover { color: #a9b1d6; background: #24283b; border-color: #565f89; }"
        )
        self._btn_close = QPushButton("Close RawView")
        self._btn_close.setToolTip("Exit the application without opening the main window.")
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.setStyleSheet(btn_close_style)
        for b in (self._btn_download_java, self._btn_download, self._btn_settings, self._btn_continue):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(btn_style)

        self._download_row = QWidget()
        self._download_row.setAutoFillBackground(True)
        self._download_row.setStyleSheet(f"background-color: {_SPLASH_PANEL};")
        dl = QHBoxLayout(self._download_row)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(10)
        dl.addWidget(self._btn_download_java)
        dl.addWidget(self._btn_download)
        dl.addStretch()
        self._download_row.hide()

        nav = QHBoxLayout()
        nav.setSpacing(10)
        nav.addWidget(self._btn_close)
        nav.addWidget(self._btn_settings)
        nav.addWidget(self._btn_continue)
        nav.addStretch()

        outer.addWidget(self._status)
        outer.addSpacing(10)
        outer.addWidget(self._bar)
        outer.addSpacing(16)
        outer.addWidget(self._download_row)
        outer.addSpacing(8)
        outer.addLayout(nav)
        outer.addStretch()

        self._apply_rounded_mask()

    def _apply_rounded_mask(self) -> None:
        r = 20.0
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), r, r)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_rounded_mask()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        # Qt starts the painter clipped to the dirty region; with a partial rect, our
        # full-widget fill/gradient only hit that sub-rectangle and stale pixels remain (H2).
        p.setClipRect(self.rect(), Qt.ClipOperation.ReplaceClip)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        inner = rect.adjusted(4, 4, -4, -4)
        # Solid erase of the entire splash (including under child widgets' repaint regions).
        p.fillRect(rect, QColor(_SPLASH_PANEL))

        grad = QLinearGradient(0, 0, float(self.width()), float(self.height()))
        grad.setColorAt(0, QColor("#16161e"))
        grad.setColorAt(0.55, QColor("#1a1b26"))
        grad.setColorAt(1, QColor("#13141c"))
        p.setBrush(grad)
        p.setPen(QPen(QColor("#3b4261"), 1))
        p.drawRoundedRect(inner, 20, 20)

    def set_status(self, text: str) -> None:
        self._status.setText(text)
        self._full_repaint()

    def set_busy(self, busy: bool) -> None:
        self._bar.setRange(0, 0 if busy else 0)

    def set_progress(self, value: int, maximum: int) -> None:
        self._bar.setRange(0, max(maximum, 1))
        self._bar.setValue(min(value, maximum))

    def _full_repaint(self) -> None:
        """Windows frameless splashes can retain stale pixels; force a client-area refresh."""
        self.repaint()

    def show_boot_actions(
        self,
        *,
        show_ghidra_download: bool = False,
        show_java_download: bool = False,
    ) -> None:
        """Show footer actions so the user must click Open RawView (splash never auto-dismisses)."""
        show_any_dl = show_ghidra_download or show_java_download
        self._download_row.setVisible(show_any_dl)
        self._btn_download.setVisible(show_ghidra_download)
        self._btn_download_java.setVisible(show_java_download)
        self._btn_settings.setVisible(True)
        self._btn_continue.setVisible(True)
        self._bar.setRange(0, 1)
        self._bar.setValue(1)
        self._full_repaint()

    def show_ghidra_actions(self, *, show_download: bool) -> None:
        """Alias for Ghidra-missing boot paths."""
        self.show_boot_actions(show_ghidra_download=show_download)
