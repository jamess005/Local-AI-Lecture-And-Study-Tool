import os
import traceback
import datetime

LOG = open("/tmp/load_test.log", "w", buffering=1)

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG.write(line + "\n")
    LOG.flush()

log("START")
os.environ.setdefault("HIP_VISIBLE_DEVICES", "0")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

log("importing torch")
import torch
log(f"  cuda available: {torch.cuda.is_available()}")
log(f"  device count: {torch.cuda.device_count()}")
for i in range(torch.cuda.device_count()):
    log(f"  device {i}: {torch.cuda.get_device_name(i)}")

log("importing bitsandbytes")
import bitsandbytes as bnb
log(f"  bnb version: {bnb.__version__}")

log("importing transformers")
from transformers import AutoModelForCausalLM, AutoTokenizer

# The AWQ checkpoint is quantized already, so no BnB config on top.
MODEL = "/home/james/ml-proj/models/qwen3-14b-awq"

log("loading tokenizer")
tok = AutoTokenizer.from_pretrained(MODEL, use_fast=True)
log("  tokenizer OK")

log("loading model (this takes 60-90 s) ...")
try:
    mdl = AutoModelForCausalLM.from_pretrained(
        MODEL,
        device_map="auto",
        max_memory={0: "15GiB", "cpu": "20GiB"},
        low_cpu_mem_usage=True,
    )
    log("  model loaded OK")
    mdl.eval()
    log("SUCCESS")
except Exception as e:
    log(f"EXCEPTION: {e}")
    traceback.print_exc()
    LOG.write(traceback.format_exc())
finally:
    LOG.close()
