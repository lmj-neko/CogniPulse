import torch
import json
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model
from datasets import Dataset

model_path = "./base_model"
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=torch.float32,
    device_map="cpu",
)
tokenizer = AutoTokenizer.from_pretrained(model_path)
tokenizer.pad_token = tokenizer.eos_token

lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

def load_and_prepare_dataset(jsonl_path):
    data = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line.strip())
            messages = item["messages"]
            # 注意：这里的 messages 已经包含了 assistant 回答中的 <|im_end|>
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
            )
            # apply_chat_template 会在末尾加上 <|im_end|>，但我们在 output 中已包含，避免重复添加。
            # 为了保险，我们移除 apply_chat_template 自动添加的末尾 eos？不，让它保留。
            # 实际上，apply_chat_template 会为 assistant 消息添加 <|im_end|>，所以如果 output 中已有，会导致双 eos，但这不是问题，模型会学到在第一个 eos 停止。
            data.append({"text": text})
    return Dataset.from_list(data)

train_dataset = load_and_prepare_dataset("dataset.jsonl")
eval_dataset = load_and_prepare_dataset("validation.jsonl")
print(f"训练集: {len(train_dataset)} 条, 验证集: {len(eval_dataset)} 条")

def tokenize_function(examples):
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=128,          # 短输出，128 足够
        padding=False,
    )

tokenized_train = train_dataset.map(tokenize_function, remove_columns=["text"])
tokenized_eval = eval_dataset.map(tokenize_function, remove_columns=["text"])

data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer,
    mlm=False,
)

training_args = TrainingArguments(
    output_dir="./lora_output",
    per_device_train_batch_size=2,
    gradient_accumulation_steps=2,
    num_train_epochs=3,
    learning_rate=2e-4,
    logging_steps=5,
    save_steps=50,
    report_to="none",
    save_total_limit=2,
    fp16=False,
    bf16=False,
    dataloader_pin_memory=False,
    gradient_checkpointing=False,
    max_grad_norm=1.0,
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
    greater_is_better=False,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_train,
    eval_dataset=tokenized_eval,
    data_collator=data_collator,
)

print("开始训练... 固定3轮")
trainer.train()

model.save_pretrained("./lora_adapter")
tokenizer.save_pretrained("./lora_adapter")
print("✅ 训练完成！")