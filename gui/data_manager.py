"""数据管理器 - 统一管理API数据获取、缓存、全局串行限流"""
import logging
import time
import random
import threading
import pandas as pd
import akshare as ak
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from instock.lib.http_client import get_session, update_ua

logger = logging.getLogger(__name__)


class TTLCache:
    """带过期时间的缓存"""

    def __init__(self, default_ttl: float = 120.0):
        self._store: dict[str, tuple[object, float]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> object | None:
        if key not in self._store:
            return None
        data, expire_at = self._store[key]
        if time.time() > expire_at:
            del self._store[key]
            return None
        return data

    def set(self, key: str, data: object, ttl: float | None = None):
        self._store[key] = (data, time.time() + (ttl or self._default_ttl))

    def clear(self):
        self._store.clear()


class DataManager:
    """单例：集中管理数据获取，内置缓存、速率限制、多主机轮换、备用API兜底"""

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

        # === 连接池 ===
        self._session = get_session()
        update_ua(self._session)
        retry_strategy = Retry(
            total=5, backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy,
                              pool_connections=20, pool_maxsize=50)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        # === 全局串行锁 ===
        self._serial_lock = threading.Lock()
        self._last_request_time = 0.0
        self._min_interval = 1.0  # 全局最小请求间隔(秒)

        # === 多主机轮换 ===
        self._push2_hosts = [
            "https://push2.eastmoney.com",
            "https://82.push2.eastmoney.com",
            "https://17.push2.eastmoney.com",
            "https://60.push2.eastmoney.com",
            "https://push2his.eastmoney.com",
        ]
        self._host_idx = 0

        # === 缓存 ===
        self._cache = TTLCache(default_ttl=120.0)

    # ==================== 基础设施 ====================

    def _cache_key(self, prefix: str, *args) -> str:
        return f"{prefix}:{':'.join(str(a) for a in args)}"

    def _cached_call(self, key: str, fetch_func, ttl: float = 120.0):
        """缓存装饰：key存在且未过期则直接返回，否则调用fetch_func并缓存"""
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        data = fetch_func()
        if data is not None and not (isinstance(data, pd.DataFrame) and data.empty):
            self._cache.set(key, data, ttl)
        return data

    def _wait_serial(self):
        """全局串行锁：同一时间只有一个HTTP请求执行，且间隔 >= 1秒"""
        with self._serial_lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_request_time = time.time()

    def _next_push2_host(self) -> str:
        host = self._push2_hosts[self._host_idx % len(self._push2_hosts)]
        self._host_idx += 1
        return host

    # ==================== HTTP请求（全局串行）====================

    def http_json(self, url: str, params: dict | None = None,
                  max_retries: int = 5) -> dict | None:
        """全局串行HTTP请求：同一时间只发一个请求，间隔至少1秒"""
        self._wait_serial()
        headers = {}
        if "eastmoney.com" in url:
            headers["Referer"] = "https://quote.eastmoney.com/"
        for attempt in range(max_retries):
            try:
                r = self._session.get(url, params=params, headers=headers, timeout=10)
                return r.json()
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = 1.5 * (attempt + 1) + random.uniform(0, 0.5)
                    logger.debug(f"HTTP重试 ({url[:50]}...): {e}")
                    time.sleep(delay)
                    if "push2" in url:
                        host = self._next_push2_host()
                        old_host = url.split("/api/")[0]
                        url = url.replace(old_host, host)
                else:
                    logger.warning(f"HTTP最终失败 ({url[:60]}...): {e}")
                    return None

    def push2_get(self, fields: str, fs: str, pz: int = 100) -> list[dict]:
        """通用 push2 API"""
        host = self._next_push2_host()
        url = f"{host}/api/qt/clist/get"
        params = {
            "pn": "1", "pz": str(pz), "po": "1", "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2", "invt": "2", "fid": "f3",
            "fs": fs, "fields": fields,
        }
        data = self.http_json(url, params)
        if data is None:
            return []
        if data.get("data") and data["data"].get("diff"):
            return data["data"]["diff"]
        return []

    def akshare(self, func, *args, max_retries: int = 3, **kwargs):
        """安全调用 akshare 函数"""
        name = getattr(func, "__name__", str(func))
        for attempt in range(max_retries):
            try:
                time.sleep(random.uniform(0.3, 0.8))
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = 2 ** attempt + random.uniform(0, 0.5)
                    logger.warning(f"[{name}] retry {attempt+1}/{max_retries}: {e}")
                    time.sleep(delay)
                else:
                    logger.warning(f"[{name}] failed: {e}")
                    raise

    # ==================== 板块数据（含缓存+备用）====================

    def get_board_list(self) -> list[dict]:
        """获取行业板块TOP列表（缓存120s，push2失败时用akshare备用）"""
        def _fetch():
            items = self.push2_get(
                fields="f12,f14,f2,f3,f4,f8,f20,f21",
                fs="m:90+t:2",
            )
            if items:
                items.sort(key=lambda x: x.get("f3", 0) or 0, reverse=True)
                return [
                    {"rank": i + 1, "name": it.get("f14", ""), "code": it.get("f12", ""),
                     "changePct": it.get("f3") or 0}
                    for i, it in enumerate(items)
                ]
            # push2失败 → akshare备用
            try:
                df = self.akshare(ak.stock_board_industry_name_em)
                if df is not None and not df.empty:
                    return [
                        {"rank": i + 1, "name": row.get("板块名称", row.get("name", "")),
                         "code": row.get("板块代码", row.get("code", "")),
                         "changePct": row.get("涨跌幅", row.get("changePct", 0)) or 0}
                        for i, (_, row) in enumerate(df.iterrows())
                    ]
            except Exception:
                pass
            return []
        return self._cached_call("board_list", _fetch, ttl=120.0)

    def get_board_overview_df(self) -> pd.DataFrame:
        """获取板块总体DataFrame（缓存120s，push2失败时akshare备用）"""
        def _fetch():
            items = self.push2_get(
                fields="f12,f14,f2,f3,f4,f5,f6,f7,f8,f15,f16,f17,f18,f20,f21",
                fs="m:90+t:2",
            )
            if items:
                items.sort(key=lambda x: abs(x.get("f3", 0) or 0), reverse=True)
                return pd.DataFrame([{
                    "排名": i + 1, "板块名称": it.get("f14", ""),
                    "板块代码": it.get("f12", ""), "最新价": it.get("f2"),
                    "涨跌幅": it.get("f3"), "涨跌额": it.get("f4"),
                    "成交量": it.get("f5"), "成交额": it.get("f6"),
                    "振幅": it.get("f7"), "换手率": it.get("f8"),
                    "最高": it.get("f15"), "最低": it.get("f16"),
                    "今开": it.get("f17"), "昨收": it.get("f18"),
                } for i, it in enumerate(items)])
            try:
                return self.akshare(ak.stock_board_industry_name_em)
            except Exception:
                return pd.DataFrame()
        return self._cached_call("board_overview", _fetch, ttl=120.0)

    def get_board_stocks_df(self, board_code: str) -> pd.DataFrame:
        """获取板块成分股（缓存60s）"""
        def _fetch():
            items = self.push2_get(
                fields="f12,f14,f2,f3,f4,f5,f6,f7,f8,f15,f16,f17,f18,f20,f21",
                fs=f"b:{board_code}", pz=50,
            )
            if items:
                items.sort(key=lambda x: abs(x.get("f3", 0) or 0), reverse=True)
                return pd.DataFrame([{
                    "序号": i + 1, "代码": it.get("f12", ""),
                    "名称": it.get("f14", ""), "最新价": it.get("f2"),
                    "涨跌幅": it.get("f3"), "涨跌额": it.get("f4"),
                    "成交量": it.get("f5"), "成交额": it.get("f6"),
                    "振幅": it.get("f7"), "换手率": it.get("f8"),
                    "最高": it.get("f15"), "最低": it.get("f16"),
                    "今开": it.get("f17"), "昨收": it.get("f18"),
                } for i, it in enumerate(items)])
            return pd.DataFrame()
        return self._cached_call(f"board_stocks:{board_code}", _fetch, ttl=60.0)

    def get_market_minute(self, code: str, bankuai: bool = False,
                          dapan: int = -1) -> dict | None:
        """获取分时数据（不做缓存，受全局串行锁控制）"""
        self._wait_serial()
        from fenshitu_tab import get_minutely_data
        return get_minutely_data(code, bankuai=bankuai, dapan=dapan)

    # ==================== 其他数据 ====================

    def get_limit_up_pool(self, date: str) -> pd.DataFrame:
        return self.akshare(LimitUpPool().get_data_df_fcb, date, save=0)

    def get_stock_selection(self) -> pd.DataFrame:
        from hot_stock import getTodayStock
        return self.akshare(getTodayStock, save=0)

    def get_board_overview(self) -> pd.DataFrame:
        return self.akshare(ak.stock_board_industry_name_em)

    def get_earn_money(self) -> pd.DataFrame:
        """赚钱效应 - 使用 push2 实时行情计算（绕过akshare的50+页不可靠分页）"""
        items = self.push2_get(
            fields="f3,f12,f14",
            fs="m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
            pz=5000, domain="push2_spot",
        )
        if not items:
            logger.warning("push2获取实时行情为空")
            return pd.DataFrame()
        # 计算涨跌统计
        change_vals = []
        for it in items:
            f3 = it.get("f3")
            if f3 is not None:
                try:
                    change_vals.append(float(f3))
                except (ValueError, TypeError):
                    pass
        total = len(change_vals)
        up = sum(1 for v in change_vals if v > 0)
        down = sum(1 for v in change_vals if v < 0)
        flat = total - up - down
        zt = sum(1 for v in change_vals if v >= 9.5)
        dt = sum(1 for v in change_vals if v <= -9.5)
        activity = round((up + down) / total * 100, 2) if total > 0 else 0
        from datetime import datetime
        data = {
            "item": ["上涨", "涨停", "真实涨停", "st st*涨停",
                     "下跌", "跌停", "真实跌停", "st st*跌停",
                     "平盘", "停牌", "活跃度", "统计日期"],
            "value": [up, zt, zt, 0, down, dt, dt, 0, flat, 0,
                      f"{activity}%", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
        }
        result = pd.DataFrame(data)
        result.index = result["item"]
        result.drop("item", axis=1, inplace=True)
        return result.T

    def api_error_msg(self, e: Exception, func_name: str = "") -> str:
        err = str(e)
        t = type(e).__name__
        if "RemoteDisconnected" in err or "remote end closed" in err.lower():
            return f"⚠ {func_name}：连接被服务器关闭"
        if "ConnectionError" in t:
            return f"⚠ {func_name}：网络连接失败"
        if "JSONDecodeError" in t or "Expecting value" in err:
            return f"⚠ {func_name}：数据源异常"
        if "timeout" in err.lower() or "timed out" in err.lower():
            return f"⚠ {func_name}：请求超时"
        return f"⚠ {func_name}：{e}"


from zhangting import LimitUpPool
