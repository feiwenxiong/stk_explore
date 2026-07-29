import json
import os
import sys
# cpath_current = os.path.dirname(os.path.dirname(__file__))
# sys.path.append(cpath_current)
from instock.core.crawling.stock_selection import * 
import pandas as pd
import numpy as np
from datetime import datetime
import instock.core.tablestructure as tbs
import akshare as ak
import sys
import os
# 添加项目路径到sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from instock.lib.akshare_patch import patch_akshare_all

# 应用akshare补丁（含requests Session、直接调用、curl_cffi）
patch_akshare_all()

def getTodayStock(save=True) -> pd.DataFrame:
    '''
    获取股吧人气榜等数据
    '''
    table = tbs.TABLE_CN_STOCK_SELECTION
    cols = table["columns"]
    cols_cn = [ tbs.get_field_cn(x,table) for x in cols]
    save_file = os.path.join(os.path.dirname(__file__) , f"today_{datetime.today().strftime('%Y-%m-%d-%H-%M-%S')}.xlsx")
    stock_selection_df = stock_selection()
    stock_selection_df.columns = cols_cn
    if save:
        stock_selection_df.to_excel(save_file, index=False)
    return stock_selection_df

def earn_money_xiaoying():
    '''赚钱效应 — 从东方财富实时行情计算（替代已失效的 legulegu 接口）
    return format:
                        item                value
    0         上涨               1198.0
    1         涨停                 26.0
    2       真实涨停                 22.0
    3   st st*涨停                  1.0
    4         下跌               3879.0
    5         跌停                333.0
    6       真实跌停                268.0
    7   st st*跌停                 77.0
    8         平盘                 37.0
    9         停牌                  2.0
    10       活跃度               23.42%
    11      统计日期  2024-04-15 15:00:00
    '''
    import logging
    logger = logging.getLogger(__name__)
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return _earn_money_fallback()

        close_col = [c for c in df.columns if "最新" in c or "收盘" in c or "close" in c.lower()]
        change_col = [c for c in df.columns if "涨跌幅" in c or "change" in c.lower()]
        name_col = [c for c in df.columns if "名称" in c or "name" in c.lower()]

        if not change_col:
            return _earn_money_fallback()

        change_series = df[change_col[0]].astype(float)
        total = len(df)
        up = int((change_series > 0).sum())
        down = int((change_series < 0).sum())
        flat = int(total - up - down)

        # 涨停判定: 主板10%, 科创/创业板20%, 北交所30%
        # 简化: >= 9.5% 视为涨停（含ST的5%不好判断）
        zt = int((change_series >= 9.5).sum())
        dt = int((change_series <= -9.5).sum())

        # 活跃度 = (上涨+下跌) / 总数 * 100
        activity = round((up + down) / total * 100, 2) if total > 0 else 0

        data = {
            "item": ["上涨", "涨停", "真实涨停", "st st*涨停",
                     "下跌", "跌停", "真实跌停", "st st*跌停",
                     "平盘", "停牌", "活跃度", "统计日期"],
            "value": [up, zt, zt, 0,
                      down, dt, dt, 0,
                      flat, 0, f"{activity}%",
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
        }
        result = pd.DataFrame(data)
        result.index = result["item"]
        result.drop("item", axis=1, inplace=True)
        return result.T
    except Exception as e:
        logger.warning(f"从实时行情计算赚钱效应失败: {e}")
        return _earn_money_fallback()


def _earn_money_fallback():
    """返回空DataFrame作为兜底"""
    return pd.DataFrame()


earn_money_xiaoying._fallback = _earn_money_fallback

def kongpan_attention():
    '''筛选关注文件中的股票的最近的控盘率走势
    '''
    
    from ATTENTION import ATTENTION
    from utils import get_code_name
    
    code_name_df,spot_df = get_code_name()
    
    data = pd.DataFrame()
    data["代码"] = ATTENTION
    
    trend = []
    for code in ATTENTION:
        try:
            stock_comment_detail_zlkp_jgcyd_em_df = ak.stock_comment_detail_zlkp_jgcyd_em(symbol=code)
            # 检查数据框中是否存在'value'列，如果不存在则尝试其他可能的列名
            if 'value' in stock_comment_detail_zlkp_jgcyd_em_df.columns:
                trend.append([round(x,2) for x in stock_comment_detail_zlkp_jgcyd_em_df["value"].tolist()])
            elif 'Value' in stock_comment_detail_zlkp_jgcyd_em_df.columns:
                trend.append([round(x,2) for x in stock_comment_detail_zlkp_jgcyd_em_df["Value"].tolist()])
            elif len(stock_comment_detail_zlkp_jgcyd_em_df.columns) > 1:
                # 如果没有明确的'value'列，使用第二列（通常是数值列）
                value_column = stock_comment_detail_zlkp_jgcyd_em_df.columns[1]
                trend.append([round(x,2) for x in stock_comment_detail_zlkp_jgcyd_em_df[value_column].tolist()])
            else:
                # 如果数据框为空或只有1列，添加空列表
                trend.append([])
        except Exception as e:
            print(f"获取股票 {code} 的控盘数据时出错: {e}")
            # 出错时添加空列表
            trend.append([])
    
    data["近来控盘比例趋势"] = trend
    
    # 只有在spot_df不为None时才进行合并
    if spot_df is not None:
        data = pd.merge(data,spot_df,left_on="代码",right_on="代码",how="left")
    # data.drop("")
    # print(data)
    # data[""]
    return data




if __name__ == "__main__":
    
    
    
    df_dict = {}
    #赚钱效应
    emx = earn_money_xiaoying()
    print(emx)
    df_dict["赚钱效应"] = emx
    
    #人气排名
    stock_hot_rank_em_df = ak.stock_hot_rank_em()
    print(stock_hot_rank_em_df)
    df_dict["人气排名"] = stock_hot_rank_em_df
    
    #飙升榜
    stock_hot_up_em_df = ak.stock_hot_up_em()
    print(stock_hot_up_em_df)
    df_dict["飙升榜"] = stock_hot_up_em_df
    
    #千人千评
    stock_comment_em_df = ak.stock_comment_em()
    print(stock_comment_em_df)
    # data = kongpan_attention()
    # print(data)