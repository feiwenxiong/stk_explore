#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
龙虎榜活跃营业部数据获取示例
根据当前时间智能判断应该使用的交易日
"""

import datetime
import pandas as pd
import akshare as ak
from trade_date_utils import get_recent_trade_date


def get_lhb_active_depts(trade_date=None):
    """
    获取指定交易日的龙虎榜活跃营业部数据
    
    Args:
        trade_date (str, optional): 交易日，格式为YYYYMMDD。如果未提供，自动判断
        
    Returns:
        pandas.DataFrame: 活跃营业部数据
    """
    # 如果没有提供交易日，则自动判断
    if not trade_date:
        trade_date = get_recent_trade_date()
        print(f"自动选择交易日: {trade_date}")
    
    try:
        # 获取龙虎榜活跃营业部数据
        df = ak.stock_lhb_hyyyb_em(start_date=trade_date, end_date=trade_date)
        return df
    except Exception as e:
        print(f"获取龙虎榜活跃营业部数据时出错: {e}")
        return pd.DataFrame()


def analyze_active_depts(df, top_n=10):
    """
    分析活跃营业部数据
    
    Args:
        df (pandas.DataFrame): 活跃营业部数据
        top_n (int): 显示前N个营业部
        
    Returns:
        None
    """
    if df.empty:
        print("没有数据可供分析")
        return
    
    print(f"=== 龙虎榜活跃营业部数据分析 ===")
    print(f"数据总条数: {len(df)}")
    
    # 显示前几个营业部
    print(f"\n净买入金额前{top_n}名营业部:")
    if '总买卖净额' in df.columns:
        top_depts = df.nlargest(top_n, '总买卖净额')
        for idx, row in top_depts.iterrows():
            print(f"{idx+1:2d}. {row['营业部名称']:<20} 净额: {row['总买卖净额']:>12.2f}")
    
    # 显示买入金额前几名
    print(f"\n买入金额前{top_n}名营业部:")
    if '买入总金额' in df.columns:
        top_buyers = df.nlargest(top_n, '买入总金额')
        for idx, row in top_buyers.iterrows():
            print(f"{idx+1:2d}. {row['营业部名称']:<20} 买入: {row['买入总金额']:>12.2f}")
    
    # 显示卖出金额前几名
    print(f"\n卖出金额前{top_n}名营业部:")
    if '卖出总金额' in df.columns:
        top_sellers = df.nlargest(top_n, '卖出总金额')
        for idx, row in top_sellers.iterrows():
            print(f"{idx+1:2d}. {row['营业部名称']:<20} 卖出: {row['卖出总金额']:>12.2f}")


def save_to_file(df, trade_date):
    """
    保存数据到文件
    
    Args:
        df (pandas.DataFrame): 数据
        trade_date (str): 交易日
        
    Returns:
        None
    """
    if df.empty:
        print("没有数据需要保存")
        return
    
    filename = f"lhb_active_depts_{trade_date}.csv"
    try:
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"数据已保存到 {filename}")
    except Exception as e:
        print(f"保存数据到文件时出错: {e}")


def main():
    """主函数"""
    print("=== 龙虎榜活跃营业部数据获取示例 ===")
    print(f"当前时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取活跃营业部数据
    df = get_lhb_active_depts()
    
    if df.empty:
        print("未能获取到数据")
        return
    
    # 分析数据
    analyze_active_depts(df)
    
    # 保存数据
    trade_date = get_recent_trade_date()
    save_to_file(df, trade_date)
    
    # 显示部分原始数据
    print(f"\n=== 原始数据示例 ===")
    print(df.head())


if __name__ == "__main__":
    main()