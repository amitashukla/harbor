import sys
import os

# Add project root to path so we can import from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import load_dataset
from src.config import BASE_MODEL, HF_TOKEN

# --- Configuration ---
OUTPUT_DIR = "./harbor-lora"
# Set this to your HF username/org to push the adapter after training.
# Example: "your-username/harbor-smollm3-lora"
HF_REPO_ID = "amitashukla/harbor-smollm3-lora"

# --- Load base model with 4-bit QLoRA ---
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL,
    max_seq_length=4096,
    load_in_4bit=True,
)

# --- Attach LoRA adapters ---
model = FastLanguageModel.get_peft_model(
    model,
    r=16,                        # LoRA rank — 16 is a good starting point for persona
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing=True,
)

# --- Load your dataset ---
data_path = os.path.join(os.path.dirname(__file__), "examples.jsonl")
dataset = load_dataset("json", data_files=data_path, split="train")

# --- Train/validation split (85/15) ---
split = dataset.train_test_split(test_size=0.15, seed=42)
train_dataset = split["train"]
eval_dataset = split["test"]

# --- Format using the model's native chat template ---
ROLE_MAP = {"human": "user", "gpt": "assistant"}

def format_conversation(example):
    messages = [
        {"role": ROLE_MAP[turn["from"]], "content": turn["value"]}
        for turn in example["conversations"]
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False)
    return {"text": text}

train_dataset = train_dataset.map(format_conversation)
eval_dataset = eval_dataset.map(format_conversation)

# --- Trainer ---
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    dataset_text_field="text",
    max_seq_length=4096,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=10,
        num_train_epochs=3,        # 3 epochs is usually enough for persona
        learning_rate=2e-4,
        fp16=True,
        logging_steps=10,
        eval_strategy="epoch",
        output_dir=OUTPUT_DIR,
        save_strategy="epoch",
    ),
)

trainer.train()

# --- Push finetuned adapter to Hugging Face Hub ---
if HF_REPO_ID:
    print(f"Pushing adapter to Hugging Face Hub: {HF_REPO_ID}")
    model.push_to_hub(HF_REPO_ID, token=HF_TOKEN)
    tokenizer.push_to_hub(HF_REPO_ID, token=HF_TOKEN)
    print(f"Done! Set MY_MODEL = \"{HF_REPO_ID}\" in src/config.py to use it.")
else:
    print("HF_REPO_ID is not set. Skipping push to Hub.")
    print("To push later, set HF_REPO_ID at the top of this script and re-run,")
    print(f"or manually upload from: {OUTPUT_DIR}")
