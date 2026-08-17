import sys
import json
import requests

def main():
    try:
        argv = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    except:
        argv = {}
    
    ip = argv.get('ip')
    if ip:
        url = f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,isp,query"
    else:
        url = "http://ip-api.com/json/?fields=status,message,country,regionName,city,isp,query"
    
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('status') == 'success':
            result = f"IP: {data['query']}\n国家: {data['country']}\n地区: {data['regionName']}\n城市: {data['city']}\nISP: {data['isp']}"
        else:
            result = f"查询失败: {data.get('message', '未知错误')}"
    except Exception as e:
        result = f"请求异常: {str(e)}"
    print(result)

if __name__ == '__main__':
    main()