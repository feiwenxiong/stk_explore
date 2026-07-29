"""主题、颜色、字体配置"""

THEME_NAME = "flatly"  # ttkbootstrap 浅色主题，清晰易读

# 涨跌颜色（中国习惯：红涨绿跌）
COLORS = {
    "up": "#e74c3c",       # 红色(涨)
    "up_bg": "#fde8e8",    # 浅红背景
    "down": "#27ae60",     # 绿色(跌)
    "down_bg": "#e8f8e8",  # 浅绿背景
    "flat": "#95a5a6",
    "limit_up": "#ff2222",
    "limit_down": "#22cc44",
    # 浅色主题背景
    "bg_dark": "#f0f2f5",
    "bg_card": "#ffffff",
    "bg_input": "#e8ecf1",
    "accent": "#3498db",
    "gold": "#d4880f",
    "text": "#2c3e50",
    "text_dim": "#7f8c8d",
    "text_bright": "#000000",
    "border": "#bdc3c7",
    "success": "#27ae60",
    "warning": "#f39c12",
    "danger": "#e74c3c",
    "info": "#3498db",
}

FONTS = {
    "title": ("Segoe UI", 13, "bold"),
    "subtitle": ("Segoe UI", 11, "bold"),
    "body": ("Segoe UI", 9),
    "small": ("Segoe UI", 8),
    "mono": ("Consolas", 9),
    "big_number": ("Segoe UI", 22, "bold"),
}

# 自定义 ttk 样式（在换肤后应用）
# 用法: style.configure("Card.TFrame", **STYLES["Card"])
STYLES = {
    "Card": {
        "TFrame": {"background": COLORS["bg_card"]},
        "TLabel": {"background": COLORS["bg_card"], "foreground": COLORS["text"]},
        "TButton": {},
    },
    "Header": {
        "TLabel": {"foreground": COLORS["gold"], "font": FONTS["title"]},
    },
    "Value": {
        "TLabel": {"font": FONTS["big_number"]},
    },
    "Label.Dim": {
        "TLabel": {"foreground": COLORS["text_dim"], "font": FONTS["small"]},
    },
    "Refresh.TButton": {
        "TButton": {},
    },
}


def price_color(change_pct):
    """根据涨跌幅返回颜色"""
    if change_pct is None:
        return COLORS["flat"]
    if change_pct > 0:
        return COLORS["up"]
    elif change_pct < 0:
        return COLORS["down"]
    return COLORS["flat"]


def format_change(value, suffix="%"):
    """格式化涨跌幅显示"""
    if value is None or value != value:  # NaN check
        return "--"
    sign = "+" if value > 0 else ""
    color = price_color(value)
    return f"{sign}{value:.2f}{suffix}", color


def apply_styles(style):
    """应用所有自定义样式"""
    for group, widgets in STYLES.items():
        for widget, opts in widgets.items():
            style_name = f"{group}.{widget}"
            try:
                style.configure(style_name, **opts)
            except Exception:
                pass
