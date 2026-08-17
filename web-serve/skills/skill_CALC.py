import sys
import json

def main():
    try:
        argv = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    except:
        argv = {}
    
    expr = argv.get('expr', '1+1')
    # 简单安全过滤
    allowed = set('0123456789+-*/(). ')
    if not all(c in allowed for c in expr):
        print("表达式包含非法字符")
        return
    try:
        result = eval(expr)
        print(f"{expr} = {result}")
    except Exception as e:
        print(f"计算错误: {e}")

if __name__ == '__main__':
    main()