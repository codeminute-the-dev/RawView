"""Main Qt window: docks + central analysis tabs + optional agent."""

from __future__ import annotations

import html
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QEvent, QEventLoop, QObject, QSettings, QTimer, Qt
from PySide6.QtGui import QAction, QFont, QGuiApplication, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from rawview.config import user_data_dir
from rawview.qt_ui.cfg_panel import CfgPanel
from rawview.qt_ui.controller import RawViewQtController
from rawview.qt_ui.hex_view import HexViewPanel
from rawview.qt_ui.highlighter import PseudocodeHighlighter
from rawview.qt_ui.shortcuts import ShortcutController, effective_sequence, load_shortcut_map
from rawview.qt_ui.themes import apply_application_style, main_window_stylesheet, pseudocode_palette
from rawview.qt_ui.branding import load_app_icon
from rawview.qt_ui.work_dock import WorkDockPanel

# Bump when dock/splitter serialization is incompatible - v1 layouts from wide monitors could force a
# minimum width > 1920px and trigger Windows setGeometry warnings on smaller displays.
_UI_STATE_VERSION = 2


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RawView")
        _ic = load_app_icon()
        if not _ic.isNull():
            self.setWindowIcon(_ic)
        self.resize(1400, 900)
        self._did_show_reconcile = False

        self._ctrl = RawViewQtController()
        self._ui_settings = QSettings(str(user_data_dir() / "ui_state.ini"), QSettings.Format.IniFormat)
        self._save_ui_timer = QTimer(self)
        self._save_ui_timer.setSingleShot(True)
        self._save_ui_timer.setInterval(450)
        self._save_ui_timer.timeout.connect(self._persist_ui_layout)
        self._ph: PseudocodeHighlighter | None = None
        self._shortcut_controller = ShortcutController(self, self._ui_settings)
        self._spotlight_overlay: QWidget | None = None
        self._agent_feed_html_chunks: list[str] = []
        self._program_loaded: bool = False
        self._psutil_mod: Any = None  # lazy: False = unavailable, else the psutil module

        self._build_central()
        self._build_docks()
        self._install_layout_save_event_filters()
        self._wire_layout_autosave()
        self._build_menu()

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready: manual RE; agent optional (configure ANTHROPIC_API_KEY).")
        self._tip_label = QLabel("")
        self._tip_label.setStyleSheet("color: #e0af68; padding-left: 12px; max-width: 520px;")
        self._analysis_ui_active = False
        self._build_status_metrics_strip()
        self.statusBar().addPermanentWidget(self._status_metrics_container)
        self.statusBar().addPermanentWidget(self._tip_label)
        self._tip_timer = QTimer(self)
        self._tip_timer.setSingleShot(True)
        self._tip_timer.timeout.connect(self._clear_user_tip)
        self._status_resource_timer = QTimer(self)
        self._status_resource_timer.setInterval(750)
        self._status_resource_timer.timeout.connect(self._refresh_status_metrics)
        self._status_resource_timer.start()

        self._re_recovery_checked = False
        self._re_autosave_timer = QTimer(self)
        self._re_autosave_timer.setInterval(300_000)  # 5 minutes - Ghidra DB + UI hints (not Work tabs)
        self._re_autosave_timer.timeout.connect(self._ctrl.tick_re_autosave)
        self._re_autosave_timer.start()

        self._connect_controller()
        self._register_shortcuts()
        self._shortcut_controller.apply()
        self._restore_ui_layout()
        self._apply_theme()
        self._apply_default_visible_tabs()
        QTimer.singleShot(0, self._apply_default_visible_tabs)
        self._populate_saved_chats_combo()

    def _setup_agent_feed_html(self) -> None:
        doc = self._agent_feed.document()
        doc.setDefaultStyleSheet(
            "body{font-family:Consolas,monospace;font-size:10pt;color:#c0caf5;}"
            ".rvt{color:#7f849c;font-style:italic;}"
            ".rva{color:#c0caf5;}"
            ".rvtool{background:#1f2335;border-left:3px solid #7aa2f7;padding:6px;margin:6px 0;}"
            ".rvpre{white-space:pre-wrap;font-family:Consolas,monospace;color:#a9b1d6;}"
            ".rvmeta{color:#565f89;font-size:9pt;}"
        )

    def _clear_agent_feed(self) -> None:
        self._agent_feed.clear()
        self._agent_feed_html_chunks.clear()
        self._setup_agent_feed_html()

    def _append_agent_html(self, fragment: str) -> None:
        self._agent_feed.moveCursor(QTextCursor.MoveOperation.End)
        self._agent_feed.insertHtml(fragment + "<br/>")
        self._agent_feed.moveCursor(QTextCursor.MoveOperation.End)

    def _append_feed_html(self, fragment: str) -> None:
        self._append_agent_html(fragment)
        self._agent_feed_html_chunks.append(fragment)

    def _replay_feed_html_chunks(self, chunks: list[str]) -> None:
        self._agent_feed.clear()
        self._setup_agent_feed_html()
        self._agent_feed_html_chunks = list(chunks)
        for fragment in chunks:
            self._append_agent_html(fragment)

    def _show_user_tip(self, message: str) -> None:
        self._tip_label.setText(message[:400])
        self._tip_timer.stop()
        self._tip_timer.start(8000)

    def _clear_user_tip(self) -> None:
        self._tip_label.clear()

    def _sync_menu_action_shortcuts(self) -> None:
        ov = load_shortcut_map(self._ui_settings)
        self._act_open.setShortcut(effective_sequence("open_binary", ov))
        self._act_settings.setShortcut(effective_sequence("open_settings", ov))
        self._act_quit.setShortcut(effective_sequence("quit", ov))

    def _register_shortcuts(self) -> None:
        sc = self._shortcut_controller
        sc.register("next_central_tab", self._shortcut_next_tab)
        sc.register("prev_central_tab", self._shortcut_prev_tab)
        sc.register("decompiler_tab", lambda: self._tabs.setCurrentWidget(self._decompiler))
        sc.register("disasm_tab", lambda: self._tabs.setCurrentWidget(self._disasm))
        sc.register("hex_tab", lambda: self._tabs.setCurrentWidget(self._hex_panel))
        sc.register("focus_agent_prompt", lambda: (self._dock_agent.show(), self._dock_agent.raise_(), self._agent_prompt.setFocus()))
        sc.register("run_agent", self._send_agent)
        sc.register("stop_agent", self._ctrl.interrupt_agent)
        sc.register("run_auto_analysis", self._on_run_auto_analysis)
        sc.register("toggle_file_dock", lambda: self._toggle_dock(self._dock_file))
        sc.register("toggle_work_dock", lambda: self._toggle_dock(self._dock_work))
        sc.register("toggle_agent_dock", lambda: self._toggle_dock(self._dock_agent))
        self._sync_menu_action_shortcuts()
        sc.apply()

    def _toggle_dock(self, dock: QDockWidget) -> None:
        dock.setVisible(not dock.isVisible())
        if dock.isVisible():
            dock.raise_()

    def _shortcut_next_tab(self) -> None:
        n = self._tabs.count()
        if n:
            self._tabs.setCurrentIndex((self._tabs.currentIndex() + 1) % n)

    def _shortcut_prev_tab(self) -> None:
        n = self._tabs.count()
        if n:
            self._tabs.setCurrentIndex((self._tabs.currentIndex() - 1 + n) % n)

    def _mono(self) -> QFont:
        f = QFont("Consolas", 10)
        f.setStyleHint(QFont.StyleHint.Monospace)
        return f

    def _build_central(self) -> None:
        mono = self._mono()
        self._decompiler = QPlainTextEdit()
        self._decompiler.setReadOnly(True)
        self._decompiler.setFont(mono)
        self._decompiler.setPlaceholderText("Decompiled pseudocode appears here.")
        self._disasm = QPlainTextEdit()
        self._disasm.setReadOnly(True)
        self._disasm.setFont(mono)
        self._disasm.setPlaceholderText("Disassembly listing.")

        self._hex_panel = HexViewPanel(self._ctrl, mono)

        self._strings_table = QTableWidget(0, 2)
        self._strings_table.setHorizontalHeaderLabels(["Address", "String"])
        self._strings_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self._imports_table = QTableWidget(0, 3)
        self._imports_table.setHorizontalHeaderLabels(["Library", "Name", "Address"])
        self._imports_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        self._exports_table = QTableWidget(0, 2)
        self._exports_table.setHorizontalHeaderLabels(["Name", "Address"])

        self._symbols_table = QTableWidget(0, 2)
        self._symbols_table.setHorizontalHeaderLabels(["Name", "Address"])

        self._xrefs_table = QTableWidget(0, 3)
        self._xrefs_table.setHorizontalHeaderLabels(["From", "To", "Type"])
        self._xrefs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self._cfg = CfgPanel()

        tabs = QTabWidget()
        tabs.addTab(self._decompiler, "Decompiler")
        tabs.addTab(self._disasm, "Disassembly")
        tabs.addTab(self._hex_panel, "Hex")
        tabs.addTab(self._strings_table, "Strings")
        tabs.addTab(self._imports_table, "Imports")
        tabs.addTab(self._exports_table, "Exports")
        tabs.addTab(self._symbols_table, "Symbols")
        tabs.addTab(self._xrefs_table, "Xrefs (to addr)")
        tabs.addTab(self._cfg, "CFG")
        tabs.setTabsClosable(False)
        tabs.setDocumentMode(True)
        tabs.setMovable(True)
        tabs.currentChanged.connect(self._on_central_tab_changed)
        self.setCentralWidget(tabs)
        self._tabs = tabs

    def _build_docks(self) -> None:
        # File dock
        file_w = QWidget()
        fl = QVBoxLayout(file_w)
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Path to binary...")
        row = QHBoxLayout()
        btn_open = QPushButton("Browse...")
        btn_open.clicked.connect(self._browse_open)
        btn_load = QPushButton("Open")
        btn_load.clicked.connect(self._open_path)
        btn_analyze = QPushButton("Run auto-analysis")
        btn_analyze.clicked.connect(self._on_run_auto_analysis)
        row.addWidget(btn_open)
        row.addWidget(btn_load)
        row.addWidget(btn_analyze)
        fl.addWidget(QLabel("Project / binary"))
        fl.addWidget(self._path_edit)
        fl.addLayout(row)
        self._dock_file = QDockWidget("File", self)
        self._dock_file.setObjectName("dock_file")
        self._dock_file.setWidget(file_w)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._dock_file)

        # Functions dock
        fw = QWidget()
        fvl = QVBoxLayout(fw)
        self._fn_search = QLineEdit()
        self._fn_search.setPlaceholderText("Search functions...")
        self._fn_search.textChanged.connect(self._ctrl.filter_functions)
        self._fn_list = QListWidget()
        self._fn_list.itemDoubleClicked.connect(self._on_fn_activated)
        fvl.addWidget(self._fn_search)
        fvl.addWidget(self._fn_list)
        self._dock_functions = QDockWidget("Functions", self)
        self._dock_functions.setObjectName("dock_functions")
        self._dock_functions.setWidget(fw)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._dock_functions)

        self.tabifyDockWidget(self._dock_file, self._dock_functions)
        self._dock_file.raise_()

        # Agent dock (optional)
        agent = QWidget()
        al = QVBoxLayout(agent)
        self._agent_feed = QTextEdit()
        self._agent_feed.setReadOnly(True)
        self._agent_feed.setAcceptRichText(True)
        self._agent_feed.setFont(self._mono())
        self._agent_feed.setPlaceholderText("Agent activity (tools, results) streams here when enabled.")
        self._agent_prompt = QTextEdit()
        self._agent_prompt.setPlaceholderText(
            "Ask the agent… Type /summarize to compress chat history when it grows. (ANTHROPIC_API_KEY required)"
        )
        self._agent_prompt.setMaximumHeight(100)
        row_head = QHBoxLayout()
        row_head.addWidget(QLabel("Agent (optional)"))
        self._btn_new_chat = QPushButton("New chat")
        self._btn_new_chat.setToolTip("Save this session to disk and start a fresh conversation.")
        self._btn_new_chat.setAutoDefault(False)
        self._btn_new_chat.clicked.connect(self._new_agent_chat)
        row_head.addWidget(self._btn_new_chat)
        row_head.addWidget(QLabel("Saved:"))
        self._chat_combo = QComboBox()
        self._chat_combo.setMinimumWidth(200)
        self._chat_combo.setToolTip("Open a previously saved agent conversation.")
        self._chat_combo.currentIndexChanged.connect(self._on_saved_chat_selected)
        row_head.addWidget(self._chat_combo, stretch=1)
        row_a = QHBoxLayout()
        self._btn_send = QPushButton("Run agent")
        self._btn_send.clicked.connect(self._send_agent)
        self._btn_stop = QPushButton("Stop")
        self._btn_stop.clicked.connect(self._ctrl.interrupt_agent)
        row_a.addWidget(self._btn_send)
        row_a.addWidget(self._btn_stop)
        al.addLayout(row_head)
        al.addWidget(self._agent_feed, stretch=1)
        al.addWidget(self._agent_prompt)
        al.addLayout(row_a)
        self._dock_agent = QDockWidget("Agent", self)
        self._dock_agent.setObjectName("dock_agent")
        self._dock_agent.setWidget(agent)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dock_agent)
        self._apply_agent_availability()
        self._setup_agent_feed_html()

        self._work_panel = WorkDockPanel()
        self._dock_work = QDockWidget("Work", self)
        self._dock_work.setObjectName("dock_work")
        self._dock_work.setWidget(self._work_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dock_work)
        self.tabifyDockWidget(self._dock_agent, self._dock_work)
        self._dock_agent.raise_()

        # Bottom: rename + comment quick actions
        tools = QWidget()
        tl = QHBoxLayout(tools)
        self._addr_edit = QLineEdit()
        self._addr_edit.setPlaceholderText("Address")
        self._rename_edit = QLineEdit()
        self._rename_edit.setPlaceholderText("New function name")
        btn_re = QPushButton("Rename function")
        btn_re.clicked.connect(self._do_rename)
        self._comment_edit = QLineEdit()
        self._comment_edit.setPlaceholderText("EOL comment text")
        btn_co = QPushButton("Set comment")
        btn_co.clicked.connect(self._do_comment)
        tl.addWidget(QLabel("Addr"))
        tl.addWidget(self._addr_edit)
        tl.addWidget(self._rename_edit)
        tl.addWidget(btn_re)
        tl.addWidget(self._comment_edit)
        tl.addWidget(btn_co)
        self._dock_tools = QDockWidget("Annotations", self)
        self._dock_tools.setObjectName("dock_annotations")
        self._dock_tools.setWidget(tools)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._dock_tools)

    def _install_layout_save_event_filters(self) -> None:
        """Dock splitter drags resize children without resizing the top-level window; watch those too."""
        self._layout_watch: tuple[QObject, ...] = (
            self._tabs,
            self._dock_file,
            self._dock_functions,
            self._dock_agent,
            self._dock_work,
            self._dock_tools,
        )
        for w in self._layout_watch:
            w.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if watched in getattr(self, "_layout_watch", ()) and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
        ):
            self._save_ui_timer.start()
        return super().eventFilter(watched, event)

    def _wire_layout_autosave(self) -> None:
        for dock in (self._dock_file, self._dock_functions, self._dock_agent, self._dock_work, self._dock_tools):
            dock.visibilityChanged.connect(lambda _v: self._save_ui_timer.start())

    def _restore_ui_layout(self) -> None:
        """Restore dock toolbars first, drop layouts that cannot fit the primary display, then geometry."""
        app = QApplication.instance()
        state = self._ui_settings.value("windowstate")
        if isinstance(state, QByteArray) and not state.isEmpty():
            if not self.restoreState(state, _UI_STATE_VERSION):
                self._ui_settings.remove("windowstate")
                self._ui_settings.sync()
        if isinstance(app, QApplication):
            app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        self.updateGeometry()
        self._coerce_docks_if_minimum_exceeds_primary_screen()
        geom = self._ui_settings.value("geometry")
        if isinstance(geom, QByteArray) and not geom.isEmpty():
            self.restoreGeometry(geom)
            self._shrink_window_client_to_primary_screen()
        if isinstance(app, QApplication):
            app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        self._reconcile_window_with_screen()
        QTimer.singleShot(0, self._reconcile_window_with_screen)
        QTimer.singleShot(80, self._reconcile_window_with_screen)

    def _coerce_docks_if_minimum_exceeds_primary_screen(self) -> None:
        """If restored (or default) docks imply a minimum window larger than the primary work area, reset docks
        and clear saved layout before restoreGeometry runs (avoids Qt/Windows setGeometry warnings)."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        margin = 12
        chrome_x = 16
        chrome_y = 31
        max_inner_w = max(320, avail.width() - 2 * margin - chrome_x)
        max_inner_h = max(240, avail.height() - 2 * margin - chrome_y)
        mw = self.minimumSize().width()
        mh = self.minimumSize().height()
        if mw > max_inner_w or mh > max_inner_h:
            self._ui_settings.remove("windowstate")
            self._ui_settings.remove("geometry")
            self._ui_settings.sync()
            self._reapply_default_dock_layout()
            app = QApplication.instance()
            if isinstance(app, QApplication):
                app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    def _shrink_window_client_to_primary_screen(self) -> None:
        """Immediately after restoreGeometry: saved size may exceed the monitor even when dock minimum is fine."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        margin = 12
        chrome_x = max(16, self.frameGeometry().width() - self.width())
        chrome_y = max(31, self.frameGeometry().height() - self.height())
        max_inner_w = max(320, avail.width() - 2 * margin - chrome_x)
        max_inner_h = max(240, avail.height() - 2 * margin - chrome_y)
        mw, mh = self.minimumSize().width(), self.minimumSize().height()
        cw = max(mw, min(self.width(), max_inner_w))
        ch = max(mh, min(self.height(), max_inner_h))
        if cw != self.width() or ch != self.height():
            self.resize(cw, ch)

    def _reapply_default_dock_layout(self) -> None:
        """Rebuild dock placement like startup when saved splitter/dock sizes are unusable on this display."""
        docks = (
            self._dock_file,
            self._dock_functions,
            self._dock_agent,
            self._dock_work,
            self._dock_tools,
        )
        for d in docks:
            self.removeDockWidget(d)
            d.setFloating(False)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._dock_file)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._dock_functions)
        self.tabifyDockWidget(self._dock_file, self._dock_functions)
        self._dock_file.raise_()
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dock_agent)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dock_work)
        self.tabifyDockWidget(self._dock_agent, self._dock_work)
        self._dock_agent.raise_()
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._dock_tools)
        self._apply_default_visible_tabs()

    def _apply_default_visible_tabs(self) -> None:
        """Saved windowstate can hide every dock or leave them floating off-screen - then only the center strip
        looks like 'no tabs'. Show core docks again, dock them to the main window, Decompiler on top, then File/Agent."""
        for dock in (
            self._dock_file,
            self._dock_functions,
            self._dock_agent,
            self._dock_work,
            self._dock_tools,
        ):
            dock.setFloating(False)
            dock.setVisible(True)
        self._tabs.setCurrentWidget(self._decompiler)
        self._dock_file.raise_()
        self._dock_agent.raise_()

    def _reconcile_window_with_screen(self) -> None:
        """Clamp window to the work area; only erase saved dock layout when minimum size cannot fit the screen.

        Previously we also cleared ``geometry``/``windowstate`` whenever the *current* client size exceeded
        the screen (e.g. moving from a large monitor). That nuked valid splitter/dock data and made layout
        feel like it never persisted. Client overflow is handled by shrinking/moving only.
        """
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        margin = 12
        min_sz = self.minimumSize()
        fg0 = self.frameGeometry()
        # Before the window is shown, frame−client delta can be 0; reserve typical Windows decoration size.
        chrome_x = max(16, fg0.width() - self.width())
        chrome_y = max(31, fg0.height() - self.height())
        max_inner_w = max(320, avail.width() - 2 * margin - chrome_x)
        max_inner_h = max(240, avail.height() - 2 * margin - chrome_y)

        min_too_wide = min_sz.width() > max_inner_w
        min_too_tall = min_sz.height() > max_inner_h
        if min_too_wide or min_too_tall:
            self._ui_settings.remove("windowstate")
            self._ui_settings.remove("geometry")
            self._ui_settings.sync()
            self._reapply_default_dock_layout()
            min_sz = self.minimumSize()
            fg0 = self.frameGeometry()
            chrome_x = max(16, fg0.width() - self.width())
            chrome_y = max(31, fg0.height() - self.height())
            max_inner_w = max(320, avail.width() - 2 * margin - chrome_x)
            max_inner_h = max(240, avail.height() - 2 * margin - chrome_y)
            if self.width() > max_inner_w or self.height() > max_inner_h:
                self.resize(1400, 900)

        min_sz = self.minimumSize()
        cw = max(min_sz.width(), min(self.width(), max_inner_w))
        ch = max(min_sz.height(), min(self.height(), max_inner_h))
        self.resize(cw, ch)

        fg = self.frameGeometry()
        x = min(max(fg.x(), avail.left() + margin), max(avail.left() + margin, avail.right() - fg.width() - margin))
        y = min(max(fg.y(), avail.top() + margin), max(avail.top() + margin, avail.bottom() - fg.height() - margin))
        self.move(x, y)

    def _persist_ui_layout(self) -> None:
        self._ui_settings.setValue("geometry", self.saveGeometry())
        self._ui_settings.setValue("windowstate", self.saveState(_UI_STATE_VERSION))
        self._ui_settings.sync()

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_application_style(app, self._ctrl.settings.rawview_theme)
        self.setStyleSheet(main_window_stylesheet(self._ctrl.settings.rawview_theme))
        if self._ph is not None:
            self._ph.setDocument(None)
            self._ph.deleteLater()
            self._ph = None
        self._ph = PseudocodeHighlighter(
            self._decompiler.document(),
            palette=pseudocode_palette(self._ctrl.settings.rawview_theme),
        )
        self._hex_panel.apply_theme(self._ctrl.settings.rawview_theme)
        self._setup_agent_feed_html()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._did_show_reconcile:
            self._did_show_reconcile = True
            QTimer.singleShot(0, self._reconcile_window_with_screen)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._save_ui_timer.start()
        if self._spotlight_overlay is not None:
            self._spotlight_overlay.setGeometry(self.rect())

    def moveEvent(self, event) -> None:  # type: ignore[override]
        super().moveEvent(event)
        self._save_ui_timer.start()

    def _apply_agent_availability(self) -> None:
        has = self._ctrl.has_anthropic_key()
        self._dock_agent.setEnabled(True)
        self._agent_prompt.setEnabled(has)
        self._btn_send.setEnabled(has)
        if not has:
            self._agent_feed.setPlaceholderText(
                "Agent disabled: set ANTHROPIC_API_KEY in File > Settings. "
                "All other panels work without AI."
            )
        else:
            self._agent_feed.setPlaceholderText("Agent activity (tools, results) streams here.")

    def _build_menu(self) -> None:
        m_file = self.menuBar().addMenu("&File")
        self._act_open = QAction("Open binary...", self)
        self._act_open.triggered.connect(self._browse_open)
        m_file.addAction(self._act_open)
        self._act_save_re = QAction("Save RE session…", self)
        self._act_save_re.setToolTip(
            "Export the current Ghidra project (names, comments, analysis) to a .rvre.zip file. "
            "Work-dock Markdown notes are not included."
        )
        self._act_save_re.setEnabled(False)
        self._act_save_re.triggered.connect(self._save_re_session)
        m_file.addAction(self._act_save_re)
        self._act_load_re = QAction("Load RE session…", self)
        self._act_load_re.setToolTip("Import a .rvre.zip saved earlier on this machine or another.")
        self._act_load_re.triggered.connect(self._load_re_session)
        m_file.addAction(self._act_load_re)
        m_file.addSeparator()
        self._act_settings = QAction("Settings...", self)
        self._act_settings.triggered.connect(self._open_settings)
        m_file.addAction(self._act_settings)
        self._act_quit = QAction("Quit", self)
        self._act_quit.triggered.connect(self.close)
        m_file.addAction(self._act_quit)

        m_view = self.menuBar().addMenu("&View")

        m_panels = m_view.addMenu("Side panels")
        for dock in (self._dock_file, self._dock_functions, self._dock_agent, self._dock_work, self._dock_tools):
            m_panels.addAction(dock.toggleViewAction())

        act_restore = QAction("Restore all panels", self)
        act_restore.setToolTip("Show every dock window again (after closing the dock close button).")
        act_restore.triggered.connect(self._restore_all_panels)
        m_view.addAction(act_restore)
        self._act_show_tutorial = QAction("Show tutorial…", self)
        self._act_show_tutorial.setToolTip("Replay the interactive RE overview tour.")
        self._act_show_tutorial.triggered.connect(self._on_show_tutorial)
        m_view.addAction(self._act_show_tutorial)

        m_tabs = m_view.addMenu("Analysis tabs")
        tab_targets: list[tuple[str, QWidget]] = [
            ("Decompiler", self._decompiler),
            ("Disassembly", self._disasm),
            ("Hex", self._hex_panel),
            ("Strings", self._strings_table),
            ("Imports", self._imports_table),
            ("Exports", self._exports_table),
            ("Symbols", self._symbols_table),
            ("Xrefs (to addr)", self._xrefs_table),
            ("CFG", self._cfg),
        ]
        for title, w in tab_targets:
            act = QAction(title, self)
            act.triggered.connect(lambda _c=False, wid=w: self._tabs.setCurrentWidget(wid))
            m_tabs.addAction(act)

        m_help = self.menuBar().addMenu("&Help")
        act_tutorial = QAction("Interactive tutorial (RE overview)", self)
        act_tutorial.triggered.connect(self._on_show_tutorial)
        m_help.addAction(act_tutorial)
        about = QAction("About RawView", self)
        about.triggered.connect(self._about)
        m_help.addAction(about)

    def _build_status_metrics_strip(self) -> None:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 8, 0)
        row.setSpacing(10)
        self._analysis_label = QLabel("")
        self._analysis_label.setVisible(False)
        self._analysis_bar = QProgressBar()
        self._analysis_bar.setFixedWidth(160)
        self._analysis_bar.setFixedHeight(16)
        self._analysis_bar.setVisible(False)
        self._cpu_ram_label = QLabel("CPU: [-]  RAM: [-]")
        row.addWidget(self._analysis_label)
        row.addWidget(self._analysis_bar)
        row.addWidget(self._cpu_ram_label)
        self._status_metrics_container = host
        try:
            import psutil

            self._psutil_mod = psutil
            # Non-blocking CPU% needs a prior sample; prime so the first timer tick is meaningful.
            psutil.cpu_percent(interval=None, percpu=False)
        except ImportError:
            self._psutil_mod = False
        except Exception:
            self._psutil_mod = None

    def _host_cpu_ram_text(self) -> tuple[str, str]:
        mod = self._psutil_mod
        if mod is False:
            return "-", "-"
        if mod is None:
            try:
                import psutil
            except ImportError:
                self._psutil_mod = False
                return "-", "-"
            except Exception:
                return "-", "-"
            self._psutil_mod = psutil
            try:
                psutil.cpu_percent(interval=None, percpu=False)
            except Exception:
                self._psutil_mod = False
                return "-", "-"
            try:
                ram = float(psutil.virtual_memory().percent)
            except Exception:
                return "-", "-"
            if not math.isfinite(ram):
                return "-", "-"
            ram = max(0.0, min(100.0, ram))
            return "-", f"{ram:.0f}%"
        try:
            cpu = float(mod.cpu_percent(interval=None, percpu=False))
            ram = float(mod.virtual_memory().percent)
        except Exception:
            return "-", "-"
        if not math.isfinite(cpu):
            cpu = 0.0
        if not math.isfinite(ram):
            return f"{max(0.0, min(100.0, cpu)):.0f}%", "-"
        cpu = max(0.0, min(100.0, cpu))
        ram = max(0.0, min(100.0, ram))
        return f"{cpu:.0f}%", f"{ram:.0f}%"

    def _refresh_status_metrics(self) -> None:
        cpu_t, ram_t = self._host_cpu_ram_text()
        self._cpu_ram_label.setText(f"CPU: [{cpu_t}]  RAM: [{ram_t}]")
        if not self._analysis_ui_active:
            return
        path = self._ctrl.analysis_progress_file()
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError, TypeError):
            self._analysis_label.setText("ANALYSING: […]")
            self._analysis_bar.setRange(0, 0)
            self._analysis_bar.setFormat("")
            return
        msg = str(data.get("message", "") or "").strip() or "…"
        if len(msg) > 100:
            msg = msg[:97] + "…"
        self._analysis_label.setText(f"ANALYSING: [{msg}]")
        indet = bool(data.get("indeterminate"))
        pct_raw = data.get("percent")
        try:
            pct = int(pct_raw) if pct_raw is not None else -1
        except (TypeError, ValueError):
            pct = -1
        if indet or pct < 0:
            self._analysis_bar.setRange(0, 0)
            self._analysis_bar.setFormat("")
        else:
            self._analysis_bar.setRange(0, 100)
            self._analysis_bar.setValue(max(0, min(100, pct)))
            self._analysis_bar.setFormat("%p%")

    def _on_ghidra_analysis_begin(self) -> None:
        self._analysis_ui_active = True
        self._analysis_label.setVisible(True)
        self._analysis_bar.setVisible(True)
        self._analysis_label.setText("ANALYSING: […]")
        self._analysis_bar.setRange(0, 0)
        self._analysis_bar.setFormat("")
        self._status_resource_timer.setInterval(200)
        try:
            self._ctrl.analysis_progress_file().unlink(missing_ok=True)
        except OSError:
            pass

    def _on_ghidra_analysis_end(self) -> None:
        self._analysis_ui_active = False
        self._status_resource_timer.setInterval(750)
        self._analysis_label.setVisible(False)
        self._analysis_bar.setVisible(False)
        self._analysis_bar.setRange(0, 100)
        self._analysis_bar.setValue(0)
        self._analysis_bar.setFormat("%p%")

    def _connect_controller(self) -> None:
        c = self._ctrl
        c.status_message.connect(self.statusBar().showMessage)
        c.ghidra_analysis_begin.connect(self._on_ghidra_analysis_begin)
        c.ghidra_analysis_end.connect(self._on_ghidra_analysis_end)
        c.functions_updated.connect(self._populate_functions)
        c.decompiler_text.connect(self._decompiler.setPlainText)
        c.disassembly_text.connect(self._disasm.setPlainText)
        c.strings_updated.connect(lambda rows: self._fill_table(self._strings_table, rows, ["address", "value"]))
        c.imports_updated.connect(
            lambda rows: self._fill_table(self._imports_table, rows, ["library", "name", "address"])
        )
        c.exports_updated.connect(lambda rows: self._fill_table(self._exports_table, rows, ["name", "address"]))
        c.symbols_updated.connect(lambda rows: self._fill_table(self._symbols_table, rows, ["name", "address"]))
        c.xrefs_updated.connect(
            lambda rows: self._fill_table(self._xrefs_table, rows, ["fromAddress", "toAddress", "type"])
        )
        c.current_address_changed.connect(self._addr_edit.setText)
        c.agent_event.connect(self._on_agent_event)
        c.log_line.connect(self._append_log)
        c.ghidra_task_failed.connect(self._toast_error)
        c.program_changed.connect(self._on_program)
        c.session_restore_hints.connect(self._apply_re_session_ui_hints)
        c.cfg_graph_updated.connect(self._cfg.load_cfg_json)

    def _restore_all_panels(self) -> None:
        """Re-show dock widgets after the user closes them from the title bar."""
        for dock in (self._dock_file, self._dock_functions, self._dock_agent, self._dock_work, self._dock_tools):
            dock.setVisible(True)
        self._dock_file.raise_()
        self.statusBar().showMessage("All side panels restored.", 4000)

    def _on_central_tab_changed(self, index: int) -> None:
        w = self._tabs.widget(index)
        if w is self._cfg:
            self._ctrl.refresh_control_flow_graph()
        if w is self._hex_panel:
            self._hex_panel.refresh_if_visible()

    def _on_program(self, name: str) -> None:
        self._program_loaded = bool(name)
        self._act_save_re.setEnabled(bool(name))
        if name:
            self.setWindowTitle(f"RawView - {name}")
        else:
            self.setWindowTitle("RawView")

    def _append_log(self, line: str) -> None:
        self.statusBar().showMessage(line, 8000)

    def _toast_error(self, msg: str) -> None:
        QMessageBox.warning(self, "RawView", msg)

    def _open_settings(self) -> None:
        from rawview.qt_ui.settings_dialog import open_settings_dialog

        if open_settings_dialog(self, self._ctrl):
            self._apply_theme()
        self._apply_agent_availability()
        self._sync_menu_action_shortcuts()
        self._shortcut_controller.apply()
        self._populate_saved_chats_combo()

    def _on_show_tutorial(self) -> None:
        """Replay tour without toggling first-run completion (users can refresh anytime)."""
        self._run_interactive_tutorial(mark_complete=False)

    def _run_interactive_tutorial(self, *, mark_complete: bool) -> None:
        if self._spotlight_overlay is not None:
            return
        from rawview.qt_ui.spotlight_tutorial import attach_spotlight_tutorial

        self._spotlight_overlay = attach_spotlight_tutorial(self, mark_complete=mark_complete)
        self._spotlight_overlay.finished.connect(self._clear_spotlight_overlay)

    def _clear_spotlight_overlay(self) -> None:
        self._spotlight_overlay = None

    def _about(self) -> None:
        mb = QMessageBox(self)
        mb.setWindowTitle("About RawView")
        mb.setIcon(QMessageBox.Icon.Information)
        mb.setTextFormat(Qt.TextFormat.RichText)
        mb.setText(
            "<p style='margin-top:0'><b>RawView</b> is a native Windows desktop UI for manual reverse engineering. "
            "It connects to <b>Ghidra</b> running headlessly in the background so you can open binaries, run analysis, "
            "and work in familiar panes: decompiler, disassembly, strings, imports/exports, xrefs, and a basic CFG "
            "view - all from one window with docked tools and saved layout.</p>"
            "<p><b>Optional agent:</b> with an Anthropic API key in <b>File → Settings</b>, an <b>Agent</b> dock can "
            "call the same Ghidra bridge (decompile, rename, navigate, and more). Nothing else requires the network "
            "or cloud services.</p>"
            "<p><b>Notes &amp; data:</b> Markdown work notes, UI state, downloads, and <code>rawview.env</code> live "
            "under your user AppData RawView folder (see Settings for paths). "
            "<b>RE sessions</b> (<code>.rvre.zip</code>) save Ghidra’s database only - not Work tabs; crash recovery "
            "autosaves every few minutes under <code>re_recovery</code>.</p>"
        )
        mb.setInformativeText(
            "Licensed under the GNU General Public License v3.0 - see the LICENSE file next to the program."
        )
        mb.exec()

    def _browse_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open binary", "", "All files (*)")
        if path:
            self._path_edit.setText(path)
            self._ctrl.open_binary(path)

    def _open_path(self) -> None:
        p = self._path_edit.text().strip()
        if not p:
            QMessageBox.warning(
                self,
                "Cannot open",
                "The file path cannot be empty.\n\n"
                "Use Browse… to choose a binary, or paste the full path, then click Open again.",
            )
            return
        self._ctrl.open_binary(p)

    def _on_run_auto_analysis(self) -> None:
        if not self._path_edit.text().strip():
            QMessageBox.warning(
                self,
                "Cannot run auto-analysis",
                "The file path cannot be empty.\n\n"
                "Set the path to your binary and click Open to load it, then run auto-analysis.",
            )
            return
        if not self._program_loaded:
            QMessageBox.warning(
                self,
                "Cannot run auto-analysis",
                "No program is loaded yet.\n\n"
                "Set the path to your binary and click Open first, then run auto-analysis.",
            )
            return
        self._ctrl.run_auto_analysis()

    def _populate_functions(self, rows: list[dict[str, str]]) -> None:
        self._fn_list.clear()
        for r in rows:
            addr = r.get("address", "")
            name = r.get("name", "")
            item = QListWidgetItem(f"{addr}  {name}")
            item.setData(Qt.ItemDataRole.UserRole, r)
            self._fn_list.addItem(item)

    def _on_fn_activated(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, dict):
            addr = data.get("address", "")
            if addr:
                self._ctrl.navigate_to_address(addr)

    def _fill_table(self, table: QTableWidget, rows: list[dict[str, str]], keys: list[str]) -> None:
        table.setRowCount(0)
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, k in enumerate(keys):
                table.setItem(i, j, QTableWidgetItem(str(row.get(k, ""))))

    def _send_agent(self) -> None:
        raw = self._agent_prompt.toPlainText()
        low = raw.strip().lower()
        self._ctrl.send_agent_prompt(raw)
        if low == "/summarize" or low.startswith("/summarize "):
            self._agent_prompt.clear()

    def _new_agent_chat(self) -> None:
        msgs = self._ctrl.agent_memory.export_messages()
        if self._ctrl.agent_memory.is_nonempty() or self._agent_feed_html_chunks:
            self._ctrl.save_agent_chat_archive(msgs, self._agent_feed_html_chunks)
        self._ctrl.clear_agent_memory()
        self._clear_agent_feed()
        self._populate_saved_chats_combo()
        self.statusBar().showMessage("New agent chat started. Previous session saved under agent_chats.", 5000)

    def _populate_saved_chats_combo(self) -> None:
        self._chat_combo.blockSignals(True)
        self._chat_combo.clear()
        self._chat_combo.addItem("Current session", "")
        for path, label in self._ctrl.list_agent_chat_archives():
            self._chat_combo.addItem(label, str(path))
        self._chat_combo.setCurrentIndex(0)
        self._chat_combo.blockSignals(False)

    def _on_saved_chat_selected(self, index: int) -> None:
        if index <= 0:
            return
        raw = self._chat_combo.itemData(index)
        if not raw:
            return
        path = Path(str(raw))
        if not path.is_file():
            return
        try:
            messages, feed_html = self._ctrl.load_agent_chat_archive(path)
        except (OSError, json.JSONDecodeError, TypeError) as e:
            QMessageBox.warning(self, "RawView", f"Could not load saved chat:\n{e}")
            return
        self._ctrl.clear_agent_memory()
        self._ctrl.agent_memory.load_messages(messages)
        self._replay_feed_html_chunks(feed_html)
        self.statusBar().showMessage(f"Loaded: {path.name}", 4000)

    def _on_agent_event(self, kind: str, data: object) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        esc = html.escape
        if not isinstance(data, dict):
            data = {"value": data}

        if kind == "user_tip":
            self._show_user_tip(str(data.get("message", "")))
            return
        if kind == "conversation_summarized":
            n = int(data.get("api_messages_before", 0) or 0)
            tin = int(data.get("transcript_chars", 0) or 0)
            tout = int(data.get("summary_chars", 0) or 0)
            self._append_feed_html(
                f'<div class="rvmeta">[{esc(ts)}] /summarize complete - replaced {esc(str(n))} API message(s); '
                f"transcript ~{tin} chars → summary ~{tout} chars.</div>"
            )
            self.statusBar().showMessage("Chat history summarized for a smaller context window.", 6000)
            return
        if kind == "work_note_updated":
            p = str(data.get("path", "")).strip()
            if p:
                self._work_panel.ensure_tab_for_path(Path(p))
            return

        if kind == "ghidra_shell_refresh":
            prog = data.get("program")
            pname = str(prog).strip() if isinstance(prog, str) and str(prog).strip() else None
            self._ctrl.schedule_ghidra_shell_refresh(pname)
            return

        if kind == "assistant_thinking":
            body = esc(str(data.get("text", ""))).replace("\n", "<br/>")
            self._append_feed_html(
                f'<div class="rvt"><span class="rvmeta">[{esc(ts)}] thinking</span><br/>{body}</div>'
            )
            return
        if kind == "assistant_text":
            body = esc(str(data.get("text", ""))).replace("\n", "<br/>")
            self._append_feed_html(
                f'<div class="rva"><span class="rvmeta">[{esc(ts)}] assistant</span><br/>{body}</div>'
            )
            return
        if kind == "tool_call":
            name = esc(str(data.get("name", "")))
            tid = esc(str(data.get("id", "")))
            inp = data.get("input", {})
            try:
                inp_s = json.dumps(inp, indent=2, ensure_ascii=False)
            except (TypeError, ValueError):
                inp_s = str(inp)
            inp_h = esc(inp_s)
            self._append_feed_html(
                f'<div class="rvtool"><span class="rvmeta">[{esc(ts)}] tool call</span> '
                f'<b>{name}</b> <span class="rvmeta">id={tid}</span>'
                f'<pre class="rvpre">{inp_h}</pre></div>'
            )
            return
        if kind == "tool_result":
            name = esc(str(data.get("name", "")))
            prev = esc(str(data.get("preview", "")))
            self._append_feed_html(
                f'<div class="rvtool"><span class="rvmeta">[{esc(ts)}] tool result</span> <b>{name}</b>'
                f'<pre class="rvpre">{prev}</pre></div>'
            )
            return
        if kind in ("agent_done", "agent_stopped", "agent_error"):
            extra = esc(json.dumps(data, ensure_ascii=False)[:2000])
            self._append_feed_html(
                f'<div class="rvmeta">[{esc(ts)}] {esc(kind)} {extra}</div>'
            )
            return

        blob = esc(json.dumps(data, ensure_ascii=False)[:4000])
        self._append_feed_html(f'<div class="rvmeta">[{esc(ts)}] {esc(kind)} {blob}</div>')

    def _do_rename(self) -> None:
        addr = self._addr_edit.text().strip()
        name = self._rename_edit.text().strip()
        if addr and name:
            self._ctrl.manual_rename_function(addr, name)
        elif not addr:
            self.statusBar().showMessage("Enter an address in the Addr field to rename.", 6000)
        elif not name:
            self.statusBar().showMessage("Enter a new function name.", 6000)

    def _do_comment(self) -> None:
        addr = self._addr_edit.text().strip()
        text = self._comment_edit.text()
        if addr:
            self._ctrl.apply_comment(addr, text)
        else:
            self.statusBar().showMessage("Enter an address in the Addr field to set a comment.", 6000)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._re_recovery_checked:
            self._re_recovery_checked = True
            QTimer.singleShot(1200, self._try_re_crash_recovery)

    def _try_re_crash_recovery(self) -> None:
        from rawview.re_session import mark_re_recovery_clean, re_autosave_zip_path, read_recovery_state

        z = re_autosave_zip_path()
        if not z.is_file():
            return
        st = read_recovery_state()
        if st and st.get("clean_shutdown"):
            try:
                z.unlink(missing_ok=True)
            except OSError:
                pass
            return
        r = QMessageBox.question(
            self,
            "Recover RE session?",
            "A crash-recovery snapshot of your Ghidra database was found from a previous run.\n\n"
            "Restore it now?\n\n"
            "Work-dock notes use a separate recovery file and are not changed here.\n\n"
            "Choose No to discard this snapshot.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if r == QMessageBox.StandardButton.Yes:
            self._ctrl.load_re_session_archive(z)
        else:
            mark_re_recovery_clean()

    def _save_re_session(self) -> None:
        if not self._program_loaded:
            self.statusBar().showMessage("Open a binary first, then save your RE session.", 5000)
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save RE session",
            "",
            "RawView RE session (*.rvre.zip)",
        )
        if path:
            if not str(path).lower().endswith(".rvre.zip"):
                path = str(path) + ".rvre.zip"
            self._ctrl.save_re_session_archive(Path(path))

    def _load_re_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load RE session",
            "",
            "RawView RE session (*.rvre.zip);;Zip archives (*.zip)",
        )
        if path:
            self._ctrl.load_re_session_archive(Path(path))

    def _apply_re_session_ui_hints(self, d: object) -> None:
        if not isinstance(d, dict):
            return
        try:
            sz = int(d.get("hex_dump_size") or 0)
            bpl = int(d.get("hex_dump_bpl") or 0)
            if sz > 0 and bpl > 0:
                self._ctrl.set_hex_view_options(sz, bpl)
                self._hex_panel.set_options_from_hints(sz, bpl)
        except (TypeError, ValueError):
            pass

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._save_ui_timer.stop()
        self._re_autosave_timer.stop()
        self._ctrl.mark_re_recovery_clean_shutdown()
        self._work_panel.mark_clean_shutdown()
        self._persist_ui_layout()
        self._ctrl.shutdown_bridge()
        super().closeEvent(event)
