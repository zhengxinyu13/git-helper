#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git 提交助手 —— PyQt6 图形界面（真玻璃拟态）

玻璃感的实现方式（重要）：
    Windows 的 DWM 亚克力接口 SetWindowCompositionAttribute 虽然能开真毛玻璃，
    但它会让窗口内容不可见、且截图/录屏得到一片空白。
    所以这里换成：窗口启动时抓一次桌面 → 高斯模糊 → 作为窗口背景自绘，
    再叠半透明白色蒙版。窗口移动结束后会重新抓取。
    卡片是真半透明（Qt 支持 widget 级 rgba），圆角也是真的 —— 这是 tkinter 做不到的部分。
"""
import os
import sys

from PyQt6.QtCore import (QDateTime, QPoint, QRect, QRectF, QObject, QRunnable,
                          Qt, QThreadPool, QTimer, pyqtSignal)
from PyQt6.QtGui import (QColor, QFont, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPixmap, QRadialGradient,
                         QIcon, QFontDatabase)
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox,
                             QComboBox, QDialog, QFileDialog, QFrame,
                             QGraphicsBlurEffect,
                             QHBoxLayout, QHeaderView, QLabel,
                             QLineEdit, QMenu, QMessageBox, QPushButton,
                             QSizeGrip, QSplitter, QSystemTrayIcon,
                             QTableWidget, QTableWidgetItem,
                             QTextEdit, QVBoxLayout, QWidget)

from gitcore import (CREDIT, DEFAULT_REPO, ERROR_LOG, RES, create_backup,
                     create_branch, delete_branch, discard_all, do_commit,
                     get_branches, get_diff, get_log, get_status, git,
                     ensure_gitignore, get_launch_at_login, init_repo,
                     is_cloud_dir, is_repo, load_config, log_exception,
                     merge_branch, abort_merge, remember_repo, reset_to,
                     restore_file, revert_commit, save_config,
                     set_launch_at_login, switch_branch)

# ---------------------------------------------------------------- 配色
CARD_BORDER = "rgba(255, 255, 255, 0.85)"

# ------------------------------------------------------- 玻璃浓度档位
# 毛玻璃透得太多时，桌面壁纸的花纹会一路透到界面上，文字区域变花、看久了累眼。
# 这里把「背景可见度」拆成一个档位，统一驱动四个参数，用户可按自己的壁纸选：
#   tint  盖在模糊桌面上的白色蒙版不透明度（0-255），越大背景越淡
#   blur  高斯模糊半径，越大背景细节越少
#   card  卡片不透明度（0-1）
#   field 输入框 / 下拉框 / 文本框
#   btn   按钮；table 表格；head 表头
#   glow  柔光强度系数（0-1），越沉越收敛
GLASS_LEVELS = {
    "通透": {"tint": 118, "blur": 26, "card": "0.42", "btn": "0.58",
             "field": "0.60", "table": "0.38", "head": "0.32", "glow": 1.0},
    "标准": {"tint": 172, "blur": 34, "card": "0.60", "btn": "0.72",
             "field": "0.74", "table": "0.54", "head": "0.48", "glow": 0.8},
    "沉稳": {"tint": 216, "blur": 44, "card": "0.76", "btn": "0.84",
             "field": "0.86", "table": "0.70", "head": "0.64", "glow": 0.5},
    "实底": {"tint": 246, "blur": 60, "card": "0.93", "btn": "0.96",
             "field": "0.97", "table": "0.90", "head": "0.86", "glow": 0.2},
}
# 默认取「沉稳」：复杂桌面下不刺眼，同时还能看出背景轮廓，玻璃感仍在。

# 自动提交撞上「文件还在写入」时，隔多久补一次（毫秒）。
# 太短会每分钟重试一次、状态栏一直跳；太长就失去「等它写完再交」的意义。
RETRY_MS = 5 * 60 * 1000
DEFAULT_GLASS = "沉稳"
TEXT = "#1f2937"
MUTED = "#7b8494"
ACCENT = "#3b6fd4"
ACCENT_HOVER = "#4c7de0"
DANGER = "#c0392b"
GREEN = "#15803d"
ORANGE = "#b45309"
RED = "#b91c1c"

SHADOW_MARGIN = 20       # 窗口四周留给阴影的空白（阴影要够宽才「浮」得起来）
CORNER = 22              # 窗口圆角
BAR_H = 52               # 自绘标题栏高度

_QSS_TEMPLATE = """
QWidget {{
    color: {text};
    font-family: "Microsoft YaHei UI";
    font-size: 9pt;
}}
QFrame#card {{
    background: {card};
    border: 1px solid {border};
    border-radius: 16px;
}}
QLabel#title {{
    font-size: 14pt;
    font-weight: bold;
    color: {text};
}}
QLabel#chip {{
    color: {accent};
    font-weight: bold;
}}
QLabel#muted {{
    color: {muted};
    font-size: 8pt;
}}
QLabel#chipWarn {{
    color: #8a5300;
    background: rgba(250, 199, 117, 0.55);
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 8pt;
}}
QLabel#groupTitle {{
    color: {muted};
    font-weight: bold;
}}
QPushButton {{
    background: {btn};
    border: 1px solid {border};
    border-radius: 9px;
    padding: 6px 14px;
    color: {text};
}}
QPushButton:hover {{ background: rgba(255, 255, 255, 0.92); }}
QPushButton:pressed {{ background: rgba(233, 240, 255, 0.95); }}
QPushButton:disabled {{ color: #b6bcc7; }}
QPushButton[accent="true"] {{
    background: {accent};
    color: #ffffff;
    border: none;
    font-weight: bold;
}}
QPushButton[accent="true"]:hover {{ background: {accent_hover}; }}
QPushButton[danger="true"] {{ color: {danger}; }}
QPushButton[danger="true"]:hover {{ background: rgba(253, 236, 235, 0.95); }}
QPushButton#winbtn {{
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 0px;
    font-size: 10pt;
}}
QPushButton#winbtn:hover {{ background: rgba(255, 255, 255, 0.85); }}
QPushButton#winbtnClose:hover {{ background: #e81123; color: #ffffff; }}
QLineEdit, QComboBox, QTextEdit {{
    background: {field};
    border: 1px solid {border};
    border-radius: 9px;
    padding: 6px 10px;
    selection-background-color: #dce8ff;
}}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
    border: 1px solid {accent};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: #ffffff;
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: #dce8ff;
}}
QTableWidget {{
    background: {table};
    border: none;
    border-radius: 12px;
    gridline-color: rgba(160, 170, 190, 0.25);
    outline: none;
}}
QTableWidget::item {{ padding: 5px 8px; }}
QTableWidget::item:selected {{ background: rgba(220, 232, 255, 0.95); color: {text}; }}
QHeaderView::section {{
    background: {head};
    border: none;
    border-bottom: 1px solid rgba(160, 170, 190, 0.30);
    padding: 6px 8px;
    color: {muted};
    font-weight: bold;
}}
QScrollBar:vertical {{
    background: transparent; width: 9px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: rgba(120, 135, 160, 0.45);
    border-radius: 4px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(120, 135, 160, 0.7); }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: rgba(120, 135, 160, 0.45);
    border-radius: 4px; min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
QCheckBox {{ background: transparent; spacing: 6px; }}

/* ---- 自绘提示框（见 GlassDialog）：跟随主界面主题，不吃系统深色模式 ---- */
QFrame#dlgCard {{ background: transparent; border: none; }}
QLabel#dlgTitle {{ color: {text}; font-size: 11pt; font-weight: bold; }}
QLabel#dlgText {{ color: {text}; }}
QPushButton#dlgClose {{
    background: transparent; border: none; border-radius: 9px; padding: 0px;
    color: {muted}; font-size: 11pt;
}}
QPushButton#dlgClose:hover {{ background: #e81123; color: #ffffff; }}
"""


def build_qss(level=None):
    """按玻璃浓度档位生成样式表。

    卡片/按钮/输入框的透明度都跟着档位走，所以切档时必须重新 setStyleSheet 一次，
    否则会出现「卡片变实了、按钮还是透的」这种不一致。
    """
    g = GLASS_LEVELS.get(level) or GLASS_LEVELS[DEFAULT_GLASS]
    return _QSS_TEMPLATE.format(
        text=TEXT, muted=MUTED, accent=ACCENT, accent_hover=ACCENT_HOVER,
        danger=DANGER, border=CARD_BORDER,
        card="rgba(255, 255, 255, %s)" % g["card"],
        btn="rgba(255, 255, 255, %s)" % g["btn"],
        field="rgba(255, 255, 255, %s)" % g["field"],
        table="rgba(255, 255, 255, %s)" % g["table"],
        head="rgba(255, 255, 255, %s)" % g["head"])


_GLOW_CACHE = {}


def glow_pixmap(col, side=256) -> QPixmap:
    """预渲染一团柔光（固定小尺寸，用时拉伸）。

    坑：不要对大矩形直接 fillRect 带 QRadialGradient —— 大面积径向渐变
    在本机软件光栅化下会卡死。固定 256×256 预渲染再缩放，成本极低。
    """
    key = (side, col)
    if key in _GLOW_CACHE:
        return _GLOW_CACHE[key]
    pm = QPixmap(side, side)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    g = QRadialGradient(side / 2.0, side / 2.0, side / 2.0)
    g.setColorAt(0.0, QColor(col[0], col[1], col[2], col[3]))
    g.setColorAt(1.0, QColor(col[0], col[1], col[2], 0))
    p.fillRect(QRectF(0, 0, side, side), g)
    p.end()
    _GLOW_CACHE[key] = pm
    return pm


def make_blurred(src: QPixmap, radius=26) -> QPixmap:
    """把桌面截图做高斯模糊，作为窗口背景"""
    if src.isNull():
        return src
    try:
        holder = QLabel()
        holder.setPixmap(src)
        holder.resize(src.size())
        eff = QGraphicsBlurEffect()
        eff.setBlurRadius(radius)
        holder.setGraphicsEffect(eff)
        return holder.grab()
    except Exception:
        return src


# ---------------------------------------------------------------- 提示框
# 为什么不用 QMessageBox：它是系统原生窗口，会跟随 Windows 的深色模式，
# 出现「深底 + 深字」完全看不清的情况（用户反馈过），而且方角、带系统标题栏，
# 跟主界面的浅色玻璃主题完全不搭。这里自绘一套同主题的对话框顶上去。
DIALOG_MARGIN = 16        # 四周留给外阴影的空白
DIALOG_RADIUS = 16        # 卡片圆角
DIALOG_TEXT_W = 520       # 正文最大宽度，超过就换行


class GlassDialog(QDialog):
    """与主界面同主题的提示框：无边框 + 圆角浅色卡片 + 柔和外阴影。

    渲染规则必须和 GlassWindow 一致（见其 render_glass 注释）：
    顶层半透明窗口的 QPainter 只能做一次 drawPixmap，path / clip / 渐变
    一律离屏预渲染，否则会直接卡死进程且不留任何日志。
    """

    ICON = {"info": ("i", "#2f7fd6"),
            "warn": ("!", "#d07b1e"),
            "error": ("×", "#cf4436"),
            "ask": ("?", "#3b6fd4")}

    def __init__(self, parent, title, text, kind="info",
                 buttons=(("ok", "确定", True),), field=None,
                 default_value=""):
        super().__init__(parent)
        self._drag = None
        self._frame = None
        self.result_key = None
        self.input = None                 # QLineEdit 或 QComboBox

        self.setWindowFlags(Qt.WindowType.Dialog |
                            Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setWindowTitle(title)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(DIALOG_MARGIN, DIALOG_MARGIN,
                                 DIALOG_MARGIN, DIALOG_MARGIN)
        card = QFrame()
        card.setObjectName("dlgCard")     # 背景由自绘 pixmap 提供，这里必须透明
        outer.addWidget(card)

        body = QVBoxLayout(card)
        body.setContentsMargins(22, 18, 22, 16)
        body.setSpacing(14)

        # 顶部一行：圆形图标 + 标题 + 关闭按钮
        head = QHBoxLayout()
        head.setSpacing(10)
        glyph, color = self.ICON.get(kind, self.ICON["info"])
        ic = QLabel(glyph)
        ic.setFixedSize(30, 30)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("background:%s; color:#ffffff; border-radius:15px;"
                         "font-size:14pt; font-weight:bold;" % color)
        head.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        lb_title = QLabel(title)
        lb_title.setObjectName("dlgTitle")
        head.addWidget(lb_title, 1, Qt.AlignmentFlag.AlignVCenter)
        btn_close = QPushButton("✕")
        btn_close.setObjectName("dlgClose")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(lambda: self._done("cancel"))
        head.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignTop)
        body.addLayout(head)

        lb_text = QLabel(text)
        lb_text.setObjectName("dlgText")
        lb_text.setWordWrap(True)
        lb_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lb_text.setMinimumWidth(290)
        lb_text.setMaximumWidth(DIALOG_TEXT_W)
        body.addWidget(lb_text)

        if field == "text":
            self.input = QLineEdit(default_value)
            self.input.setMinimumWidth(330)
            self.input.returnPressed.connect(lambda: self._done("ok"))
            body.addWidget(self.input)
        elif isinstance(field, (tuple, list)) and len(field) >= 2:
            self.input = QComboBox()
            self.input.addItems([str(x) for x in field[1]])
            cur = int(field[2]) if len(field) > 2 else 0
            if 0 <= cur < self.input.count():
                self.input.setCurrentIndex(cur)
            self.input.setMinimumWidth(330)
            body.addWidget(self.input)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)
        for key, label, accent in buttons:
            b = QPushButton(label)
            if accent:
                b.setProperty("accent", True)
                b.setDefault(True)
            b.setMinimumSize(88, 32)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._done(k))
            row.addWidget(b)
        body.addLayout(row)

        self.adjustSize()
        self._center_on_parent()
        self._build_frame()
        if self.input is not None:
            QTimer.singleShot(0, self.input.setFocus)

    # ------------------------------------------------------------ 渲染
    def _build_frame(self):
        """离屏预渲染：外阴影 + 圆角浅色卡片 + 两道描边。"""
        W, H = max(1, self.width()), max(1, self.height())
        inner = QRect(DIALOG_MARGIN, DIALOG_MARGIN,
                      max(1, W - DIALOG_MARGIN * 2),
                      max(1, H - DIALOG_MARGIN * 2))
        fm = QPixmap(W, H)
        fm.fill(Qt.GlobalColor.transparent)
        p = QPainter(fm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 外阴影（QRect.adjusted 只接受 int —— 传 float 会抛 TypeError 并杀进程）
        for i in range(6, 0, -1):
            pad = int(i * 2.0)
            sp = QPainterPath()
            sp.addRoundedRect(QRectF(inner.adjusted(-pad, -pad + 2, pad, pad)),
                              float(DIALOG_RADIUS + pad),
                              float(DIALOG_RADIUS + pad))
            p.fillPath(sp, QColor(17, 23, 38, 3 + i * 3))

        # 卡片底：浅色近乎不透明，保证任何壁纸下文字都清晰
        card = QPainterPath()
        card.addRoundedRect(QRectF(inner), float(DIALOG_RADIUS),
                            float(DIALOG_RADIUS))
        p.fillPath(card, QColor(249, 251, 255, 252))

        # 描边两道：外侧淡灰（浅底上也看得出轮廓）+ 内侧白高光
        op = QPainterPath()
        op.addRoundedRect(QRectF(inner.adjusted(-1, -1, 1, 1)),
                          float(DIALOG_RADIUS + 1), float(DIALOG_RADIUS + 1))
        p.setPen(QPen(QColor(118, 130, 156, 90), 1))
        p.drawPath(op)
        p.setPen(QPen(QColor(255, 255, 255, 240), 1))
        p.drawPath(card)
        p.end()
        self._frame = fm

    def paintEvent(self, event):
        """只贴一张预渲染好的位图（规则同 GlassWindow）。"""
        f = self._frame
        if f is None or f.isNull():
            return super().paintEvent(event)
        p = QPainter(self)
        p.drawPixmap(0, 0, f)
        p.end()

    # ------------------------------------------------------------ 交互
    def _center_on_parent(self):
        par = self.parentWidget()
        if par is not None and par.isVisible():
            c = par.frameGeometry().center()
        else:
            scr = self.screen() or QApplication.primaryScreen()
            if scr is None:
                return
            c = scr.availableGeometry().center()
        self.move(c.x() - self.width() // 2, c.y() - self.height() // 2)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = (event.globalPosition().toPoint() -
                          self.frameGeometry().topLeft())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag is not None and (event.buttons() &
                                       Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._done("cancel")
            return
        super().keyPressEvent(event)

    def _done(self, key):
        self.result_key = key
        if key == "ok":
            self.accept()
        else:
            self.reject()

    def value(self):
        if self.input is None:
            return ""
        if isinstance(self.input, QComboBox):
            return self.input.currentText()
        return self.input.text()

    def run(self):
        """模态执行，返回被点的按钮 key（ok / cancel），取消或异常为 None。"""
        self.exec()
        return self.result_key


class Msg:
    """统一的提示框入口。

    方法名刻意与 QMessageBox / QInputDialog 保持同名同义，这样原来的调用点
    只需把类名换掉即可 —— 尤其 question() 返回 QMessageBox.StandardButton，
    调用点的「!= QMessageBox.StandardButton.Yes」一个字都不用改。
    """

    @staticmethod
    def _show(parent, title, text, kind, buttons,
              field=None, default_value=""):
        try:
            d = GlassDialog(parent, title, text, kind=kind, buttons=buttons,
                            field=field, default_value=default_value)
            return d.run(), d
        except Exception:
            # 自绘失败就用原生兜底，至少别让用户什么都看不到
            # （这里必须显式写 QMessageBox，写成 Msg.* 会无限递归）
            log_exception(*sys.exc_info())
            try:
                QMessageBox.information(parent, title, text)
            except Exception:
                pass
            return None, None

    @staticmethod
    def information(parent, title, text):
        Msg._show(parent, title, text, "info", (("ok", "确定", True),))

    @staticmethod
    def warning(parent, title, text):
        Msg._show(parent, title, text, "warn", (("ok", "确定", True),))

    @staticmethod
    def critical(parent, title, text):
        Msg._show(parent, title, text, "error", (("ok", "确定", True),))

    @staticmethod
    def question(parent, title, text, ok_text="确定", cancel_text="取消"):
        """返回 QMessageBox.StandardButton，与原生 question() 行为一致。"""
        key, _d = Msg._show(parent, title, text, "ask",
                            (("ok", ok_text, True), ("cancel", cancel_text, False)))
        if key == "ok":
            return QMessageBox.StandardButton.Yes
        return QMessageBox.StandardButton.No

    @staticmethod
    def getText(parent, title, label, ok_text="确定", cancel_text="取消"):
        key, d = Msg._show(parent, title, label, "ask",
                           (("ok", ok_text, True), ("cancel", cancel_text, False)),
                           field="text")
        if key == "ok" and d is not None:
            return d.value(), True
        return "", False

    @staticmethod
    def getItem(parent, title, label, items, current=0, editable=False):
        key, d = Msg._show(parent, title, label, "ask",
                           (("ok", "确定", True), ("cancel", "取消", False)),
                           field=("choice", list(items), current))
        if key == "ok" and d is not None:
            return d.value(), True
        return "", False


# ---------------------------------------------------------------- 后台执行
# git 命令是子进程调用，在云盘目录里尤其慢（status 要扫一遍工作区）。
# 直接放在主线程里跑，执行那几百毫秒到几秒里界面是完全卡住的：
# 拖不动、按钮没反应。所以统一丢到后台线程，主线程只负责收结果刷界面。
class _TaskSignals(QObject):
    done = pyqtSignal(object)
    error = pyqtSignal(str)


class _Task(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = _TaskSignals()

    def run(self):
        try:
            self.signals.done.emit(self.fn())
        except Exception as e:
            self.signals.error.emit(str(e))


class GlassWindow(QWidget):
    """无边框 + 半透明 + 自绘玻璃背景的主窗口。

    注意：这里刻意继承 QWidget 而不是 QMainWindow —— QMainWindow 重写
    paintEvent 后，半透明窗口会出现重绘风暴（Qt 认为画面永远没画完），
    表现为界面卡死在第一帧。QWidget 顶层窗口没有这个问题。
    """

    def __init__(self, repo=None):
        super().__init__()
        self.cfg = load_config()
        self.repo = repo or self.cfg.get("lastRepo") or DEFAULT_REPO
        self.glass_name = self.cfg.get("glassLevel") or DEFAULT_GLASS
        if self.glass_name not in GLASS_LEVELS:
            self.glass_name = DEFAULT_GLASS
        self.glass = GLASS_LEVELS[self.glass_name]
        self.files, self.logs, self.branches = [], [], []
        self.backdrop = QPixmap()
        self._frame = None                # 整窗离屏渲染缓存（阴影+玻璃+边框）
        self._frame_size = None
        self._drag_pos = None
        self._maximized = False

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("Git 提交助手")
        self.resize(1460, 950)
        self.setMinimumSize(1080, 680)
        self._center_on_screen()

        self._build_ui()
        self._wire_timers()
        self._mark_cloud()

        # 同一仓库上的 git 操作必须串行：两个 git 同时写 .git 会互相踩
        # （典型后果是 index.lock 报错、提交丢一半）。所以池子里只留 1 条线程。
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._tasks = []
        self._pending = 0
        self._real_close = False          # 托盘菜单「退出」时置 True，绕开缩托盘
        self._init_tray()

        # 关键：在窗口 show 之前抓桌面，抓到的才是纯桌面背景（不含自己）
        self.grab_backdrop()

        # 启动后立刻读一次仓库，不用干等第一个 20 秒轮询
        QTimer.singleShot(200, self.refresh)
        QTimer.singleShot(1500, self.auto_tick)
        QTimer.singleShot(2000, self._warn_cloud)

    # ------------------------------------------------------------ 系统托盘
    def _init_tray(self):
        """托盘常驻：关掉窗口只是藏起来，定时自动提交继续在后台跑。

        这是「自动提交」能真正自动的前提 —— 否则窗口一关，定时器就没了。
        """
        self.tray = None
        # 开机自启以注册表为准（配置可能和真实状态不同步），托盘可用与否都要同步
        if hasattr(self, "chk_boot"):
            self.chk_boot.blockSignals(True)
            self.chk_boot.setChecked(get_launch_at_login())
            self.chk_boot.blockSignals(False)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon_path = os.path.join(RES, "app.ico")
        self.tray = QSystemTrayIcon(QIcon(icon_path) if os.path.exists(icon_path)
                                    else QIcon(), self)
        self.tray.setToolTip("Git 提交助手")

        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background: #fbfcfe; border: 1px solid rgba(120,132,156,0.35);"
            " border-radius: 10px; padding: 6px; }"
            "QMenu::item { padding: 6px 22px; border-radius: 6px; color: #2f3742; }"
            "QMenu::item:selected { background: #e7efff; }")

        act_show = menu.addAction("打开主界面")
        act_show.triggered.connect(self._tray_show)
        act_now = menu.addAction("立即提交")
        act_now.triggered.connect(self.run_now)
        menu.addSeparator()
        self.act_boot = menu.addAction("开机自启")
        self.act_boot.setCheckable(True)
        self.act_boot.setChecked(get_launch_at_login())
        self.act_boot.triggered.connect(self._toggle_boot)
        menu.addSeparator()
        act_quit = menu.addAction("退出")
        act_quit.triggered.connect(self._tray_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        # 窗口藏起来时不能让 Qt 认为「最后一个窗口关了」而直接退出程序
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(False)

    def _tray_show(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.grab_backdrop()

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick,
                      QSystemTrayIcon.ActivationReason.Trigger):
            self._tray_show()

    def _apply_boot(self, checked):
        """开机自启总入口：写 HKCU 的 Run 项，并把状态栏和托盘菜单两处开关同步。

        开机自启只对打包后的 exe 生效 —— 源码模式没有可登记的程序路径。
        """
        widgets = [getattr(self, "act_boot", None), getattr(self, "chk_boot", None)]
        if not set_launch_at_login(checked):
            for wgt in widgets:
                if wgt is None:
                    continue
                wgt.blockSignals(True)
                wgt.setChecked(False)
                wgt.blockSignals(False)
            Msg.information(
                self, "未能设置",
                "开机自启只对打包后的程序生效（源码模式没有可登记的程序路径）。")
            return
        self.cfg["launchAtLogin"] = checked
        save_config(self.cfg)
        for wgt in widgets:
            if wgt is None:
                continue
            wgt.blockSignals(True)
            wgt.setChecked(checked)
            wgt.blockSignals(False)
        self.set_status("开机自启已%s" % ("开启" if checked else "关闭"))

    def _toggle_boot(self, checked):
        self._apply_boot(checked)

    def on_boot_change(self, *_a):
        self._apply_boot(self.chk_boot.isChecked())

    def _tray_quit(self):
        self._real_close = True
        self.close()

    def _center_on_screen(self):
        try:
            scr = QApplication.primaryScreen()
            if scr is None:
                return
            avail = scr.availableGeometry()
            w = min(1460, avail.width() - 80)
            h = min(950, avail.height() - 80)
            self.resize(w, h)
            self.move(avail.x() + (avail.width() - w) // 2,
                      avail.y() + (avail.height() - h) // 2)
        except Exception:
            pass

    # ------------------------------------------------------------ 背景
    def grab_backdrop(self):
        """抓一次桌面并模糊，存起来当窗口背景"""
        if not self.cfg.get("blurBackground", True):
            self.backdrop = QPixmap()
            self._rebuild_frame()
            return
        try:
            screen = self.screen() or QApplication.primaryScreen()
            if screen is None:
                return
            full = screen.grabWindow(0)
            if full.isNull():
                return
            g = self.frameGeometry()
            x = max(0, g.x())
            y = max(0, g.y())
            w = min(self.width(), max(1, full.width() - x))
            h = min(self.height(), max(1, full.height() - y))
            if w <= 1 or h <= 1:
                return
            crop = full.copy(QRect(x, y, w, h))
            self.backdrop = make_blurred(crop, self.glass["blur"])
        except Exception:
            self.backdrop = QPixmap()
        self._rebuild_frame()             # 背景变了，整窗缓存重建

    def render_glass(self, w, h, radius):
        """离屏渲染玻璃底图（不含阴影和边框）。

        重大坑（本机实测）：
          1. 顶层半透明窗口的 QPainter 上做 setClipPath() 会卡死；
          2. 在窗口上做抗锯齿的 fillPath() 同样卡死；
          3. 对大矩形 fillRect 一个 QRadialGradient 也会卡死。
        结论：窗口的 paintEvent 只允许做一次 drawPixmap，其余全部离屏预渲染。
        """
        pm = QPixmap(w, h)
        pm.fill(Qt.GlobalColor.transparent)
        pp = QPainter(pm)
        pp.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 圆角裁剪：必须在画内容「之前」用 setClipPath 定好裁剪区。
        #
        # 坑（PyQt6 6.11 实测）：不要用 DestinationIn 合成模式去裁 ——
        # `setCompositionMode(DestinationIn) + fillPath(圆角矩形)` 在 QPixmap 上
        # 完全不生效（换成 ARGB32 格式、换成 QBrush 结果一样），四角会残留
        # 「模糊桌面 + 白蒙版」，在深色壁纸上表现为窗口圆角外侧一块白透的小三角。
        # setClipPath 在**离屏 pixmap** 上是好的；会卡死的是顶层半透明窗口的
        # QPainter（见上方函数注释），两者别混。
        if radius > 0:
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(0, 0, w, h), float(radius), float(radius))
            pp.setClipPath(clip)

        # 底：模糊桌面，没有就用渐变
        if not self.backdrop.isNull():
            pp.drawPixmap(QRectF(0, 0, w, h), self.backdrop,
                          QRectF(0, 0, self.backdrop.width(), self.backdrop.height()))
        else:
            grad = QLinearGradient(0, 0, w, h)
            grad.setColorAt(0.0, QColor("#dfe7f5"))
            grad.setColorAt(1.0, QColor("#eef1fa"))
            pp.fillRect(QRectF(0, 0, w, h), grad)

        # 白色蒙版 —— 玻璃感主体，也是「背景有多花」的总闸
        pp.fillRect(QRectF(0, 0, w, h), QColor(246, 249, 255, self.glass["tint"]))

        # 两团柔光：用预渲染的小贴图放大贴（大尺寸径向渐变会拖垮软件光栅化）
        gk = self.glass["glow"]
        for fx, fy, fr, col in ((0.20, 0.12, 0.42, (150, 190, 255, int(92 * gk))),
                                (0.86, 0.80, 0.45, (200, 175, 255, int(84 * gk)))):
            r = max(40, int(w * fr))
            blob = glow_pixmap(col)
            pp.drawPixmap(QRectF(int(w * fx) - r, int(h * fy) - r, r * 2, r * 2),
                          blob, QRectF(blob.rect()))

        pp.end()
        return pm

    def build_frame(self):
        """整窗离屏渲染：阴影 + 玻璃底 + 高光边框，全部画进一张 pixmap。

        paintEvent 里只 drawPixmap 一次，绝不碰 path / clip / 渐变。
        """
        W, H = max(1, self.width()), max(1, self.height())
        inner = QRect(SHADOW_MARGIN, SHADOW_MARGIN,
                      max(1, W - SHADOW_MARGIN * 2), max(1, H - SHADOW_MARGIN * 2))
        radius = 0 if self._maximized else CORNER

        frame = QPixmap(W, H)
        frame.fill(Qt.GlobalColor.transparent)
        p = QPainter(frame)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 1) 外阴影（QRect.adjusted 只接受 int，传 float 会抛 TypeError
        #    并让整个进程直接退出 —— 这个坑踩过一次）
        #    分 8 层由外向内叠加：越靠外越淡。原先只有 4 层、扩散不到 11px，
        #    在浅色/花哨壁纸上几乎看不见，窗口边界糊在背景里，看起来就像
        #    「直角矩形 + 角上一条圆弧」。加宽后圆角轮廓才浮得出来。
        if not self._maximized:
            for i in range(8, 0, -1):
                pad = int(i * 2.2)
                sp = QPainterPath()
                sp.addRoundedRect(QRectF(inner.adjusted(-pad, -pad + 2, pad, pad)),
                                  float(radius + pad), float(radius + pad))
                p.fillPath(sp, QColor(17, 23, 38, 3 + i * 2))

        # 2) 玻璃底
        glass = self.render_glass(inner.width(), inner.height(), radius)
        p.drawPixmap(inner.topLeft(), glass)

        # 3) 边缘两道：外侧淡灰 + 内侧白色高光。
        #    只留一道白高光时，玻璃边缘在浅色壁纸上完全看不出，圆角就"消失"了。
        outer = QPainterPath()
        outer.addRoundedRect(QRectF(inner.adjusted(-1, -1, 1, 1)),
                             float(radius + 1), float(radius + 1))
        p.setPen(QPen(QColor(118, 130, 156, 95), 1))
        p.drawPath(outer)

        path = QPainterPath()
        path.addRoundedRect(QRectF(inner), radius, radius)
        p.setPen(QPen(QColor(255, 255, 255, 240), 1))
        p.drawPath(path)
        p.end()

        self._frame = frame
        self._frame_size = (W, H, radius)

    def _schedule_frame(self):
        """防抖重建整窗缓存（不在 paint 里做重活）"""
        if getattr(self, "_frame_timer", None) is None:
            self._frame_timer = QTimer(self)
            self._frame_timer.setSingleShot(True)
            self._frame_timer.timeout.connect(self._rebuild_frame)
        self._frame_timer.start(150)

    def _rebuild_frame(self):
        self._frame = None
        self.build_frame()
        self.update()

    def paintEvent(self, event):
        """只贴一张现成的位图。

        重大坑（本机实测）：绝不能在 paintEvent 里创建/绘制离屏 QPixmap，
        否则第一次 paint 就不会返回，界面卡死在白屏。所有绘制必须在
        paint 之外完成，这里只允许 drawPixmap。
        """
        f = self._frame
        if f is None or f.isNull():
            return super().paintEvent(event)

        # 兜底：paintEvent 里任何异常都会让 Qt 直接结束进程（界面"sudden death"），
        # 表现为窗口一闪就没了且没有任何提示。这里全部吞掉，只记日志。
        try:
            p = QPainter(self)
            if f.size() == self.size():
                p.drawPixmap(0, 0, f)
            else:
                # 尺寸变化后、防抖重建前的过渡：拉伸旧图顶上
                p.drawPixmap(self.rect(), f, f.rect())
            p.end()
        except Exception:
            log_exception(*sys.exc_info())

    def moveEvent(self, event):
        super().moveEvent(event)
        self._schedule_backdrop()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_backdrop()
        self._schedule_frame()

    def _schedule_backdrop(self):
        if getattr(self, "_bd_timer", None) is None:
            self._bd_timer = QTimer(self)
            self._bd_timer.setSingleShot(True)
            self._bd_timer.timeout.connect(self.grab_backdrop)
        self._bd_timer.start(180)

    # ------------------------------------------------------------ 无边框的拖动
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= BAR_H + SHADOW_MARGIN:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if self._maximized:
                self._toggle_max()
                return
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def _toggle_max(self):
        if self._maximized:
            self._maximized = False
            self.showNormal()
        else:
            self._maximized = True
            self.showMaximized()
        QTimer.singleShot(120, self.grab_backdrop)

    def _minimize(self):
        self.showMinimized()

    # ------------------------------------------------------------ 界面搭建
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SHADOW_MARGIN + 16, SHADOW_MARGIN + 4,
                                 SHADOW_MARGIN + 16, SHADOW_MARGIN + 12)
        outer.setSpacing(8)

        outer.addLayout(self._build_titlebar())
        outer.addLayout(self._build_reporow())
        outer.addLayout(self._build_branchrow())
        outer.addLayout(self._build_body(), 1)
        outer.addLayout(self._build_statusbar())

    def _build_titlebar(self):
        bar = QHBoxLayout()
        bar.setContentsMargins(4, 0, 0, 0)

        self.lbl_title = QLabel("Git 提交助手")
        self.lbl_title.setObjectName("title")
        bar.addWidget(self.lbl_title)

        self.lbl_chip = QLabel("—")
        self.lbl_chip.setObjectName("chip")
        bar.addWidget(self.lbl_chip)
        bar.addSpacing(10)

        self.chk_auto = QCheckBox("自动提交")
        self.chk_auto.setChecked(bool(self.cfg.get("autoEnabled")))
        self.chk_auto.stateChanged.connect(self.on_schedule_change)
        bar.addWidget(self.chk_auto)

        self.cb_interval = QComboBox()
        self.cb_interval.addItems(["1", "2", "4", "8", "24"])
        self.cb_interval.setCurrentText(str(self.cfg.get("intervalHours", 1)))
        self.cb_interval.setFixedWidth(70)
        self.cb_interval.currentTextChanged.connect(self.on_schedule_change)
        bar.addWidget(self.cb_interval)
        bar.addWidget(QLabel("小时"))

        self.btn_runnow = QPushButton("立即执行")
        self.btn_runnow.clicked.connect(self.run_now)
        bar.addWidget(self.btn_runnow)

        self.chk_safe = QCheckBox("跳过写入中")
        self.chk_safe.setChecked(bool(self.cfg.get("skipUnstable", True)))
        self.chk_safe.setToolTip(
            "提交时跳过三类文件：Office/WPS 的 ~$ 锁文件、正被 Office 打开的文档、"
            "以及 2 分钟内刚改过的文件（云盘可能还没同步完）。\n"
            "取消勾选 = 回到原来的「全部 add 进去」。")
        self.chk_safe.stateChanged.connect(self.on_safe_change)
        bar.addWidget(self.chk_safe)

        self.lbl_last = QLabel("")
        self.lbl_last.setObjectName("muted")
        bar.addWidget(self.lbl_last)

        self.lbl_cloud = QLabel("")
        self.lbl_cloud.setObjectName("chipWarn")
        self.lbl_cloud.setVisible(False)
        bar.addWidget(self.lbl_cloud)

        bar.addStretch(1)

        for txt, fn, close in (("—", self._minimize, False),
                               ("□", self._toggle_max, False),
                               ("✕", self.close, True)):
            b = QPushButton(txt)
            b.setObjectName("winbtnClose" if close else "winbtn")
            b.setFixedSize(34, 30)
            b.clicked.connect(fn)
            bar.addWidget(b)
        return bar

    def _build_reporow(self):
        row = QHBoxLayout()
        row.addWidget(QLabel("仓库："))
        self.ed_repo = QLineEdit(self.repo)
        self.ed_repo.returnPressed.connect(self.open_repo)
        row.addWidget(self.ed_repo, 1)

        self.cb_recent = QComboBox()
        self.cb_recent.setFixedWidth(230)
        self.cb_recent.currentTextChanged.connect(self.on_recent)
        row.addWidget(self.cb_recent)

        b = QPushButton("浏览")
        b.clicked.connect(self.browse_repo)
        row.addWidget(b)

        b = QPushButton("打开")
        b.setProperty("accent", True)
        b.clicked.connect(self.open_repo)
        row.addWidget(b)

        b = QPushButton("初始化此目录并首次提交")
        b.clicked.connect(self.init_current)
        row.addWidget(b)

        b = QPushButton("忽略规则")
        b.setToolTip("在仓库里生成 / 补齐 .gitignore：\n"
                     "Office 锁文件（~$*）、临时文件、云盘冲突副本等默认不入库。")
        b.clicked.connect(self.do_gitignore)
        row.addWidget(b)
        self.update_recent()
        return row

    def _build_branchrow(self):
        row = QHBoxLayout()
        row.addWidget(QLabel("分支："))
        self.cb_branch = QComboBox()
        self.cb_branch.setFixedWidth(230)
        row.addWidget(self.cb_branch)

        for txt, fn, danger in (("切换", self.do_switch, False),
                                ("新建", self.do_create_branch, False),
                                ("合并到当前分支", self.do_merge, False),
                                ("删除", self.do_delete_branch, True),
                                ("中止合并", self.do_abort_merge, True)):
            b = QPushButton(txt)
            if danger:
                b.setProperty("danger", True)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        return row

    def _build_body(self):
        body = QVBoxLayout()
        body.setSpacing(12)

        # ---------- 上半：变更 | 历史（可拖动分隔条）
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(10)
        split.setStyleSheet(
            "QSplitter::handle { background: transparent; }"
            "QSplitter::handle:hover { background: rgba(59,111,212,0.25);"
            " border-radius: 3px; }")

        # --- 左卡：工作区变更
        left = QFrame()
        left.setObjectName("card")
        left.setMinimumWidth(420)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(16, 14, 16, 16)
        lv.setSpacing(10)

        head = QHBoxLayout()
        t = QLabel("工作区变更")
        t.setObjectName("groupTitle")
        head.addWidget(t)
        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("muted")
        head.addWidget(self.lbl_count)
        head.addStretch(1)
        b = QPushButton("全选")
        b.clicked.connect(self.sel_all)
        head.addWidget(b)
        b = QPushButton("全不选")
        b.clicked.connect(self.sel_none)
        head.addWidget(b)
        lv.addLayout(head)

        self.tbl_files = QTableWidget(0, 2)
        self.tbl_files.setHorizontalHeaderLabels(["状态", "文件"])
        self.tbl_files.verticalHeader().setVisible(False)
        self.tbl_files.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_files.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tbl_files.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_files.setShowGrid(False)
        self.tbl_files.setWordWrap(False)
        hh = self.tbl_files.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.resizeSection(0, 64)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setHighlightSections(False)
        lv.addWidget(self.tbl_files, 1)

        msgrow = QHBoxLayout()
        msgrow.addWidget(QLabel("提交说明："))
        self.ed_msg = QLineEdit()
        self.ed_msg.setPlaceholderText("留空则自动生成「chore: 自动提交 时间」")
        msgrow.addWidget(self.ed_msg, 1)
        lv.addLayout(msgrow)

        r = QHBoxLayout()
        b = QPushButton("提交选中 / 全部")
        b.setProperty("accent", True)
        b.clicked.connect(self.on_commit)
        r.addWidget(b)
        b = QPushButton("刷新")
        b.clicked.connect(self.refresh)
        r.addWidget(b)
        r.addStretch(1)
        b = QPushButton("还原选中文件")
        b.clicked.connect(self.restore_selected)
        r.addWidget(b)
        b = QPushButton("撤销全部未提交改动")
        b.setProperty("danger", True)
        b.clicked.connect(self.discard_all)
        r.addWidget(b)
        lv.addLayout(r)

        # --- 右卡：提交历史
        right = QFrame()
        right.setObjectName("card")
        right.setMinimumWidth(420)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(16, 14, 16, 16)
        rv.setSpacing(10)

        head2 = QHBoxLayout()
        t = QLabel("提交历史")
        t.setObjectName("groupTitle")
        head2.addWidget(t)
        head2.addStretch(1)
        for txt, fn, danger in (("查看差异", self.show_commit_diff, False),
                                ("反向撤销", self.revert_commit, False),
                                ("回退到此", self.reset_to_commit, True)):
            b = QPushButton(txt)
            if danger:
                b.setProperty("danger", True)
            b.clicked.connect(fn)
            head2.addWidget(b)
        rv.addLayout(head2)

        self.tbl_log = QTableWidget(0, 3)
        self.tbl_log.setHorizontalHeaderLabels(["版本", "说明", "作者 · 时间"])
        self.tbl_log.verticalHeader().setVisible(False)
        self.tbl_log.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_log.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl_log.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_log.setShowGrid(False)
        self.tbl_log.setWordWrap(False)
        hh2 = self.tbl_log.horizontalHeader()
        hh2.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh2.resizeSection(0, 74)
        hh2.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh2.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh2.resizeSection(2, 218)
        hh2.setHighlightSections(False)
        rv.addWidget(self.tbl_log, 1)

        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        split.setSizes([700, 700])
        body.addWidget(split, 3)

        # ---------- 下方：差异预览（横跨整宽）
        diffcard = QFrame()
        diffcard.setObjectName("card")
        dv = QVBoxLayout(diffcard)
        dv.setContentsMargins(16, 12, 16, 14)
        dv.setSpacing(8)

        head3 = QHBoxLayout()
        t = QLabel("差异预览")
        t.setObjectName("groupTitle")
        head3.addWidget(t)
        head3.addStretch(1)
        for txt, kind in (("未暂存改动", "unstaged"), ("已暂存改动", "staged")):
            b = QPushButton(txt)
            b.clicked.connect(lambda _c, k=kind: self.show_diff(k))
            head3.addWidget(b)
        dv.addLayout(head3)

        self.txt_diff = QTextEdit()
        self.txt_diff.setReadOnly(True)
        self.txt_diff.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(9)
        self.txt_diff.setFont(mono)
        self.txt_diff.setPlainText("选中一次提交后点「查看差异」，或点右上两个按钮看工作区改动。")
        dv.addWidget(self.txt_diff, 1)
        body.addWidget(diffcard, 2)
        return body

    def _build_statusbar(self):
        row = QHBoxLayout()
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setObjectName("muted")
        row.addWidget(self.lbl_status)
        row.addStretch(1)

        self.chk_tray = QCheckBox("缩到托盘")
        self.chk_tray.setChecked(bool(self.cfg.get("minimizeToTray", True)))
        self.chk_tray.setToolTip(
            "关闭窗口时只藏到系统托盘，定时自动提交继续在后台跑。\n"
            "取消勾选后，关窗口就是真正退出（自动提交随之停止）。")
        self.chk_tray.stateChanged.connect(self.on_tray_change)
        row.addWidget(self.chk_tray)
        row.addSpacing(10)

        self.chk_boot = QCheckBox("开机自启")
        self.chk_boot.setToolTip("登录 Windows 后自动启动（登记在「当前用户」的启动项里）。")
        self.chk_boot.stateChanged.connect(self.on_boot_change)
        row.addWidget(self.chk_boot)
        row.addSpacing(12)

        lb = QLabel("玻璃浓度")
        lb.setObjectName("muted")
        row.addWidget(lb)
        self.cb_glass = QComboBox()
        self.cb_glass.addItems(list(GLASS_LEVELS.keys()))
        self.cb_glass.setCurrentText(self.glass_name)
        self.cb_glass.setFixedWidth(88)
        self.cb_glass.setToolTip(
            "桌面壁纸花、看久了累眼时，选「沉稳」或「实底」：\n"
            "背景会被压得更淡、模糊更强，卡片也更实。")
        self.cb_glass.currentTextChanged.connect(self.on_glass_change)
        row.addWidget(self.cb_glass)
        row.addSpacing(12)

        credit = QLabel(CREDIT)
        credit.setObjectName("muted")
        credit.setStyleSheet("color:#9aa1ab;")
        row.addWidget(credit)
        grip = QSizeGrip(self)
        row.addWidget(grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        return row

    def on_glass_change(self, name):
        """切换玻璃浓度：换样式表 + 按新模糊半径重抓桌面 + 重建整窗缓存。

        三件事必须一起做，缺一个就会出现「卡片实了但背景还是花的」这类半吊子状态。
        """
        if name not in GLASS_LEVELS:
            return
        self.glass_name = name
        self.glass = GLASS_LEVELS[name]
        self.cfg["glassLevel"] = name
        save_config(self.cfg)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_qss(name))
        self.grab_backdrop()
        self.set_status("玻璃浓度已切换为：%s（已记住，下次启动沿用）" % name)

    def on_tray_change(self, *_a):
        on = self.chk_tray.isChecked()
        self.cfg["minimizeToTray"] = on
        save_config(self.cfg)
        self.set_status("关闭窗口时：%s"
                        % ("缩到托盘，后台继续自动提交" if on else "直接退出程序"))

    def on_safe_change(self, *_a):
        self.cfg["skipUnstable"] = self.chk_safe.isChecked()
        save_config(self.cfg)
        self.set_status("跳过写入中的文件：%s"
                        % ("开启" if self.cfg["skipUnstable"] else "关闭（全部提交）"))

    def _wire_timers(self):
        self.timer_refresh = QTimer(self)
        self.timer_refresh.timeout.connect(self.refresh)
        self.timer_refresh.start(20000)

        self.timer_auto = QTimer(self)
        self.timer_auto.timeout.connect(self.auto_tick)
        self.timer_auto.start(60000)

    # ------------------------------------------------------------ 仓库
    def update_recent(self):
        self.cb_recent.blockSignals(True)
        self.cb_recent.clear()
        vals = [r for r in self.cfg.get("recentRepos", []) if r]
        if vals:
            self.cb_recent.addItems(vals)
        self.cb_recent.blockSignals(False)

    def on_recent(self, text):
        if text:
            self.ed_repo.setText(text)
            self.open_repo()

    def browse_repo(self):
        d = QFileDialog.getExistingDirectory(
            self, "选择一个文件夹（可以是普通文件夹）",
            self.repo or DEFAULT_REPO)
        if d:
            self.ed_repo.setText(os.path.normpath(d))
            self.open_repo()

    def open_repo(self):
        path = os.path.normpath(self.ed_repo.text().strip().strip('"'))
        self.ed_repo.setText(path)
        if not os.path.isdir(path):
            Msg.warning(self, "路径无效",
                                "目录不存在：\n%s\n\n点「初始化此目录并首次提交」可以创建它。" % path)
            return
        self.repo = path
        self._mark_cloud()
        if is_repo(path):
            remember_repo(self.cfg, path)
            self.update_recent()
            self.set_status("已打开仓库：%s" % path)
            self.refresh()
            self._warn_cloud()
        else:
            self.set_status("该目录不是 Git 仓库，点「初始化此目录并首次提交」即可。")
            self.clear_views()
            self.lbl_chip.setText("未初始化")
            self.lbl_count.setText("（不是 Git 仓库）")

    def init_current(self):
        path = os.path.normpath(self.ed_repo.text().strip().strip('"'))
        if not path:
            Msg.information(self, "提示", "先填或浏览一个文件夹路径。")
            return
        if not os.path.isdir(path):
            if Msg.question(self, "目录不存在", "目录不存在：\n%s\n\n要创建它吗？" % path) \
                    != QMessageBox.StandardButton.Yes:
                return
        if is_repo(path):
            Msg.information(self, "提示", "已经是 Git 仓库了，无需初始化。")
            return
        if Msg.question(
                self, "确认初始化",
                "将在下面这个目录执行 git init，并把现有文件全部纳入首次提交：\n\n%s" % path) \
                != QMessageBox.StandardButton.Yes:
            return
        self._run(lambda: init_repo(path),
                  lambda res: self._after_init(path, res), "初始化仓库…")

    def _after_init(self, path, res):
        ok, msg = res
        if not ok:
            Msg.critical(self, "初始化失败", msg)
            return
        self.repo = path
        self.ed_repo.setText(path)
        self._mark_cloud()
        remember_repo(self.cfg, path)
        self.update_recent()
        Msg.information(self, "完成", msg)
        self.set_status(msg)
        self.refresh()
        self._warn_cloud()

    def do_gitignore(self):
        """生成 / 补齐默认忽略规则。"""
        path = os.path.normpath(self.ed_repo.text().strip().strip('"'))
        if not path or not os.path.isdir(path):
            Msg.information(self, "提示", "先填写或浏览一个仓库目录。")
            return
        try:
            n = ensure_gitignore(path)
        except Exception as e:
            Msg.critical(self, "写入失败", str(e))
            return
        if is_repo(path):
            self.refresh()
        Msg.information(
            self, "完成",
            ("已在 %s 写入 %d 条默认忽略规则：\n"
             "Office 锁文件、临时文件、云盘冲突副本等不再入库。" % (path, n))
            if n else "忽略规则已齐全，无需改动。")
        self.set_status("忽略规则：新增 %d 条" % n if n else "忽略规则已齐全")

    def _mark_cloud(self):
        """仓库在云盘同步目录里时，标题栏挂一个提示标签。"""
        cloud = is_cloud_dir(self.repo)
        if not cloud:
            self.lbl_cloud.setVisible(False)
            return
        self.lbl_cloud.setText("云盘目录 · %s" % cloud)
        self.lbl_cloud.setToolTip(
            "这个仓库在 %s 的同步目录里：\n"
            "git 每次写入都会让云盘同步一批 .git 小文件，两边同时改同一文件时\n"
            "还可能交到没同步完的半成品。已默认开启「跳过写入中」来规避。" % cloud)
        self.lbl_cloud.setVisible(True)

    def _warn_cloud(self):
        """云盘目录里的仓库，每个路径只提示一次，避免每次启动都弹窗。"""
        cloud = is_cloud_dir(self.repo)
        if not cloud or self.cfg.get("cloudWarnedFor") == self.repo:
            return
        self.cfg["cloudWarnedFor"] = self.repo
        save_config(self.cfg)
        Msg.information(
            self, "仓库位于云同步目录",
            "当前仓库在 %s 的同步目录里：\n\n%s\n\n"
            "git 每次写入都会触发云盘同步一批 .git 小文件；两边同时改同一个文件时，"
            "还可能把没同步完的半成品交进去。\n\n"
            "程序这边已经做了两件事：\n"
            "1. 默认开启「跳过写入中」：刚改过 2 分钟内的、正被 Office 打开的文档，"
            "不进本次提交；\n"
            "2. 5 分钟后自动补交，不用你手动管。\n\n"
            "建议你再做一步：在云盘客户端里把这个仓库的 .git 目录排除同步"
            "（如果客户端有过滤规则的话）。" % (cloud, self.repo))

    def clear_views(self):
        self.files, self.logs, self.branches = [], [], []
        self.tbl_files.setRowCount(0)
        self.tbl_log.setRowCount(0)
        self.cb_branch.clear()

    # ------------------------------------------------------------ 后台执行
    def _run(self, fn, on_done=None, busy="执行中…", on_error=None):
        """把一次 git 操作丢到后台串行执行，结果回到主线程再刷界面。

        注意闭包里只能捕获「已经取出来的值」，不要在子线程里读控件
        （Qt 的控件只能在主线程碰，跨线程调用会随机崩）。
        """
        task = _Task(fn)
        task.setAutoDelete(False)
        self._tasks.append(task)          # 持有引用，否则 Python 侧会被提前回收
        self._pending += 1
        self.set_status(busy)
        task.signals.done.connect(lambda r, t=task: self._task_done(t, on_done, r))
        task.signals.error.connect(lambda e, t=task: self._task_error(t, e, on_error))
        self.pool.start(task)

    def _task_done(self, task, on_done, result):
        self._release(task)
        try:
            if on_done:
                on_done(result)
        except Exception:
            log_exception(*sys.exc_info())
            Msg.critical(self, "处理结果失败", "界面更新时出错，详情见 error.log")

    def _task_error(self, task, msg, on_error):
        self._release(task)
        if on_error:
            try:
                on_error(msg)
                return
            except Exception:
                log_exception(*sys.exc_info())
        self.set_status("执行失败：" + msg)
        Msg.critical(self, "执行失败", msg)

    def _release(self, task):
        self._pending = max(0, self._pending - 1)
        try:
            self._tasks.remove(task)
        except ValueError:
            pass

    # ------------------------------------------------------------ 分支
    def _need_repo(self):
        if not is_repo(self.repo):
            Msg.warning(self, "提示", "当前目录不是 Git 仓库：\n%s" % self.repo)
            return False
        return True

    def _after_simple(self, msg):
        """分支新建/切换/删除这类「一句话结果」的通用收尾。"""
        self.set_status(msg)
        self.refresh()

    def do_create_branch(self):
        if not self._need_repo():
            return
        name, ok = Msg.getText(self, "新建分支", "分支名：")
        if not ok or not name.strip():
            return
        repo, nm = self.repo, name.strip()
        self._run(lambda: create_branch(repo, nm, switch=True),
                  self._after_simple, "新建分支…")

    def do_switch(self):
        if not self._need_repo():
            return
        name = self.cb_branch.currentText()
        if not name:
            Msg.information(self, "提示", "先在下拉框里选一个分支。")
            return
        repo = self.repo
        self._run(lambda: switch_branch(repo, name),
                  self._after_simple, "切换分支…")

    def do_merge(self):
        if not self._need_repo():
            return
        src = self.cb_branch.currentText()
        cur = next((b["name"] for b in self.branches if b["current"]), "")
        if not src:
            Msg.information(self, "提示", "先在下拉框里选要合并进来的分支。")
            return
        if src == cur:
            Msg.information(self, "提示", "不能把分支合并到它自己。")
            return
        if Msg.question(self, "确认合并",
                                "把「%s」合并进当前分支「%s」？" % (src, cur)) \
                != QMessageBox.StandardButton.Yes:
            return
        repo = self.repo

        def done(r):
            if r["merged"]:
                Msg.information(self, "合并完成", r["message"])
                self.set_status("已合并 %s → %s" % (src, cur))
            else:
                cf = r["conflicts"]
                Msg.warning(
                    self, "合并有冲突",
                    "合并未完成，需要手动解决冲突：\n\n%s\n\n解决后提交，或点「中止合并」回到合并前。"
                    % ("\n".join(cf) if cf else r["message"]))
                self.set_status("合并冲突：%d 个文件" % len(cf))
            self.refresh()

        self._run(lambda: merge_branch(repo, src), done, "合并中…")

    def do_delete_branch(self):
        if not self._need_repo():
            return
        name = self.cb_branch.currentText()
        if not name:
            return
        if Msg.question(self, "确认删除",
                                "删除分支「%s」？\n未合并的改动会丢失，建议先合并。" % name) \
                != QMessageBox.StandardButton.Yes:
            return
        repo = self.repo

        def on_error(e):
            if Msg.question(self, "删除失败",
                                    "%s\n\n有未合并的改动。要强制删除吗？" % e) \
                    != QMessageBox.StandardButton.Yes:
                return
            self._run(lambda: delete_branch(repo, name, force=True),
                      self._after_simple, "强制删除分支…")

        self._run(lambda: delete_branch(repo, name), self._after_simple,
                  "删除分支…", on_error=on_error)

    def do_abort_merge(self):
        if not self._need_repo():
            return
        repo = self.repo
        self._run(lambda: abort_merge(repo), self._after_simple, "中止合并…")

    # ------------------------------------------------------------ 刷新
    def refresh(self):
        if not is_repo(self.repo):
            self.clear_views()
            self.lbl_chip.setText("未初始化")
            self.lbl_count.setText("（不是 Git 仓库）")
            return
        repo, maxlog = self.repo, int(self.cfg.get("maxLog", 200))
        self._run(lambda: (get_status(repo), get_log(repo, maxlog), get_branches(repo)),
                  self._apply_refresh, "读取仓库…",
                  on_error=lambda e: self.set_status("读取仓库失败：%s" % e))

    def _apply_refresh(self, data):
        (branch, files), logs, branches = data
        keep = set(self.selected_paths())
        self.files, self.logs, self.branches = files, logs, branches
        self.lbl_chip.setText("分支 " + branch)

        self.tbl_files.setRowCount(0)
        for f in files:
            r = self.tbl_files.rowCount()
            self.tbl_files.insertRow(r)
            st = QTableWidgetItem(f["status"])
            color = GREEN if f["status"] == "新增" else (RED if f["status"] == "删除" else ORANGE)
            st.setForeground(QColor(color))
            self.tbl_files.setItem(r, 0, st)
            self.tbl_files.setItem(r, 1, QTableWidgetItem(f["path"]))
            if f["path"] in keep:
                self.tbl_files.selectRow(r)
        self.lbl_count.setText(("（%d 个文件）" % len(files)) if files else "（干净）")

        self.cb_branch.blockSignals(True)
        self.cb_branch.clear()
        self.cb_branch.addItems([b["name"] for b in branches])
        cur = next((b["name"] for b in branches if b["current"]), None)
        if cur:
            self.cb_branch.setCurrentText(cur)
        self.cb_branch.blockSignals(False)

        self.tbl_log.setRowCount(0)
        for c in logs:
            r = self.tbl_log.rowCount()
            self.tbl_log.insertRow(r)
            self.tbl_log.setItem(r, 0, QTableWidgetItem(c["short"]))
            self.tbl_log.setItem(r, 1, QTableWidgetItem(c["subject"]))
            # 列表里日期只留「月-日 时:分」，完整时间在差异区和命令行里都有
            short_date = c["date"][5:16] if len(c["date"]) >= 16 else c["date"]
            self.tbl_log.setItem(r, 2,
                                 QTableWidgetItem("%s · %s" % (c["author"], short_date)))
            self.tbl_log.item(r, 0).setData(Qt.ItemDataRole.UserRole, c["hash"])

        last = self.cfg.get("lastRunAt", 0)
        self.lbl_last.setText(
            ("上次自动执行：" + QDateTime.fromMSecsSinceEpoch(int(last)).toString("MM-dd HH:mm"))
            if last else "尚未自动执行")
        self.set_status("已刷新 · " + QDateTime.currentDateTime().toString("HH:mm:ss"))

    def selected_paths(self):
        rows = {i.row() for i in self.tbl_files.selectedIndexes()}
        out = []
        for r in rows:
            it = self.tbl_files.item(r, 1)
            if it:
                out.append(it.text())
        return out

    def set_status(self, text):
        self.lbl_status.setText(text)

    def set_diff(self, text):
        self.txt_diff.setPlainText(text or "（无差异）")

    def sel_hash(self):
        rows = {i.row() for i in self.tbl_log.selectedIndexes()}
        if not rows:
            return None
        r = list(rows)[0]
        it = self.tbl_log.item(r, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    # ------------------------------------------------------------ 提交 / 回退
    def on_commit(self):
        if not self._need_repo():
            return
        paths = self.selected_paths()
        text = self.ed_msg.text()          # 控件只能在主线程读，先把值取出来
        repo = self.repo
        skip = bool(self.cfg.get("skipUnstable", True))
        self._run(lambda: do_commit(repo, text, paths or None, skip_unstable=skip),
                  self._after_commit, "提交中…")

    def _after_commit(self, res):
        h, msg, skipped = res
        if h:
            self.ed_msg.clear()
            self._report_skipped(skipped, "已提交 %s：%s" % (h[:7], msg))
        else:
            self._report_skipped(skipped, msg)
            Msg.information(self, "无需提交", msg)
        self.refresh()

    def _report_skipped(self, skipped, base):
        """把「本次跳过了哪些文件、为什么」接到状态栏文案后面。"""
        if not skipped:
            self.set_status(base)
            return
        head = skipped[0]
        more = "等 %d 个文件" % len(skipped) if len(skipped) > 1 else ""
        self.set_status("%s（跳过 %s：%s %s）"
                        % (base, head["path"], head["reason"], more))

    def sel_all(self):
        self.tbl_files.selectAll()

    def sel_none(self):
        self.tbl_files.clearSelection()

    def restore_selected(self):
        paths = self.selected_paths()
        if not paths:
            Msg.information(self, "提示", "先在上方列表中选中要还原的文件。")
            return
        if Msg.question(
                self, "确认还原",
                "把选中的 %d 个文件还原到最近一次提交的状态？\n未保存的改动会丢失。\n\n%s"
                % (len(paths), "\n".join(paths[:12]))) != QMessageBox.StandardButton.Yes:
            return
        repo = self.repo

        def job():
            backup = create_backup(repo)
            errs = []
            for p in paths:
                try:
                    restore_file(repo, p)
                except Exception as e:
                    errs.append("%s：%s" % (p, e))
            return backup, errs

        def done(res):
            backup, errs = res
            if errs:
                Msg.critical(self, "还原失败", "\n".join(errs))
            self.set_status("已还原 %d 个文件（备份分支：%s）"
                            % (len(paths) - len(errs), backup or "无"))
            self.refresh()

        self._run(job, done, "还原文件…")

    def discard_all(self):
        if not self._need_repo():
            return
        if Msg.question(
                self, "⚠️ 危险操作",
                "此操作非常危险，可能导致不可逆的数据丢失！\n\n"
                "将丢弃工作区所有未提交的改动，并删除所有未跟踪的新文件。\n"
                "系统会先创建一个备份分支。\n\n确定继续？") != QMessageBox.StandardButton.Yes:
            return
        if Msg.question(self, "再次确认", "真的要丢弃全部未提交改动吗？") \
                != QMessageBox.StandardButton.Yes:
            return
        repo = self.repo
        self._run(lambda: discard_all(repo),
                  lambda backup: (
                      self.set_status("已撤销全部未提交改动（备份分支：%s）" % (backup or "无")),
                      self.refresh()),
                  "撤销改动…")

    def show_commit_diff(self):
        h = self.sel_hash()
        if not h:
            Msg.information(self, "提示", "先在历史列表里选中一次提交。")
            return
        repo = self.repo
        self._run(lambda: get_diff(repo, "commit", h), self.set_diff, "读取差异…")

    def show_diff(self, kind):
        repo = self.repo
        self._run(lambda: get_diff(repo, kind), self.set_diff, "读取差异…")

    def revert_commit(self):
        h = self.sel_hash()
        if not h:
            Msg.information(self, "提示", "先在历史列表里选中一次提交。")
            return
        if Msg.question(
                self, "反向撤销",
                "生成一次「反向提交」来抵消 %s 的改动。\n历史记录完整保留，可再次撤销。\n\n继续？" % h[:7]) \
                != QMessageBox.StandardButton.Yes:
            return
        repo = self.repo
        self._run(lambda: revert_commit(repo, h), self._after_simple, "反向撤销…")

    def reset_to_commit(self):
        h = self.sel_hash()
        if not h:
            Msg.information(self, "提示", "先在历史列表里选中一次提交。")
            return
        row = list({i.row() for i in self.tbl_log.selectedIndexes()})[0]
        subject = self.tbl_log.item(row, 1).text() if self.tbl_log.item(row, 1) else ""
        if Msg.question(
                self, "⚠️ 回退确认",
                "把 HEAD 直接回退到 %s：%s\n\n之后的提交记录会从当前分支移除。\n"
                "系统会先创建备份分支，可随时恢复。\n\n确定继续？" % (h[:7], subject)) \
                != QMessageBox.StandardButton.Yes:
            return
        items = ["soft  —— 改动保留在暂存区，可直接再提交",
                 "mixed —— 改动保留在工作区，需重新 add（默认）",
                 "hard  —— 丢弃全部改动，工作区彻底回到那次提交"]
        mode, ok = Msg.getItem(self, "选择回退模式", "回退模式：", items, 1, False)
        if not ok:
            return
        mode = mode.split()[0]
        repo = self.repo
        self._run(lambda: reset_to(repo, h, mode),
                  lambda backup: (
                      self.set_status("已回退到 %s（%s，备份分支：%s）"
                                      % (h[:7], mode, backup or "无")),
                      self.refresh()),
                  "回退中…")

    # ------------------------------------------------------------ 定时
    def on_schedule_change(self, *_a):
        self.cfg["autoEnabled"] = self.chk_auto.isChecked()
        try:
            self.cfg["intervalHours"] = max(1, int(self.cb_interval.currentText()))
        except Exception:
            self.cfg["intervalHours"] = 1
        save_config(self.cfg)
        self.set_status("定时设置已保存：%s，每 %d 小时"
                        % ("开启" if self.cfg["autoEnabled"] else "关闭",
                           self.cfg["intervalHours"]))

    def run_now(self):
        self.cfg["lastRunAt"] = 0
        save_config(self.cfg)
        self.auto_tick()

    def auto_tick(self):
        if not (self.cfg.get("autoEnabled") and is_repo(self.repo)):
            return
        now_ms = QDateTime.currentMSecsSinceEpoch()
        need = max(1, int(self.cfg.get("intervalHours", 1))) * 3600 * 1000
        if now_ms - int(self.cfg.get("lastRunAt", 0)) < need:
            return
        repo = self.repo
        skip = bool(self.cfg.get("skipUnstable", True))
        self._run(lambda: do_commit(repo, None, None, skip_unstable=skip),
                  lambda res: self._after_auto(res, now_ms, need), "自动提交…",
                  on_error=lambda e: self.set_status("自动提交失败：" + e))

    def _after_auto(self, res, now_ms, need):
        h, msg, skipped = res
        if h:
            self.cfg["lastRunAt"] = now_ms
            self._report_skipped(skipped,
                                 "自动提交完成 %s：%s" % (h[:7], msg))
            self.refresh()
        else:
            # 有文件还在写入 → 5 分钟后补交，别干等一整个周期；
            # 单纯无变更 → 照常计时。
            self.cfg["lastRunAt"] = (now_ms - need + RETRY_MS
                                     if skipped else now_ms)
            self._report_skipped(skipped,
                                 "自动提交检查：" + (msg or "无变更"))
        save_config(self.cfg)

    def closeEvent(self, event):
        save_config(self.cfg)
        # 关窗口 = 缩到托盘（默认）。只有托盘真的在、且用户没点「退出」时才这么做，
        # 否则会出现「关不掉窗口」的假死。
        if (not self._real_close) and self.cfg.get("minimizeToTray", True) \
                and self.tray is not None and self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Git 提交助手",
                "已缩到系统托盘，定时自动提交继续在后台运行。\n双击托盘图标可重新打开。",
                QSystemTrayIcon.MessageIcon.Information, 3000)
            return
        if self.tray is not None:
            self.tray.hide()
        event.accept()
        app = QApplication.instance()
        if app is not None:
            app.quit()


def run_gui(repo=None):
    """供入口调用；异常会写 error.log 并弹窗"""
    app = QApplication.instance() or QApplication(sys.argv)
    _cfg = load_config()
    app.setStyleSheet(build_qss(_cfg.get("glassLevel") or DEFAULT_GLASS))
    icon_path = os.path.join(RES, "app.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    try:
        w = GlassWindow(repo)
        if os.path.exists(icon_path):
            w.setWindowIcon(QIcon(icon_path))
        w.show()
        return app.exec()
    except Exception:
        # 走到这里说明界面根本没起来，自绘对话框（依赖已经建好的窗口环境）
        # 不可靠，所以刻意用原生对话框报错。
        log_exception(*sys.exc_info())
        QMessageBox.critical(
            None, "启动失败",
            "%s\n\n详情见：\n%s" % (sys.exc_info()[1], ERROR_LOG))
        return 1
