import requests
import pandas as pd
import json
import re
import time
from random import randint
from typing import Dict, List, Optional
from akshare.utils.tqdm import get_tqdm


def parse_response_data(response_text: str) -> Dict:
    """
    解析响应数据，支持JSON和JSONP两种格式
    
    遵循项目规范：
    1. 自动识别响应格式（JSON/JSONP）
    2. 对JSONP格式提取其中的JSON部分
    3. 对标准JSON格式直接解析
    """
    if not response_text:
        raise ValueError("响应内容为空")
    
    # 去除首尾空白字符
    response_text = response_text.strip()
    
    # 检查是否为JSONP格式 (callback(data))
    jsonp_match = re.search(r'^[a-zA-Z0-9_$]+\s*\((.*)\);?$', response_text, re.S)
    
    if jsonp_match:
        # JSONP格式，提取其中的JSON部分
        json_str = jsonp_match.group(1)
        if not json_str.strip():
            raise ValueError("JSONP中的JSON内容为空")
        return json.loads(json_str)
    else:
        # 直接是JSON格式
        return json.loads(response_text)


def fetch_page_data(url: str, params: Dict, page_num: int) -> Optional[Dict]:
    """
    获取指定页码的数据
    
    遵循项目网络请求规范：
    1. 添加随机延迟避免触发反爬虫机制
    2. 完善的异常处理机制
    3. 详细的错误日志记录
    """
    # 更新页码
    params['pageNumber'] = str(page_num)
    
    # 设置请求头，模拟浏览器访问
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://data.eastmoney.com/',
    }
    
    # 添加随机延迟，避免触发反爬虫机制
    time.sleep(randint(1, 3))
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        # 检查响应内容是否为空
        if not response.text:
            print(f"第 {page_num} 页返回空内容")
            return None
            
        # 解析响应数据
        data = parse_response_data(response.text)
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"获取第 {page_num} 页数据时请求出错: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"解析第 {page_num} 页JSON时出错: {e}")
        print(f"响应内容: {response.text[:200] if 'response' in locals() else '无响应内容'}")
        return None
    except ValueError as e:
        print(f"解析第 {page_num} 页数据时出错: {e}")
        print(f"响应内容: {response.text[:200] if 'response' in locals() else '无响应内容'}")
        return None
    except Exception as e:
        print(f"获取第 {page_num} 页数据时发生其他错误: {e}")
        return None


