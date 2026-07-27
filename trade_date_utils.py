import datetime
import akshare as ak
import pandas as pd


def get_recent_trade_date():
    """
    根据当前时间判断应该使用的交易日数据日期
    
    规则:
    1. 如果今天是交易日且当前时间在下午4:30之后，使用今天
    2. 如果今天是交易日但当前时间在下午4:30之前，使用最近一个交易日
    3. 如果今天不是交易日，使用最近一个交易日
    
    Returns:
        str: YYYYMMDD格式的日期字符串
    """
    # 获取当前时间
    now = datetime.datetime.now()
    today = now.date()
    today_str = today.strftime("%Y%m%d")
    
    try:
        # 获取近期交易日数据
        # 使用一个较大的时间范围来确保能获取到足够的数据
        start_date = (today - datetime.timedelta(days=30)).strftime("%Y%m%d")
        end_date = today_str
        
        # 获取交易日历数据
        tool_trade_date_hist_sina_df = ak.tool_trade_date_hist_sina()
        
        if tool_trade_date_hist_sina_df.empty:
            print("无法获取交易日历数据，使用今天作为默认日期")
            return today_str
        
        # 转换日期格式
        tool_trade_date_hist_sina_df['trade_date'] = pd.to_datetime(
            tool_trade_date_hist_sina_df['trade_date']).dt.date
        
        # 获取近期的交易日列表
        recent_trades = tool_trade_date_hist_sina_df[
            (tool_trade_date_hist_sina_df['trade_date'] >= datetime.datetime.strptime(start_date, "%Y%m%d").date()) & 
            (tool_trade_date_hist_sina_df['trade_date'] <= today)
        ].sort_values('trade_date', ascending=False)
        
        if recent_trades.empty:
            print("近期没有交易日数据，使用今天作为默认日期")
            return today_str
        
        # 判断今天是否是交易日
        today_is_trade_date = today in recent_trades['trade_date'].values
        
        if today_is_trade_date:
            # 今天是交易日
            if now.hour >= 16 and now.minute >= 30:
                # 当前时间在下午4:30之后，使用今天的数据
                return today_str
            else:
                # 当前时间在下午4:30之前，使用最近一个交易日（不包括今天）
                past_trades = recent_trades[recent_trades['trade_date'] < today]
                if not past_trades.empty:
                    last_trade_date = past_trades.iloc[0]['trade_date']
                    return last_trade_date.strftime("%Y%m%d")
                else:
                    print("无法找到之前的交易日，使用今天作为默认日期")
                    return today_str
        else:
            # 今天不是交易日，使用最近一个交易日
            last_trade_date = recent_trades.iloc[0]['trade_date']
            return last_trade_date.strftime("%Y%m%d")
            
    except Exception as e:
        print(f"获取交易日数据时出错: {e}")
        print("使用今天作为默认日期")
        return today_str


def get_recent_trade_date_v2():
    """
    另一种实现方式，通过查询每日活跃营业部数据来判断最近的交易日
    
    Returns:
        str: YYYYMMDD格式的日期字符串
    """
    # 从今天开始往前推，最多查询10天
    for i in range(10):
        check_date = (datetime.datetime.now().date() - datetime.timedelta(days=i))
        check_date_str = check_date.strftime("%Y%m%d")
        
        try:
            # 尝试获取该日期的活跃营业部数据
            df = ak.stock_lhb_hyyyb_em(start_date=check_date_str, end_date=check_date_str)
            # 如果能成功获取到数据，说明这是交易日
            if not df.empty:
                return check_date_str
        except Exception as e:
            # 如果出错，继续检查前一天
            continue
    
    # 如果都没找到，默认返回今天
    return datetime.datetime.now().date().strftime("%Y%m%d")


if __name__ == "__main__":
    # 测试函数
    date_to_use = get_recent_trade_date()
    print(f"应该使用的交易日日期: {date_to_use}")
    
    date_to_use_v2 = get_recent_trade_date_v2()
    print(f"方法二获取的交易日日期: {date_to_use_v2}")