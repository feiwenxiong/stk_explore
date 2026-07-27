import os
import sys
cpath_current = os.path.dirname(os.path.dirname(__file__))
sys.path.append(cpath_current)
import akshare as ak
from utils import *
import requests as rq
import os
import pandas as pd
from datetime import timedelta, datetime
from hot_stock import *
import time
from lhb import yyb_stocks2stock_yybs 
import threading
import tkinter as tk
from pandastable import Table as Table2
import ttkbootstrap as ttk
from ttkbootstrap.constants import SUCCESS 
import warnings
from zhangting import LimitUpPool, DataFramePretty
from PIL import Image, ImageTk
import webbrowser
from jin10tab import Jin10App
from fenshitu_tab import (
    get_minutely_data, data_to_data_frame, get_bankuai_dapan_minute_trend,
    get_bankuai_data, get_bankuai_stock_data
)
import logging
import traceback
import random
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import sys
import os
# Matplotlib for fenshitu charts
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from collections import OrderedDict
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
# 添加项目路径到sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from instock.lib.http_client import get_session, update_ua
from instock.lib.akshare_patch import patch_akshare_session, patch_akshare_direct

# 应用akshare补丁
patch_akshare_session()
patch_akshare_direct()

warnings.filterwarnings('ignore')
pd.set_option('future.no_silent_downcasting', True)

# 设置日志记录
logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG 级别，输出更多信息
    format='%(asctime)s - %(levelname)s - [%(threadName)s] %(message)s'
)
logger = logging.getLogger(__name__)