def stock_lhb_hyyyb_em(start_date: str = "20251113", end_date: str = "20251113") -> pd.DataFrame:
    """
    东方财富网-数据中心-龙虎榜单-每日活跃营业部
    https://data.eastmoney.com/stock/hyyyb.html
    
    :param start_date: 开始日期 format: YYYYMMDD
    :param end_date: 结束日期 format: YYYYMMDD
    :return: 每日活跃营业部数据
    """
    # 格式化日期
    start_date_formatted = "-".join([start_date[:4], start_date[4:6], start_date[6:]])
    end_date_formatted = "-".join([end_date[:4], end_date[4:6], end_date[6:]])
    
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "TOTAL_NETAMT,ONLIST_DATE,OPERATEDEPT_CODE",
        "sortTypes": "-1,-1,1",
        "pageSize": "50",  # 使用较小的页大小以便测试分页功能
        "pageNumber": "1",
        "reportName": "RPT_OPERATEDEPT_ACTIVE",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": f"(ONLIST_DATE>='{start_date_formatted}')(ONLIST_DATE<='{end_date_formatted}')",
    }
    
    # 先获取第一页，确定总页数
    print("开始获取第一页数据以确定总页数...")
    first_page_data = fetch_page_data(url, params.copy(), 1)
    if not first_page_data:
        print("无法获取第一页数据")
        return pd.DataFrame()
    
    total_pages = first_page_data.get('result', {}).get('pages', 1)
    total_count = first_page_data.get('result', {}).get('count', 0)
    print(f"总共 {total_pages} 页数据，{total_count} 条记录")
    
    # 存储所有页面数据
    all_data: List[Dict] = []
    
    # 获取第一页数据
    page_data = first_page_data.get('result', {}).get('data', [])
    all_data.extend(page_data)
    print(f"第 1 页数据获取完成，获取到 {len(page_data)} 条记录")
    
    # 获取剩余页面数据
    tqdm = get_tqdm()
    for page in tqdm(range(2, total_pages + 1), leave=False):
        page_data_result = fetch_page_data(url, params.copy(), page)
        if not page_data_result:
            print(f"跳过第 {page} 页")
            continue
            
        page_data = page_data_result.get('result', {}).get('data', [])
        all_data.extend(page_data)
        print(f"第 {page} 页数据获取完成，获取到 {len(page_data)} 条记录")
    
    print(f"\n总共获取到 {len(all_data)} 条数据")
    
    # 如果没有数据，返回空的DataFrame
    if not all_data:
        return pd.DataFrame()
    
    # 转换为DataFrame
    result_df = pd.DataFrame(all_data)
    
    # 重置索引
    result_df.reset_index(inplace=True)
    result_df["index"] = result_df.index + 1
    
    # 重命名列
    result_df.rename(
        columns={
            "index": "序号",
            "OPERATEDEPT_NAME": "营业部名称",
            "ONLIST_DATE": "上榜日",
            "BUYER_APPEAR_NUM": "买入个股数",
            "SELLER_APPEAR_NUM": "卖出个股数",
            "TOTAL_BUYAMT": "买入总金额",
            "TOTAL_SELLAMT": "卖出总金额",
            "TOTAL_NETAMT": "总买卖净额",
            "OPERATEDEPT_CODE": "营业部代码",
            "BUYER_STOCKS": "买入股票"
        },
        inplace=True,
    )
    
    # 选择需要的列
    columns = [
        "序号",
        "营业部名称",
        "上榜日",
        "买入个股数",
        "卖出个股数",
        "买入总金额",
        "卖出总金额",
        "总买卖净额",
        "买入股票",
        "营业部代码",
    ]
    
    # 检查列是否存在，避免KeyError
    existing_columns = [col for col in columns if col in result_df.columns]
    result_df = result_df[existing_columns]
    
    # 数据类型转换
    try:
        result_df["上榜日"] = pd.to_datetime(result_df["上榜日"], errors="coerce").dt.date
        result_df["买入个股数"] = pd.to_numeric(result_df["买入个股数"], errors="coerce")
        result_df["卖出个股数"] = pd.to_numeric(result_df["卖出个股数"], errors="coerce")
        result_df["买入总金额"] = pd.to_numeric(result_df["买入总金额"], errors="coerce")
        result_df["卖出总金额"] = pd.to_numeric(result_df["卖出总金额"], errors="coerce")
        result_df["总买卖净额"] = pd.to_numeric(result_df["总买卖净额"], errors="coerce")
    except Exception as e:
        print(f"数据类型转换时出错: {e}")
    
    return result_df


def display_data_summary(df: pd.DataFrame) -> None:
    """
    显示数据摘要信息
    """
    if df.empty:
        print("数据为空")
        return
    
    print(f"数据总条数: {len(df)}")
    print(f"列名: {list(df.columns)}")
    
    # 显示前几条数据
    print("\n前5条数据:")
    print(df.head())
    
    # 显示数值型列的统计信息
    numeric_columns = df.select_dtypes(include=['number']).columns
    if len(numeric_columns) > 0:
        print("\n数值型列统计信息:")
        print(df[numeric_columns].describe())


if __name__ == "__main__":
    print("=== 东方财富网每日活跃营业部数据获取 ===")
    
    # 获取数据
    df = stock_lhb_hyyyb_em(start_date="20251113", end_date="20251113")
    
    # 显示数据摘要
    display_data_summary(df)
    
    # 保存数据到CSV文件（可选）
    if not df.empty:
        df.to_csv("eastmoney_active_dept_20251113.csv", index=False, encoding="utf-8-sig")
        print("\n数据已保存到 eastmoney_active_dept_20251113.csv")