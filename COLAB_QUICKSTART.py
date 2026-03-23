# === MD.Piece Autoresearch — Colab One-Click ===
# 使用方式：
# 1. 開 https://colab.research.google.com
# 2. Runtime → Change runtime type → T4 GPU
# 3. 把這整段貼到第一個 cell，按 Shift+Enter 執行
# ================================================

# --- Step 1: 確認 GPU ---
!nvidia-smi
import torch
if torch.cuda.is_available():
    name = torch.cuda.get_device_name(0)
    cap = torch.cuda.get_device_capability(0)
    print(f"\n✅ GPU: {name} (compute capability: {cap[0]}.{cap[1]})")
else:
    raise RuntimeError("❌ 未偵測到 GPU！請到 Runtime → Change runtime type → 選 GPU")

# --- Step 2: 安裝 uv ---
!curl -LsSf https://astral.sh/uv/install.sh | sh
import os
os.environ['PATH'] = os.path.expanduser('~/.local/bin') + ':' + os.environ['PATH']

# --- Step 3: Clone autoresearch ---
!git clone https://github.com/karpathy/autoresearch.git
os.chdir('autoresearch')

# --- Step 4: 安裝依賴 ---
!uv sync

# --- Step 5: T4 Patch (自動偵測，Ampere+ 不需要) ---
import re
from pathlib import Path

train_path = Path("train.py")
if not train_path.exists():
    train_path = Path("autoresearch/train.py")

if train_path.exists():
    cap = torch.cuda.get_device_capability(0)
    if cap[0] < 8:
        print(f"[t4_patch] Pre-Ampere GPU (sm_{cap[0]}{cap[1]}) — applying T4 patch...")
        text = train_path.read_text()
        original = text

        fa3_replacement = """import torch
_gpu_cap = torch.cuda.get_device_capability(0) if torch.cuda.is_available() else (0, 0)
_is_ampere_plus = _gpu_cap[0] >= 8

if _is_ampere_plus:
    import kernels
    fa3 = kernels.get_kernel("flash_attn3")
else:
    fa3 = None  # Will use SDPA fallback"""

        text = re.sub(
            r'import kernels\s*\nfa3\s*=\s*kernels\.get_kernel\(["\']flash_attn3["\']\)',
            fa3_replacement, text
        )

        text = re.sub(
            r'y = fa3\.flash_attn_func\(q, k, v, causal=True, window_size=window_size\)',
            """if fa3 is not None:
            y = fa3.flash_attn_func(q, k, v, causal=True, window_size=window_size)
        else:
            y = torch.nn.functional.scaled_dot_product_attention(
                q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2),
                is_causal=True,
            ).transpose(1, 2)""", text
        )

        text = text.replace('torch.bfloat16', 'torch.float16')
        text = re.sub(
            r"autocast\(device_type=['\"]cuda['\"],\s*dtype=torch\.bfloat16\)",
            "autocast(device_type='cuda', dtype=torch.float16)", text
        )

        if text != original:
            train_path.write_text(text)
            print("[t4_patch] ✅ Done! Flash Attn 3 → SDPA, bf16 → fp16")
        else:
            print("[t4_patch] No changes needed")
    else:
        print(f"[t4_patch] Ampere+ GPU — no patch needed")

# --- Step 6: 準備資料 ---
!uv run prepare.py --num-shards 10

# --- Step 7: 訓練 ---
!uv run train.py 2>&1 | tee /tmp/run.log

log = open("/tmp/run.log").read()
bpb_match = re.findall(r"val_bpb[:\s]+([\d.]+)", log)
loss_match = re.findall(r"train_loss[:\s]+([\d.]+)", log)
step_match = re.findall(r"step[:\s]+(\d+)", log)

val_bpb = float(bpb_match[-1]) if bpb_match else None
train_loss = float(loss_match[-1]) if loss_match else None
steps = int(step_match[-1]) if step_match else None

print(f"\n{'='*40}")
print(f"val_bpb:    {val_bpb}")
print(f"train_loss: {train_loss}")
print(f"steps:      {steps}")
print(f"{'='*40}")
