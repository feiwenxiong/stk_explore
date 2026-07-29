import os
import sys
cpath_current = os.path.dirname(os.path.dirname(__file__))
sys.path.append(cpath_current)
import akshare as ak
from utils import *
import requests as rq
import os
import pandas as pd
from datetime import timedelta
from hot_stock import *
import time
from lhb import yyb_stocks2stock_yybs 
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.live import Live
import select  # 确保导入 select 模块
import keyboard
import tkinter as tk
from pandastable import Table as Table2
import pandas as pd
from tkinter import ttk
import sys
import os
# 添加项目路径到sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from instock.lib.http_client import get_session, update_ua
from instock.lib.akshare_patch import patch_akshare_all

# 应用akshare补丁（含requests Session、直接调用、curl_cffi）
patch_akshare_all()

pd.set_option('future.no_silent_downcasting', True)

class Continuous_limit_up(DataClass):
    
    def get_data_json(self,date,filt):
        '''
            date:20240726
        '''
        url = " https://data.10jqka.com.cn/dataapi/limit_up/continuous_limit_up"
        match filt:
            case 0:
                # 沪深除了创科
                filt = "HS"
            case _:
                # + 创、科创
                filt = "HS,GEM2STAR"
        params = {"filter": filt,
                "date": date}
        
        # 使用统一配置的HTTP客户端
        session = get_session()
        # 更新User-Agent以避免反爬虫
        update_ua(session)
        
        headers = session.headers.copy()
        
        url = "https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool"
        resp = session.get(url, params=params)
        res = resp.json()
        return res

    
    def get_data_df(self,date,filt):
        data = self.get_data_json(date,filt)
        if data["status_code"]:
            return pd.DataFrame()
        return data["info"]
        
class LimitUpPool(DataClass):
    '''获取涨停的股票池
    '''

    
    def __init__(self):
        super().__init__()
        self.data_json = None
        
    def get_data_json(self,date):
        
        params = {
        "page": 1,
        "limit": 200,
        "field": "199112,10,9001,330323,330324,330325,9002,330329,133971,133970,1968584,3475914,9003,9004",
        "filter": "HS,GEM2STAR",
        "order_field": "330324",
        "order_type": 0,
        "date": date,
        "_": 1722309210154
        }
        
        # 使用统一配置的HTTP客户端
        session = get_session()
        # 更新User-Agent以避免反爬虫
        update_ua(session)
        
        headers = session.headers.copy()
        
        url = "https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool"
        resp = session.get(url, params=params)
        res = resp.json()
        self.data_json = res
        return res

    def get_data_df(self,date,save=True):
        data = self.get_data_json(date)["data"]
        cols_cn = {
        "open_num":"开板次数",
        "first_limit_up_time" :"首次涨停时间",
        "last_limit_up_time":"最后涨停时间",
        "code":"代码",
        "limit_up_type":'涨停形态',
        "order_volume":"封单量",
        "is_new":'新上',
        "limit_up_suc_rate":"近一年涨停封板率",
        "currency_value":"流通市值",
        "is_again_limit":"是否连板",
        "change_rate":"涨幅",
        "turnover_rate":"换手率",
        "reason_type":"涨停原因",
        "order_amount":"封单额",
        "high_days":"几天几板",
        "name":"名称",
        "change_tag":"是否回封",
        "latest":"最新",
        "time_preview":"分时预览",}

        info = data["info"]
        info_df = pd.DataFrame(info)
        info_df_cn = info_df.rename(columns=cols_cn)
        
        # 添加错误处理，确保时间字段是数值类型
        try:
            info_df_cn["首次涨停时间"] = info_df_cn["首次涨停时间"].apply(
                lambda x: int(x) if isinstance(x, (str, float)) and str(x).isdigit() else 0
            )
            info_df_cn["最后涨停时间"] = info_df_cn["最后涨停时间"].apply(
                lambda x: int(x) if isinstance(x, (str, float)) and str(x).isdigit() else 0
            )
            info_df_cn["首次涨停时间"] = pd.to_datetime(info_df_cn["首次涨停时间"], unit="s") + timedelta(hours=8)
            info_df_cn["最后涨停时间"] = pd.to_datetime(info_df_cn["最后涨停时间"], unit="s") + timedelta(hours=8)
        except Exception as e:
            print(f"处理时间字段时出错: {e}")
            # 如果处理失败，使用默认值
            info_df_cn["首次涨停时间"] = pd.to_datetime('1970-01-01 08:00:00')
            info_df_cn["最后涨停时间"] = pd.to_datetime('1970-01-01 08:00:00')

        limit_up_count = data["limit_up_count"]
        limit_down_count = data["limit_down_count"]
        if save:
            file_name  =os.path.join(os.path.dirname(__file__) ,getStrDate(2) + "_limit_up.xlsx")
            info_df_cn.to_excel(file_name,index=False)
        return info_df_cn,limit_up_count,limit_down_count
    
    def get_data_df_fcb(self,date,save=True):
        limit_up,limit_up_count,limit_down_count  = LimitUpPool().get_data_df(date,save=False)
        lst = []
        for code in limit_up["代码"]:
            tmp = {}
            tmp["代码"] = code
            try:
                # 将日期格式从YYYYMMDD转换为YYYY-MM-DD
                formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
                # 优先尝试 Sina 数据源（更稳定）
                try:
                    stock_zh_a_hist_df = ak.stock_zh_a_hist(
                        symbol=code,
                        period="daily",
                        start_date=formatted_date,
                        end_date=formatted_date,
                        adjust="qfq"
                    )
                except Exception:
                    # Sina 失败，回退到腾讯数据源
                    stock_zh_a_hist_df = ak.stock_zh_a_hist_tx(
                        symbol=code,
                        start_date=formatted_date,
                        end_date=formatted_date,
                        adjust="qfq"
                    )
                print(stock_zh_a_hist_df)
                # 检查是否有数据并且成交量列存在
                if not stock_zh_a_hist_df.empty and "成交量" in stock_zh_a_hist_df.columns:
                    tmp["成交量"] = stock_zh_a_hist_df["成交量"].iloc[0] * 100
                else:
                    print(f"股票 {code} 没有找到历史数据")
                    tmp["成交量"] = 0  # 如果没有数据，设置默认值
            except Exception as e:
                print(f"获取股票 {code} 的历史数据时出错: {e}")
                tmp["成交量"] = 0
            lst.append(tmp)
        df = pd.DataFrame(lst)
        
        df_merged = pd.merge(limit_up,df,on=["代码"])
        # 避免除以零的情况
        df_merged["封成比"] = df_merged.apply(
            lambda row: row["封单量"] / row["成交量"] if row["成交量"] != 0 else 0, axis=1
        )
        # print(df_merged)
        
        df_merged["预测"] = df_merged["封成比"].apply(self.fcb_map)
        if save:
            file_name  =os.path.join(os.path.dirname(__file__) ,getStrDate(2) + "_limit_up_fengchengbi.xlsx")
            df_merged.to_excel(file_name,index=False)
        return df_merged
    
    def fcb_map(self, fcb):
        '''
        封成比映射关系
        '''
        if fcb >= 10:
            return "极高"
        elif fcb >= 5:
            return "很高"
        elif fcb >= 2:
            return "较高"
        elif fcb >= 1:
            return "一般"
        elif fcb >= 0.5:
            return "较低"
        elif fcb >= 0.1:
            return "很低"
        else:
            return "极低"

