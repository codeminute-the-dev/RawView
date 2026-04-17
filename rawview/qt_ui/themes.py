"""Qt stylesheets and decompiler palettes keyed by ``RAWVIEW_THEME``."""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class _AgentDockChrome:
    """Embed colors for the Agent dock (must stay aligned with ``main_window_stylesheet`` per theme)."""

    root_bg: str
    root_fg: str
    activity_bg: str
    activity_border: str
    muted: str
    thinking_fg: str
    thinking_bg: str
    thinking_border: str
    stream_fg: str
    stream_bg: str
    feed_bg: str
    feed_fg: str
    feed_border: str
    prompt_bg: str
    prompt_fg: str
    prompt_border: str
    html_body_bg: str
    html_body_fg: str
    html_rvt: str
    html_rva: str
    html_tool_bg: str
    html_tool_border: str
    html_pre_fg: str
    html_meta: str
    html_link: str
    html_notice: str
    html_code_bg: str


_AGENT_DOCK_CHROME: dict[str, _AgentDockChrome] = {
    "tokyo_night": _AgentDockChrome(
        root_bg="#1a1b26",
        root_fg="#c0caf5",
        activity_bg="#1f212d",
        activity_border="#3a3f55",
        muted="#aab6d6",
        thinking_fg="#9aa7b8",
        thinking_bg="#171923",
        thinking_border="#3d4358",
        stream_fg="#d0d5e0",
        stream_bg="#1b1d28",
        feed_bg="#16161e",
        feed_fg="#c8ccd8",
        feed_border="#2c2f3d",
        prompt_bg="#1e2130",
        prompt_fg="#d8dbe6",
        prompt_border="#2c2f3d",
        html_body_bg="#16161e",
        html_body_fg="#c8ccd8",
        html_rvt="#8b92a8",
        html_rva="#d8dbe6",
        html_tool_bg="#1e2130",
        html_tool_border="#5b7aa8",
        html_pre_fg="#b8bfd4",
        html_meta="#6b7080",
        html_link="#8eb8e5",
        html_notice="#c9b87a",
        html_code_bg="#252836",
    ),
    "gruvbox": _AgentDockChrome(
        root_bg="#282828",
        root_fg="#ebdbb2",
        activity_bg="#32302f",
        activity_border="#504945",
        muted="#bdae93",
        thinking_fg="#d5c4a1",
        thinking_bg="#3c3836",
        thinking_border="#504945",
        stream_fg="#ebdbb2",
        stream_bg="#32302f",
        feed_bg="#3c3836",
        feed_fg="#ebdbb2",
        feed_border="#504945",
        prompt_bg="#3c3836",
        prompt_fg="#ebdbb2",
        prompt_border="#504945",
        html_body_bg="#3c3836",
        html_body_fg="#ebdbb2",
        html_rvt="#928374",
        html_rva="#ebdbb2",
        html_tool_bg="#504945",
        html_tool_border="#83a598",
        html_pre_fg="#d5c4a1",
        html_meta="#928374",
        html_link="#83a598",
        html_notice="#fabd2f",
        html_code_bg="#504945",
    ),
    "catppuccin_mocha": _AgentDockChrome(
        root_bg="#1e1e2e",
        root_fg="#cdd6f4",
        activity_bg="#252536",
        activity_border="#45475a",
        muted="#9399b2",
        thinking_fg="#a6adc8",
        thinking_bg="#181825",
        thinking_border="#45475a",
        stream_fg="#cdd6f4",
        stream_bg="#313244",
        feed_bg="#313244",
        feed_fg="#cdd6f4",
        feed_border="#45475a",
        prompt_bg="#313244",
        prompt_fg="#cdd6f4",
        prompt_border="#45475a",
        html_body_bg="#313244",
        html_body_fg="#cdd6f4",
        html_rvt="#6c7086",
        html_rva="#cdd6f4",
        html_tool_bg="#45475a",
        html_tool_border="#89b4fa",
        html_pre_fg="#bac2de",
        html_meta="#6c7086",
        html_link="#89b4fa",
        html_notice="#f9e2af",
        html_code_bg="#45475a",
    ),
    "nord": _AgentDockChrome(
        root_bg="#2e3440",
        root_fg="#eceff4",
        activity_bg="#3b4252",
        activity_border="#4c566a",
        muted="#d8dee9",
        thinking_fg="#e5e9f0",
        thinking_bg="#434c5e",
        thinking_border="#4c566a",
        stream_fg="#eceff4",
        stream_bg="#3b4252",
        feed_bg="#3b4252",
        feed_fg="#eceff4",
        feed_border="#4c566a",
        prompt_bg="#3b4252",
        prompt_fg="#eceff4",
        prompt_border="#4c566a",
        html_body_bg="#3b4252",
        html_body_fg="#eceff4",
        html_rvt="#616e88",
        html_rva="#eceff4",
        html_tool_bg="#434c5e",
        html_tool_border="#88c0d0",
        html_pre_fg="#e5e9f0",
        html_meta="#616e88",
        html_link="#88c0d0",
        html_notice="#ebcb8b",
        html_code_bg="#434c5e",
    ),
    "dracula": _AgentDockChrome(
        root_bg="#282a36",
        root_fg="#f8f8f2",
        activity_bg="#343746",
        activity_border="#6272a4",
        muted="#bd93f9",
        thinking_fg="#bdc7e0",
        thinking_bg="#44475a",
        thinking_border="#6272a4",
        stream_fg="#f8f8f2",
        stream_bg="#44475a",
        feed_bg="#44475a",
        feed_fg="#f8f8f2",
        feed_border="#6272a4",
        prompt_bg="#44475a",
        prompt_fg="#f8f8f2",
        prompt_border="#6272a4",
        html_body_bg="#44475a",
        html_body_fg="#f8f8f2",
        html_rvt="#6272a4",
        html_rva="#f8f8f2",
        html_tool_bg="#6272a4",
        html_tool_border="#bd93f9",
        html_pre_fg="#e0e0f0",
        html_meta="#6272a4",
        html_link="#8be9fd",
        html_notice="#ffb86c",
        html_code_bg="#6272a4",
    ),
    "onedark": _AgentDockChrome(
        root_bg="#282c34",
        root_fg="#abb2bf",
        activity_bg="#2c323c",
        activity_border="#3e4451",
        muted="#6b7280",
        thinking_fg="#9da5b4",
        thinking_bg="#21252b",
        thinking_border="#3e4451",
        stream_fg="#abb2bf",
        stream_bg="#2c323c",
        feed_bg="#3e4451",
        feed_fg="#abb2bf",
        feed_border="#181a1f",
        prompt_bg="#3e4451",
        prompt_fg="#abb2bf",
        prompt_border="#181a1f",
        html_body_bg="#3e4451",
        html_body_fg="#abb2bf",
        html_rvt="#5c6370",
        html_rva="#c8ccd4",
        html_tool_bg="#2c323c",
        html_tool_border="#61afef",
        html_pre_fg="#abb2bf",
        html_meta="#5c6370",
        html_link="#61afef",
        html_notice="#e5c07b",
        html_code_bg="#2c323c",
    ),
    "solarized_dark": _AgentDockChrome(
        root_bg="#002b36",
        root_fg="#839496",
        activity_bg="#073642",
        activity_border="#586e75",
        muted="#93a1a1",
        thinking_fg="#93a1a1",
        thinking_bg="#073642",
        thinking_border="#586e75",
        stream_fg="#839496",
        stream_bg="#073642",
        feed_bg="#073642",
        feed_fg="#839496",
        feed_border="#586e75",
        prompt_bg="#073642",
        prompt_fg="#839496",
        prompt_border="#586e75",
        html_body_bg="#073642",
        html_body_fg="#839496",
        html_rvt="#586e75",
        html_rva="#eee8d5",
        html_tool_bg="#094656",
        html_tool_border="#268bd2",
        html_pre_fg="#93a1a1",
        html_meta="#586e75",
        html_link="#268bd2",
        html_notice="#b58900",
        html_code_bg="#094656",
    ),
    "kanagawa": _AgentDockChrome(
        root_bg="#1f1f28",
        root_fg="#dcd7ba",
        activity_bg="#2a2a37",
        activity_border="#54546d",
        muted="#9cabca",
        thinking_fg="#a4a09f",
        thinking_bg="#16161d",
        thinking_border="#54546d",
        stream_fg="#dcd7ba",
        stream_bg="#2a2a37",
        feed_bg="#2a2a37",
        feed_fg="#dcd7ba",
        feed_border="#54546d",
        prompt_bg="#2a2a37",
        prompt_fg="#dcd7ba",
        prompt_border="#54546d",
        html_body_bg="#2a2a37",
        html_body_fg="#dcd7ba",
        html_rvt="#727169",
        html_rva="#dcd7ba",
        html_tool_bg="#363646",
        html_tool_border="#7e9cd8",
        html_pre_fg="#c8c093",
        html_meta="#727169",
        html_link="#7e9cd8",
        html_notice="#e6c384",
        html_code_bg="#363646",
    ),
    "light": _AgentDockChrome(
        root_bg="#f6f8fa",
        root_fg="#24292f",
        activity_bg="#eaeef2",
        activity_border="#d0d7de",
        muted="#57606a",
        thinking_fg="#57606a",
        thinking_bg="#ffffff",
        thinking_border="#d0d7de",
        stream_fg="#24292f",
        stream_bg="#ffffff",
        feed_bg="#ffffff",
        feed_fg="#24292f",
        feed_border="#d0d7de",
        prompt_bg="#ffffff",
        prompt_fg="#24292f",
        prompt_border="#d0d7de",
        html_body_bg="#ffffff",
        html_body_fg="#24292f",
        html_rvt="#57606a",
        html_rva="#24292f",
        html_tool_bg="#eaeef2",
        html_tool_border="#0969da",
        html_pre_fg="#24292f",
        html_meta="#57606a",
        html_link="#0969da",
        html_notice="#9a6700",
        html_code_bg="#f6f8fa",
    ),
}


