import json
import os

input_file = "id.json"
output_file = "dataset.jsonl"

with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)   # data 是一个列表

with open(output_file, "w", encoding="utf-8") as f:
    for item in data:
        instruction = item.get("instruction", "").strip()
        output = item.get("output", "").strip()
        if not instruction or not output:
            continue
        sample = {
            "messages": [
                {"role": "user", "content": instruction},
                {"role": "assistant", "content": output}
            ]
        }
        f.write(json.dumps(sample, ensure_ascii=False) + "\n")

print(f"✅ 转换完成！生成 {output_file}，共 {len(data)} 条数据")
os.system('pause')