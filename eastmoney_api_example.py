import requests
import json
import re
import time
from random import randint

def parse_response_data(response_text):
    """
    解析响应数据，支持JSON和JSONP两种格式
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

def fetch_eastmoney_data():
    """
    访问东方财富网营业部活跃度数据接口
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    
    # 请求参数
    params = {
        'callback': 'jQuery112302523114553989869_1763106097941',
        'sortColumns': 'TOTAL_NETAMT,ONLIST_DATE,OPERATEDEPT_CODE',
        'sortTypes': '-1,-1,1',
        'pageSize': '50',
        'pageNumber': '1',
        'reportName': 'RPT_OPERATEDEPT_ACTIVE',
        'columns': 'ALL',
        'source': 'WEB',
        'client': 'WEB',
        'filter': "(ONLIST_DATE>='2025-11-13')"
    }
    
    # 设置请求头，模拟浏览器访问
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://data.eastmoney.com/',
        'Accept': 'text/javascript, application/javascript, application/ecmascript, application/x-ecmascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br'
    }
    
    try:
        # 发送GET请求
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()  # 如果响应状态码不是200，会抛出异常
        
        # 解析响应数据
        data = parse_response_data(response.text)
        
        # 输出结果
        print("请求成功!")
        print(f"总页数: {data.get('result', {}).get('pages', 'N/A')}")
        print(f"数据总数: {data.get('result', {}).get('count', 'N/A')}")
        
        # 输出部分数据
        result_data = data.get('result', {}).get('data', [])
        if result_data:
            print(f"\n第一页前5条数据:")
            for i, item in enumerate(result_data[:5]):
                print(f"{i+1}. 营业部代码: {item.get('OPERATEDEPT_CODE', 'N/A')}, "
                      f"营业部名称: {item.get('OPERATEDEPT_NAME', 'N/A')}, "
                      f"上榜日期: {item.get('ONLIST_DATE', 'N/A')}")
        else:
            print("未获取到数据")
            
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"请求出错: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON解析出错: {e}")
        print(f"返回内容: {response.text[:200] if 'response' in locals() else '无返回内容'}")
        return None
    except ValueError as e:
        print(f"数据解析出错: {e}")
        print(f"返回内容: {response.text[:200] if 'response' in locals() else '无返回内容'}")
        return None
    except Exception as e:
        print(f"其他错误: {e}")
        return None

def fetch_page_data(url, params, headers, page_num):
    """
    获取指定页码的数据
    """
    # 更新页码
    params['pageNumber'] = str(page_num)
    
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

def fetch_all_pages():
    """
    获取所有分页数据的示例
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    
    # 基础参数
    base_params = {
        'sortColumns': 'TOTAL_NETAMT,ONLIST_DATE,OPERATEDEPT_CODE',
        'sortTypes': '-1,-1,1',
        'pageSize': '50',
        'reportName': 'RPT_OPERATEDEPT_ACTIVE',
        'columns': 'ALL',
        'source': 'WEB',
        'client': 'WEB',
        'filter': "(ONLIST_DATE>='2025-11-13')"
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://data.eastmoney.com/',
    }
    
    all_data = []
    
    try:
        print("开始获取第一页数据以确定总页数...")
        # 先获取第一页，确定总页数
        first_page_data = fetch_page_data(url, base_params.copy(), headers, 1)
        if not first_page_data:
            print("无法获取第一页数据")
            return all_data
            
        total_pages = first_page_data.get('result', {}).get('pages', 1)
        print(f"总共 {total_pages} 页数据")
        
        # 获取第一页数据
        page_data = first_page_data.get('result', {}).get('data', [])
        all_data.extend(page_data)
        print(f"第 1 页数据获取完成，获取到 {len(page_data)} 条记录")
        
        # 获取剩余页面数据
        for page in range(2, total_pages + 1):
            page_data_result = fetch_page_data(url, base_params.copy(), headers, page)
            if not page_data_result:
                print(f"跳过第 {page} 页")
                continue
                
            page_data = page_data_result.get('result', {}).get('data', [])
            all_data.extend(page_data)
            print(f"第 {page} 页数据获取完成，获取到 {len(page_data)} 条记录")
            
        print(f"\n总共获取到 {len(all_data)} 条数据")
        return all_data
        
    except Exception as e:
        print(f"获取数据时出错: {e}")
        return all_data

if __name__ == "__main__":
    print("=== 单页数据获取示例 ===")
    fetch_eastmoney_data()
    
    print("\n=== 多页数据获取示例 ===")
    fetch_all_pages()