def agent_dock_stylesheet(theme_id: str) -> str:
    """Qt stylesheet for the embedded Agent panel (object names on widgets in ``MainWindow``)."""
    tid = normalize_theme_id(theme_id)
    if tid == "system":
        return """
            QWidget#agent_dock_root { background-color: palette(base); color: palette(window-text); }
            QFrame#agent_activity { background-color: palette(alternate-base); border: 1px solid palette(mid);
                border-radius: 8px; }
            QLabel#agent_gen_label { color: palette(mid); font-size: 10pt; }
            QLabel#agent_live_thinking { color: palette(mid); font-family: Consolas, monospace; font-size: 9pt;
                font-style: italic; background: palette(window); border-radius: 4px; padding: 6px;
                border: 1px solid palette(mid); }
            QLabel#agent_live_stream { color: palette(text); font-family: Consolas, monospace; font-size: 9.5pt;
                background: palette(base); border-radius: 4px; padding: 6px; border: 1px solid palette(mid); }
            QTextBrowser#agent_feed { background-color: palette(base); color: palette(text);
                border: 1px solid palette(mid); border-radius: 6px; }
            QTextEdit#agent_prompt { background-color: palette(base); color: palette(text);
                border: 1px solid palette(mid); border-radius: 6px; padding: 4px; }
        """
    c = _AGENT_DOCK_CHROME.get(tid) or _AGENT_DOCK_CHROME["tokyo_night"]
    return f"""
        QWidget#agent_dock_root {{ background-color: {c.root_bg}; color: {c.root_fg}; }}
        QFrame#agent_activity {{ background-color: {c.activity_bg}; border: 1px solid {c.activity_border}; border-radius: 8px; }}
        QLabel#agent_gen_label {{ color: {c.muted}; font-size: 10pt; }}
        QLabel#agent_live_thinking {{
            color: {c.thinking_fg}; font-family: Consolas, monospace; font-size: 9pt; font-style: italic;
            background: {c.thinking_bg}; border-radius: 4px; padding: 6px; border: 1px solid {c.thinking_border};
        }}
        QLabel#agent_live_stream {{
            color: {c.stream_fg}; font-family: Consolas, monospace; font-size: 9.5pt;
            background: {c.stream_bg}; border-radius: 4px; padding: 6px; border: 1px solid {c.activity_border};
        }}
        QTextBrowser#agent_feed {{
            background-color: {c.feed_bg}; color: {c.feed_fg}; border: 1px solid {c.feed_border}; border-radius: 6px;
        }}
        QTextEdit#agent_prompt {{
            background-color: {c.prompt_bg}; color: {c.prompt_fg};
            border: 1px solid {c.prompt_border}; border-radius: 6px; padding: 4px;
        }}
    """


