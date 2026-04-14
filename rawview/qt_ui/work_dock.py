"""Work dock: Markdown notes, manual save, debounced disk save, and crash-recovery autosave."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from rawview.config import user_data_dir


def work_notes_dir() -> Path:
    d = user_data_dir() / "work"
    d.mkdir(parents=True, exist_ok=True)
    return d


def work_recovery_dir() -> Path:
    """Separate from `work/`: crash-recovery snapshots (session.json + optional copies)."""
    d = user_data_dir() / "work_recovery"
    d.mkdir(parents=True, exist_ok=True)
    return d


def recovery_session_path() -> Path:
    return work_recovery_dir() / "session.json"


def _slug_filename(title: str) -> str:
    s = re.sub(r"[^\w\-]+", "-", title.strip().lower(), flags=re.UNICODE).strip("-")
    return s[:48] or "note"


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _read_session_file() -> dict[str, object] | None:
    p = recovery_session_path()
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


class _WorkEditor(QWidget):
    def __init__(self, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path = path
        self._edit = QPlainTextEdit()
        self._edit.setPlaceholderText("Write findings here (Markdown). Use the toolbar to insert syntax.")
        if path.is_file():
            self._edit.setPlainText(path.read_text(encoding="utf-8"))
        self._dirty = False
        self._edit.textChanged.connect(self._mark_dirty)
        self._edit.textChanged.connect(self._schedule_preview_update)

        self._preview = QTextBrowser()
        self._preview.setOpenExternalLinks(True)
        self._preview.setPlaceholderText("Rendered Markdown preview")
        self._preview.setMinimumHeight(80)

        self._split = QSplitter(Qt.Orientation.Vertical)
        self._split.addWidget(self._edit)
        self._split.addWidget(self._preview)
        self._split.setStretchFactor(0, 3)
        self._split.setStretchFactor(1, 2)

        self._view_mode = QComboBox()
        self._view_mode.addItem("Split (edit + preview)", "split")
        self._view_mode.addItem("Editor only", "edit")
        self._view_mode.addItem("Preview only", "preview")
        self._view_mode.setCurrentIndex(0)
        self._view_mode.currentIndexChanged.connect(self._apply_view_mode)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(280)
        self._preview_timer.timeout.connect(self._update_preview)

        bar = QHBoxLayout()
        for label, fn in (
            ("Bold", self._wrap_bold),
            ("Italic", self._wrap_italic),
            ("Code", self._wrap_code),
            ("H1", lambda: self._heading("# ")),
            ("H2", lambda: self._heading("## ")),
            ("Bullet", self._bullet),
            ("Number", self._numbered),
            ("Link", self._link),
        ):
            b = QPushButton(label)
            b.setAutoDefault(False)
            b.clicked.connect(fn)
            bar.addWidget(b)
        bar.addStretch(1)
        bar.addWidget(QLabel("View:"))
        bar.addWidget(self._view_mode)

        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.addLayout(bar)
        vl.addWidget(self._split, stretch=1)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(650)
        self._save_timer.timeout.connect(self._save_if_dirty)

        self._update_preview()

    def _schedule_preview_update(self) -> None:
        self._preview_timer.start()

    def _update_preview(self) -> None:
        md = self._edit.toPlainText()
        self._preview.setMarkdown(md)

    def _apply_view_mode(self) -> None:
        mode = self._view_mode.currentData()
        if mode == "edit":
            self._edit.show()
            self._preview.hide()
        elif mode == "preview":
            self._edit.hide()
            self._preview.show()
            self._update_preview()
        else:
            self._edit.show()
            self._preview.show()
            self._update_preview()

    def refresh_preview(self) -> None:
        self._update_preview()

    def path(self) -> Path:
        return self._path

    def set_path(self, path: Path) -> None:
        self._path = path

    def plain_text(self) -> str:
        return self._edit.toPlainText()

    def set_plain_text(self, text: str) -> None:
        self._edit.blockSignals(True)
        self._edit.setPlainText(text)
        self._edit.blockSignals(False)
        self._mark_dirty()

    def scroll_value(self) -> int:
        return int(self._edit.verticalScrollBar().value())

    def set_scroll_value(self, v: int) -> None:
        self._edit.verticalScrollBar().setValue(v)

    def cursor_position(self) -> int:
        return int(self._edit.textCursor().position())

    def set_cursor_position(self, pos: int) -> None:
        c = self._edit.textCursor()
        c.setPosition(max(0, pos))
        self._edit.setTextCursor(c)

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._save_timer.start()

    def _mark_clean(self) -> None:
        self._dirty = False

    def _save_if_dirty(self) -> None:
        if not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(self._edit.toPlainText(), encoding="utf-8")
        self._mark_clean()

    def save_now(self) -> None:
        self._save_timer.stop()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(self._edit.toPlainText(), encoding="utf-8")
        self._mark_clean()

    def reload_from_disk(self) -> None:
        if self._path.is_file():
            self._edit.blockSignals(True)
            self._edit.setPlainText(self._path.read_text(encoding="utf-8"))
            self._edit.blockSignals(False)
        self._mark_clean()
        self._update_preview()

    def append_markdown(self, text: str) -> None:
        self._edit.moveCursor(QTextCursor.MoveOperation.End)
        if not self._edit.toPlainText().endswith("\n") and self._edit.toPlainText():
            self._edit.insertPlainText("\n")
        self._edit.insertPlainText(text.rstrip() + "\n")
        self._mark_dirty()

    def _cursor(self) -> QTextCursor:
        return self._edit.textCursor()

    def _wrap_bold(self) -> None:
        self._wrap_selection("**", "**")

    def _wrap_italic(self) -> None:
        self._wrap_selection("*", "*")

    def _wrap_code(self) -> None:
        self._wrap_selection("`", "`")

    def _wrap_selection(self, left: str, right: str) -> None:
        c = self._cursor()
        if c.hasSelection():
            t = c.selectedText().replace("\u2029", "\n")
            c.insertText(f"{left}{t}{right}")
        else:
            c.insertText(f"{left}text{right}")
        self._edit.setTextCursor(c)

    def _heading(self, prefix: str) -> None:
        c = self._cursor()
        c.movePosition(QTextCursor.MoveOperation.StartOfLine)
        c.insertText(prefix)

    def _bullet(self) -> None:
        c = self._cursor()
        c.movePosition(QTextCursor.MoveOperation.StartOfLine)
        c.insertText("- ")

    def _numbered(self) -> None:
        c = self._cursor()
        c.movePosition(QTextCursor.MoveOperation.StartOfLine)
        c.insertText("1. ")

    def _link(self) -> None:
        c = self._cursor()
        if c.hasSelection():
            t = c.selectedText().replace("\u2029", "\n")
            c.insertText(f"[{t}](url)")
        else:
            c.insertText("[label](url)")


class WorkDockPanel(QWidget):
    """Tabbed markdown notes with recovery autosave (separate from normal .md writes)."""

    RECOVERY_VERSION = 1
    AUTOSAVE_INTERVAL_MS = 2500

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        tb = self._tabs.tabBar()
        tb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tb.customContextMenuRequested.connect(self._tab_bar_context_menu)

        self._btn_new = QPushButton("New note")
        self._btn_new.setAutoDefault(False)
        self._btn_new.clicked.connect(self._new_tab)
        self._btn_open_folder = QPushButton("Open work folder")
        self._btn_open_folder.setToolTip("Open the Work notes directory in your file manager.")
        self._btn_open_folder.setAutoDefault(False)
        self._btn_open_folder.clicked.connect(self._open_work_folder)
        self._btn_save = QPushButton("Save notes to disk")
        self._btn_save.setToolTip("Writes every open tab to its .md file immediately (normal save).")
        self._btn_save.setAutoDefault(False)
        self._btn_save.clicked.connect(self._explicit_save_all)
        self._btn_delete = QPushButton("Delete note…")
        self._btn_delete.setToolTip("Delete the current tab’s .md file from disk and close the tab.")
        self._btn_delete.setAutoDefault(False)
        self._btn_delete.clicked.connect(self._delete_current_tab)

        top = QHBoxLayout()
        top.addWidget(self._btn_new)
        top.addWidget(self._btn_open_folder)
        top.addWidget(self._btn_save)
        top.addWidget(self._btn_delete)
        top.addStretch(1)
        self._hint = QLabel(
            "Close a tab (×) to remove it from the workspace - the .md file stays on disk. "
            "Use Delete note to remove the file. Notes live under AppData\\RawView\\work; "
            f"crash recovery every {self.AUTOSAVE_INTERVAL_MS // 1000}s in work_recovery."
        )
        self._hint.setStyleSheet("color: #7f849c; font-size: 11px;")
        self._hint.setWordWrap(True)
        top.addWidget(self._hint, stretch=1)

        vl = QVBoxLayout(self)
        vl.setContentsMargins(4, 4, 4, 4)
        vl.addLayout(top)
        vl.addWidget(self._tabs, stretch=1)

        self._recovery_timer = QTimer(self)
        self._recovery_timer.setInterval(self.AUTOSAVE_INTERVAL_MS)
        self._recovery_timer.timeout.connect(lambda: self._write_recovery_snapshot(clean_shutdown=False))
        self._recovery_timer.start()

        # Defer until embedded in the main window so recovery dialogs have the correct parent and
        # `_load_existing_or_default` runs when `window()` is the real QMainWindow (otherwise note tabs may not open).
        QTimer.singleShot(0, self._try_restore_or_default)

    def _on_tab_changed(self, _index: int) -> None:
        self._write_recovery_snapshot(clean_shutdown=False)

    def _try_restore_or_default(self) -> None:
        data = _read_session_file()
        if data and data.get("clean_shutdown"):
            try:
                recovery_session_path().unlink(missing_ok=True)
            except OSError:
                pass
            data = None

        recovered = False
        if data and not data.get("clean_shutdown"):
            notes = data.get("notes")
            if isinstance(notes, list) and notes:
                reply = QMessageBox.question(
                    self.window() or self,
                    "Recover notes?",
                    "RawView found a crash-recovery snapshot from a previous run (the app may have closed "
                    "without a clean shutdown).\n\n"
                    "Restore your Work tabs from that autosave?\n\n"
                    "Choose No to discard the snapshot and load notes from the work folder as usual.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._restore_from_session(data)
                    recovered = True
                try:
                    recovery_session_path().unlink(missing_ok=True)
                except OSError:
                    pass

        if not recovered:
            self._load_existing_or_default()

    def _restore_from_session(self, data: dict[str, object]) -> None:
        while self._tabs.count():
            self._tabs.removeTab(0)
        wd = work_notes_dir()
        notes = data.get("notes")
        if not isinstance(notes, list):
            self._new_tab()
            return
        for entry in notes:
            if not isinstance(entry, dict):
                continue
            rel = str(entry.get("path", "")).strip().replace("\\", "/")
            text = str(entry.get("text", ""))
            scroll = int(entry.get("scroll", 0) or 0)
            cursor = int(entry.get("cursor", 0) or 0)
            name = Path(rel).name.strip() if rel else ""
            if not name.endswith(".md"):
                name = f"note-{uuid.uuid4().hex[:8]}.md"
            path = wd / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            ed = self._add_tab_for_path(path, set_current=False)
            ed.set_scroll_value(scroll)
            ed.set_cursor_position(cursor)
            ed.save_now()
        cur = int(data.get("current_tab", 0) or 0)
        if self._tabs.count() > 0:
            self._tabs.setCurrentIndex(min(cur, self._tabs.count() - 1))
        if self._tabs.count() == 0:
            self._new_tab()

    def _serialize_notes(self) -> list[dict[str, object]]:
        wd = work_notes_dir()
        out: list[dict[str, object]] = []
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if not isinstance(w, _WorkEditor):
                continue
            try:
                rel = w.path().resolve().relative_to(wd.resolve())
            except ValueError:
                rel = Path(w.path().name)
            out.append(
                {
                    "path": rel.as_posix(),
                    "text": w.plain_text(),
                    "scroll": w.scroll_value(),
                    "cursor": w.cursor_position(),
                }
            )
        return out

    def _write_recovery_snapshot(self, *, clean_shutdown: bool) -> None:
        payload: dict[str, object] = {
            "version": self.RECOVERY_VERSION,
            "saved_at": time.time(),
            "clean_shutdown": clean_shutdown,
            "current_tab": self._tabs.currentIndex(),
            "notes": self._serialize_notes(),
        }
        try:
            _atomic_write_json(recovery_session_path(), payload)
        except OSError:
            pass

    def mark_clean_shutdown(self) -> None:
        """Flush canonical .md files then write a clean recovery marker (normal exit)."""
        self.save_all()
        self._write_recovery_snapshot(clean_shutdown=True)

    def _explicit_save_all(self) -> None:
        self.save_all()
        self._write_recovery_snapshot(clean_shutdown=False)
        win = self.window()
        if win is not None and hasattr(win, "statusBar"):
            sb = win.statusBar()
            if sb is not None:
                sb.showMessage("All Work notes saved to disk.", 4000)

    def _open_work_folder(self) -> None:
        wd = work_notes_dir()
        ok = QDesktopServices.openUrl(QUrl.fromLocalFile(str(wd.resolve())))
        if not ok:
            QMessageBox.information(
                self.window() or self,
                "Work folder",
                f"Could not open the folder automatically. Path:\n\n{wd.resolve()}",
            )

    def _tab_bar_context_menu(self, pos) -> None:
        idx = self._tabs.tabBar().tabAt(pos)
        if idx < 0:
            return
        menu = QMenu(self)
        act_open = menu.addAction("Open work folder")
        act_del = menu.addAction("Delete this note from disk…")
        chosen = menu.exec(self._tabs.tabBar().mapToGlobal(pos))
        if chosen == act_open:
            self._open_work_folder()
        elif chosen == act_del:
            self._delete_tab_at_index(idx)

    def _delete_current_tab(self) -> None:
        idx = self._tabs.currentIndex()
        if idx < 0:
            return
        self._delete_tab_at_index(idx)

    def _delete_tab_at_index(self, index: int) -> None:
        w = self._tabs.widget(index)
        if not isinstance(w, _WorkEditor):
            return
        path = w.path()
        wd = work_notes_dir().resolve()
        try:
            path.resolve().relative_to(wd)
        except ValueError:
            QMessageBox.warning(
                self.window() or self,
                "RawView",
                "This note is not under the Work folder; it will not be deleted from disk.",
            )
            return
        reply = QMessageBox.question(
            self.window() or self,
            "Delete note?",
            f"Permanently delete this file?\n\n{path.name}\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._tabs.removeTab(index)
        try:
            if path.is_file():
                path.unlink()
        except OSError as e:
            QMessageBox.warning(self.window() or self, "RawView", f"Could not delete file:\n{e}")
        self._write_recovery_snapshot(clean_shutdown=False)
        if self._tabs.count() == 0:
            self._new_tab()

    def _load_existing_or_default(self) -> None:
        wd = work_notes_dir()
        paths = sorted(wd.glob("*.md"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        if paths:
            for p in paths:
                self._add_tab_for_path(p, set_current=False)
            self._tabs.setCurrentIndex(0)
        else:
            self._new_tab()

    def _add_tab_for_path(self, path: Path, *, set_current: bool = True) -> _WorkEditor:
        ed = _WorkEditor(path)
        idx = self._tabs.addTab(ed, path.stem)
        if set_current:
            self._tabs.setCurrentIndex(idx)
        return ed

    def _new_tab(self) -> None:
        wd = work_notes_dir()
        name = f"note-{uuid.uuid4().hex[:8]}.md"
        path = wd / name
        path.write_text("# Findings\n\n", encoding="utf-8")
        self._add_tab_for_path(path)

    def _close_tab(self, index: int) -> None:
        w = self._tabs.widget(index)
        if isinstance(w, _WorkEditor):
            w.save_now()
        self._tabs.removeTab(index)
        if self._tabs.count() == 0:
            self._new_tab()
        self._write_recovery_snapshot(clean_shutdown=False)

    def reload_path(self, path: Path) -> None:
        p = path.resolve()
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, _WorkEditor) and w.path().resolve() == p:
                w.reload_from_disk()
                return

    def ensure_tab_for_path(self, path: Path) -> None:
        p = path.resolve()
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, _WorkEditor) and w.path().resolve() == p:
                w.reload_from_disk()
                self._tabs.setCurrentIndex(i)
                return
        self._add_tab_for_path(path, set_current=True)

    def append_to_tab(self, tab_title: str, markdown: str) -> Path | None:
        title_key = _slug_filename(tab_title) if tab_title.strip() else ""
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, _WorkEditor):
                if title_key and _slug_filename(w.path().stem) == title_key:
                    w.append_markdown(markdown)
                    w.save_now()
                    return w.path()
        w = self._tabs.currentWidget()
        if isinstance(w, _WorkEditor):
            w.append_markdown(markdown)
            w.save_now()
            return w.path()
        return None

    def save_all(self) -> None:
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, _WorkEditor):
                w.save_now()
