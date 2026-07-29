# GUI重设计划

> **目标:** 将当前1425行单体ggui.py改造为模块化、专业外观的量化交易工具

**架构:** 将当前单体GUI拆分为 `gui/` 包，包含基类、各标签页模块、主题配置、数据管理器。保留现有功能不变，重构UI架构和视觉设计。

**技术栈:** Tkinter + ttkbootstrap (dark主题), pandastable, matplotlib, threading

---

### 任务1: 创建新目录结构和模块基类

**文件:**
- Create: `gui/__init__.py`
- Create: `gui/base_tab.py` - 标签页基类
- Create: `gui/theme.py` - 主题配置
- Create: `gui/data_manager.py` - 数据管理器

- [ ] **步骤1: 创建目录结构**

```python
gui/
  __init__.py
  theme.py         # 主题、颜色、字体配置
  base_tab.py      # BaseTab基类
  data_manager.py  # 线程安全的数据管理器
  tab_dashboard.py # 大盘仪表盘
  tab_limitup.py   # 涨停池
  tab_board.py     # 板块
  tab_lhb.py       # 龙虎榜
  tab_attention.py # 关注
  tab_fenshitu.py  # 分时图
```

### 任务2: 主题和样式配置

**文件:**
- Create: `gui/theme.py`

- [ ] **步骤1: 创建主题配置**

```python
# gui/theme.py
import ttkbootstrap as ttk

THEME = "darkly"  # ttkbootstrap暗色主题

# 自定义颜色
COLORS = {
    "up": "#e74c3c",       # 红色(涨)
    "down": "#2ecc71",     # 绿色(跌) 
    "flat": "#95a5a6",     # 灰色(平)
    "limit_up": "#ff4444", # 亮红(涨停)
    "limit_down": "#44ff44", # 亮绿(跌停)
    "bg_dark": "#1a1a2e",  # 深色背景
    "bg_card": "#16213e",  # 卡片背景
    "accent": "#0f3460",   # 强调色
    "gold": "#e8b830",     # 金色
    "text": "#e0e0e0",     # 文字颜色
    "text_dim": "#7f8c8d", # 弱化文字
}

FONTS = {
    "title": ("Arial", 12, "bold"),
    "subtitle": ("Arial", 10, "bold"),
    "body": ("Arial", 9),
    "small": ("Arial", 8),
    "mono": ("Consolas", 9),
}

STYLES = {
    "Card.TFrame": {"background": COLORS["bg_card"]},
    "Card.TLabel": {"background": COLORS["bg_card"], "foreground": COLORS["text"]},
}
```

### 任务3: 标签页基类 BaseTab

**文件:**
- Create: `gui/base_tab.py`

```python
# gui/base_tab.py - 所有标签页的基类
from abc import ABC, abstractmethod
import threading
import logging
import pandas as pd
import ttkbootstrap as ttk
from gui.theme import COLORS, FONTS

logger = logging.getLogger(__name__)

class BaseTab(ABC):
    """标签页基类，提供通用模式：控制栏 + 内容区 + 自动刷新"""
    
    def __init__(self, parent, tab_name: str, auto_refresh: bool = False):
        self.frame = ttk.Frame(parent)
        self.tab_name = tab_name
        self._stop_flag = threading.Event()
        self._thread = None
        self._auto_refresh = auto_refresh
        
        self._build_ui()
    
    def _build_ui(self):
        """构建控制栏 + 内容区"""
        self.control_bar = ttk.Frame(self.frame)
        self.control_bar.pack(fill="x", padx=10, pady=(8, 4))
        self._build_control_bar()
        
        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=10)
        
        self.content = ttk.Frame(self.frame)
        self.content.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self._build_content()
    
    @abstractmethod
    def _build_control_bar(self):
        """子类实现：添加控制按钮"""
        pass
    
    @abstractmethod
    def _build_content(self):
        """子类实现：添加内容组件"""
        pass
    
    @abstractmethod
    def refresh_data(self):
        """子类实现：刷新数据"""
        pass
    
    def start_auto_refresh(self, interval: int = 60):
        """启动自动刷新"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_flag.clear()
        def _loop():
            while not self._stop_flag.wait(interval):
                try:
                    self.refresh_data()
                except Exception as e:
                    logger.error(f"[{self.tab_name}] auto-refresh error: {e}")
        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()
    
    def stop_auto_refresh(self):
        self._stop_flag.set()
    
    def add_refresh_button(self):
        """快速添加刷新按钮到控制栏"""
        btn = ttk.Button(self.control_bar, text="⟳ 刷新", bootstyle="info-outline",
                        command=lambda: threading.Thread(target=self.refresh_data, daemon=True).start())
        btn.pack(side="left", padx=2)
        return btn
    
    def add_table(self, **kwargs):
        """创建 pandastable"""
        from pandastable import Table as Table2
        pt = Table2(self.content, dataframe=pd.DataFrame(), 
                    showtoolbar=True, showstatusbar=True, **kwargs)
        pt.currheight = 0
        pt.show()
        return pt
    
    def safe_update_table(self, pt, df, error_msg="数据获取失败"):
        """线程安全地更新表格"""
        import traceback
        try:
            self.frame.after(0, lambda: self._update_table(pt, df))
        except Exception as e:
            logger.error(f"[{self.tab_name}] {error_msg}: {e}\n{traceback.format_exc()}")
            err_df = pd.DataFrame({"提示": [f"{error_msg}: {e}"]})
            self.frame.after(0, lambda: self._update_table(pt, err_df))
    
    def _update_table(self, pt, df):
        """在主线程更新表格"""
        pt.model.df = df.copy() if hasattr(df, 'copy') else pd.DataFrame(df)
        pt.redraw()
```

### 任务4: 数据管理器 DataManager

**文件:**
- Create: `gui/data_manager.py`

```python
# gui/data_manager.py - 集中管理数据获取和缓存
import logging
import time
import random
from functools import lru_cache
from instock.lib.http_client import get_session, update_ua

logger = logging.getLogger(__name__)

class DataManager:
    """数据管理器：统一数据获取、缓存、重试"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._session = get_session()
        update_ua(self._session)
        self._cache = {}
        self._last_call = {}  # domain -> timestamp
    
    def _rate_limit(self, domain: str, min_interval: float = 0.8):
        """速率限制"""
        now = time.time()
        last = self._last_call.get(domain, 0)
        elapsed = now - last
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call[domain] = time.time()
    
    def http_get(self, url, params=None, max_retries=3, domain="eastmoney"):
        """带重试和速率限制的HTTP GET"""
        self._rate_limit(domain)
        for attempt in range(max_retries):
            try:
                r = self._session.get(url, params=params, timeout=10)
                return r.json()
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1.5 * (attempt + 1) + random.uniform(0, 0.5))
                else:
                    logger.warning(f"HTTP GET failed ({max_retries} retries): {url[:80]}... {e}")
                    raise
    
    def safe_call(self, func, *args, max_retries=3, **kwargs):
        """通用安全调用"""
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.warning(f"Safe call failed: {func.__name__} {e}")
                    raise
```

### 任务5: 大盘仪表盘 Dashboard

**文件:**
- Create: `gui/tab_dashboard.py`

提供市场概览：大盘指数、赚钱效应、涨跌家数、北向资金、热门板块

### 任务6: 重构ggui.py为主入口

**文件:**
- Modify: `ggui.py`

使用新的模块化结构，保留导航和主布局。

### 任务7: 迁移现有标签页

迁移现有的12个标签页到独立的模块文件。
