import sys
import json
import os

def main():
    try:
        argv = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    except:
        argv = {}

    path = argv.get('path')
    if not path:
        print("错误：缺少 path 参数")
        return

    if os.path.exists(path):
        print(f"文件已存在：{path}")
        return

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'w', encoding='utf-8').close()
        print(f"空文件已创建：{path}")
    except Exception as e:
        print(f"创建文件失败：{e}")

if __name__ == '__main__':
    main()