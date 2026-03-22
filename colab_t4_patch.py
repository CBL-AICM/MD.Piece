"""
T4 Compatibility Patch for karpathy/autoresearch train.py

Tesla T4 (Turing, sm_75) 不支援：
  1. Flash Attention 3（需要 Ampere sm_80+）
  2. 原生 bfloat16 計算

此腳本在 clone 後的 autoresearch/train.py 上打 patch，使其能在 T4 上執行。
用法：python colab_t4_patch.py （在 autoresearch/ 目錄內執行）
"""
import re
import subprocess
import sys
from pathlib import Path


def get_gpu_capability():
    """偵測 GPU compute capability"""
    try:
        import torch
        if torch.cuda.is_available():
            cap = torch.cuda.get_device_capability(0)
            return cap[0] * 10 + cap[1]  # e.g. 75 for T4, 80 for A100
    except Exception:
        pass
    return 0


def patch_train_py(train_path: Path):
    """Patch train.py to support T4 GPUs"""
    text = train_path.read_text()
    original = text

    # --- Patch 1: Add fallback attention import block ---
    # Replace the flash_attn3 import with a capability-aware import
    fa3_import_pattern = r'(import kernels\nfa3 = kernels\.get_kernel\("flash_attn3"\))'
    fa3_replacement = """import torch
_gpu_cap = torch.cuda.get_device_capability(0) if torch.cuda.is_available() else (0, 0)
_is_ampere_plus = _gpu_cap[0] >= 8

if _is_ampere_plus:
    import kernels
    fa3 = kernels.get_kernel("flash_attn3")
else:
    fa3 = None  # Will use SDPA fallback"""

    if 'import kernels' in text and 'fa3 = kernels.get_kernel' in text:
        # Handle multi-line import
        text = re.sub(
            r'import kernels\s*\nfa3\s*=\s*kernels\.get_kernel\(["\']flash_attn3["\']\)',
            fa3_replacement,
            text,
        )

    # --- Patch 2: Replace fa3.flash_attn_func call with fallback ---
    # The attention forward method uses: y = fa3.flash_attn_func(q, k, v, causal=True, window_size=window_size)
    fa3_call_pattern = r'y = fa3\.flash_attn_func\(q, k, v, causal=True, window_size=window_size\)'
    sdpa_fallback = """if fa3 is not None:
            y = fa3.flash_attn_func(q, k, v, causal=True, window_size=window_size)
        else:
            # SDPA fallback for T4 / non-Ampere GPUs
            y = torch.nn.functional.scaled_dot_product_attention(
                q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2),
                is_causal=True,
            ).transpose(1, 2)"""

    text = re.sub(fa3_call_pattern, sdpa_fallback, text)

    # --- Patch 3: bfloat16 → float16 for T4 ---
    # T4 doesn't support bf16 natively; torch.compile will warn/fail
    if not _check_ampere():
        text = text.replace('torch.bfloat16', 'torch.float16')
        # Also handle string references in autocast
        text = re.sub(
            r"autocast\(device_type=['\"]cuda['\"],\s*dtype=torch\.bfloat16\)",
            "autocast(device_type='cuda', dtype=torch.float16)",
            text,
        )

    if text == original:
        print("[t4_patch] No changes needed (already patched or Ampere+ GPU)")
        return False

    train_path.write_text(text)
    print("[t4_patch] Patched train.py for T4 compatibility:")
    print("  - Flash Attention 3 → SDPA fallback")
    if not _check_ampere():
        print("  - bfloat16 → float16")
    return True


def _check_ampere():
    cap = get_gpu_capability()
    return cap >= 80


def main():
    train_path = Path("train.py")
    if not train_path.exists():
        # Try from parent
        train_path = Path("autoresearch/train.py")
    if not train_path.exists():
        print("[t4_patch] ERROR: train.py not found. Run this from the autoresearch directory.")
        sys.exit(1)

    cap = get_gpu_capability()
    print(f"[t4_patch] GPU compute capability: {cap}")

    if cap >= 80:
        print("[t4_patch] Ampere+ GPU detected — no patch needed, Flash Attention 3 is supported.")
        return

    print(f"[t4_patch] Pre-Ampere GPU (sm_{cap}) detected — applying T4 compatibility patch...")
    patched = patch_train_py(train_path)
    if patched:
        print("[t4_patch] Done! You can now run: uv run train.py")


if __name__ == "__main__":
    main()
