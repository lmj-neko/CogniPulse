import sys
import json
import subprocess

def main():
    try:
        argv = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    except:
        argv = {}

    command = argv.get('command')
    if not command:
        print("错误：缺少 command 参数")
        return

    try:
        # 使用 shell=True 执行命令（注意安全风险）
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        print(output if output else "(无输出)")
    except Exception as e:
        print(f"执行命令异常：{e}")

if __name__ == '__main__':
    main()