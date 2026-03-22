#!/usr/bin/env python3
"""
AutoResearch Runner — 自動實驗循環腳本
在 Colab / GPU 機器上執行，自動化 train → evaluate → keep/revert 循環。

用法:
  python autoresearch_runner.py --rounds 10 --api-url http://localhost:8000

此腳本必須在 autoresearch/ 目錄內（含 train.py）執行。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# ── 實驗假設列表（每輪依序嘗試） ──────────────────────────
HYPOTHESES = [
    {
        "name": "deeper-model",
        "description": "增加模型深度 n_layer 8→12",
        "patch": {"target": "n_layer", "old": "8", "new": "12"},
    },
    {
        "name": "wider-model",
        "description": "增加模型寬度 n_embd 512→768",
        "patch": {"target": "n_embd", "old": "512", "new": "768"},
    },
    {
        "name": "more-heads",
        "description": "增加注意力頭數 n_head 4→8, n_kv_head 4→8",
        "patch": {"target": "n_head", "old": "4", "new": "8"},
    },
    {
        "name": "larger-batch",
        "description": "增大 batch size TOTAL_BATCH_SIZE ×2",
        "patch": {"target": "TOTAL_BATCH_SIZE", "find_multiply": 2},
    },
    {
        "name": "higher-lr",
        "description": "提高學習率 ×1.5",
        "patch": {"target": "learning_rate", "find_multiply": 1.5},
    },
    {
        "name": "lower-lr",
        "description": "降低學習率 ×0.5",
        "patch": {"target": "learning_rate", "find_multiply": 0.5},
    },
    {
        "name": "longer-warmup",
        "description": "增加 warmup 步數",
        "patch": {"target": "warmup_steps", "find_multiply": 2},
    },
    {
        "name": "window-pattern-SSSS",
        "description": "改變 attention window pattern 為全 sliding",
        "patch": {"target": "window_pattern", "old": "'SSSL'", "new": "'SSSS'"},
    },
    {
        "name": "window-pattern-SLSL",
        "description": "改變 attention window pattern 為交替",
        "patch": {"target": "window_pattern", "old": "'SSSL'", "new": "'SLSL'"},
    },
    {
        "name": "sequence-len-4096",
        "description": "增加序列長度 2048→4096",
        "patch": {"target": "sequence_len", "old": "2048", "new": "4096"},
    },
]

# ── TSV 記錄 ──────────────────────────────────────────────
TSV_HEADER = "name\tval_bpb\ttrain_loss\tsteps\tduration\tkept\tdescription\ttimestamp\n"


def init_results_tsv(path: Path):
    if not path.exists():
        path.write_text(TSV_HEADER)


def append_result(path: Path, result: dict):
    line = (
        f"{result['name']}\t{result.get('val_bpb', '')}\t{result.get('train_loss', '')}\t"
        f"{result.get('steps', '')}\t{result.get('duration_seconds', '')}\t"
        f"{result.get('kept', '')}\t{result.get('description', '')}\t"
        f"{result.get('timestamp', '')}\n"
    )
    with open(path, "a") as f:
        f.write(line)


# ── 訓練 ──────────────────────────────────────────────────
def run_training(timeout_extra: int = 60) -> dict:
    """執行 uv run train.py 並解析結果"""
    print("  ⏳ Training...")
    start = time.time()

    try:
        result = subprocess.run(
            ["uv", "run", "train.py"],
            capture_output=True,
            text=True,
            timeout=600 + timeout_extra,
        )
        log = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return {"error": "Training timed out", "duration_seconds": time.time() - start}

    duration = time.time() - start

    # Parse val_bpb
    bpb_matches = re.findall(r"val(?:_|\s)bpb[:\s]+([\d.]+)", log)
    loss_matches = re.findall(r"train(?:_|\s)loss[:\s]+([\d.]+)", log)
    step_matches = re.findall(r"step[:\s]+(\d+)", log)

    val_bpb = float(bpb_matches[-1]) if bpb_matches else None
    train_loss = float(loss_matches[-1]) if loss_matches else None
    steps = int(step_matches[-1]) if step_matches else None

    if val_bpb is None and result.returncode != 0:
        # Training crashed
        error_lines = [l for l in log.split("\n") if "Error" in l or "error" in l]
        return {
            "error": error_lines[-1] if error_lines else "Training failed",
            "duration_seconds": duration,
        }

    return {
        "val_bpb": val_bpb,
        "train_loss": train_loss,
        "steps": steps,
        "duration_seconds": round(duration, 1),
    }


# ── Git 操作 ──────────────────────────────────────────────
def git_commit(message: str):
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-am", message], check=True)


def git_revert():
    subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True)


# ── Patch train.py ────────────────────────────────────────
def apply_patch(train_path: Path, patch: dict) -> bool:
    """Apply a single-variable patch to train.py"""
    text = train_path.read_text()
    target = patch["target"]

    if "old" in patch and "new" in patch:
        # Simple string replacement
        if patch["old"] not in text:
            print(f"  ⚠️ Could not find '{patch['old']}' in train.py, skipping")
            return False
        text = text.replace(patch["old"], patch["new"], 1)
    elif "find_multiply" in patch:
        # Find a numeric value and multiply it
        pattern = rf"({target}\s*=\s*)([\d.]+)"
        match = re.search(pattern, text)
        if not match:
            print(f"  ⚠️ Could not find '{target} = <number>' in train.py, skipping")
            return False
        old_val = float(match.group(2))
        new_val = old_val * patch["find_multiply"]
        if new_val == int(new_val):
            new_val = int(new_val)
        text = text[:match.start()] + f"{match.group(1)}{new_val}" + text[match.end():]
    else:
        return False

    train_path.write_text(text)
    return True


# ── API 回傳 ──────────────────────────────────────────────
def submit_to_api(api_url: str, result: dict):
    """POST experiment result to MD.Piece API"""
    if not api_url:
        return
    try:
        import requests
        payload = {
            "name": result["name"],
            "val_bpb": result.get("val_bpb"),
            "train_loss": result.get("train_loss"),
            "steps": result.get("steps"),
            "duration_seconds": result.get("duration_seconds"),
            "notes": result.get("description", ""),
            "kept": result.get("kept", False),
        }
        r = requests.post(f"{api_url}/research/", json=payload, timeout=10)
        if r.ok:
            print(f"  📡 Submitted to API: {r.json().get('message')}")
        else:
            print(f"  ⚠️ API error {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"  ⚠️ Could not reach API: {e}")


# ── 主循環 ────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AutoResearch experiment runner")
    parser.add_argument("--rounds", type=int, default=5, help="Number of experiment rounds")
    parser.add_argument("--api-url", type=str, default="", help="MD.Piece API URL (e.g. http://localhost:8000)")
    parser.add_argument("--results-tsv", type=str, default="results.tsv", help="Path to results TSV file")
    args = parser.parse_args()

    train_path = Path("train.py")
    if not train_path.exists():
        print("❌ train.py not found. Run this from the autoresearch directory.")
        sys.exit(1)

    results_path = Path(args.results_tsv)
    init_results_tsv(results_path)

    # ── Step 1: Baseline ──
    print("=" * 60)
    print("🔬 AutoResearch Runner")
    print(f"   Rounds: {args.rounds}")
    print(f"   API: {args.api_url or '(none)'}")
    print("=" * 60)

    print("\n📊 Round 0: Baseline")
    baseline = run_training()

    if "error" in baseline:
        print(f"  ❌ Baseline failed: {baseline['error']}")
        sys.exit(1)

    best_bpb = baseline["val_bpb"]
    print(f"  ✅ Baseline val_bpb: {best_bpb}")

    baseline_result = {
        "name": "baseline",
        "description": "Initial baseline run",
        "kept": True,
        "timestamp": datetime.utcnow().isoformat(),
        **baseline,
    }
    append_result(results_path, baseline_result)
    submit_to_api(args.api_url, baseline_result)

    # ── Step 2: Experiment loop ──
    hypotheses = HYPOTHESES[: args.rounds]

    for i, hyp in enumerate(hypotheses, 1):
        print(f"\n{'='*60}")
        print(f"🧪 Round {i}/{len(hypotheses)}: {hyp['name']}")
        print(f"   Hypothesis: {hyp['description']}")

        # Apply patch
        if not apply_patch(train_path, hyp["patch"]):
            print("  ⏭️ Skipping (patch failed)")
            continue

        # Commit
        git_commit(f"hypothesis: {hyp['description']}")

        # Train
        result = run_training()

        if "error" in result:
            print(f"  ❌ Training failed: {result['error']}")
            kept = False
            git_revert()
        elif result["val_bpb"] is not None and result["val_bpb"] < best_bpb:
            improvement = best_bpb - result["val_bpb"]
            print(f"  ✅ KEPT — val_bpb: {result['val_bpb']} (improved by {improvement:.4f})")
            best_bpb = result["val_bpb"]
            kept = True
        else:
            val = result.get("val_bpb", "N/A")
            print(f"  ↩️ REVERTED — val_bpb: {val} (no improvement over {best_bpb})")
            git_revert()
            kept = False

        exp_result = {
            "name": hyp["name"],
            "description": hyp["description"],
            "kept": kept,
            "timestamp": datetime.utcnow().isoformat(),
            **{k: v for k, v in result.items() if k != "error"},
        }
        append_result(results_path, exp_result)
        submit_to_api(args.api_url, exp_result)

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"🏁 Done! Best val_bpb: {best_bpb}")
    print(f"   Results saved to: {results_path}")
    if args.api_url:
        print(f"   Results submitted to: {args.api_url}/research/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
