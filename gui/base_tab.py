"""标签页基类 - 所有标签页的通用模式"""
from abc import ABC, abstractmethod
import threading
import logging
import pandas as pd
import ttkbootstrap as ttk
from gui.theme import COLORS, FONTS

logger = logging.getLogger(__name__)


class BaseTab(ABC):
    """标签页基类，提供控制栏+内容区+自动刷新+线程安全表格更新"""

    def __init__(self, parent, tab_name: str = ""):
        self.frame = ttk.Frame(parent)
        self.tab_name = tab_name
        self._stop_flag = threading.Event()
        self._thread: threading.Thread | None = None
        self._build_ui()

    def _build_ui(self):
        """构建控制栏 + 分割线 + 内容区"""
        self.control_bar = ttk.Frame(self.frame)
        self.control_bar.pack(fill="x", padx=10, pady=(8, 4))
        self._build_control_bar()

        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=10)

        self.content = ttk.Frame(self.frame)
        self.content.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self._build_content()

    @abstractmethod
    def _build_control_bar(self):
        """子类实现：向self.control_bar添加控件"""

    @abstractmethod
    def _build_content(self):
        """子类实现：向self.content添加内容组件"""

    @abstractmethod
    def refresh_data(self):
        """子类实现：刷新数据（在后台线程调用）"""

    def add_refresh_btn(self, text: str = "⟳ 刷新") -> ttk.Button:
        """快速添加刷新按钮"""
        btn = ttk.Button(
            self.control_bar, text=text, bootstyle="info-outline",
            command=lambda: threading.Thread(target=self.refresh_data, daemon=True).start(),
        )
        btn.pack(side="left", padx=2)
        return btn

    def add_table(self, **kwargs):
        """创建并返回一个 pandastable 表格"""
        from pandastable import Table as Table2
        pt = Table2(
            self.content, dataframe=pd.DataFrame(),
            showtoolbar=True, showstatusbar=True, **kwargs,
        )
        pt.currheight = 0
        pt.show()
        return pt

    def update_table(self, pt, df, err_msg: str = ""):
        """线程安全地更新表格，出错时显示错误信息"""
        import traceback
        try:
            self.frame.after(0, lambda: self._apply_table(pt, df))
        except Exception as e:
            logger.error(f"[{self.tab_name}] {err_msg}: {e}\n{traceback.format_exc()}")
            err_df = pd.DataFrame({"提示": [f"{err_msg}: {e}"]})
            self.frame.after(0, lambda: self._apply_table(pt, err_df))

    def _apply_table(self, pt, df):
        """在主线程应用表格数据"""
        pt.model.df = df.copy() if hasattr(df, "copy") else pd.DataFrame(df)
        pt.redraw()

    def start_auto_refresh(self, interval: int = 60):
        """启动自动刷新线程（间隔秒数）"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_flag.clear()

        def _loop():
            while not self._stop_flag.wait(interval):
                try:
                    self.refresh_data()
                except Exception as e:
                    logger.error(f"[{self.tab_name}] auto-refresh: {e}")

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop_auto_refresh(self):
        """停止自动刷新"""
        self._stop_flag.set()

    def add_status_indicator(self, text: str, default: str = "⚪",
                             color: str = "gray") -> dict:
        """添加状态指示灯，返回 {'label': .., 'light': ..} 用于后续更新"""
        row = ttk.Frame(self.control_bar)
        row.pack(side="right", padx=5)
        light = ttk.Label(row, text=default, font=("", 10), foreground=color)
        light.pack(side="left")
        lbl = ttk.Label(row, text=text, font=FONTS["small"])
        lbl.pack(side="left")
        return {"label": lbl, "light": light}

    def set_indicator(self, ind: dict, status: str):
        """更新状态指示灯: 'ok'/'error'/'running'/'idle'"""
        mapping = {
            "ok": ("🟢", COLORS["success"]),
            "error": ("🔴", COLORS["danger"]),
            "running": ("🟡", COLORS["warning"]),
            "idle": ("⚪", "gray"),
        }
        text, color = mapping.get(status, ("⚪", "gray"))
        ind["light"].configure(text=text, foreground=color)
