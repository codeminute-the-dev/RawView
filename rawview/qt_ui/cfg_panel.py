"""Control Flow Graph panel — real basic block rendering via QGraphicsView."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)

# Layout constants
_NODE_W = 300
_HEADER_H = 22
_LINE_H = 15
_MAX_INSNS = 16
_PAD_BOTTOM = 8
_COL_GAP = 60
_ROW_GAP = 72

# Palette (Tokyo Night)
_C = {
    "bg": QColor("#1a1b26"),
    "node_bg": QColor("#24283b"),
    "node_border": QColor("#414868"),
    "node_hover": QColor("#7aa2f7"),
    "header_bg": QColor("#292e42"),
    "header_sep": QColor("#3b4261"),
    "text_addr": QColor("#7dcfff"),
    "text_header": QColor("#7aa2f7"),
    "text_body": QColor("#a9b1d6"),
    "text_more": QColor("#565f89"),
    "edge_cond": QColor("#9ece6a"),    # green: conditional taken
    "edge_fall": QColor("#e0af68"),    # amber: fall-through
    "edge_uncond": QColor("#7aa2f7"),  # blue: unconditional
    "edge_other": QColor("#565f89"),   # muted: default
}


def _node_height(total_insns: int) -> float:
    shown = min(total_insns, _MAX_INSNS)
    h = _HEADER_H + shown * _LINE_H + _PAD_BOTTOM
    if total_insns > _MAX_INSNS:
        h += _LINE_H
    return float(h)


def _edge_color(flow_type: str) -> QColor:
    ft = flow_type.upper()
    if "CONDITIONAL" in ft:
        return _C["edge_cond"]
    if "FALL" in ft:
        return _C["edge_fall"]
    if "UNCONDITIONAL" in ft:
        return _C["edge_uncond"]
    return _C["edge_other"]


class _BlockItem(QGraphicsRectItem):
    """A single basic block; drawn via paint(); clickable for navigation."""

    def __init__(self, node: dict[str, Any], x: float, y: float, h: float, navigate_fn) -> None:
        super().__init__(0, 0, _NODE_W, h)
        self.setPos(x, y)
        self._addr = node["id"]
        self._navigate_fn = navigate_fn
        self._node = node
        self._default_pen = QPen(_C["node_border"], 1.0)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        r = self.rect()
        w, h = r.width(), r.height()

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        pen = QPen(_C["node_hover"], 1.8) if self.isSelected() else self._default_pen
        painter.setPen(pen)
        painter.setBrush(QBrush(_C["node_bg"]))
        painter.drawRect(r)

        # Header fill
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(_C["header_bg"]))
        painter.drawRect(QRectF(1, 1, w - 2, _HEADER_H - 1))

        # Header separator
        painter.setPen(QPen(_C["header_sep"], 0.5))
        painter.drawLine(QPointF(0, _HEADER_H), QPointF(w, _HEADER_H))

        insns = self._node.get("instructions", [])
        total = self._node.get("total_insns", len(insns))

        # Header label
        hfont = QFont("Consolas", 8)
        hfont.setBold(True)
        painter.setFont(hfont)
        painter.setPen(_C["text_header"])
        painter.drawText(
            QRectF(4, 0, w - 8, _HEADER_H),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f"{self._addr}  [{total} insns]",
        )

        # Instructions
        bfont = QFont("Consolas", 8)
        painter.setFont(bfont)
        for i, insn in enumerate(insns[:_MAX_INSNS]):
            iy = float(_HEADER_H + i * _LINE_H)
            addr_text = insn.get("addr", "")
            instr_text = insn.get("text", "")

            painter.setPen(_C["text_addr"])
            painter.drawText(
                QRectF(4, iy, 84, _LINE_H),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                addr_text,
            )
            painter.setPen(_C["text_body"])
            painter.drawText(
                QRectF(92, iy, w - 96, _LINE_H),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                instr_text,
            )

        if total > _MAX_INSNS:
            iy = float(_HEADER_H + _MAX_INSNS * _LINE_H)
            painter.setFont(bfont)
            painter.setPen(_C["text_more"])
            painter.drawText(
                QRectF(4, iy, w - 8, _LINE_H),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"… {total - _MAX_INSNS} more",
            )

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self._navigate_fn:
            self._navigate_fn(self._addr)

    def hoverEnterEvent(self, event) -> None:
        self.setPen(QPen(_C["node_hover"], 1.5))
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.setPen(self._default_pen)
        self.update()
        super().hoverLeaveEvent(event)


class _PanZoomView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QBrush(_C["bg"]))
        self._zoom = 1.0

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        new_zoom = self._zoom * factor
        if 0.08 <= new_zoom <= 10.0:
            self.scale(factor, factor)
            self._zoom = new_zoom


class CfgPanel(QWidget):
    navigate_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._scene = QGraphicsScene(self)
        self._view = _PanZoomView(self._scene)
        layout.addWidget(self._view, stretch=1)
        self._status = QLabel()
        self._status.setStyleSheet("color: #565f89; font-size: 10px; padding: 1px 6px;")
        layout.addWidget(self._status)
        self._show_placeholder()

    def _show_placeholder(self, msg: str = "Select a function — CFG renders automatically after analysis.") -> None:
        self._scene.clear()
        from PySide6.QtWidgets import QGraphicsTextItem
        t = QGraphicsTextItem(msg)
        t.setDefaultTextColor(QColor("#565f89"))
        f = QFont("Consolas", 9)
        t.setFont(f)
        self._scene.addItem(t)
        self._status.clear()

    def load_cfg_json(self, data: dict[str, Any]) -> None:
        self._scene.clear()

        if data.get("error") == "no_function":
            self._show_placeholder("No function at the selected address.")
            return

        nodes: list[dict[str, Any]] = data.get("nodes", [])
        edges: list[dict[str, Any]] = data.get("edges", [])
        entry: str = data.get("entry", "")
        fn_name: str = data.get("function", "")
        truncated: bool = bool(data.get("truncated", False))

        if not nodes:
            self._show_placeholder(f"No basic blocks found for {fn_name!r}.")
            return

        node_ids = {n["id"] for n in nodes}
        layers = self._assign_layers(nodes, edges, entry, node_ids)
        positions, node_h = self._compute_positions(nodes, layers)

        # Draw edges first (behind nodes)
        for edge in edges:
            src, dst = edge.get("from", ""), edge.get("to", "")
            if src in positions and dst in positions:
                self._draw_edge(src, dst, edge.get("type", ""), positions, node_h)

        # Draw nodes
        for node in nodes:
            nid = node["id"]
            if nid not in positions:
                continue
            x, y = positions[nid]
            h = node_h[nid]
            item = _BlockItem(node, x, y, h, self._navigate)
            self._scene.addItem(item)

        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-50, -50, 50, 50))
        self._view.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._view._zoom = 1.0

        trunc = "  (truncated — too many blocks)" if truncated else ""
        self._status.setText(
            f"{fn_name}  ·  {len(nodes)} blocks  ·  {len(edges)} edges{trunc}"
            f"  ·  scroll=zoom  drag=pan  click block=navigate"
        )

    def _navigate(self, addr: str) -> None:
        self.navigate_requested.emit(addr)

    # ------------------------------------------------------------------
    # Layout

    def _assign_layers(
        self,
        nodes: list[dict],
        edges: list[dict],
        entry: str,
        node_ids: set[str],
    ) -> dict[str, int]:
        succ: dict[str, list[str]] = {n["id"]: [] for n in nodes}
        for e in edges:
            s, d = e.get("from", ""), e.get("to", "")
            if s in succ and d in node_ids:
                succ[s].append(d)

        start = entry if entry in node_ids else (nodes[0]["id"] if nodes else "")
        layers: dict[str, int] = {}
        if not start:
            return layers

        queue = [start]
        layers[start] = 0
        visited = {start}
        while queue:
            curr = queue.pop(0)
            for nxt in succ.get(curr, []):
                if nxt not in visited:
                    layers[nxt] = layers[curr] + 1
                    visited.add(nxt)
                    queue.append(nxt)

        # Nodes unreachable from entry
        max_layer = max(layers.values(), default=0)
        for n in nodes:
            if n["id"] not in layers:
                max_layer += 1
                layers[n["id"]] = max_layer

        return layers

    def _compute_positions(
        self,
        nodes: list[dict],
        layers: dict[str, int],
    ) -> tuple[dict[str, tuple[float, float]], dict[str, float]]:
        node_h: dict[str, float] = {
            n["id"]: _node_height(n.get("total_insns", len(n.get("instructions", []))))
            for n in nodes
        }

        if not layers:
            return {}, node_h

        max_layer = max(layers.values())
        by_layer: list[list[str]] = [[] for _ in range(max_layer + 1)]
        for n in nodes:
            by_layer[layers.get(n["id"], max_layer)].append(n["id"])

        def _hex_key(addr: str) -> int:
            try:
                return int(addr.strip(), 16)
            except ValueError:
                return 0

        for layer in by_layer:
            layer.sort(key=_hex_key)

        # y positions: accumulate based on tallest node in previous layer
        y_pos: list[float] = [0.0] * (max_layer + 1)
        for i in range(1, max_layer + 1):
            prev_max_h = max(
                (node_h.get(nid, _HEADER_H + _PAD_BOTTOM) for nid in by_layer[i - 1]),
                default=80.0,
            )
            y_pos[i] = y_pos[i - 1] + prev_max_h + _ROW_GAP

        positions: dict[str, tuple[float, float]] = {}
        for i, layer in enumerate(by_layer):
            if not layer:
                continue
            total_w = len(layer) * _NODE_W + (len(layer) - 1) * _COL_GAP
            start_x = -total_w / 2.0
            for j, nid in enumerate(layer):
                x = start_x + j * (_NODE_W + _COL_GAP)
                positions[nid] = (x, y_pos[i])

        return positions, node_h

    # ------------------------------------------------------------------
    # Edge drawing

    def _draw_edge(
        self,
        src: str,
        dst: str,
        flow_type: str,
        positions: dict[str, tuple[float, float]],
        node_h: dict[str, float],
    ) -> None:
        sx, sy = positions[src]
        dx, dy = positions[dst]
        sh = node_h.get(src, 80.0)

        # Bottom-center of source, top-center of destination
        x1 = sx + _NODE_W / 2.0
        y1 = sy + sh
        x2 = dx + _NODE_W / 2.0
        y2 = dy

        color = _edge_color(flow_type)
        pen = QPen(color, 1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        path = QPainterPath()
        path.moveTo(x1, y1)

        if y2 > y1:
            # Forward edge: cubic bezier S-curve
            mid_y = (y1 + y2) / 2.0
            path.cubicTo(x1, mid_y, x2, mid_y, x2, y2)
        else:
            # Back edge (loop): route to the right
            offset = _NODE_W * 0.75
            path.cubicTo(x1 + offset, y1 + 50, x2 + offset, y2 - 50, x2, y2)

        edge_item = QGraphicsPathItem(path)
        edge_item.setPen(pen)
        self._scene.addItem(edge_item)

        # Arrowhead at destination
        size = 7.0
        pts = QPolygonF([
            QPointF(x2, y2),
            QPointF(x2 - size / 2.0, y2 - size),
            QPointF(x2 + size / 2.0, y2 - size),
        ])
        arrow = QGraphicsPolygonItem(pts)
        arrow.setBrush(QBrush(color))
        arrow.setPen(QPen(Qt.PenStyle.NoPen))
        self._scene.addItem(arrow)