class StockClient:
    def __init__(self):
        self.stop_event = threading.Event()
        self.nearest_trade_date = closest_trade_date()
        self.my_images = []
        self.setup_gui()
        
    def setup_gui(self):
        """设置GUI界面 - 侧边树形导航"""
        self.root = ttk.Window(themename="yeti")
        style = ttk.Style()
        style.configure('Custom.TLabel',
                        background='yellow',  
                        foreground='black',       
                        padding=10) 
        style.configure('Treeview', rowheight=30, font=('Arial', 10))
        theme_names = style.theme_names()
        print("themes: ", theme_names)
        
        wwidth = 1480
        wheight = 820
        self.root.geometry(f"{wwidth}x{wheight}")  
        
        screen_width = self.root.winfo_screenwidth()  
        screen_height = self.root.winfo_screenheight()  
        x = (screen_width - wwidth) // 2
        y = (screen_height - wheight) // 2
        self.root.geometry(f"{wwidth}x{wheight}+{x}+{y}")  
        self.root.title('myStock')
        
        # ========== Panedwindow: 侧边栏 + 内容区 ==========
        self.main_pane = tk.PanedWindow(self.root, orient="horizontal", sashwidth=3)
        self.main_pane.pack(fill='both', expand=True)
        
        # ----- 左侧：树形导航 -----
        sidebar = ttk.Frame(self.main_pane, width=200)
        
        # 标题
        ttk.Label(sidebar, text="功能导航", font=("Arial", 10, "bold"),
                  padding=(10, 5)).pack(fill="x")
        ttk.Separator(sidebar, orient="horizontal").pack(fill="x")
        
        self.nav_tree = ttk.Treeview(sidebar, show="tree", padding=5)
        self.nav_tree.pack(fill="both", expand=True)
        
        # 分类和子项
        categories = [
            ("📰 资讯", [
                ("新闻直播", "news"),
            ]),
            ("📊 实时行情", [
                ("涨停池[实时]", 0),
                ("板块总体[实时]", 1),
                ("板块成分股", 2),
                ("分时图[实时]", 11),
            ]),
            ("📈 趋势分析", [
                ("板块趋势[实时]", 3),
                ("板块个股趋势[实时]", 4),
            ]),
            ("💹 智能选股", [
                ("选股", 5),
            ]),
            ("🏦 龙虎榜", [
                ("龙虎榜和营业部", 6),
                ("今日涨停池[+龙虎榜]", 7),
            ]),
            ("⭐ 我的关注", [
                ("关注列表", 8),
                ("关注控盘", 9),
                ("关注列表-今日K线", 10),
            ]),
        ]
        
        self.node_map = {}  # tree item iid -> (frame or "news")
        for cat_name, items in categories:
            cat_id = self.nav_tree.insert("", "end", text=cat_name, open=True)
            for item_name, frame_id in items:
                node_id = self.nav_tree.insert(cat_id, "end", text=f"  {item_name}")
                self.node_map[node_id] = frame_id
        
        self.nav_tree.bind("<<TreeviewSelect>>", self._on_nav_select)
        
        self.main_pane.add(sidebar, width=220)
        
        # ----- 右侧：内容区 -----
        self.content_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(self.content_frame)
        
        # 新闻帧（特殊处理，不属于 tab_frames）
        self.news_frame = tk.Frame(self.content_frame)
        try:
            app = Jin10App(self.news_frame)
        except Exception as e:
            logger.error(f"创建新闻直播失败: {e}" + chr(10) + traceback.format_exc())
            tk.Label(self.news_frame, text=f"新闻加载失败: {e}", 
                     fg="red", font=("", 10)).pack(pady=20)
        
        # 创建所有功能标签页的帧
        self.tab_frames = []
        for i in range(12):
            tab_frame = ttk.Frame(self.content_frame)
            self.tab_frames.append(tab_frame)
        
        self._current_frame = None
        
        self.create_tabs()
        self.root.mainloop()
        
    def create_request_session(self):
        """创建带有重试机制的请求会话"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def safe_akshare_call(self, func, *args, **kwargs):
        """安全调用akshare函数，包含重试和延迟机制，详细的错误日志"""
        func_name = getattr(func, '__qualname__', getattr(func, '__name__', str(func)))
        max_retries = 3
        
        # 截断参数以保持日志可读
        args_repr = []
        for a in args:
            s = str(a)
            if len(s) > 80:
                s = s[:77] + "..."
            args_repr.append(s)
        kwargs_repr = {}
        for k, v in kwargs.items():
            s = str(v)
            if len(s) > 80:
                s = s[:77] + "..."
            kwargs_repr[k] = s
        
        call_signature = f"{func_name}({', '.join(args_repr)}"
        if kwargs_repr:
            call_signature += f", {', '.join(f'{k}={v}' for k, v in kwargs_repr.items())}"
        call_signature += ")"
        
        for attempt in range(max_retries):
            try:
                time.sleep(random.uniform(0.1, 0.5))
                logger.debug(f"调用: {call_signature}")
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                err_type = type(e).__name__
                logger.warning(
                    f"[{func_name}] 调用失败 (尝试 {attempt+1}/{max_retries}) | "
                    f"异常类型: {err_type} | 异常信息: {e}"
                )
                if attempt < max_retries - 1:
                    delay = 2 ** attempt + random.uniform(0.1, 0.5)
                    logger.info(f"[{func_name}] 将在 {delay:.1f}秒 后重试...")
                    time.sleep(delay)
                else:
                    logger.error(
                        f"[{func_name}] 最终失败! | 调用签名: {call_signature}\n"
                        f"完整堆栈:\n{traceback.format_exc()}"
                    )
                    raise e
    
    def _on_nav_select(self, event):
        """树形菜单点击切换内容"""
        selection = self.nav_tree.selection()
        if not selection:
            return
        node_id = selection[0]
        frame_id = self.node_map.get(node_id)
        if frame_id is None:
            return
        
        # 隐藏当前帧
        if self._current_frame:
            self._current_frame.pack_forget()
        
        # 显示目标帧
        if frame_id == "news":
            self.news_frame.pack(fill="both", expand=True)
            self._current_frame = self.news_frame
        else:
            target = self.tab_frames[frame_id]
            target.pack(fill="both", expand=True)
            self._current_frame = target
    
    def create_tabs(self):
        """创建所有功能标签页内容（复用原有方法，只改容器）"""
        ttk.Style().configure('TNotebook.Tab', font=('Arial', 12))
        
        self.create_limit_up_tab()
        self.create_board_overview_tab()
        self.create_board_components_tab()
        self.create_ths_block_trend_tab()
        self.create_ths_block_stocks_tab()
        self.create_stock_selection_tab()
        self.create_lhb_yyb_tab()
        self.create_limit_up_lhb_tab()
        self.create_attention_tab()
        self.create_control_trend_tab()
        self.create_attention_kline_tab()
        try:
            self.create_fenshitu_tab()
        except Exception as e:
            logger.error(f"创建分时图标签页失败: {e}" + chr(10) + traceback.format_exc())
        
        # 默认选中新闻直播
        for cat_id in self.nav_tree.get_children(""):
            for child_id in self.nav_tree.get_children(cat_id):
                if self.node_map.get(child_id) == "news":
                    self.nav_tree.selection_set(child_id)
                    self.nav_tree.see(child_id)
                    break
        self._on_nav_select(None)
        
    def create_fenshitu_tab(self):
        """创建分时图标签页 - 含诊断面板、状态指示器、后台线程数据抓取"""
        tab = self.tab_frames[11]
        
        # ========== Top: Control bar ==========
        control_bar = ttk.Frame(tab)
        control_bar.pack(fill="x", padx=5, pady=5)
        
        self.fenshitu_running = False
        self.fenshitu_stop = threading.Event()
        self.fenshitu_data = (None, None)  # (outer, inner)
        
        def toggle_fenshitu():
            if not self.fenshitu_running:
                self.fenshitu_running = True
                self.fenshitu_stop.clear()
                btn_start.configure(text="暂停", bootstyle="warning")
                self._log_fenshitu("INFO", "分时图数据抓取已启动")
                t = threading.Thread(target=self._fenshitu_fetch_loop, daemon=True)
                t.start()
            else:
                self.fenshitu_running = False
                self.fenshitu_stop.set()
                btn_start.configure(text="开始", bootstyle="success")
                self._log_fenshitu("INFO", "分时图数据抓取已暂停")
        
        btn_start = ttk.Button(control_bar, text="开始", bootstyle="success",
                               command=toggle_fenshitu)
        btn_start.pack(side="left", padx=5)
        
        refresh_label = ttk.Label(control_bar, text="刷新间隔: 50秒 (交易时段)")
        refresh_label.pack(side="left", padx=15)
        
        self.fenshitu_elapsed_var = tk.StringVar(value="上次刷新: --")
        ttk.Label(control_bar, textvariable=self.fenshitu_elapsed_var).pack(side="right", padx=5)
        
        # ========== Middle: Panedwindow (diagnostics + charts) ==========
        paned = ttk.Panedwindow(tab, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=5, pady=5)
        
        # ----- Left: Diagnostic panel -----
        diag_frame = ttk.LabelFrame(paned, text="实时诊断", padding=3)
        
        # Status grid
        status_grid = ttk.Frame(diag_frame)
        status_grid.pack(fill="x", padx=3, pady=3)
        
        self.fenshitu_indicators = {}
        status_names = [
            ("指数数据", "上证/深证/创业板分时"),
            ("板块数据", "前6行业板块分时"),
            ("个股数据", "板块内个股分时+换手率"),
            ("图表渲染", "Matplotlib绘图"),
        ]
        for i, (short, desc) in enumerate(status_names):
            row = ttk.Frame(status_grid)
            row.pack(fill="x", pady=1)
            light = tk.Label(row, text="  ⚪  ", fg="gray", font=("", 9))
            light.pack(side="left")
            ttk.Label(row, text=short, font=("", 9, "bold")).pack(side="left")
            ttk.Label(row, text=desc, font=("", 8), foreground="gray").pack(side="left", padx=5)
            timer = ttk.Label(row, text="--", font=("", 8))
            timer.pack(side="right")
            self.fenshitu_indicators[short] = (light, timer)
        
        # Separator
        ttk.Separator(diag_frame, orient="horizontal").pack(fill="x", padx=3, pady=3)
        
        # Log area
        log_header = ttk.Frame(diag_frame)
        log_header.pack(fill="x", padx=3)
        ttk.Label(log_header, text="事件日志", font=("", 9, "bold")).pack(side="left")
        ttk.Button(log_header, text="清空", size="sm", 
                   command=lambda: self._clear_fenshitu_log()).pack(side="right")
        
        log_container = ttk.Frame(diag_frame)
        log_container.pack(fill="both", expand=True, padx=3, pady=3)
        
        self.fenshitu_log = tk.Text(log_container, height=20, width=42, wrap="word",
                                     state="disabled", font=("Consolas", 8),
                                     bg="#f8f8f8", relief="sunken", borderwidth=1)
        log_scroll = ttk.Scrollbar(log_container, orient="vertical", 
                                   command=self.fenshitu_log.yview)
        self.fenshitu_log.configure(yscrollcommand=log_scroll.set)
        self.fenshitu_log.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")
        
        paned.add(diag_frame, weight=1)
        
        # ----- Right: Chart area -----
        chart_frame = ttk.LabelFrame(paned, text="分时图", padding=3)
        
        self.fenshitu_chart_canvas = tk.Canvas(chart_frame, bg="white")
        chart_scroll_y = ttk.Scrollbar(chart_frame, orient="vertical", 
                                        command=self.fenshitu_chart_canvas.yview)
        chart_scroll_x = ttk.Scrollbar(chart_frame, orient="horizontal",
                                        command=self.fenshitu_chart_canvas.xview)
        
        self.fenshitu_scrollable = ttk.Frame(self.fenshitu_chart_canvas)
        self.fenshitu_scrollable.bind(
            "<Configure>",
            lambda e: self.fenshitu_chart_canvas.configure(
                scrollregion=self.fenshitu_chart_canvas.bbox("all"))
        )
        
        self.fenshitu_chart_canvas.create_window((0, 0), window=self.fenshitu_scrollable, anchor="nw")
        self.fenshitu_chart_canvas.configure(
            yscrollcommand=chart_scroll_y.set,
            xscrollcommand=chart_scroll_x.set
        )
        
        self.fenshitu_chart_canvas.pack(side="left", fill="both", expand=True)
        chart_scroll_y.pack(side="right", fill="y")
        chart_scroll_x.pack(side="bottom", fill="x")
        
        # Mouse wheel
        self.fenshitu_chart_canvas.bind_all("<MouseWheel>", 
            lambda e: self.fenshitu_chart_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        paned.add(chart_frame, weight=4)
        
        # Placeholder
        ttk.Label(self.fenshitu_scrollable, 
                  text="点击 '开始' 按钮加载分时图数据\n(仅在交易时段有效)",
                  font=("", 12), foreground="gray").pack(pady=100)
        
        self._log_fenshitu("INFO", "分时图标签页初始化完成，等待启动")
    
    def _log_fenshitu(self, level, msg):
        """线程安全地写入诊断日志"""
        def _write():
            if not hasattr(self, 'fenshitu_log') or self.fenshitu_log is None:
                return
            self.fenshitu_log.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            color_map = {"ERROR": "red", "WARN": "orange", "INFO": "blue", "OK": "green"}
            color = color_map.get(level, "black")
            self.fenshitu_log.insert("end", f"[{ts}] ", ("gray",))
            self.fenshitu_log.insert("end", f"[{level}] ", (color,))
            self.fenshitu_log.insert("end", f"{msg}\n")
            self.fenshitu_log.see("end")
            self.fenshitu_log.configure(state="disabled")
        
        # Configure tags
        def _setup_tags():
            if not hasattr(self, 'fenshitu_log') or self.fenshitu_log is None:
                return
            self.fenshitu_log.tag_configure("gray", foreground="gray")
            for tag, fg in [("ERROR", "red"), ("WARN", "darkorange"), 
                            ("INFO", "blue"), ("OK", "green")]:
                self.fenshitu_log.tag_configure(tag, foreground=fg)
        
        if not hasattr(self, '_fenshitu_tags_setup'):
            self.root.after(0, _setup_tags)
            self._fenshitu_tags_setup = True
        
        self.root.after(0, _write)
    
    def _clear_fenshitu_log(self):
        if not hasattr(self, 'fenshitu_log') or self.fenshitu_log is None:
            return
        self.fenshitu_log.configure(state="normal")
        self.fenshitu_log.delete("1.0", "end")
        self.fenshitu_log.configure(state="disabled")
    
    def _update_fenshitu_indicator(self, name, status, elapsed=None):
        """更新诊断面板状态指示灯 - thread-safe"""
        colors = {
            "pending": ("  ⚪  ", "gray"),
            "running": ("  🟡  ", "#d4a800"),
            "ok":      ("  🟢  ", "green"),
            "error":   ("  🔴  ", "red"),
            "skip":    ("  ⚫  ", "darkgray"),
        }
        def _update():
            if not hasattr(self, 'fenshitu_indicators'):
                return
            if name in self.fenshitu_indicators:
                light, timer = self.fenshitu_indicators[name]
                text, color = colors.get(status, colors["pending"])
                light.configure(text=text, fg=color)
                if elapsed is not None:
                    timer.configure(text=f"{elapsed:.1f}s")
        self.root.after(0, _update)
    
    def _fenshitu_fetch_loop(self):
        """后台线程：循环抓取分时图数据"""
        import time
        
        while not self.fenshitu_stop.is_set():
            loop_start = time.time()
            self._log_fenshitu("INFO", "=" * 40)
            
            # Check if it's trading hours (for user info, still try anyway)
            from utils import is_now_open
            if is_now_open():
                self._log_fenshitu("INFO", "交易时段中，开始抓取分时数据...")
            else:
                self._log_fenshitu("INFO", "当前非交易时段(9:30-11:30/13:00-15:00)，分时API可能无数据返回")
                self.root.after(0, lambda: self.fenshitu_elapsed_var.set(
                    f"非交易时段: {datetime.now().strftime('%H:%M:%S')}"))
            
            try:
                # Phase 1: Index data
                self._update_fenshitu_indicator("指数数据", "running")
                t0 = time.time()
                outer, inner = get_bankuai_dapan_minute_trend()
                t1 = time.time()
                
                # Check index data
                index_ok = all(
                    k in outer and not outer[k].empty 
                    for k in ["上证指数", "深证指数", "创业指数"]
                    if k in outer
                )
                if index_ok:
                    self._update_fenshitu_indicator("指数数据", "ok", t1 - t0)
                    self._log_fenshitu("OK", f"指数数据获取成功 ({t1-t0:.1f}s)")
                else:
                    missing = [k for k in ["上证指数","深证指数","创业指数"] 
                               if k not in outer or (k in outer and outer[k].empty)]
                    self._update_fenshitu_indicator("指数数据", "error", t1 - t0)
                    self._log_fenshitu("ERROR", f"指数数据缺失: {missing}")
                
                # Phase 2: Sector data (in outer dict after indices)
                self._update_fenshitu_indicator("板块数据", "running")
                sector_count = len(outer) - 3  # subtract 3 indices
                if sector_count > 0:
                    self._update_fenshitu_indicator("板块数据", "ok", t1 - t0)
                    self._log_fenshitu("OK", f"板块数据获取成功 ({sector_count}个板块, 总耗时{t1-t0:.1f}s)")
                else:
                    self._update_fenshitu_indicator("板块数据", "error")
                    self._log_fenshitu("WARN", "板块数据为空 (非交易时段?)")
                
                # Phase 3: Stock data
                self._update_fenshitu_indicator("个股数据", "running")
                stock_count = sum(len(v) for v in inner.values()) if inner else 0
                if stock_count > 0:
                    self._update_fenshitu_indicator("个股数据", "ok", t1 - t0)
                    self._log_fenshitu("OK", f"个股数据获取成功 ({stock_count}只)")
                else:
                    self._update_fenshitu_indicator("个股数据", "skip")
                    self._log_fenshitu("WARN", "个股数据为空")
                
                # Phase 4: Render charts
                self._update_fenshitu_indicator("图表渲染", "running")
                t2 = time.time()
                self.fenshitu_data = (outer, inner)
                self.root.after(0, self._fenshitu_render_charts)
                t3 = time.time()
                self._update_fenshitu_indicator("图表渲染", "ok", t3 - t2)
                
                total = time.time() - loop_start
                self._log_fenshitu("INFO", f"本轮完成, 总耗时 {total:.1f}s")
                self.root.after(0, lambda: self.fenshitu_elapsed_var.set(
                    f"上次刷新: {datetime.now().strftime('%H:%M:%S')} (耗时{total:.1f}s)"))
                
            except Exception as e:
                self._log_fenshitu("ERROR", f"抓取异常: {type(e).__name__}: {e}")
                self._update_fenshitu_indicator("指数数据", "error")
                self._update_fenshitu_indicator("板块数据", "error")
                self._update_fenshitu_indicator("个股数据", "error")
            
            # Wait for next refresh (50s intervals during trading)
            if not self.fenshitu_stop.is_set():
                self._log_fenshitu("INFO", "等待50秒后进行下一轮刷新...")
                for _ in range(50):
                    if self.fenshitu_stop.is_set():
                        break
                    time.sleep(1)
        
        self._log_fenshitu("INFO", "抓取线程已退出")
    
    def _fenshitu_render_charts(self):
        """在主线程渲染Matplotlib分时图"""
        if not hasattr(self, 'fenshitu_scrollable') or self.fenshitu_scrollable is None:
            return
        outer, inner = self.fenshitu_data
        if not outer or not inner:
            self._log_fenshitu("WARN", "无数据可渲染")
            return
        
        # Clear existing widgets
        for w in self.fenshitu_scrollable.winfo_children():
            w.destroy()
        
        # Extract indices
        outer_items = list(outer.items())
        if len(outer_items) < 4:
            ttk.Label(self.fenshitu_scrollable, 
                      text="数据不足 (非交易时段?)", font=("", 11)).pack(pady=20)
            return
        
        shanghai_index_df = outer_items[0][1]
        sz_index_df = outer_items[1][1]
        chuangye_index_df = outer_items[2][1]
        
        # Track figures for mouse events
        self._fenshitu_figures = []
        self._fenshitu_cross_lines = []
        
        sector_count = len(outer_items) - 3
        self._log_fenshitu("INFO", f"渲染 {sector_count} 个板块的分时图...")
        
        for i in range(3, len(outer_items)):
            bankuai_name = outer_items[i][0]
            bankuai_rank = outer_items[i][1][0]
            bankuai_data = outer_items[i][1][1]
            
            if bankuai_data.empty:
                self._log_fenshitu("WARN", f"板块 {bankuai_name} 数据为空，跳过")
                continue
            
            fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=False)
            
            # Subplot 1: Sector vs Index comparison
            ax0 = axes[0]
            ax0.plot(bankuai_data.index, bankuai_data.Close,
                    label=bankuai_name, color="red", linewidth=1)
            if not shanghai_index_df.empty:
                ax0.plot(shanghai_index_df.index, shanghai_index_df.Close,
                        label="上证指数", color="green", linewidth=0.8)
            if not sz_index_df.empty:
                ax0.plot(sz_index_df.index, sz_index_df.Close,
                        label="深证指数", color="blue", linewidth=0.8)
            if not chuangye_index_df.empty:
                ax0.plot(chuangye_index_df.index, chuangye_index_df.Close,
                        label="创业指数", color="black", linewidth=0.8)
            ax0.set_ylabel("板块涨幅 %")
            ax0.set_title(f"Rank{int(bankuai_rank)}: {bankuai_name}")
            ax0.grid(True, alpha=0.3)
            ax0.legend(fontsize=7, loc="upper left")
            
            # Subplot 2 & 3: Individual stocks within sector
            ax1 = axes[1]
            ax2 = axes[2]
            stock_data_available = False
            
            if bankuai_name in inner:
                for stock_name, item in inner[bankuai_name].items():
                    item_vals = list(item)
                    stock_rank = item_vals[0]
                    stock_data = item_vals[1]
                    stock_code = item_vals[2] if len(item_vals) > 2 else ""
                    stock_turnover = item_vals[3] if len(item_vals) > 3 else None
                    
                    if stock_data.empty:
                        continue
                    stock_data_available = True
                    
                    # Price trend
                    ax1.plot(stock_data.index, stock_data.Close,
                            label=f"{stock_rank}_{stock_name}",
                            linewidth=0.8)
                    
                    # Turnover rate (pre-calculated in background thread)
                    if stock_turnover is not None:
                        ax2.plot(stock_data.index, stock_turnover,
                                label=f"{stock_rank}_{stock_name}",
                                linewidth=0.8)
            
            ax1.set_ylabel("个股票涨幅 %")
            ax1.grid(True, alpha=0.3)
            if stock_data_available:
                ax1.legend(fontsize=6, loc="upper left")
            
            ax2.set_ylabel("换手率 %")
            ax2.set_xlabel("时间")
            ax2.grid(True, alpha=0.3)
            if stock_data_available:
                ax2.legend(fontsize=6, loc="upper left")
            
            plt.setp(ax0.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=7)
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=7)
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=7)
            
            fig.tight_layout()
            
            # Add crosshair lines
            for ax in axes:
                hline, = ax.plot([], [], color='r', linestyle='--', linewidth=0.8)
                vline, = ax.plot([], [], color='r', linestyle='--', linewidth=0.8)
                self._fenshitu_cross_lines.append((hline, vline, ax))
            
            # Embed in tkinter
            canvas_fig = FigureCanvasTkAgg(fig, self.fenshitu_scrollable)
            canvas_fig.get_tk_widget().grid(
                row=(int(bankuai_rank) - 1) // 2, 
                column=(int(bankuai_rank) - 1) % 2, 
                padx=8, pady=8, sticky="nsew"
            )
            canvas_fig.draw()
            self._fenshitu_figures.append((fig, canvas_fig))
            canvas_fig.mpl_connect('motion_notify_event', self._on_fenshitu_mouse_move)
        
        # Configure grid weights
        for c in range(2):
            self.fenshitu_scrollable.columnconfigure(c, weight=1)
        
        self._log_fenshitu("OK", f"图表渲染完成 ({len(self._fenshitu_figures)}个板块)")
    
    def _on_fenshitu_mouse_move(self, event):
        """分时图鼠标十字线处理"""
        if event.inaxes is None:
            return
        if not hasattr(self, '_fenshitu_cross_lines'):
            return
        from matplotlib.dates import num2date
        
        for hline, vline, axis in self._fenshitu_cross_lines:
            if event.inaxes == axis:
                x, y = event.xdata, event.ydata
                if x is None or y is None:
                    return
                x_dt = num2date(x).strftime("%H:%M:%S") if x else "--"
                hline.set_data([axis.get_xlim()[0], axis.get_xlim()[1]], [y, y])
                vline.set_data([x, x], [axis.get_ylim()[0], axis.get_ylim()[1]])
                
                # Show coordinate annotation
                for txt in axis.texts:
                    txt.remove()
                axis.text(0.02, 0.98, f"{x_dt}, {y:.2f}%", 
                         transform=axis.transAxes, fontsize=8,
                         verticalalignment='top',
                         bbox=dict(facecolor='white', alpha=0.7, boxstyle='round'))
                event.inaxes.figure.canvas.draw_idle()
                break
                
    def _api_error_to_user_msg(self, e, func_name=""):
        """将 API 异常转换为用户可读的中文提示"""
        err_str = str(e)
        err_type = type(e).__name__
        
        # 盘后常见错误
        if "RemoteDisconnected" in err_str or "remote end closed" in err_str.lower():
            return f"⚠ {func_name}：连接被远程服务器关闭（盘后接口可能已关闭，下一交易日可恢复）"
        if "ConnectionError" in err_type:
            return f"⚠ {func_name}：网络连接失败（盘后部分接口不可用）"
        if "500" in err_str and "data.eastmoney.com" in err_str:
            return f"⚠ {func_name}：东方财富选股接口盘后关闭（HTTP 500）"
        if "JSONDecodeError" in err_type or "Expecting value" in err_str:
            return f"⚠ {func_name}：服务器返回格式异常（盘后接口不可用）"
        if "read timed out" in err_str or "timeout" in err_str.lower():
            return f"⚠ {func_name}：请求超时，请检查网络连接"
        if "404" in err_str:
            return f"⚠ {func_name}：接口地址不存在"
        if "429" in err_str or "too many requests" in err_str.lower():
            return f"⚠ {func_name}：请求过于频繁，请稍后再试"
        
        # 兜底：显示原始错误
        return f"⚠ {func_name}：{e}"
    
    def _update_pandastable(self, pt, df):
        """线程安全地更新 pandastable 表格数据（在主线程调用）"""
        pt.model.df = df.copy()
        pt.redraw()
        print(f"表格已更新, {len(df)} 行")
    
    def _render_kline_images(self, images_folder):
        """在主线程渲染K线图片到画布"""
        # 清空旧图片
        self.canvas.delete("all")
        self.my_images.clear()
        
        cols = 1
        x_offset = 0
        y_offset = 0
        image_width, image_height = 0, 0
        loaded = 0
        
        for i, img_name in enumerate(sorted(os.listdir(images_folder))):
            if img_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                try:
                    img_path = os.path.join(images_folder, img_name)
                    img = Image.open(img_path)
                    if loaded == 0:
                        image_width = img.width
                        image_height = img.height
                    
                    x = x_offset + (i % cols) * image_width  
                    y = y_offset + (i // cols) * image_height
                    
                    img_tk = ImageTk.PhotoImage(img)
                    self.canvas.create_image(x, y, image=img_tk, anchor='nw')
                    self.my_images.append(img_tk)
                    loaded += 1
                except Exception as e:
                    logger.error(f"加载图片 {img_name} 时出错: {e}" + chr(10) + traceback.format_exc())
        
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        print(f"已加载 {loaded} 张K线图")
        if loaded == 0:
            self.canvas.create_text(10, 10, anchor="nw", 
                text="未能生成K线图\n（盘后部分数据源不可用，请交易时段重试）",
                fill="darkorange", font=("", 10))
        
    def create_limit_up_tab(self):
        """创建涨停池标签页"""
        tab = self.tab_frames[0]
        duration_label = tk.Label(tab, text="间隔时间: ", justify="right")  
        date_label = tk.Label(tab, text="日期: ", justify="right")  
        
        date_var = tk.StringVar()  
        date_var.set(self.nearest_trade_date)
        self.date_entry = tk.Entry(tab, textvariable=date_var)

        duration_var = tk.IntVar()
        duration_var.set(1)
        self.duration_entry = tk.Entry(tab, textvariable=duration_var)    

        start_button = ttk.Button(tab, text="start", 
                                  command=lambda: threading.Thread(target=self.start_track_stock_changes_qt).start())
        stop_button = ttk.Button(tab, text="stop", 
                                 command=lambda: self.stop_update(self.stop_event))
        
        date_label.grid(row=0, column=0, sticky="E", pady=5)
        self.date_entry.grid(row=0, column=1, sticky="E", columnspan=2) 
        duration_label.grid(row=1, column=0, sticky="E", pady=5)
        self.duration_entry.grid(row=1, column=1, sticky=tk.E, columnspan=2)  
        
        start_button.grid(row=2, column=1, ipadx=30)
        stop_button.grid(row=2, column=2, ipadx=30)
        
        self.table_frame = tk.Frame(tab, bg="green")
        self.table_frame.place(x=20, y=150)
        
    def create_board_overview_tab(self):
        """创建东财板块总体标签页"""
        tab = self.tab_frames[1]
        from utils import is_now_open, is_now_break
        
        def update_board_data():
            while 1:
                if is_now_open():
                    if not is_now_break():
                        try:
                            stock_board_industry_name_em_df = self.safe_akshare_call(ak.stock_board_industry_name_em)
                            self.pt5.model.df = stock_board_industry_name_em_df.copy()
                            self.pt5.redraw()
                            print("updating 板块总体!")
                        except Exception as e:
                            logger.error(f"更新板块总体数据时出错: {e}" + chr(10) + traceback.format_exc())
                            user_msg = self._api_error_to_user_msg(e, "板块数据")
                            self.pt5.model.df = pd.DataFrame({"提示信息": [user_msg]})
                            self.pt5.redraw()
                    else:
                        pass
                time.sleep(3.5)
                
        # 立即创建空表格（不阻塞主线程），数据后台异步加载
        self.pt5 = Table2(tab, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        self.pt5.currheight = 0
        self.pt5.show()
        
        # 后台线程异步加载板块数据（不阻塞GUI启动）
        def _init_board_data():
            try:
                df = self.safe_akshare_call(ak.stock_board_industry_name_em)
                self.root.after(0, lambda: self._update_pandastable(self.pt5, df))
            except Exception as e:
                logger.warning(f"异步加载板块数据失败(盘后不可用): {e}")
                err_df = pd.DataFrame({"提示信息": [self._api_error_to_user_msg(e, "板块数据")]})
                self.root.after(0, lambda: self._update_pandastable(self.pt5, err_df))
        threading.Thread(target=_init_board_data, daemon=True).start()
            
        thread5 = threading.Thread(target=update_board_data)
        thread5.daemon = True
        thread5.start()
        
    def create_board_components_tab(self):
        """创建东财板块成标签页"""
        tab = self.tab_frames[2]
        
        self.bankuai_var = tk.StringVar()  
        self.bankuai_var.set("消费电子")
        bankuai_entry = tk.Entry(tab, textvariable=self.bankuai_var)  
        bankuai_entry.pack()
        
        update_button6 = ttk.Button(tab, text="start", 
                                    command=lambda: threading.Thread(target=update_board_components).start())
        update_button6.pack()
        
        self.tab_frame6 = tk.Frame(tab)
        self.tab_frame6.pack(fill='both', expand=True)
        
        # 先创建空表格在主线程
        self.pt6 = Table2(self.tab_frame6, dataframe=pd.DataFrame(), 
                          showtoolbar=True, showstatusbar=True)
        self.pt6.currheight = 0
        self.pt6.show()
        
        def update_board_components():
            print("start 板块个股 ")
            bankuai_str = self.bankuai_var.get()
            try:
                stock_board_industry_cons_em_df = self.safe_akshare_call(
                    ak.stock_board_industry_cons_em, symbol=bankuai_str)
                self.root.after(0, lambda: self._update_pandastable(self.pt6, stock_board_industry_cons_em_df))
            except Exception as e:
                logger.error(f"获取板块成分股数据时出错: {e}" + chr(10) + traceback.format_exc())
                err_df = pd.DataFrame({"提示信息": [self._api_error_to_user_msg(e, "板块成分")]})
                self.root.after(0, lambda: self._update_pandastable(self.pt6, err_df))
        
    def create_ths_block_trend_tab(self):
        """创建同花顺板块趋势标签页"""
        tab = self.tab_frames[3]
        
        def update_ths_block_trend():
            print("start dapan !!!")
            from hot_stock import earn_money_xiaoying
            from zhangting import Continuous_limit_up, BlockTop
            
            try:
                emx = pd.DataFrame(earn_money_xiaoying())
                self.pt91.model.df = emx
                self.pt91.redraw()
            except Exception as e:
                logger.error(f"更新赚钱效应数据时出错: {e}" + chr(10) + traceback.format_exc())
                self.pt91.model.df = pd.DataFrame({"错误": [f"获取赚钱效应数据失败: {str(e)}"]})
                self.pt91.redraw()
            
            t_name = "初始化失败"
            try:
                js_data = Continuous_limit_up().get_data_json(date=self.nearest_trade_date, filt=1)
                t = js_data["data"]
                t_name = t["trade_status"]["name"]
                t_data = pd.DataFrame(t["limit_up_count"]).reset_index()
                
                self.pt92.model.df = t_data
                self.pt92.redraw()
            except Exception as e:
                logger.error(f"更新涨停统计数据时出错: {e}" + chr(10) + traceback.format_exc())
                err_df = pd.DataFrame({"提示信息": [self._api_error_to_user_msg(e, "涨跌停统计")]})
                self.pt92.model.df = err_df
                self.pt92.redraw()
            
            try:
                bt = BlockTop().get_data_df(date=self.nearest_trade_date, filt=1).drop("stock_list", axis=1)
                self.pt93.model.df = bt
                self.pt93.bind("<Button-1>", lambda event: self.on_cell_click(event, self.pt93))
                self.pt93.columncolors['code'] = 'yellow'
                self.pt93.redraw()
            except Exception as e:
                logger.error(f"更新板块Top数据时出错: {e}" + chr(10) + traceback.format_exc())
                self.pt93.model.df = pd.DataFrame({"错误": [f"获取板块Top数据失败: {str(e)}"]})
                self.pt93.redraw()
            
            while str(t_name) == "交易中":
                print("    大盘趋势循环更新")
                try:
                    emx = pd.DataFrame(earn_money_xiaoying())
                    js_data = Continuous_limit_up().get_data_json(date=self.nearest_trade_date, filt=1)
                    t = js_data["data"]
                    t_name = t["trade_status"]["name"]
                    t_data = pd.DataFrame(t["limit_up_count"]).reset_index()
                    bt = BlockTop().get_data_df(date=self.nearest_trade_date, filt=1).drop("stock_list", axis=1)
                    
                    self.pt91.model.df = emx
                    self.pt92.model.df = t_data
                    self.pt93.model.df = bt
                    
                    self.pt91.redraw()
                    self.pt92.redraw()
                    self.pt93.redraw()
                except Exception as e:
                    logger.error(f"循环更新大盘趋势数据时出错: {e}" + chr(10) + traceback.format_exc())
                    # 出错时继续循环，但记录错误
                
                time.sleep(3)
        
        button_9 = ttk.Button(tab, text="start", 
                              command=lambda: threading.Thread(target=update_ths_block_trend).start())
        button_9.grid(row=0, column=0, pady=(5, 0))
        
        label_9 = ttk.Label(tab, style='Custom.TLabel',
                            text="提示！:点击黄色单元格可以跳转到同花顺网页看板块信息！")
        label_9.grid(row=0, column=1, pady=(5, 0), sticky=tk.W)
        
        table_frame91 = ttk.Frame(tab)
        table_frame92 = ttk.Frame(tab)
        table_frame93 = ttk.Frame(tab)
        
        self.pt91 = Table2(table_frame91, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        # 修复pandastable兼容性问题
        self.pt91.currheight = 0
        self.pt91.show()
        self.pt92 = Table2(table_frame92, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        # 修复pandastable兼容性问题
        self.pt92.currheight = 0
        self.pt92.show()
        self.pt93 = Table2(table_frame93, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        # 修复pandastable兼容性问题
        self.pt93.currheight = 0
        self.pt93.show()
       
        table_frame91.grid(row=1, column=0, sticky='nsew')
        table_frame92.grid(row=1, column=1, sticky='nsew')
        table_frame93.grid(row=2, column=0, columnspan=2, sticky='nsew')

        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=12)
        tab.rowconfigure(2, weight=1)
        
    def create_ths_block_stocks_tab(self):
        """创建同花顺板块个股趋势标签页"""
        tab = self.tab_frames[4]
        from zhangting import BlockTop, Continuous_limit_up
        
        def process_blocks_data(blocks):
            t = []
            for block in blocks:
                t.extend(block["stock_list"])
            t = pd.DataFrame(t)
            t["first_limit_up_time"] = t["first_limit_up_time"].map(int).map(datetime.fromtimestamp)
            t["last_limit_up_time"] = t["last_limit_up_time"].map(int).map(datetime.fromtimestamp)
            return t
            
        def update_ths_block_stocks():
            print("start 同花顺热点板块成分股 ！")
            try:
                bt = BlockTop().get_data_json(date=self.nearest_trade_date, filt=1)["data"]
                bt = process_blocks_data(bt)
                self.pt11.model.df = bt
                self.pt11.redraw()
            except Exception as e:
                logger.error(f"初始化同花顺热点板块成分股时出错: {e}" + chr(10) + traceback.format_exc())
                self.pt11.model.df = pd.DataFrame({"错误": [f"获取板块成分股数据失败: {str(e)}"]})
                self.pt11.redraw()
            
            t_name = "初始化失败"
            try:
                js_data = Continuous_limit_up().get_data_json(date=self.nearest_trade_date, filt=1)
                t = js_data["data"]
                t_name = t["trade_status"]["name"]
                
                while str(t_name) == "交易中":
                    print("    热点板块个股循环更新")
                    try:
                        js_data = Continuous_limit_up().get_data_json(date=self.nearest_trade_date, filt=1)
                        t = js_data["data"]
                        t_name = t["trade_status"]["name"]
                    
                        bt = BlockTop().get_data_json(date=self.nearest_trade_date, filt=1)["data"]
                        bt = process_blocks_data(bt)
                        
                        self.pt11.model.df = bt
                        self.pt11.redraw()
                    except Exception as e:
                        logger.error(f"循环更新热点板块个股时出错: {e}" + chr(10) + traceback.format_exc())
                    
                    time.sleep(3)
            except Exception as e:
                logger.error(f"获取同花顺热点板块成分股时出错: {e}" + chr(10) + traceback.format_exc())
        
        button_11 = ttk.Button(tab, text="start", 
                               command=lambda: threading.Thread(target=update_ths_block_stocks).start())
        button_11.pack()
        
        table_frame11 = ttk.Frame(tab)
        table_frame11.pack(fill='both', expand=True)
        
        self.pt11 = Table2(table_frame11, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        # 修复pandastable兼容性问题
        self.pt11.currheight = 0
        self.pt11.show()
        
    def create_stock_selection_tab(self):
        """创建选股标签页"""
        tab = self.tab_frames[5]
        
        def update_stock_selection():
            print("start stock selection!")
            try:
                stock_selection_df = self.safe_akshare_call(getTodayStock, save=0)
                self.pt8.model.df = stock_selection_df
                self.pt8.redraw()
            except Exception as e:
                logger.error(f"更新选股数据时出错: {e}" + chr(10) + traceback.format_exc())
                user_msg = self._api_error_to_user_msg(e, "选股数据")
                self.pt8.model.df = pd.DataFrame({"提示信息": [user_msg]})
                self.pt8.redraw()
             
        start_button_8 = ttk.Button(tab, text="start", 
                                    command=lambda: threading.Thread(target=update_stock_selection).start())
        start_button_8.pack()
        
        tab_frame8 = tk.Frame(tab)
        tab_frame8.pack(fill='both', expand=True)
        
        self.pt8 = Table2(tab_frame8, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        # 修复pandastable兼容性问题
        self.pt8.currheight = 0
        self.pt8.show()
        
    def create_lhb_yyb_tab(self):
        """创建龙虎榜和营业部标签页"""
        tab = self.tab_frames[6]
        
        def update_lhb_yyb():
            print("start stock2yyb")
            youzi_file = os.path.join(os.path.dirname(__file__), "swim_cash3.json")
            
            try:
                stock2yyb = yyb_stocks2stock_yybs(self.nearest_trade_date, youzi_file)
                self.pt3.model.df = stock2yyb
                self.pt3.redraw()
            except Exception as e:
                logger.error(f"更新龙虎榜和营业部数据时出错: {e}" + chr(10) + traceback.format_exc())
                self.pt3.model.df = pd.DataFrame({"错误": [f"获取龙虎榜数据失败: {str(e)}"]})
                self.pt3.redraw()
            
        update_button3 = ttk.Button(tab, text="start", 
                                    command=lambda: threading.Thread(target=update_lhb_yyb).start())
        update_button3.pack()
        
        tab_frame3 = tk.Frame(tab)
        tab_frame3.pack(fill='both', expand=True)
        
        self.pt3 = Table2(tab_frame3, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        # 修复pandastable兼容性问题
        self.pt3.currheight = 0
        self.pt3.show()
    
    def create_limit_up_lhb_tab(self):
        """创建今日涨停池[+龙虎榜信息]标签页"""
        tab = self.tab_frames[7]
        
        def update_limit_up_lhb():
            print("start today_limit_up_pool_detail_in_longhubang")
            try:
                from zhangting import today_limit_up_pool_detail_in_longhubang
                limit_up_detail, _ = today_limit_up_pool_detail_in_longhubang()
                
                self.pt4.model.df = limit_up_detail
                self.pt4.redraw()
            except Exception as e:
                logger.error(f"更新今日涨停池+龙虎榜信息时出错: {e}" + chr(10) + traceback.format_exc())
                self.pt4.model.df = pd.DataFrame({"错误": [f"获取涨停池+龙虎榜数据失败: {str(e)}"]})
                self.pt4.redraw()
            
        update_button4 = ttk.Button(tab, text="start", 
                                    command=lambda: threading.Thread(target=update_limit_up_lhb).start())
        update_button4.pack()
        
        tab_frame4 = tk.Frame(tab)
        tab_frame4.pack(fill='both', expand=True)
        
        self.pt4 = Table2(tab_frame4, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        # 修复pandastable兼容性问题
        self.pt4.currheight = 0
        self.pt4.show()
    
    def create_attention_tab(self):
        """创建关注列表标签页"""
        try:
            tab = self.tab_frames[8]
            from ATTENTION import ATTENTION
            df = pd.DataFrame(ATTENTION)
            df.columns = ["代码"]
            pt7 = Table2(tab, dataframe=df, showtoolbar=True, showstatusbar=True)
            # 修复pandastable兼容性问题
            pt7.currheight = 0
            pt7.show()
        except Exception as e:
            logger.error(f"创建关注列表标签页失败: {e}" + chr(10) + traceback.format_exc())
            tab = self.tab_frames[8]
            pt7 = Table2(tab, dataframe=pd.DataFrame({"错误": [f"加载关注列表失败: {e}"]}),
                         showtoolbar=True, showstatusbar=True)
            pt7.currheight = 0
            pt7.show()
    
    def create_control_trend_tab(self):
        """创建关注控盘标签页"""
        tab = self.tab_frames[9]
        
        # 先创建 UI 组件
        self.tab_frame2 = tk.Frame(tab)
        self.tab_frame2.pack(fill='both', expand=True)
        
        self.pt2 = Table2(self.tab_frame2, dataframe=pd.DataFrame(),
                          showtoolbar=True, showstatusbar=True)
        self.pt2.currheight = 0
        self.pt2.show()
        
        def update_control_trend():
            print("start kongpan_attention")
            try:
                data = kongpan_attention()
                self.root.after(0, lambda: self._update_pandastable(self.pt2, data))
            except Exception as e:
                logger.error(f"更新关注控盘数据时出错: {e}" + chr(10) + traceback.format_exc())
                err_df = pd.DataFrame({"提示信息": [self._api_error_to_user_msg(e, "控盘数据")]})
                self.root.after(0, lambda: self._update_pandastable(self.pt2, err_df))
        
        update_button2 = ttk.Button(tab, text="start", 
                                    command=lambda: threading.Thread(target=update_control_trend).start())
        update_button2.pack()
    
    def create_attention_kline_tab(self):
        """创建关注列表-今日K线标签页"""
        tab = self.tab_frames[10]
        
        def update_attention_kline():
            images_folder = self.folder_var.get()
            
            # 清空旧图片（后台线程安全）
            if os.path.exists(images_folder):
                import shutil
                shutil.rmtree(images_folder)
            os.makedirs(images_folder, exist_ok=True)
            
            # 生成K线图文件（后台线程安全）
            try:
                attention_kongpan(images_folder)
            except Exception as e:
                logger.error(f"生成关注列表K线图时出错: {e}" + chr(10) + traceback.format_exc())
                self.root.after(0, lambda: self.canvas.create_text(
                    10, 10, anchor="nw", text=f"K线图生成失败: {e}", 
                    fill="red", font=("", 10)))
                return
            
            # 将 canvas 渲染调度到主线程
            self.root.after(0, lambda: self._render_kline_images(images_folder))
        
        self.folder_var = tk.StringVar()  
        self.folder_var.set("trends")
        folder_entry = tk.Entry(tab, textvariable=self.folder_var)  
        folder_entry.pack()
        
        button10 = ttk.Button(tab, text="start", 
                              command=lambda: threading.Thread(target=update_attention_kline).start())
        button10.pack()
        
        img_frame = ttk.Frame(tab)
        img_frame.pack(fill='both', expand=True)
        
        self.canvas = tk.Canvas(img_frame, borderwidth=1, bg="#ffffff")
        vsb = tk.Scrollbar(img_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set) 
        self.canvas.bind_all("<MouseWheel>", lambda event: self.on_mouse_wheel(event, self.canvas))
        
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
    def on_mouse_wheel(self, event, canvas):
        """处理鼠标滚轮事件"""
        if event.delta:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            if event.num == 5:
                canvas.xview_scroll(1, "units")
            elif event.num == 4:
                canvas.xview_scroll(-1, "units")

    def update_data(self, date, attention, stock_cache_lst, dfp, poll_interval, code_name_df, indicator_lst, stop_event, pt):
        """更新数据的线程函数"""
        while not stop_event.is_set():
            try:
                stock_cache = stock_cache_lst[0]
                stock_data = self.safe_akshare_call(LimitUpPool().get_data_df_fcb, date, save=0)
                stock_data.drop("分时预览", axis=1, inplace=True)
                stock_data = pd.merge(stock_data, code_name_df, on="代码", how="left", suffixes=("", "_y"))
                stock_new = pd.merge(stock_data, stock_cache, on="代码", how="left", suffixes=("", "_y"))
                
                for indicator in indicator_lst:
                    new_col = round((stock_new[indicator] - stock_new[indicator + "_y"]) / stock_new[indicator + "_y"], 4) * 100
                    new_col = new_col.apply(lambda x: str(x) + "%")
                    stock_data[indicator + "_change"] = new_col
                    
                stock_cache_lst[0] = stock_data.copy()
                dfp.data = stock_data.copy()
                print("updating zhangting data !!")
                
                pt.model.df = stock_data
                pt.redraw()
            except Exception as e:
                logger.error(f"更新涨停池数据时出错: {e}" + chr(10) + traceback.format_exc())
                err_df = pd.DataFrame({"提示信息": [self._api_error_to_user_msg(e, "涨停池")]})
                self.root.after(0, lambda p=pt, d=err_df: self._update_pandastable(p, d))
            time.sleep(poll_interval)
            
    def start_update(self, stop_event, update_thread):
        """开始更新数据"""
        stop_event.clear()
        update_thread.start()
        
    def stop_update(self, stop_event):
        """停止更新数据"""
        stop_event.set()
        print("stop zhangting data !")

    def start_track_stock_changes_qt(self):
        """跟踪股票变化"""
        print("start_track_stock_changes_qt")
        date = self.date_entry.get()
        attention = None
        indicator_lst = ["封单额"]
        poll_interval = int(self.duration_entry.get())
        
        try:
            code_name_df, _ = self.safe_akshare_call(get_code_name)
            if attention:
                code_name_df = code_name_df[code_name_df["code"].isin(attention)]
                
            code_name_df = code_name_df.rename(columns={"code": "代码", "name": "名称"})
            stock_cache = self.safe_akshare_call(LimitUpPool().get_data_df_fcb, date, save=0)
            stock_cache.drop("分时预览", axis=1, inplace=True)
            stock_cache = pd.merge(stock_cache, code_name_df, on="代码", how="left", suffixes=("", "_y"))
            
            dfp = DataFramePretty(stock_cache)
            stock_cache_lst = [stock_cache]
            
            pt = Table2(self.table_frame, dataframe=dfp.data, showtoolbar=True, showstatusbar=True, width=1080, height=520)
            # 修复pandastable兼容性问题
            pt.currheight = 0
            pt.show()
            
            update_thread = threading.Thread(target=self.update_data, 
                                             args=(date, attention, 
                                                   stock_cache_lst, 
                                                   dfp, 
                                                   poll_interval, 
                                                   code_name_df, 
                                                   indicator_lst, 
                                                   self.stop_event,
                                                   pt))
            update_thread.daemon = True
            self.start_update(self.stop_event, update_thread)
            print("updating thread started!")
        except Exception as e:
            logger.error(f"启动股票变化跟踪时出错: {e}" + chr(10) + traceback.format_exc())
            # 显示错误信息到表格
            error_df = pd.DataFrame({"错误": [f"启动失败: {str(e)}"]})
            pt = Table2(self.table_frame, dataframe=error_df, showtoolbar=True, showstatusbar=True, width=1080, height=520)
            # 修复pandastable兼容性问题
            pt.currheight = 0
            pt.show()
        
    def on_cell_click(self, event, table):
        """处理表格单元格点击事件"""
        try:
            row_clicked = table.get_row_clicked(event)
            col_clicked = table.get_col_clicked(event)
            col_name = table.model.df.columns[col_clicked]
            
            if col_name == 'code':
                cell_value = table.model.getValueAt(row_clicked, col_clicked)
                url = f"https://q.10jqka.com.cn/thshy/detail/code/{str(int(cell_value))}/" 
                if url:
                    webbrowser.open(url)
                else:
                    print("No URL found for this row")
        except Exception as e:
            logger.error(f"处理表格点击事件时出错: {e}" + chr(10) + traceback.format_exc())

def get_code_name():
    """安全获取股票代码和名称"""
    import akshare as ak
    # 尝试多种方法获取股票代码和名称
    
    # 方法1: 尝试使用stock_info_a_code_name接口
    try:
        # 获取所有A股股票列表
        stock_list = ak.stock_info_a_code_name()
        # 重命名列
        stock_list.columns = ["code", "name"]
        return stock_list, None  # 第二个返回值为None，因为没有详细数据
    except Exception as e:
        logger.error(f"使用stock_info_a_code_name获取股票列表失败: {e}" + chr(10) + traceback.format_exc())
    
    # 方法2: 尝试分别获取上海和深圳股票（不使用前缀，保持纯数字代码）
    try:
        # 获取上海股票
        sh_stock = ak.stock_sh_a_spot()
        sh_df = sh_stock[["代码", "名称"]].copy()
        sh_df.columns = ["code", "name"]
        
        # 获取深圳股票
        sz_stock = ak.stock_sz_a_spot()
        sz_df = sz_stock[["代码", "名称"]].copy()
        sz_df.columns = ["code", "name"]
        
        # 合并数据
        combined_df = pd.concat([sh_df, sz_df], ignore_index=True)
        return combined_df, None
    except Exception as e:
        logger.error(f"分别获取沪市和深市股票失败: {e}" + chr(10) + traceback.format_exc())
    
    # 方法3: 如果以上都失败，使用备选方案从网络获取
    try:
        # 使用一个更稳定的接口
        stock_zh_a_spot = ak.stock_zh_a_spot()
        df = stock_zh_a_spot[["代码", "名称"]].copy()
        df.columns = ["code", "name"]
        return df, stock_zh_a_spot
    except Exception as e:
        logger.error(f"使用备选方案获取股票列表也失败了: {e}" + chr(10) + traceback.format_exc())
        # 如果所有方法都失败，返回空的数据框
        empty_df = pd.DataFrame({"code": [], "name": []})
        return empty_df, None

def getTodayStock(save=True):
    '''安全获取今日股票数据'''
    from instock.core.crawling.stock_selection import stock_selection
    import instock.core.tablestructure as tbs
    '''
    获取股吧人气榜等数据
    '''
    table = tbs.TABLE_CN_STOCK_SELECTION
    cols = table["columns"]
    cols_cn = [ tbs.get_field_cn(x, table) for x in cols]
    save_file = os.path.join(os.path.dirname(__file__) , f"today_{datetime.today().strftime('%Y-%m-%d-%H-%M-%S')}.xlsx")
    stock_selection_df = stock_selection()
    stock_selection_df.columns = cols_cn
    if save:
        stock_selection_df.to_excel(save_file, index=False)
    return stock_selection_df

if __name__ == "__main__":
    app = StockClient()