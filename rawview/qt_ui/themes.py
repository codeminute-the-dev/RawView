"""Qt stylesheets and decompiler palettes keyed by ``RAWVIEW_THEME``."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from rawview.theme_ids import THEME_IDS


def theme_display_name(theme_id: str) -> str:
    return {
        "tokyo_night": "Tokyo Night (dark)",
        "gruvbox": "Gruvbox (dark)",
        "catppuccin_mocha": "Catppuccin Mocha (dark)",
        "nord": "Nord (dark)",
        "dracula": "Dracula (dark)",
        "onedark": "One Dark (dark)",
        "solarized_dark": "Solarized Dark",
        "kanagawa": "Kanagawa (dark)",
        "light": "Light",
        "system": "System default",
    }.get(theme_id, theme_id)


def normalize_theme_id(raw: str) -> str:
    t = (raw or "").strip().lower().replace("-", "_")
    if t in THEME_IDS:
        return t
    return "tokyo_night"


def pseudocode_palette(theme_id: str) -> dict[str, str]:
    tid = normalize_theme_id(theme_id)
    if tid == "light":
        return {
            "keyword": "#005cc5",
            "string": "#22863a",
            "number": "#e36209",
            "comment": "#6a737d",
            "preprocessor": "#6f42c1",
        }
    if tid == "system":
        return {
            "keyword": "#0066cc",
            "string": "#008000",
            "number": "#a31545",
            "comment": "#808080",
            "preprocessor": "#800080",
        }
    if tid == "gruvbox":
        return {
            "keyword": "#fabd2f",
            "string": "#b8bb26",
            "number": "#fe8019",
            "comment": "#928374",
            "preprocessor": "#d3869b",
        }
    if tid == "catppuccin_mocha":
        return {
            "keyword": "#cba6f7",
            "string": "#a6e3a1",
            "number": "#fab387",
            "comment": "#6c7086",
            "preprocessor": "#f5c2e7",
        }
    if tid == "nord":
        return {
            "keyword": "#88c0d0",
            "string": "#a3be8c",
            "number": "#d08770",
            "comment": "#616e88",
            "preprocessor": "#b48ead",
        }
    if tid == "dracula":
        return {
            "keyword": "#ff79c6",
            "string": "#50fa7b",
            "number": "#ffb86c",
            "comment": "#6272a4",
            "preprocessor": "#bd93f9",
        }
    if tid == "onedark":
        return {
            "keyword": "#c678dd",
            "string": "#98c379",
            "number": "#d19a66",
            "comment": "#5c6370",
            "preprocessor": "#e06c75",
        }
    if tid == "solarized_dark":
        return {
            "keyword": "#268bd2",
            "string": "#859900",
            "number": "#cb4b16",
            "comment": "#586e75",
            "preprocessor": "#6c71c4",
        }
    if tid == "kanagawa":
        return {
            "keyword": "#7e9cd8",
            "string": "#98bb6c",
            "number": "#ffa066",
            "comment": "#727169",
            "preprocessor": "#957fb8",
        }
    return {
        "keyword": "#7aa2f7",
        "string": "#9ece6a",
        "number": "#e0af68",
        "comment": "#565f89",
        "preprocessor": "#bb9af7",
    }


def main_window_stylesheet(theme_id: str) -> str:
    tid = normalize_theme_id(theme_id)
    if tid == "light":
        return """
            QMainWindow { background-color: #f6f8fa; color: #24292f; }
            QWidget { background-color: #f6f8fa; color: #24292f; }
            QDockWidget::title { background: #eaeef2; padding: 6px; color: #24292f; }
            QTabWidget::pane { border: 1px solid #d0d7de; border-top: none; border-radius: 0 0 8px 8px; margin-top: -1px; }
            QTabBar::tab { background: #eaeef2; padding: 8px 14px; color: #57606a;
                border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #ffffff; color: #0969da; border: 1px solid #d0d7de; border-bottom: none;
                border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QLineEdit, QPlainTextEdit, QTextEdit {
                background: #ffffff; border: 1px solid #d0d7de; border-radius: 8px; padding: 4px; color: #24292f;
            }
            QComboBox, QAbstractSpinBox {
                background: #ffffff; color: #24292f; border: 1px solid #d0d7de; border-radius: 8px; padding: 3px 6px;
            }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none; }
            QListWidget { background: #ffffff; border: 1px solid #d0d7de; color: #24292f; border-radius: 8px; outline: none; }
            QTableWidget { background: #ffffff; gridline-color: #d0d7de; border: 1px solid #d0d7de; color: #24292f;
                border-radius: 8px; outline: none; }
            QHeaderView::section { background: #eaeef2; color: #24292f; padding: 4px; border: 1px solid #d0d7de; }
            QPushButton { background: #f6f8fa; border: 1px solid #d0d7de; padding: 6px 12px; border-radius: 8px; color: #24292f; }
            QPushButton:hover { background: #eaeef2; }
            QMenuBar { background: #f6f8fa; color: #24292f; }
            QMenu { background: #ffffff; color: #24292f; }
            QStatusBar { background: #eaeef2; color: #24292f; }
        """
    if tid == "system":
        return """
            QMainWindow { background-color: palette(base); color: palette(window-text); }
            QWidget { background-color: palette(base); color: palette(window-text); }
            QDockWidget::title { background: palette(midlight); padding: 6px; }
            QTabWidget::pane { border: 1px solid palette(mid); border-top: none; border-radius: 0 0 8px 8px; margin-top: -1px; }
            QTabBar::tab { background: palette(button); padding: 8px 14px;
                border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: palette(base);
                border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QLineEdit, QPlainTextEdit, QTextEdit {
                background: palette(base); border: 1px solid palette(mid); border-radius: 8px; padding: 4px;
            }
            QComboBox, QAbstractSpinBox {
                background: palette(base); color: palette(text); border: 1px solid palette(mid); border-radius: 8px; padding: 3px 6px;
            }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none; }
            QListWidget { background: palette(base); border: 1px solid palette(mid); border-radius: 8px; outline: none; }
            QTableWidget { background: palette(base); gridline-color: palette(mid); border: 1px solid palette(mid);
                border-radius: 8px; outline: none; }
            QPushButton { background: palette(button); border: 1px solid palette(mid); padding: 6px 12px; border-radius: 8px; }
            QPushButton:hover { background: palette(midlight); }
        """
    if tid == "gruvbox":
        return """
            QMainWindow { background-color: #282828; color: #ebdbb2; }
            QWidget { background-color: #282828; color: #ebdbb2; }
            QDockWidget::title { background: #1d2021; padding: 6px; }
            QTabWidget::pane { border: 1px solid #504945; border-top: none; border-radius: 0 0 8px 8px; margin-top: -1px; }
            QTabBar::tab { background: #1d2021; padding: 8px 14px;
                border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #3c3836; color: #83a598; border: 1px solid #504945; border-bottom: none;
                border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QLineEdit, QPlainTextEdit, QTextEdit {
                background: #3c3836; border: 1px solid #504945; border-radius: 8px; padding: 4px;
            }
            QComboBox, QAbstractSpinBox {
                background: #3c3836; color: #ebdbb2; border: 1px solid #504945; border-radius: 8px; padding: 3px 6px;
            }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none; }
            QListWidget { background: #3c3836; border: 1px solid #504945; border-radius: 8px; outline: none; }
            QTableWidget { background: #3c3836; gridline-color: #504945; border: 1px solid #504945;
                border-radius: 8px; outline: none; }
            QPushButton { background: #504945; border: 1px solid #665c54; padding: 6px 12px; border-radius: 8px; }
            QPushButton:hover { background: #665c54; }
        """
    if tid == "catppuccin_mocha":
        return """
            QMainWindow { background-color: #1e1e2e; color: #cdd6f4; }
            QWidget { background-color: #1e1e2e; color: #cdd6f4; }
            QDockWidget::title { background: #181825; padding: 6px; }
            QTabWidget::pane { border: 1px solid #45475a; border-top: none; border-radius: 0 0 8px 8px; margin-top: -1px; }
            QTabBar::tab { background: #181825; padding: 8px 14px;
                border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #313244; color: #89b4fa; border: 1px solid #45475a; border-bottom: none;
                border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QLineEdit, QPlainTextEdit, QTextEdit {
                background: #313244; border: 1px solid #45475a; border-radius: 8px; padding: 4px;
            }
            QComboBox, QAbstractSpinBox {
                background: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 8px; padding: 3px 6px;
            }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none; }
            QListWidget { background: #313244; border: 1px solid #45475a; border-radius: 8px; outline: none; }
            QTableWidget { background: #313244; gridline-color: #45475a; border: 1px solid #45475a;
                border-radius: 8px; outline: none; }
            QPushButton { background: #45475a; border: 1px solid #585b70; padding: 6px 12px; border-radius: 8px; }
            QPushButton:hover { background: #585b70; }
        """
    if tid == "nord":
        return """
            QMainWindow { background-color: #2e3440; color: #eceff4; }
            QWidget { background-color: #2e3440; color: #eceff4; }
            QDockWidget::title { background: #3b4252; padding: 6px; }
            QTabWidget::pane { border: 1px solid #4c566a; border-top: none; border-radius: 0 0 8px 8px; margin-top: -1px; }
            QTabBar::tab { background: #3b4252; padding: 8px 14px;
                border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #434c5e; color: #88c0d0; border: 1px solid #4c566a; border-bottom: none;
                border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QLineEdit, QPlainTextEdit, QTextEdit {
                background: #3b4252; border: 1px solid #4c566a; border-radius: 8px; padding: 4px;
            }
            QComboBox, QAbstractSpinBox {
                background: #3b4252; color: #eceff4; border: 1px solid #4c566a; border-radius: 8px; padding: 3px 6px;
            }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none; }
            QListWidget { background: #3b4252; border: 1px solid #4c566a; border-radius: 8px; outline: none; }
            QTableWidget { background: #3b4252; gridline-color: #4c566a; border: 1px solid #4c566a;
                border-radius: 8px; outline: none; }
            QPushButton { background: #434c5e; border: 1px solid #4c566a; padding: 6px 12px; border-radius: 8px; }
            QPushButton:hover { background: #4c566a; }
        """
    if tid == "dracula":
        return """
            QMainWindow { background-color: #282a36; color: #f8f8f2; }
            QWidget { background-color: #282a36; color: #f8f8f2; }
            QDockWidget::title { background: #21222c; padding: 6px; }
            QTabWidget::pane { border: 1px solid #6272a4; border-top: none; border-radius: 0 0 8px 8px; margin-top: -1px; }
            QTabBar::tab { background: #21222c; padding: 8px 14px;
                border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #44475a; color: #bd93f9; border: 1px solid #6272a4; border-bottom: none;
                border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QLineEdit, QPlainTextEdit, QTextEdit {
                background: #44475a; border: 1px solid #6272a4; border-radius: 8px; padding: 4px;
            }
            QComboBox, QAbstractSpinBox {
                background: #44475a; color: #f8f8f2; border: 1px solid #6272a4; border-radius: 8px; padding: 3px 6px;
            }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none; }
            QListWidget { background: #44475a; border: 1px solid #6272a4; border-radius: 8px; outline: none; }
            QTableWidget { background: #44475a; gridline-color: #6272a4; border: 1px solid #6272a4;
                border-radius: 8px; outline: none; }
            QPushButton { background: #6272a4; border: 1px solid #bd93f9; padding: 6px 12px; border-radius: 8px; }
            QPushButton:hover { background: #7a7f99; }
        """
    if tid == "onedark":
        return """
            QMainWindow { background-color: #282c34; color: #abb2bf; }
            QWidget { background-color: #282c34; color: #abb2bf; }
            QDockWidget::title { background: #21252b; padding: 6px; }
            QTabWidget::pane { border: 1px solid #3e4451; border-top: none; border-radius: 0 0 8px 8px; margin-top: -1px; }
            QTabBar::tab { background: #21252b; padding: 8px 14px;
                border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #3e4451; color: #61afef; border: 1px solid #3e4451; border-bottom: none;
                border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QLineEdit, QPlainTextEdit, QTextEdit {
                background: #3e4451; border: 1px solid #181a1f; border-radius: 8px; padding: 4px;
            }
            QComboBox, QAbstractSpinBox {
                background: #3e4451; color: #abb2bf; border: 1px solid #181a1f; border-radius: 8px; padding: 3px 6px;
            }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none; }
            QListWidget { background: #3e4451; border: 1px solid #181a1f; border-radius: 8px; outline: none; }
            QTableWidget { background: #3e4451; gridline-color: #181a1f; border: 1px solid #181a1f;
                border-radius: 8px; outline: none; }
            QPushButton { background: #3e4451; border: 1px solid #5c6370; padding: 6px 12px; border-radius: 8px; }
            QPushButton:hover { background: #4b5263; }
        """
    if tid == "solarized_dark":
        return """
            QMainWindow { background-color: #002b36; color: #839496; }
            QWidget { background-color: #002b36; color: #839496; }
            QDockWidget::title { background: #073642; padding: 6px; }
            QTabWidget::pane { border: 1px solid #586e75; border-top: none; border-radius: 0 0 8px 8px; margin-top: -1px; }
            QTabBar::tab { background: #073642; padding: 8px 14px;
                border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #094656; color: #268bd2; border: 1px solid #586e75; border-bottom: none;
                border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QLineEdit, QPlainTextEdit, QTextEdit {
                background: #073642; border: 1px solid #586e75; border-radius: 8px; padding: 4px;
            }
            QComboBox, QAbstractSpinBox {
                background: #073642; color: #839496; border: 1px solid #586e75; border-radius: 8px; padding: 3px 6px;
            }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none; }
            QListWidget { background: #073642; border: 1px solid #586e75; border-radius: 8px; outline: none; }
            QTableWidget { background: #073642; gridline-color: #586e75; border: 1px solid #586e75;
                border-radius: 8px; outline: none; }
            QPushButton { background: #073642; border: 1px solid #268bd2; padding: 6px 12px; border-radius: 8px; }
            QPushButton:hover { background: #094656; }
        """
    if tid == "kanagawa":
        return """
            QMainWindow { background-color: #1f1f28; color: #dcd7ba; }
            QWidget { background-color: #1f1f28; color: #dcd7ba; }
            QDockWidget::title { background: #16161d; padding: 6px; }
            QTabWidget::pane { border: 1px solid #54546d; border-top: none; border-radius: 0 0 8px 8px; margin-top: -1px; }
            QTabBar::tab { background: #16161d; padding: 8px 14px;
                border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #2a2a37; color: #7e9cd8; border: 1px solid #54546d; border-bottom: none;
                border-top-left-radius: 8px; border-top-right-radius: 8px; }
            QLineEdit, QPlainTextEdit, QTextEdit {
                background: #2a2a37; border: 1px solid #54546d; border-radius: 8px; padding: 4px;
            }
            QComboBox, QAbstractSpinBox {
                background: #2a2a37; color: #dcd7ba; border: 1px solid #54546d; border-radius: 8px; padding: 3px 6px;
            }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none; }
            QListWidget { background: #2a2a37; border: 1px solid #54546d; border-radius: 8px; outline: none; }
            QTableWidget { background: #2a2a37; gridline-color: #54546d; border: 1px solid #54546d;
                border-radius: 8px; outline: none; }
            QPushButton { background: #363646; border: 1px solid #7e9cd8; padding: 6px 12px; border-radius: 8px; }
            QPushButton:hover { background: #43444f; }
        """
    return """
        QMainWindow { background-color: #1a1b26; color: #c0caf5; }
        QWidget { background-color: #1a1b26; color: #c0caf5; }
        QDockWidget::title { background: #16161e; padding: 6px; }
        QTabWidget::pane { border: 1px solid #24283b; border-top: none; border-radius: 0 0 8px 8px; margin-top: -1px; }
        QTabBar::tab { background: #16161e; padding: 8px 14px;
            border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
        QTabBar::tab:selected { background: #24283b; color: #7aa2f7; border: 1px solid #24283b; border-bottom: none;
            border-top-left-radius: 8px; border-top-right-radius: 8px; }
        QLineEdit, QPlainTextEdit, QTextEdit {
            background: #16161e; border: 1px solid #24283b; border-radius: 8px; padding: 4px;
        }
        QComboBox, QAbstractSpinBox {
            background: #16161e; color: #c0caf5; border: 1px solid #24283b; border-radius: 8px; padding: 3px 6px;
        }
        QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none; }
        QListWidget { background: #16161e; border: 1px solid #24283b; border-radius: 8px; outline: none; }
        QTableWidget { background: #16161e; gridline-color: #24283b; border: 1px solid #24283b;
            border-radius: 8px; outline: none; }
        QPushButton { background: #24283b; border: 1px solid #414868; padding: 6px 12px; border-radius: 8px; }
        QPushButton:hover { background: #414868; }
    """


def apply_application_style(app: QApplication, theme_id: str) -> None:
    """Set QStyle so custom palettes look consistent; ``system`` follows the OS style."""
    tid = normalize_theme_id(theme_id)
    if tid == "system":
        app.setStyle("")
    else:
        app.setStyle("Fusion")
