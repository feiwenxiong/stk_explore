#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP客户端使用示例
展示如何在项目中统一管理User-Agent和其他HTTP请求头
"""

import sys
import os
# 添加项目路径到sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instock.lib.http_client import get_session, update_ua
import requests

def example_basic_usage():
    """基本使用示例"""
    print("=== 基本使用示例 ===")
    
    # 获取配置好的会话
    session = get_session()
    
    # 发送请求（自动包含User-Agent）
    response = session.get("https://httpbin.org/headers")
    headers = response.json()["headers"]
    
    print(f"User-Agent: {headers.get('User-Agent', 'Not set')}")
    print(f"Accept: {headers.get('Accept', 'Not set')}")
    print(f"Accept-Language: {headers.get('Accept-Language', 'Not set')}")

def example_customizing_requests():
    """自定义请求示例"""
    print("\n=== 自定义请求示例 ===")
    
    session = get_session()
    
    # 临时添加额外的请求头
    custom_headers = {
        "X-Custom-Header": "MyValue",
        "Referer": "https://example.com"
    }
    
    response = session.get(
        "https://httpbin.org/headers", 
        headers=custom_headers
    )
    
    headers = response.json()["headers"]
    print(f"Custom Header: {headers.get('X-Custom-Header', 'Not set')}")
    print(f"Referer: {headers.get('Referer', 'Not set')}")

def example_updating_user_agent():
    """更新User-Agent示例"""
    print("\n=== 更新User-Agent示例 ===")
    
    session = get_session()
    
    # 查看当前User-Agent
    response = session.get("https://httpbin.org/headers")
    old_ua = response.json()["headers"]["User-Agent"]
    print(f"旧User-Agent: {old_ua}")
    
    # 更新User-Agent
    update_ua(session)
    
    # 查看新User-Agent
    response = session.get("https://httpbin.org/headers")
    new_ua = response.json()["headers"]["User-Agent"]
    print(f"新User-Agent: {new_ua}")

def example_multiple_requests():
    """多个请求示例"""
    print("\n=== 多个请求示例 ===")
    
    session = get_session()
    
    urls = [
        "https://httpbin.org/headers",
        "https://httpbin.org/user-agent",
        "https://httpbin.org/get"
    ]
    
    for i, url in enumerate(urls, 1):
        response = session.get(url)
        print(f"请求 {i}: 状态码 {response.status_code}")
        
        # 每个请求使用相同的User-Agent
        if 'headers' in response.json():
            ua = response.json()['headers'].get('User-Agent', 'Not set')
            print(f"  User-Agent: {ua[:50]}...")  # 只显示前50个字符

if __name__ == "__main__":
    print("HTTP客户端使用示例")
    print("=" * 50)
    
    example_basic_usage()
    example_customizing_requests()
    example_updating_user_agent()
    example_multiple_requests()
    
    print("\n" + "=" * 50)
    print("示例完成")