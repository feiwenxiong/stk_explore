#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络连接测试脚本
用于诊断stk_explore项目中的网络连接问题
"""

import requests
import akshare as ak
import time
import logging
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_basic_connection():
    """测试基本网络连接"""
    print("=== 基本网络连接测试 ===")
    try:
        response = requests.get("https://www.baidu.com", timeout=10)
        print(f"百度连接测试: 成功 - 状态码 {response.status_code}")
        return True
    except Exception as e:
        print(f"百度连接测试: 失败 - {e}")
        return False

def test_akshare_connection():
    """测试Akshare库的连接"""
    print("\n=== Akshare连接测试 ===")
    try:
        # 测试获取股票数据
        stock_data = ak.stock_zh_a_spot_em()
        print(f"Akshare股票数据获取: 成功 - 获取到 {len(stock_data)} 条记录")
        return True
    except Exception as e:
        print(f"Akshare股票数据获取: 失败 - {e}")
        return False

def test_ths_connection():
    """测试同花顺数据接口连接"""
    print("\n=== 同花顺数据接口测试 ===")
    urls_to_test = [
        "https://data.10jqka.com.cn",
        "https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool",
        "https://data.10jqka.com.cn/dataapi/limit_up/block_top"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    for url in urls_to_test:
        try:
            # 创建一个带有重试策略的会话
            session = requests.Session()
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            response = session.get(url, headers=headers, timeout=10)
            print(f"同花顺接口 {url}: 成功 - 状态码 {response.status_code}")
        except Exception as e:
            print(f"同花顺接口 {url}: 失败 - {e}")

def test_with_different_user_agents():
    """测试使用不同User-Agent的连接"""
    print("\n=== 不同User-Agent测试 ===")
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    ]
    
    url = "https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool"
    params = {
        "page": 1,
        "limit": 10,
        "field": "199112,10,9001,330323,330324,330325,9002,330329,133971,133970,1968584,3475914,9003,9004",
        "filter": "HS,GEM2STAR",
        "order_field": "330324",
        "order_type": 0,
        "date": "20251113",
        "_": int(time.time() * 1000)
    }
    
    for i, ua in enumerate(user_agents):
        try:
            headers = {"User-Agent": ua}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            print(f"User-Agent测试 {i+1}: 成功 - 状态码 {response.status_code}")
            if response.status_code == 200:
                break  # 如果成功则停止测试
        except Exception as e:
            print(f"User-Agent测试 {i+1}: 失败 - {e}")

def test_with_proxies():
    """测试使用代理的连接（如果配置了代理）"""
    print("\n=== 代理连接测试 ===")
    # 这里可以添加代理测试逻辑
    # 如果您有代理服务器，可以取消注释并配置以下代码
    """
    proxies = {
        'http': 'http://your-proxy:port',
        'https': 'http://your-proxy:port'
    }
    
    try:
        response = requests.get("https://data.10jqka.com.cn", proxies=proxies, timeout=10)
        print(f"代理连接测试: 成功 - 状态码 {response.status_code}")
    except Exception as e:
        print(f"代理连接测试: 失败 - {e}")
    """
    print("如果您需要使用代理，请在代码中配置代理服务器信息")

def test_connection_speed():
    """测试连接速度"""
    print("\n=== 连接速度测试 ===")
    urls = [
        "https://www.baidu.com",
        "https://www.sina.com.cn",
        "https://data.10jqka.com.cn"
    ]
    
    for url in urls:
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"{url}: 响应时间 {elapsed_time:.2f} 秒 - 状态码 {response.status_code}")
        except Exception as e:
            print(f"{url}: 连接失败 - {e}")

def main():
    """主测试函数"""
    print("开始网络连接诊断...")
    
    # 基本连接测试
    test_basic_connection()
    
    # Akshare连接测试
    test_akshare_connection()
    
    # 同花顺接口测试
    test_ths_connection()
    
    # 不同User-Agent测试
    test_with_different_user_agents()
    
    # 代理测试
    test_with_proxies()
    
    # 连接速度测试
    test_connection_speed()
    
    print("\n网络诊断完成。如果仍然存在问题，请检查：")
    print("1. 网络连接是否正常")
    print("2. 是否有防火墙或安全软件阻止连接")
    print("3. 目标网站是否启用了反爬虫机制")
    print("4. 是否需要使用代理服务器")

if __name__ == "__main__":
    main()