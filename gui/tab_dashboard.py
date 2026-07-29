"""大盘仪表盘 - 市场概览首页"""
import threading
import logging
import pandas as pd
import ttkbootstrap as ttk
from gui.base_tab import BaseTab
from gui.theme import COLORS, FONTS, format_change
from gui.data_manager import DataManager

logger = logging.getLogger(__name__)
dm = DataManager()


class DashboardTab(BaseTab):
    """市场概览仪表盘：指数 + 赚钱效应 + 热门板块"""

    def __init__(self, parent):
        super().__init__(parent, tab_name="仪表盘")

    def _build_control_bar(self):
        self.add_refresh_btn("⟳ 刷新")
        self.indicator = self.add_status_indicator("数据状态")

    def _build_content(self):
        """三行布局：指数卡 / 赚钱效应卡 / 板块卡"""
        # 指数行
        self.index_frame = ttk.Frame(self.content)
        self.index_frame.pack(fill="x", pady=5)
        ttk.Label(self.index_frame, text="📊 大盘指数", font=FONTS["subtitle"],
                  foreground=COLORS["gold"]).pack(anchor="w")

        self.index_cards = {}
        for name in ("上证指数", "深证成指", "创业板指"):
            card = self._make_card(self.index_frame, name)
            self.index_cards[name] = card

        # 赚钱效应行
        earn_frame = ttk.Frame(self.content)
        earn_frame.pack(fill="x", pady=5)
        ttk.Label(earn_frame, text="💰 赚钱效应", font=FONTS["subtitle"],
                  foreground=COLORS["gold"]).pack(anchor="w")
        self.earn_card = self._make_card(earn_frame, "赚钱效应")

        # 热门板块行
        board_frame = ttk.Frame(self.content)
        board_frame.pack(fill="both", expand=True, pady=5)
        ttk.Label(board_frame, text="🔥 热门板块 TOP 10", font=FONTS["subtitle"],
                  foreground=COLORS["gold"]).pack(anchor="w")
        # 表格放在独立子容器中，避免与 label 的 pack() 冲突
        table_container = ttk.Frame(board_frame)
        table_container.pack(fill="both", expand=True)
        from pandastable import Table as Table2
        self.pt_board = Table2(table_container, dataframe=pd.DataFrame(),
                               showtoolbar=True, showstatusbar=True)
        self.pt_board.currheight = 0
        self.pt_board.show()

    def _make_card(self, parent, title: str) -> ttk.Frame:
        """创建信息卡片"""
        frame = ttk.Frame(parent, bootstyle="info", relief="raised", padding=8)
        frame.pack(side="left", fill="x", expand=True, padx=4, pady=2)
        ttk.Label(frame, text=title, font=FONTS["body"],
                  foreground=COLORS["text_dim"]).pack(anchor="w")
        value = ttk.Label(frame, text="--", font=FONTS["big_number"],
                          foreground=COLORS["text"])
        value.pack(anchor="w")
        change = ttk.Label(frame, text="", font=FONTS["small"])
        change.pack(anchor="w")
        return {"frame": frame, "value": value, "change": change}

    def _set_card(self, card: dict, value_text: str,
                  change_text: str = "", color: str = COLORS["text"]):
        card["value"].configure(text=value_text, foreground=color)
        card["change"].configure(text=change_text, foreground=color)

    def refresh_data(self):
        """后台线程：获取所有仪表盘数据"""
        self.set_indicator(self.indicator, "running")
        try:
            self._fetch_hot_boards()  # push2 API，稳定可用
            self._fetch_earn_money()  # 通过spot行情计算
            # 指数分时数据（push2his易限流，失败不影响其他数据）
            try:
                self._fetch_index_data()
            except Exception:
                pass
            self.set_indicator(self.indicator, "ok")
        except Exception as e:
            logger.warning(f"[仪表盘] 部分数据获取异常: {e}")
            self.set_indicator(self.indicator, "ok")  # 部分成功也算ok

    def _fetch_index_data(self):
        """获取大盘指数分时数据并提取最新值（push2his限流时跳过）"""
        indices = [
            ("上证指数", "0", 0),
            ("深证成指", "0", 1),
            ("创业板指", "0", 2),
        ]
        ok_count = 0
        for name, code, market in indices:
            try:
                raw = dm.get_market_minute(code, dapan=market)
                if raw and raw.get("data") and raw["data"].get("trends"):
                    trends = raw["data"]["trends"]
                    if trends:
                        last = trends[-1].split(",")
                        if len(last) >= 3:
                            close = float(last[2])
                            pre_close = raw["data"].get("prePrice", close)
                            change_pct = (close - pre_close) / pre_close * 100 if pre_close else 0
                            display, disp_color = format_change(change_pct)
                            self.frame.after(0, lambda n=name, v=f"{close:.2f}",
                                             c=display, cl=disp_color: self._set_card(
                                self.index_cards[n], v, c, cl))
                            ok_count += 1
                            continue
                # 数据不可用 -> 显示暂缺
                self.frame.after(0, lambda n=name: self._set_card(
                    self.index_cards[n], "--", "暂缺", COLORS["text_dim"]))
            except Exception:
                self.frame.after(0, lambda n=name: self._set_card(
                    self.index_cards[n], "--", "暂缺", COLORS["text_dim"]))

    def _fetch_earn_money(self):
        """获取赚钱效应（失败时静默跳过，不影响仪表盘）"""
        try:
            emx = dm.get_earn_money()
            # earn_money_xiaoying 返回 transposed DF:
            # columns=["上涨","涨停",...,"活跃度","统计日期"], index=["value"]
            if emx is not None and not emx.empty and "上涨" in emx.columns:
                up_val = emx["上涨"].values[0] if "上涨" in emx.columns else "--"
                down_val = emx["下跌"].values[0] if "下跌" in emx.columns else "--"
                act_val = emx["活跃度"].values[0] if "活跃度" in emx.columns else "--"
                text = f"↑{up_val}  ↓{down_val}  活跃:{act_val}"
                self.frame.after(0, lambda: self._set_card(
                    self.earn_card, text, "", COLORS["text"]))
        except Exception:
            pass  # 赚钱效应失败不影响仪表盘

    def _fetch_hot_boards(self):
        """获取热门板块"""
        try:
            boards = dm.get_board_list()
            if not boards:
                return
            top10 = boards[:10]
            rows = []
            for b in top10:
                chg = b.get("changePct", 0) or 0
                sign = "+" if chg > 0 else ""
                rows.append({
                    "排名": b["rank"], "板块名称": b["name"],
                    "涨幅%": f"{sign}{chg:.2f}",
                })
            df = pd.DataFrame(rows)
            self.frame.after(0, lambda: self._apply_table(self.pt_board, df))
        except Exception as e:
            logger.warning(f"[仪表盘] 热门板块获取失败: {e}")
