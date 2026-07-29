#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stk_explore 量化交易桌面客户端 v4.0
模块化架构: gui/ 包管理各标签页，ggui.py 为主入口+导航
"""
import os
import sys
import time
import threading
import logging
import traceback
import random
import warnings

import pandas as pd
import akshare as ak
import tkinter as tk
import ttkbootstrap as ttk
from pandastable import Table as Table2
from datetime import timedelta, datetime

# 项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import *
from hot_stock import *
from zhangting import LimitUpPool, DataFramePretty
from lhb import yyb_stocks2stock_yybs
from fenshitu_tab import (
    get_minutely_data, data_to_data_frame, get_bankuai_dapan_minute_trend,
    get_bankuai_data, get_bankuai_stock_data,
)
from jin10tab import Jin10App
from instock.lib.http_client import get_session, update_ua
from instock.lib.akshare_patch import patch_akshare_all
from gui.theme import THEME_NAME, COLORS, FONTS, apply_styles
from gui.tab_dashboard import DashboardTab
from gui.data_manager import DataManager

# 应用补丁
patch_akshare_all()

warnings.filterwarnings('ignore')
pd.set_option('future.no_silent_downcasting', True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] %(message)s',
)
logger = logging.getLogger(__name__)


class StockClient:
    """主窗口 - 导航 + 内容区"""

    def __init__(self):
        self.stop_event = threading.Event()
        self.nearest_trade_date = closest_trade_date()
        self.my_images = []
        self._setup_gui()

    def _setup_gui(self):
        self.root = ttk.Window(themename=THEME_NAME)
        apply_styles(ttk.Style())

        ww, wh = 1480, 820
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}")
        self.root.title("stk_explore 量化交易终端 v4.0")

        # ===== 主导航布局 =====
        self.main_pane = tk.PanedWindow(self.root, orient="horizontal",
                                         sashwidth=3, bg=COLORS["bg_dark"])
        self.main_pane.pack(fill="both", expand=True)

        # --- 左侧导航树 ---
        sidebar = ttk.Frame(self.main_pane, width=200)
        ttk.Label(sidebar, text="功能导航", font=FONTS["title"],
                  foreground=COLORS["gold"]).pack(fill="x", padx=10, pady=8)
        ttk.Separator(sidebar, orient="horizontal").pack(fill="x")

        self.nav_tree = ttk.Treeview(sidebar, show="tree", padding=5)
        self.nav_tree.pack(fill="both", expand=True)

        # 底部交易状态
        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=5)
        st_frame = ttk.Frame(sidebar, padding=5)
        st_frame.pack(fill="x", padx=5, pady=5)
        self.trade_light = tk.Label(st_frame, text="⚪", fg="gray", font=("", 12))
        self.trade_light.pack(side="left", padx=(0, 5))
        self.trade_text = ttk.Label(st_frame, text="检测中...", font=FONTS["small"])
        self.trade_text.pack(side="left")

        self.main_pane.add(sidebar, width=220)

        # --- 右侧内容区 ---
        self.content_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(self.content_frame)

        # 新闻帧（特殊处理）
        self.news_frame = tk.Frame(self.content_frame, bg=COLORS["bg_dark"])
        try:
            Jin10App(self.news_frame)
        except Exception as e:
            logger.error(f"新闻加载失败: {e}")
            tk.Label(self.news_frame, text=f"新闻加载失败: {e}",
                     fg="red", font=FONTS["body"]).pack(pady=20)

        # 创建所有标签页帧
        self.tab_frames = []
        for _ in range(14):
            self.tab_frames.append(ttk.Frame(self.content_frame))

        # ----- 导航分类 -----
        categories = [
            ("📊 市场总览", [
                ("仪表盘", "dash"),
                ("新闻直播", "news"),
            ]),
            ("📈 实时行情", [
                ("涨停池[实时]", 0),
                ("板块总体[实时]", 1),
                ("板块成分股", 2),
                ("分时图[实时]", 11),
            ]),
            ("📈 趋势分析", [
                ("板块趋势[实时]", 3),
                ("板块个股趋势[实时]", 4),
            ]),
            ("💹 智能选股", [("选股", 5)]),
            ("🏦 龙虎榜", [
                ("龙虎榜和营业部", 6),
                ("今日涨停池[+龙虎榜]", 7),
            ]),
            ("⭐ 我的关注", [
                ("关注列表", 8),
                ("关注控盘", 9),
                ("关注列表-今日K线", 10),
            ]),
            ("⚙️ 扩展", [
                ("实用工具", 12),
                ("策略回测", 13),
            ]),
        ]

        self.node_map = {}
        for cat_name, items in categories:
            cat_id = self.nav_tree.insert("", "end", text=cat_name, open=True)
            for item_name, fid in items:
                nid = self.nav_tree.insert(cat_id, "end", text=f"  {item_name}")
                self.node_map[nid] = fid

        self.nav_tree.bind("<<TreeviewSelect>>", self._on_nav_select)
        self._current_frame = None

        # 构建仪表盘（特殊处理）
        self._dash_tab = DashboardTab(self.tab_frames[12])

        # 构建所有标签页
        self._create_tabs()

        # 默认显示仪表盘
        for cat_id in self.nav_tree.get_children(""):
            for child_id in self.nav_tree.get_children(cat_id):
                if self.node_map.get(child_id) == "dash":
                    self.nav_tree.selection_set(child_id)
                    self.nav_tree.see(child_id)
                    break
        self._on_nav_select(None)

        # 启动交易状态轮询
        self._update_trade_status()
        threading.Thread(target=self._poll_trade_status, daemon=True).start()

        self.root.mainloop()

    def _on_nav_select(self, _event=None):
        """导航切换"""
        sel = self.nav_tree.selection()
        if not sel:
            return
        fid = self.node_map.get(sel[0])
        if fid is None:
            return
        if self._current_frame:
            self._current_frame.pack_forget()

        if fid == "news":
            self.news_frame.pack(fill="both", expand=True)
            self._current_frame = self.news_frame
        elif fid == "dash":
            self._dash_tab.frame.pack(fill="both", expand=True)
            self._current_frame = self._dash_tab.frame
            threading.Thread(target=self._dash_tab.refresh_data, daemon=True).start()
        elif isinstance(fid, int) and 0 <= fid < len(self.tab_frames):
            self.tab_frames[fid].pack(fill="both", expand=True)
            self._current_frame = self.tab_frames[fid]

    # ==================== 以下保留所有现有标签页构建方法 ====================

    def _create_tabs(self):
        """构建所有标签页"""
        self._create_limit_up_tab()
        self._create_board_overview_tab()
        self._create_board_components_tab()
        self._create_ths_block_trend_tab()
        self._create_ths_block_stocks_tab()
        self._create_stock_selection_tab()
        self._create_lhb_yyb_tab()
        self._create_limit_up_lhb_tab()
        self._create_attention_tab()
        self._create_control_trend_tab()
        self._create_attention_kline_tab()
        try:
            self._create_fenshitu_tab()
        except Exception as e:
            logger.error(f"分时图标签页创建失败: {e}")

    # ---------- 涨停池 (tab 0) ----------
    def _create_limit_up_tab(self):
        tab = self.tab_frames[0]
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Label(bar, text="日期:", font=FONTS["body"]).grid(row=0, column=0, sticky="e", padx=3, pady=2)
        self.date_var = tk.StringVar(value=self.nearest_trade_date)
        ttk.Entry(bar, textvariable=self.date_var, width=14).grid(row=0, column=1, sticky="w", padx=3, pady=2)
        ttk.Label(bar, text="间隔(秒):", font=FONTS["body"]).grid(row=1, column=0, sticky="e", padx=3, pady=2)
        self.duration_var = tk.IntVar(value=60)
        ttk.Entry(bar, textvariable=self.duration_var, width=8).grid(row=1, column=1, sticky="w", padx=3, pady=2)
        ttk.Button(bar, text="开始监控", bootstyle="success", width=10,
                   command=lambda: threading.Thread(target=self._start_track_stock_changes_qt).start()
                   ).grid(row=0, column=2, rowspan=2, padx=5)
        ttk.Button(bar, text="停止", bootstyle="warning", width=8,
                   command=lambda: self.stop_update(self.stop_event)
                   ).grid(row=0, column=3, rowspan=2, padx=5)
        bar.columnconfigure(2, weight=1)
        ttk.Separator(tab, orient="horizontal").pack(fill="x", padx=10)
        self.table_frame = ttk.Frame(tab)
        self.table_frame.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self.pt_limitup = None

    # ---------- 板块总体 (tab 1) ----------
    def _create_board_overview_tab(self):
        tab = self.tab_frames[1]
        self.pt5 = Table2(tab, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        self.pt5.currheight = 0
        self.pt5.show()

        def _init():
            dm = DataManager()
            try:
                df = dm.get_board_overview_df()
                self.root.after(0, lambda: self._update_pt(self.pt5, df))
            except Exception as e:
                logger.warning(f"板块数据加载失败: {e}")
                self.root.after(0, lambda: self._update_pt(self.pt5,
                    pd.DataFrame({"提示": [self._api_err(e, "板块数据")]})))

        threading.Thread(target=_init, daemon=True).start()

    # ---------- 板块成分股 (tab 2) ----------
    def _create_board_components_tab(self):
        tab = self.tab_frames[2]
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        self.bankuai_var = tk.StringVar(value="消费电子")
        ttk.Label(bar, text="板块名称:", font=FONTS["body"]).pack(side="left", padx=(0, 3))
        ttk.Entry(bar, textvariable=self.bankuai_var, width=16).pack(side="left", padx=5)
        ttk.Button(bar, text="查询", bootstyle="success", width=8,
                   command=lambda: threading.Thread(target=self._update_board_components).start()
                   ).pack(side="left", padx=10)
        ttk.Separator(tab, orient="horizontal").pack(fill="x", padx=10)
        self.tab_frame6 = ttk.Frame(tab)
        self.tab_frame6.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self.pt6 = Table2(self.tab_frame6, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        self.pt6.currheight = 0
        self.pt6.show()

    def _update_board_components(self):
        name = self.bankuai_var.get()
        dm = DataManager()

        def _show_data(df):
            self.root.after(0, lambda d=df: self._update_pt(self.pt6, d))

        def _show_err(msg):
            self.root.after(0, lambda m=msg: self._update_pt(self.pt6,
                pd.DataFrame({"提示": [m]})))

        try:
            # 方法1: push2 API 全部板块列表中查找
            boards = dm.get_board_list()
            code = next((b["code"] for b in boards if b["name"] == name), "")
            if not code:
                matched = [b for b in boards if name in b["name"]]
                if len(matched) == 1:
                    code, name = matched[0]["code"], matched[0]["name"]
            if code:
                df = dm.get_board_stocks_df(code)
                if not df.empty:
                    _show_data(df)
                    return

            # 方法2: akshare 兜底（按名称直接查询）
            _show_err(f"正在尝试备用接口查询 \"{name}\"...")
            try:
                df_ak = self._safe_akshare(ak.stock_board_industry_cons_em, symbol=name)
                if df_ak is not None and not df_ak.empty:
                    _show_data(df_ak)
                    return
            except Exception:
                pass
            _show_err(f"未找到板块: {name}")
        except Exception as e:
            logger.error(f"板块成分股失败: {e}")
            _show_err(self._api_err(e, "板块成分"))

    # ---------- 同花顺板块趋势 (tab 3) ----------
    def _create_ths_block_trend_tab(self):
        tab = self.tab_frames[3]
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Button(bar, text="开始刷新", bootstyle="success", width=10,
                   command=lambda: threading.Thread(target=self._update_ths_trend).start()
                   ).pack(side="left", padx=(0, 10))
        ttk.Label(bar, text="点击表格黄色单元格跳转同花顺", font=FONTS["small"],
                  foreground=COLORS["text_dim"]).pack(side="left")
        ttk.Separator(tab, orient="horizontal").pack(fill="x", padx=10)
        content = ttk.Frame(tab)
        content.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        for c in range(2):
            content.columnconfigure(c, weight=1)
        content.rowconfigure(0, weight=12)
        content.rowconfigure(1, weight=1)

        f91, f92, f93 = ttk.Frame(content), ttk.Frame(content), ttk.Frame(content)
        f91.grid(row=0, column=0, sticky="nsew")
        f92.grid(row=0, column=1, sticky="nsew")
        f93.grid(row=1, column=0, columnspan=2, sticky="nsew")

        self.pt91 = Table2(f91, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        self.pt91.currheight = 0; self.pt91.show()
        self.pt92 = Table2(f92, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        self.pt92.currheight = 0; self.pt92.show()
        self.pt93 = Table2(f93, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        self.pt93.currheight = 0; self.pt93.show()

    def _update_ths_trend(self):
        from hot_stock import earn_money_xiaoying
        from zhangting import Continuous_limit_up, BlockTop
        def _apply91(df):
            self.pt91.model.df = df; self.pt91.redraw()
        def _apply92(df):
            self.pt92.model.df = df; self.pt92.redraw()
        def _apply93(df):
            self.pt93.model.df = df; self.pt93.redraw()
        try:
            emx = pd.DataFrame(earn_money_xiaoying())
            self.root.after(0, lambda: _apply91(emx))
        except Exception as e:
            logger.error(f"赚钱效应: {e}")
            self.root.after(0, lambda: _apply91(pd.DataFrame({"错误": [f"赚钱效应失败: {e}"]})))
        t_name = "初始"
        try:
            js = Continuous_limit_up().get_data_json(date=self.nearest_trade_date, filt=1)
            t = js["data"]
            t_name = t["trade_status"]["name"]
            self.root.after(0, lambda: _apply92(pd.DataFrame(t["limit_up_count"]).reset_index()))
        except Exception as e:
            logger.error(f"涨停统计: {e}")
        try:
            bt = BlockTop().get_data_df(date=self.nearest_trade_date, filt=1).drop("stock_list", axis=1)
            self.root.after(0, lambda: _apply93(bt))
            self.pt93.bind("<Button-1>", lambda ev: self._on_cell_click(ev, self.pt93))
            self.pt93.columncolors['code'] = 'yellow'
        except Exception as e:
            logger.error(f"板块Top: {e}")
        while t_name == "交易中":
            time.sleep(3)
            try:
                emx = pd.DataFrame(earn_money_xiaoying())
                js = Continuous_limit_up().get_data_json(date=self.nearest_trade_date, filt=1)
                t = js["data"]
                t_name = t["trade_status"]["name"]
                bt = BlockTop().get_data_df(date=self.nearest_trade_date, filt=1).drop("stock_list", axis=1)
                self.root.after(0, lambda: _apply91(emx))
                self.root.after(0, lambda: _apply92(pd.DataFrame(t["limit_up_count"]).reset_index()))
                self.root.after(0, lambda: _apply93(bt))
            except Exception:
                pass

    # ---------- 同花顺板块个股趋势 (tab 4) ----------
    def _create_ths_block_stocks_tab(self):
        tab = self.tab_frames[4]
        from zhangting import BlockTop, Continuous_limit_up

        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Button(bar, text="开始刷新", bootstyle="success", width=10,
                   command=lambda: threading.Thread(target=self._update_ths_stocks).start()
                   ).pack(side="left")
        ttk.Separator(tab, orient="horizontal").pack(fill="x", padx=10)
        f11 = ttk.Frame(tab)
        f11.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self.pt11 = Table2(f11, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        self.pt11.currheight = 0; self.pt11.show()

    def _update_ths_stocks(self):
        from zhangting import BlockTop, Continuous_limit_up
        def _proc(blocks):
            t = []
            for b in blocks:
                t.extend(b["stock_list"])
            t = pd.DataFrame(t)
            t["first_limit_up_time"] = t["first_limit_up_time"].map(int).map(datetime.fromtimestamp)
            t["last_limit_up_time"] = t["last_limit_up_time"].map(int).map(datetime.fromtimestamp)
            return t
        try:
            bt = BlockTop().get_data_json(date=self.nearest_trade_date, filt=1)["data"]
            self.root.after(0, lambda: self._update_pt(self.pt11, _proc(bt)))
        except Exception as e:
            logger.error(f"热点板块成分股: {e}")
        try:
            js = Continuous_limit_up().get_data_json(date=self.nearest_trade_date, filt=1)
            t = js["data"]
            while t["trade_status"]["name"] == "交易中":
                time.sleep(3)
                bt = BlockTop().get_data_json(date=self.nearest_trade_date, filt=1)["data"]
                self.root.after(0, lambda: self._update_pt(self.pt11, _proc(bt)))
                js = Continuous_limit_up().get_data_json(date=self.nearest_trade_date, filt=1)
                t = js["data"]
        except Exception as e:
            logger.error(f"热点板块个股循环: {e}")

    # ---------- 智能选股 (tab 5) ----------
    def _create_stock_selection_tab(self):
        tab = self.tab_frames[5]
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Button(bar, text="开始刷新", bootstyle="success", width=10,
                   command=lambda: threading.Thread(target=self._update_selection).start()
                   ).pack(side="left")
        ttk.Separator(tab, orient="horizontal").pack(fill="x", padx=10)
        f8 = ttk.Frame(tab)
        f8.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self.pt8 = Table2(f8, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        self.pt8.currheight = 0; self.pt8.show()

    def _update_selection(self):
        try:
            df = self._safe_akshare(getTodayStock, save=0)
            self.root.after(0, lambda: self._update_pt(self.pt8, df))
        except Exception as e:
            logger.error(f"选股失败: {e}")
            self.root.after(0, lambda: self._update_pt(self.pt8,
                pd.DataFrame({"提示": [self._api_err(e, "选股")]})))

    # ---------- 龙虎榜和营业部 (tab 6) ----------
    def _create_lhb_yyb_tab(self):
        tab = self.tab_frames[6]
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Button(bar, text="开始刷新", bootstyle="success", width=10,
                   command=lambda: threading.Thread(target=self._update_lhb).start()
                   ).pack(side="left")
        ttk.Separator(tab, orient="horizontal").pack(fill="x", padx=10)
        f3 = ttk.Frame(tab)
        f3.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self.pt3 = Table2(f3, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        self.pt3.currheight = 0; self.pt3.show()

    def _update_lhb(self):
        try:
            fp = os.path.join(os.path.dirname(__file__), "swim_cash3.json")
            df = yyb_stocks2stock_yybs(self.nearest_trade_date, fp)
            self.root.after(0, lambda: self._update_pt(self.pt3, df))
        except Exception as e:
            logger.error(f"龙虎榜: {e}")
            self.root.after(0, lambda: self._update_pt(self.pt3,
                pd.DataFrame({"提示": [self._api_err(e, "龙虎榜")]})))

    # ---------- 涨停池+龙虎榜 (tab 7) ----------
    def _create_limit_up_lhb_tab(self):
        tab = self.tab_frames[7]
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Button(bar, text="开始刷新", bootstyle="success", width=10,
                   command=lambda: threading.Thread(target=self._update_limit_up_lhb).start()
                   ).pack(side="left")
        ttk.Separator(tab, orient="horizontal").pack(fill="x", padx=10)
        f4 = ttk.Frame(tab)
        f4.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self.pt4 = Table2(f4, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        self.pt4.currheight = 0; self.pt4.show()

    def _update_limit_up_lhb(self):
        try:
            from zhangting import today_limit_up_pool_detail_in_longhubang
            detail, _ = today_limit_up_pool_detail_in_longhubang()
            self.root.after(0, lambda: self._update_pt(self.pt4, detail))
        except Exception as e:
            logger.error(f"涨停池+LHB: {e}")
            self.root.after(0, lambda: self._update_pt(self.pt4,
                pd.DataFrame({"提示": [self._api_err(e, "涨停池+LHB")]})))

    # ---------- 关注列表 (tab 8) ----------
    def _create_attention_tab(self):
        tab = self.tab_frames[8]
        try:
            from ATTENTION import ATTENTION
            df = pd.DataFrame({"代码": ATTENTION})
        except Exception as e:
            logger.error(f"关注列表加载: {e}")
            df = pd.DataFrame({"错误": [f"加载失败: {e}"]})
        pt = Table2(tab, dataframe=df, showtoolbar=True, showstatusbar=True)
        pt.currheight = 0; pt.show()

    # ---------- 关注控盘 (tab 9) ----------
    def _create_control_trend_tab(self):
        tab = self.tab_frames[9]
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Button(bar, text="开始刷新", bootstyle="success", width=10,
                   command=lambda: threading.Thread(target=self._update_control).start()
                   ).pack(side="left")
        ttk.Separator(tab, orient="horizontal").pack(fill="x", padx=10)
        self.tab_frame2 = ttk.Frame(tab)
        self.tab_frame2.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self.pt2 = Table2(self.tab_frame2, dataframe=pd.DataFrame(), showtoolbar=True, showstatusbar=True)
        self.pt2.currheight = 0; self.pt2.show()

    def _update_control(self):
        try:
            data = kongpan_attention()
            self.root.after(0, lambda: self._update_pt(self.pt2, data))
        except Exception as e:
            logger.error(f"控盘: {e}")
            self.root.after(0, lambda: self._update_pt(self.pt2,
                pd.DataFrame({"提示": [self._api_err(e, "控盘")]})))

    # ---------- 关注K线 (tab 10) ----------
    def _create_attention_kline_tab(self):
        tab = self.tab_frames[10]
        self.folder_var = tk.StringVar(value="trends")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Label(bar, text="输出文件夹:", font=FONTS["body"]).pack(side="left", padx=(0, 3))
        ttk.Entry(bar, textvariable=self.folder_var, width=16).pack(side="left", padx=5)
        ttk.Button(bar, text="生成K线图", bootstyle="success", width=10,
                   command=lambda: threading.Thread(target=self._update_kline).start()
                   ).pack(side="left", padx=10)
        ttk.Separator(tab, orient="horizontal").pack(fill="x", padx=10)
        img_frame = ttk.Frame(tab)
        img_frame.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self.canvas = tk.Canvas(img_frame, borderwidth=1, bg=COLORS["bg_dark"])
        vsb = tk.Scrollbar(img_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.bind("<MouseWheel>", lambda ev: self._on_mw(ev, self.canvas))
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _update_kline(self):
        folder = self.folder_var.get()
        if os.path.exists(folder):
            import shutil
            shutil.rmtree(folder)
        os.makedirs(folder, exist_ok=True)
        try:
            attention_kongpan(folder)
        except Exception as e:
            logger.error(f"K线图生成: {e}")
            return
        self.root.after(0, lambda: self._render_kline_images(folder))

    # ---------- 分时图 (tab 11) ----------
    def _create_fenshitu_tab(self):
        """分时图标签页 - 保持完整原有逻辑"""
        # 引用原来自带的 fenshitu 方法（内联在类中，无需额外导入）
        self._fenshitu_build_ui(self.tab_frames[11])

    def _fenshitu_build_ui(self, tab):
        """构建分时图UI（原有逻辑迁移到类方法）"""
        import tkinter as tk
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        control_bar = ttk.Frame(tab)
        control_bar.pack(fill="x", padx=5, pady=5)

        self.fenshitu_running = False
        self.fenshitu_stop = threading.Event()
        self.fenshitu_data = (None, None)

        def toggle():
            if not self.fenshitu_running:
                self.fenshitu_running = True
                self.fenshitu_stop.clear()
                btn.configure(text="暂停", bootstyle="warning")
                self._log_fs("INFO", "分时图已启动")
                threading.Thread(target=self._fenshitu_loop, daemon=True).start()
            else:
                self.fenshitu_running = False
                self.fenshitu_stop.set()
                btn.configure(text="开始", bootstyle="success")
                self._log_fs("INFO", "分时图已暂停")

        btn = ttk.Button(control_bar, text="开始", bootstyle="success", command=toggle)
        btn.pack(side="left", padx=5)
        self.fs_elapsed = tk.StringVar(value="上次刷新: --")
        ttk.Label(control_bar, textvariable=self.fs_elapsed).pack(side="right", padx=5)

        paned = ttk.Panedwindow(tab, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=5, pady=5)

        # 右侧图表区
        chart_frame = ttk.Labelframe(paned, text="分时图", padding=3)
        self.fs_canvas = tk.Canvas(chart_frame, bg="white")
        vsb = ttk.Scrollbar(chart_frame, orient="vertical", command=self.fs_canvas.yview)
        hsb = ttk.Scrollbar(chart_frame, orient="horizontal", command=self.fs_canvas.xview)
        self.fs_scroll = ttk.Frame(self.fs_canvas)
        self.fs_scroll.bind("<Configure>",
            lambda e: self.fs_canvas.configure(scrollregion=self.fs_canvas.bbox("all")))
        self.fs_canvas.create_window((0, 0), window=self.fs_scroll, anchor="nw")
        self.fs_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.fs_canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.fs_canvas.bind("<MouseWheel>",
            lambda e: self.fs_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        paned.add(chart_frame, weight=4)

        ttk.Label(self.fs_scroll, text="点击'开始'加载分时图数据",
                  font=("", 12), foreground="gray").pack(pady=100)

    def _log_fs(self, level, msg):
        print(f"[分时图] {level}: {msg}")

    def _fenshitu_loop(self):
        """分时图抓取循环"""
        import time
        # self.fenshitu_stock_snapshots = {}
        while not self.fenshitu_stop.is_set():
            t0 = time.time()
            try:
                outer, inner, snaps = get_bankuai_dapan_minute_trend()
                self.fenshitu_data = (outer, inner)
                self.fenshitu_stock_snapshots = snaps
                self.root.after(0, self._fs_render)
                self.root.after(0, lambda: self.fs_elapsed.set(
                    f"刷新: {datetime.now().strftime('%H:%M:%S')} ({time.time()-t0:.1f}s)"))
            except Exception as e:
                self._log_fs("ERROR", f"抓取异常: {e}")
            # 等待
            if not self.fenshitu_stop.is_set():
                for _ in range(50):
                    if self.fenshitu_stop.is_set():
                        break
                    time.sleep(1)

    def _fs_render(self):
        """渲染分时图"""
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        outer, inner = self.fenshitu_data
        if not outer:
            return
        # 清理旧图
        for w in self.fs_scroll.winfo_children():
            w.destroy()
        items = list(outer.items())
        if len(items) < 4:
            ttk.Label(self.fs_scroll, text="数据不足", font=("", 11)).pack(pady=20)
            return
        sh, sz, cy = items[0][1], items[1][1], items[2][1]
        for i in range(3, len(items)):
            name = items[i][0]
            rank = items[i][1][0]
            data = items[i][1][1]
            # 即使板块数据为空，也渲染个股分时图（不跳过）
            has_board_data = not data.empty
            fig, axes = plt.subplots(2, 1, figsize=(8, 5.5), sharex=False)
            ax0, ax1 = axes
            if has_board_data:
                # 板块 vs 指数
                ax0.plot(data.index, data.Close, label=name, color="red", linewidth=1)
            if not sh.empty:
                ax0.plot(sh.index, sh.Close, label="上证", color="green", linewidth=0.8)
            if not sz.empty:
                ax0.plot(sz.index, sz.Close, label="深证", color="blue", linewidth=0.8)
            if not cy.empty:
                ax0.plot(cy.index, cy.Close, label="创业板", color="black", linewidth=0.8)
            ax0.set_title(f"Rank{int(rank)}: {name}" + ("" if has_board_data else " [板块数据暂不可用]"))
            ax0.grid(True, alpha=0.3)
            ax0.legend(fontsize=7)
            # 个股
            if name in inner:
                for sname, sitem in inner[name].items():
                    svals = list(sitem)
                    sdata = svals[1]
                    if not sdata.empty:
                        ax1.plot(sdata.index, sdata.Close, label=f"{svals[0]}_{sname}", linewidth=0.8)
            ax1.grid(True, alpha=0.3)
            ax1.legend(fontsize=6)
            fig.tight_layout()
            cvs = FigureCanvasTkAgg(fig, self.fs_scroll)
            cvs.get_tk_widget().grid(row=(int(rank)-1)//2, column=(int(rank)-1)%2, padx=8, pady=8, sticky="nsew")
            # 让两列均匀分配宽度
            self.fs_scroll.grid_columnconfigure(0, weight=1)
            self.fs_scroll.grid_columnconfigure(1, weight=1)
            self.fs_scroll.grid_rowconfigure((int(rank)-1)//2, weight=1)
            cvs.draw()
            plt.close(fig)
        # 确保滚动区域重新计算
        self.fs_scroll.update_idletasks()

    # ==================== 通用辅助方法 ====================

    def _safe_akshare(self, func, *args, **kwargs):
        for attempt in range(5):
            try:
                if attempt > 0:
                    time.sleep(2 ** attempt + random.uniform(0.1, 1))
                else:
                    time.sleep(random.uniform(0.5, 1.5))
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == 4:
                    raise e

    def _update_pt(self, pt, df):
        pt.model.df = df.copy() if hasattr(df, 'copy') else pd.DataFrame(df)
        pt.redraw()

    def _api_err(self, e, name=""):
        s = str(e)
        if "RemoteDisconnected" in s or "remote end closed" in s.lower():
            return f"⚠ {name}：连接被服务器关闭（非交易时段）"
        if "ConnectionError" in type(e).__name__:
            return f"⚠ {name}：网络连接失败"
        if "Expecting value" in s or "JSONDecodeError" in type(e).__name__:
            return f"⚠ {name}：数据源格式异常（盘后不可用）"
        return f"⚠ {name}：{e}"

    def _update_trade_status(self):
        from utils import is_now_open, is_now_break
        try:
            if is_now_open():
                if is_now_break():
                    self.trade_light.configure(text="🟡", fg="#d4a800")
                    self.trade_text.configure(text="午间休市")
                else:
                    self.trade_light.configure(text="🟢", fg="green")
                    self.trade_text.configure(text="交易中")
            else:
                self.trade_light.configure(text="🔴", fg="red")
                self.trade_text.configure(text="已收盘")
        except Exception:
            self.trade_light.configure(text="⚪", fg="gray")

    def _poll_trade_status(self):
        while True:
            self.root.after(0, self._update_trade_status)
            time.sleep(60)

    def _render_kline_images(self, folder):
        from PIL import Image, ImageTk
        self.canvas.delete("all")
        self.my_images.clear()
        loaded = 0
        for img_name in sorted(os.listdir(folder)):
            if not img_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
            try:
                path = os.path.join(folder, img_name)
                img = Image.open(path)
                tk_img = ImageTk.PhotoImage(img)
                x = 0
                y = loaded * img.height
                self.canvas.create_image(x, y, image=tk_img, anchor='nw')
                self.my_images.append(tk_img)
                img.close()
                loaded += 1
            except Exception as e:
                logger.error(f"加载图片 {img_name}: {e}")
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        if loaded == 0:
            self.canvas.create_text(10, 10, anchor="nw", text="无K线图（盘后不可用）",
                                    fill="darkorange", font=FONTS["body"])

    def _on_mw(self, event, canvas):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_cell_click(self, event, table):
        import webbrowser
        try:
            row = table.get_row_clicked(event)
            col = table.get_col_clicked(event)
            if table.model.df.columns[col] == 'code':
                val = table.model.getValueAt(row, col)
                url = f"https://q.10jqka.com.cn/thshy/detail/code/{str(int(val))}/"
                webbrowser.open(url)
        except Exception as e:
            logger.error(f"单元格点击: {e}")

    def _start_track_stock_changes_qt(self):
        date = self.date_var.get()
        interval = int(self.duration_var.get())

        def _run():
            try:
                code_name_df, _ = self._safe_akshare(get_code_name)
                code_name_df = code_name_df.rename(columns={"code": "代码", "name": "名称"})
                cache = self._safe_akshare(LimitUpPool().get_data_df_fcb, date, save=0)
                cache.drop("分时预览", axis=1, inplace=True)
                cache = pd.merge(cache, code_name_df, on="代码", how="left", suffixes=("", "_y"))
                dfp = DataFramePretty(cache)
                clist = [cache]

                def _create():
                    for w in self.table_frame.winfo_children():
                        w.destroy()
                    self.pt_limitup = Table2(self.table_frame, dataframe=dfp.data,
                                             showtoolbar=True, showstatusbar=True)
                    self.pt_limitup.currheight = 0
                    self.pt_limitup.show()
                    t = threading.Thread(target=self._update_data,
                                         args=(date, clist, dfp, interval, code_name_df, self.stop_event, self.pt_limitup))
                    t.daemon = True
                    t.start()
                self.root.after(0, _create)
            except Exception as e:
                logger.error(f"启动监控: {e}")

        threading.Thread(target=_run, daemon=True).start()

    def _update_data(self, date, cache_lst, dfp, interval, code_name_df, stop_event, pt):
        indicators = ["封单额"]
        while not stop_event.is_set():
            try:
                cache = cache_lst[0]
                data = self._safe_akshare(LimitUpPool().get_data_df_fcb, date, save=0)
                data.drop("分时预览", axis=1, inplace=True)
                data = pd.merge(data, code_name_df, on="代码", how="left", suffixes=("", "_y"))
                new = pd.merge(data, cache, on="代码", how="left", suffixes=("", "_y"))
                for ind in indicators:
                    col = round((new[ind] - new[ind + "_y"]) / new[ind + "_y"], 4) * 100
                    data[ind + "_change"] = col.apply(lambda x: f"{x}%")
                cache_lst[0] = data.copy()
                dfp.data = data.copy()
                self.root.after(0, lambda p=pt, d=data: self._update_pt(p, d))
            except Exception as e:
                logger.error(f"更新涨停池: {e}")
            time.sleep(interval)

    def stop_update(self, stop_event):
        stop_event.set()


if __name__ == "__main__":
    StockClient()