def agent_feed_document_default_stylesheet(theme_id: str) -> str:
    """Default CSS for rich text in the Agent feed (must track ``agent_dock_stylesheet`` colors)."""
    tid = normalize_theme_id(theme_id)
    if tid == "system":
        return (
            "body{font-family:'Segoe UI',Consolas,sans-serif;font-size:10pt;}"
            ".rvpre{white-space:pre-wrap;font-family:Consolas,monospace;font-size:9.5pt;}"
            "code,pre{font-family:Consolas,monospace;font-size:9.5pt;}"
            "a.rvlink:hover{text-decoration:underline;}"
        )
    c = _AGENT_DOCK_CHROME.get(tid) or _AGENT_DOCK_CHROME["tokyo_night"]
    return (
        f"body{{font-family:'Segoe UI',Consolas,sans-serif;font-size:10pt;color:{c.html_body_fg};"
        f"background:{c.html_body_bg};}}"
        f".rvt{{color:{c.html_rvt};font-style:italic;}}"
        f".rva{{color:{c.html_rva};line-height:1.45;}}"
        f".rvtool{{background:{c.html_tool_bg};border-left:3px solid {c.html_tool_border};"
        f"border-radius:4px;padding:8px 10px;margin:8px 0;}}"
        f".rvtool-fold{{border-left-color:{c.html_meta};}}"
        ".rvweb .rvweb-primary{margin-top:6px;word-break:break-all;}"
        f".rvpre{{white-space:pre-wrap;font-family:Consolas,monospace;font-size:9.5pt;color:{c.html_pre_fg};}}"
        f".rvmeta{{color:{c.html_meta};font-size:9pt;}}"
        f".rvlink{{color:{c.html_link};text-decoration:none;}}"
        f".rvnotice{{color:{c.html_notice};font-size:9.5pt;padding:4px 0;}}"
        "a.rvlink:hover{text-decoration:underline;}"
        f"code{{font-family:Consolas,monospace;background:{c.html_code_bg};padding:1px 4px;"
        f"border-radius:3px;font-size:9.5pt;}}"
        f"pre{{background:{c.html_code_bg};border-radius:4px;padding:6px;}}"
    )


def apply_application_style(app: QApplication, theme_id: str) -> None:
    """Set QStyle so custom palettes look consistent; ``system`` follows the OS style."""
    tid = normalize_theme_id(theme_id)
    if tid == "system":
        app.setStyle("")
    else:
        app.setStyle("Fusion")
