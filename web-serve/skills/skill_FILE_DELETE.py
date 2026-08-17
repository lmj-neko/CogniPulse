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

    if not os.path.isfile(path):
        print(f"错误：文件不存在或不是普通文件：{path}")
        return

    try:
        os.remove(path)
        print(f"文件已删除：{path}")
    except Exception as e:
        print(f"删除文件失败：{e}")

if __name__ == '__main__':
    main()