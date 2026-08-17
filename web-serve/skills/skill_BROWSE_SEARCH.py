import sys
import json
import requests
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import time

# ---------- 修复 Windows 控制台编码问题 ----------
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def search_bing(query, max_results=5, retries=2):
    """使用 Bing 搜索，支持重试"""
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            # 手动指定编码为 UTF-8
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            results = []
            # Bing 搜索结果在 <li class="b_algo"> 中
            for item in soup.select('li.b_algo'):
                title_elem = item.select_one('h2 a')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href')
                snippet_elem = item.select_one('.b_caption p')
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                results.append({
                    'title': title,
                    'url': link,
                    'snippet': snippet
                })
                if len(results) >= max_results:
                    break
            
            if results:
                return results
            else:
                # 可能页面结构变化，尝试备用选择器
                for item in soup.select('.b_algo'):
                    title_elem = item.find('a', href=True)
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href')
                    snippet_elem = item.find('p', class_='b_caption')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                    results.append({
                        'title': title,
                        'url': link,
                        'snippet': snippet
                    })
                    if len(results) >= max_results:
                        break
                if results:
                    return results
                
        except Exception as e:
            if attempt == retries:
                return {'error': f'搜索失败（尝试 {retries+1} 次）：{str(e)}'}
            time.sleep(2)  # 重试前等待
    
    return {'error': '搜索失败：多次重试无响应'}

def main():
    try:
        argv = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    except:
        argv = {}

    query = argv.get('query')
    if not query:
        print("错误：缺少 query 参数")
        return

    results = search_bing(query)
    if isinstance(results, dict) and 'error' in results:
        print(results['error'])
        return

    if not results:
        print("未找到相关结果。")
        return

    output = f"找到 {len(results)} 个结果：\n\n"
    for i, r in enumerate(results):
        output += f"【{i+1}】{r['title']}\n"
        output += f"URL: {r['url']}\n"
        output += f"摘要：{r['snippet']}\n\n"

    print(output.strip())

if __name__ == '__main__':
    main()