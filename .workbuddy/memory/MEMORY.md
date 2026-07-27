# stk_explore 项目记忆

## 项目概况
- 股票客户端 GUI 应用，基于 tkinter/ttkbootstrap
- 主要入口：`ggui.py`，用 `python ggui.py` 或双击 `我的股票客户端.bat` 启动
- 运行环境：conda 环境 `stock`（路径 `C:\Users\xiongfeiwen\.conda\envs\stock`）

## 核心依赖
- akshare：金融数据接口
- ttkbootstrap：GUI 主题（使用 "yeti" 主题）
- pandastable：DataFrame 表格显示
- instock：内部数据抓取/lib 库

## 关键文件
- `ggui.py`：主 GUI 入口（StockClient 类）
- `zhangting.py`：涨停池相关（LimitUpPool, BlockTop, Continuous_limit_up, DataFramePretty）
- `utils.py`：工具函数（DataClass 基类, attention_kongpan, get_code_name 等）
- `hot_stock.py`：热门股票数据
- `lhb.py`：龙虎榜数据
- `jin10tab.py`：金十数据新闻直播
- `ATTENTION.py`：关注股票列表
- `instock/lib/http_client.py`：全局 HTTP 配置
- `instock/lib/akshare_patch.py`：akshare 补丁（User-Agent + 延迟）

## 已知问题与修复记录
- akshare API 请求经常被远端断开（RemoteDisconnected），在 HTTP 层添加了 Retry 机制
- pandastable 兼容性：需要设置 `pt.currheight = 0`
