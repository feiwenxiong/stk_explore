#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
akshare库专用的HTTP客户端配置
用于为akshare库添加User-Agent支持，避免被服务器识别为爬虫
"""

import requests
from fake_useragent import UserAgent
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# 创建全局User-Agent实例
ua = UserAgent()

# 防止重复打补丁
_session_patched = False
_direct_patched = False

# 保存原始引用（只在第一次保存）
_original_Session = requests.Session
_original_get = requests.get
_original_post = requests.post


def _mount_retry_adapter(session):
    """为 session 挂载连接重试适配器，处理 RemoteDisconnected 等瞬态错误"""
    retry_strategy = Retry(
        total=2,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "HEAD"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=5, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)


def get_random_ua():
    """
    获取随机User-Agent
    :return: 随机User-Agent字符串
    """
    try:
        return ua.random
    except:
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


def patch_akshare_session():
    """为akshare库修补Session，添加User-Agent支持（幂等，只应用一次）"""
    global _session_patched
    if _session_patched:
        return True

    try:
        # 创建带有浏览器级别头部的Session类
        class AkshareSession(_original_Session):
            def __init__(self):
                super().__init__()
                self.headers.update({
                    "User-Agent": get_random_ua(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Cache-Control": "max-age=0",
                    "Upgrade-Insecure-Requests": "1",
                })
                # 为每个新 Session 自动挂载连接重试适配器
                _mount_retry_adapter(self)

            def request(self, method, url, **kwargs):
                if "headers" not in kwargs:
                    kwargs["headers"] = {}
                if "User-Agent" not in kwargs["headers"]:
                    kwargs["headers"]["User-Agent"] = get_random_ua()
                # 为东方财富系域名自动添加 Referer
                if "eastmoney.com" in url or "10jqka.com.cn" in url:
                    if "Referer" not in kwargs["headers"]:
                        kwargs["headers"]["Referer"] = "https://data.eastmoney.com/"
                # 设置超时
                if "timeout" not in kwargs:
                    kwargs["timeout"] = 15
                return super().request(method, url, **kwargs)

        requests.Session = AkshareSession
        _session_patched = True
        print("成功为akshare库添加User-Agent支持")
        return True
    except Exception as e:
        print(f"为akshare库添加User-Agent支持时出错: {e}")
        return False


def patch_akshare_direct():
    """直接修补akshare内部的requests调用（幂等，只应用一次）"""
    global _direct_patched
    if _direct_patched:
        return True

    try:
        def patched_get(url, **kwargs):
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            if "User-Agent" not in kwargs["headers"]:
                kwargs["headers"]["User-Agent"] = get_random_ua()
            # 为东方财富/同花顺自动添加 Referer
            if "eastmoney.com" in url or "10jqka.com.cn" in url:
                if "Referer" not in kwargs["headers"]:
                    kwargs["headers"]["Referer"] = "https://data.eastmoney.com/"
            if "timeout" not in kwargs:
                kwargs["timeout"] = 15
            return _original_get(url, **kwargs)

        def patched_post(url, **kwargs):
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            if "User-Agent" not in kwargs["headers"]:
                kwargs["headers"]["User-Agent"] = get_random_ua()
            if "timeout" not in kwargs:
                kwargs["timeout"] = 15
            return _original_post(url, **kwargs)

        requests.get = patched_get
        requests.post = patched_post
        _direct_patched = True

        print("成功直接修补akshare的requests调用")
        return True
    except Exception as e:
        print(f"直接修补akshare的requests调用时出错: {e}")
        return False