class DataFramePretty(object):
    """DataFrame 包装类，用于在 pandas 表格和 rich 表格之间传递数据"""
    def __init__(self, df: pd.DataFrame) -> None:
        self.data = df

    def show(self, start_row=0, end_row=None):
        """
        显示指定范围的数据。
        :param start_row: 起始行号
        :param end_row: 结束行号
        :return: rich 表格对象
        """
        table = Table(show_header=True, header_style="bold magenta", show_lines=True)
        df = self.data.copy()
        if end_row is None:
            end_row = len(df)
        df = df.iloc[start_row:end_row]
        column_widths = {col: max(df[col].astype(str).map(len).max(), len(col)) for col in df.columns}
        for col in df.columns:
            table.add_column(col, width=column_widths[col], overflow="fold")
        for idx, row in df.iterrows():
            table.add_row(*row.astype(str))
        return table


class BlockTop(DataClass):
    """获取板块的信息（同花顺热点板块Top）"""

    def get_data_json(self, date, filt):
        url = "https://data.10jqka.com.cn/dataapi/limit_up/block_top"
        match filt:
            case 0:
                filt = "HS"
            case _:
                filt = "HS,GEM2STAR"
        params = {"filter": filt, "date": date}

        session = get_session()
        update_ua(session)
        resp = session.get(url, params=params)
        res = resp.json()
        return res

    def get_data_df(self, date, filt):
        data = self.get_data_json(date, filt)
        if data["status_code"]:
            return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        return df


def today_limit_up_pool_detail_in_longhubang(date=None):
    """获取今日涨停池并附带龙虎榜信息"""
    from utils import closest_trade_date
    if date is None:
        date = closest_trade_date()

    try:
        limit_up_df, limit_up_count, limit_down_count = LimitUpPool().get_data_df(date, save=False)

        youzi_file = os.path.join(os.path.dirname(__file__), "swim_cash3.json")
        lhb_df = yyb_stocks2stock_yybs(date, youzi_file)

        if lhb_df is not None and not lhb_df.empty and "代码" in lhb_df.columns:
            limit_up_detail = pd.merge(limit_up_df, lhb_df, on="代码", how="left", suffixes=("", "_lhb"))
        else:
            limit_up_detail = limit_up_df

        return limit_up_detail, limit_up_count
    except Exception as e:
        print(f"获取涨停池+龙虎榜数据时出错: {e}")
        return pd.DataFrame(), 0


if __name__ == "__main__":
    # 测试函数功能
    # 使用最近的实际交易日进行测试
    date = "20241113"  # 修改为最近的实际交易日
    print(f"正在获取 {date} 的涨停封成比数据...")
    
    try:
        stock_data = LimitUpPool().get_data_df_fcb(date, save=False)
        print("获取数据成功！前5行数据预览：")
        print(stock_data.head())
        
        # 显示封成比统计信息
        if not stock_data.empty:
            print("\n封成比统计信息：")
            print(stock_data["封成比"].describe())
            
            # 按预测等级分组统计
            print("\n按预测等级分组统计：")
            print(stock_data["预测"].value_counts())
        else:
            print("未获取到数据")
            
    except Exception as e:
        print(f"获取数据时发生错误: {e}")
