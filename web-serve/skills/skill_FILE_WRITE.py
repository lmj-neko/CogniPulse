import sys
import json
import os

def main():
    try:
        argv = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    except:
        argv = {}

    path = argv.get('path')
    content = argv.get('content', '')
    if not path:
        print("错误：缺少 path 参数")
        return

    try:
        # 创建父目录（如果不存在）
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"文件已写入：{path}")
    except Exception as e:
        print(f"写入文件失败：{e}")

if __name__ == '__main__':
    main()