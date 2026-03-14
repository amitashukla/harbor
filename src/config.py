import os
from dotenv import load_dotenv

# Load from .env file. Store your HF token in the .env file.
load_dotenv()


BASE_MODEL = "Qwen/Qwen2.5-7B-Instruct"
# Other options:
# BASE_MODEL = "meta-llama/Llama-3.2-3B-Instruct"  # gated — requires Meta license approval
# BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"        # ungated, smaller/faster
# BASE_MODEL = "HuggingFaceH4/zephyr-7b-beta"       # ungated

# If you finetune the model or change it in any way, save it to huggingface hub, then set MY_MODEL to your model ID. The model ID is in the format "your-username/your-model-name".
MY_MODEL = "" #"amitashukla/harbor-qwn25-lora"

HF_TOKEN = os.getenv("HF_TOKEN")
