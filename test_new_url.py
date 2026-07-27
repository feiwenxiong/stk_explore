import requests
from instock.lib.http_client import get_session, update_ua
from instock.lib.akshare_patch import patch_akshare_session, patch_akshare_direct
import math
import pandas as pd
from typing import List, Dict
from akshare.utils.tqdm import get_tqdm
# 应用akshare补丁
patch_akshare_session()
patch_akshare_direct()

def fetch_paginated_data(url: str, base_params: Dict, timeout: int = 15):
    """
    东方财富-分页获取数据并合并结果
    https://quote.eastmoney.com/f1.html?newcode=0.000001
    :param url: 股票代码
    :type url: str
    :param base_params: 基础请求参数
    :type base_params: dict
    :param timeout: 请求超时时间
    :type timeout: str
    :return: 合并后的数据
    :rtype: pandas.DataFrame
    """
    # 复制参数以避免修改原始参数
    params = base_params.copy()
    # 获取第一页数据，用于确定分页信息
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36 Edge/16.16299"}
    # update_ua(headers)
    print(headers)
    r = requests.get(url, params=params, timeout=timeout,headers=headers)
    data_json = r.json()
    # 计算分页信息
    per_page_num = len(data_json["data"]["diff"])
    total_page = math.ceil(data_json["data"]["total"] / per_page_num)
    # 存储所有页面数据
    temp_list = []
    # 添加第一页数据
    temp_list.append(pd.DataFrame(data_json["data"]["diff"]))
    # 获取进度条
    tqdm = get_tqdm()
    # 获取剩余页面数据
    for page in tqdm(range(2, total_page + 1), leave=False):
        params.update({"pn": page})
        r = requests.get(url, params=params, timeout=timeout)
        data_json = r.json()
        inner_temp_df = pd.DataFrame(data_json["data"]["diff"])
        temp_list.append(inner_temp_df)
    # 合并所有数据
    temp_df = pd.concat(temp_list, ignore_index=True)
    temp_df["f3"] = pd.to_numeric(temp_df["f3"], errors="coerce")
    temp_df.sort_values(by=["f3"], ascending=False, inplace=True, ignore_index=True)
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"].astype(int) + 1
    return temp_df

def stock_board_industry_name_em() -> pd.DataFrame:
    """
    东方财富网-沪深板块-行业板块-名称
    https://quote.eastmoney.com/center/boardlist.html#industry_board
    :return: 行业板块-名称
    :rtype: pandas.DataFrame
    """
    url = "https://17.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:90 t:2 f:!50",
        "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,"
        "f23,f24,f25,f26,f22,f33,f11,f62,f128,f136,f115,f152,f124,f107,f104,f105,"
        "f140,f141,f207,f208,f209,f222",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.columns = [
        "排名",
        "-",
        "最新价",
        "涨跌幅",
        "涨跌额",
        "-",
        "_",
        "-",
        "换手率",
        "-",
        "-",
        "-",
        "板块代码",
        "-",
        "板块名称",
        "-",
        "-",
        "-",
        "-",
        "总市值",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "上涨家数",
        "下跌家数",
        "-",
        "-",
        "-",
        "领涨股票",
        "-",
        "-",
        "领涨股票-涨跌幅",
        "-",
        "-",
        "-",
        "-",
        "-",
    ]
    temp_df = temp_df[
        [
            "排名",
            "板块名称",
            "板块代码",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "总市值",
            "换手率",
            "上涨家数",
            "下跌家数",
            "领涨股票",
            "领涨股票-涨跌幅",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["总市值"] = pd.to_numeric(temp_df["总市值"], errors="coerce")
    temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
    temp_df["上涨家数"] = pd.to_numeric(temp_df["上涨家数"], errors="coerce")
    temp_df["下跌家数"] = pd.to_numeric(temp_df["下跌家数"], errors="coerce")
    temp_df["领涨股票-涨跌幅"] = pd.to_numeric(
        temp_df["领涨股票-涨跌幅"], errors="coerce"
    )
    return temp_df

if __name__ == "__main__":
    stock_board_industry_name_em_df = stock_board_industry_name_em()
    print(stock_board_industry_name_em_df)
    
    
    
