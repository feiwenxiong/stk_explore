import os
import sys
import pandas as pd
from datetime import datetime

# 添加项目路径
cpath_current = os.path.dirname(os.path.dirname(__file__))
sys.path.append(cpath_current)

from lhb import yyb_stocks2stock_yybs
from trade_date_utils import get_recent_trade_date

def test_yyb_stocks():
    """测试营业部股票数据处理功能"""
    print("=== 测试营业部股票数据处理功能 ===")
    
    # 获取最近的交易日
    trade_date = get_recent_trade_date()
    print(f"使用交易日: {trade_date}")
    
    # 游资文件路径
    youzi_file = os.path.join(os.path.dirname(__file__), "swim_cash3.json")
    print(f"游资文件: {youzi_file}")
    
    # 检查游资文件是否存在
    if not os.path.exists(youzi_file):
        print("警告: 游资文件不存在，将创建一个示例文件")
        create_sample_youzi_file(youzi_file)
    
    try:
        # 处理营业部股票数据
        print("开始处理营业部股票数据...")
        stock2yyb = yyb_stocks2stock_yybs(trade_date, youzi_file)
        
        print(f"成功处理 {len(stock2yyb)} 条记录")
        if not stock2yyb.empty:
            print("前5条数据:")
            print(stock2yyb.head())
            
            # 统计有股票名称的数据
            non_empty_names = stock2yyb[stock2yyb["名称"] != ""]
            print(f"其中包含股票名称的记录有 {len(non_empty_names)} 条")
            
            # 保存结果
            output_file = f"test_yyb_stocks_{trade_date}.xlsx"
            stock2yyb.to_excel(output_file, index=False)
            print(f"结果已保存到: {output_file}")
        else:
            print("未生成任何数据")
        
        return True
    except Exception as e:
        print(f"处理过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_sample_youzi_file(file_path):
    """创建示例游资文件"""
    sample_data = [
        ["深股通专用", "机构", "稳健"],
        ["华泰证券股份有限公司总部", "游资", "激进"],
        ["东方财富证券股份有限公司拉萨东环路第二证券营业部", "游资", "散户集中"]
    ]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        import json
        json.dump(sample_data, f, ensure_ascii=False, indent=2)
    
    print(f"已创建示例游资文件: {file_path}")

if __name__ == "__main__":
    test_yyb_stocks()