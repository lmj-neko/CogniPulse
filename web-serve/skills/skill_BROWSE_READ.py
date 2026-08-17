import sys
import json
import requests
from bs4 import BeautifulSoup
import re

# ---------- 修复 Windows 控制台编码问题 ----------
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def fetch_text(url):
    """获取网页纯文本（去除 HTML 标签），并检测是否是需要 JavaScript 的页面"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = 'utf-8'  # 强制 UTF-8
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 检查页面是否需要 JavaScript（例如标题中包含“JavaScript”或页面内容极短且包含“加载”）
        title = soup.title.string if soup.title else ''
        body_text = soup.get_text(separator='\n')
        body_text_clean = '\n'.join([line.strip() for line in body_text.splitlines() if line.strip()])
        
        # 如果页面内容很少，可能是 SPA，尝试从页面中提取一些 meta 或描述信息
        if len(body_text_clean) < 200 and ('加载' in body_text_clean or 'JavaScript' in body_text_clean or 'js' in body_text_clean.lower()):
            # 提取 meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            meta_desc_content = meta_desc.get('content', '') if meta_desc else ''
            og_title = soup.find('meta', attrs={'property': 'og:title'})
            og_title_content = og_title.get('content', '') if og_title else ''
            result = f"该页面可能是一个需要 JavaScript 渲染的 SPA 页面，无法直接获取完整内容。\n"
            result += f"页面标题：{title}\n"
            if og_title_content:
                result += f"Open Graph 标题：{og_title_content}\n"
            if meta_desc_content:
                result += f"页面描述：{meta_desc_content}\n"
            result += "建议查看网页源代码或使用可执行 JavaScript 的浏览器访问。"
            return result
        
        # 移除脚本、样式等
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        text = soup.get_text(separator='\n')
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        content = '\n'.join(lines)
        if not content:
            return "未提取到任何文本内容，该页面可能为空或完全由 JavaScript 驱动。"
        return content
    except Exception as e:
        return f"获取网页内容失败：{str(e)}"

def main():
    try:
        argv = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    except:
        argv = {}

    url = argv.get('url')
    if not url:
        print("错误：缺少 url 参数")
        return

    content = fetch_text(url)
    print(content)

if __name__ == '__main__':
    main()