from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

base_model_path = "./base_model"
lora_path = "./lora_adapter"

print("正在加载基础模型...")
model = AutoModelForCausalLM.from_pretrained(base_model_path, torch_dtype=torch.bfloat16)
tokenizer = AutoTokenizer.from_pretrained(base_model_path)

print("正在加载 LoRA 适配器并合并...")
lora_model = PeftModel.from_pretrained(model, lora_path)
merged_model = lora_model.merge_and_unload()

merged_path = "./merged_model"
print(f"保存合并后的模型到 {merged_path} ...")
merged_model.save_pretrained(merged_path)
tokenizer.save_pretrained(merged_path)

print("✅ 合并完成！")