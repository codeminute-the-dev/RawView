"""Lightweight C-like syntax highlighting for decompiler text (Qt only, no web)."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class PseudocodeHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, *, palette: dict[str, str] | None = None) -> None:
        super().__init__(parent)
        p = palette or {}
        self._kw = QColor(p.get("keyword", "#7aa2f7"))
        self._str = QColor(p.get("string", "#9ece6a"))
        self._num = QColor(p.get("number", "#e0af68"))
        self._com = QColor(p.get("comment", "#565f89"))
        self._pre = QColor(p.get("preprocessor", "#bb9af7"))

        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        kws = (
            "if else for while return sizeof struct union enum void int char long short "
            "unsigned const static extern break continue switch case default do "
            "float double bool true false nullptr NULL"
        ).split()
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(self._kw)
        kw_fmt.setFontWeight(QFont.Weight.DemiBold)
        for w in kws:
            pat = QRegularExpression(rf"\b{w}\b")
            self._rules.append((pat, kw_fmt))

        str_fmt = QTextCharFormat()
        str_fmt.setForeground(self._str)
        self._rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), str_fmt))
        self._rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), str_fmt))

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(self._num)
        self._rules.append((QRegularExpression(r"\b0[xX][0-9a-fA-F]+\b|\b\d+\b"), num_fmt))

        pre_fmt = QTextCharFormat()
        pre_fmt.setForeground(self._pre)
        self._rules.append(
            (
                QRegularExpression(r"^\s*#.*$", QRegularExpression.PatternOption.MultilineOption),
                pre_fmt,
            )
        )

        com_fmt = QTextCharFormat()
        com_fmt.setForeground(self._com)
        self._rules.append((QRegularExpression(r"//[^\n]*"), com_fmt))
        block_com = QRegularExpression(
            r"/\*[\s\S]*?\*/",
            QRegularExpression.PatternOption.DotMatchesEverythingOption,
        )
        self._rules.append((block_com, com_fmt))

    def highlightBlock(self, text: str) -> None:
        for rx, fmt in self._rules:
            it = rx.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
