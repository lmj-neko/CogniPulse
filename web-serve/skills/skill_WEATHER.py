import sys
import json
import requests

def main():
    try:
        argv = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    except:
        argv = {}
    
    city = argv.get('city', '北京')
    url = f"https://wttr.in/{city}?format=%C+%t&lang=zh"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            print(f"{city} 天气：{resp.text.strip()}")
        else:
            print(f"获取天气失败，状态码 {resp.status_code}")
    except Exception as e:
        print(f"请求异常: {str(e)}")

if __name__ == '__main__':
    main()