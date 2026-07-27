#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局HTTP客户端配置
用于统一管理所有网络请求的配置，包括User-Agent等
"""

import requests
from fake_useragent import UserAgent
import functools
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# 创建全局User-Agent实例
ua = UserAgent()

# 创建全局requests会话
session = requests.Session()

# 设置默认的User-Agent
default_headers = {
    "User-Agent": ua.random,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

session.headers.update(default_headers)

# 为全局会话添加连接重试机制，解决 RemoteDisconnected 等问题
retry_strategy = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST", "HEAD"],
    # 处理连接级别的错误（如 RemoteDisconnected）
    raise_on_status=False,
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
session.mount("http://", adapter)
session.mount("https://", adapter)

def get_session():
    """
    获取配置好的requests会话
    :return: requests.Session对象
    """
    return session

def get_random_ua():
    """
    获取随机User-Agent
    :return: 随机User-Agent字符串
    """
    return ua.random

def update_ua(session_obj=None):
    """
    更新User-Agent
    :param session_obj: requests会话对象，如果为None则更新全局会话
    """
    if session_obj is None:
        session_obj = session
    
    session_obj.headers.update({"User-Agent": ua.random})