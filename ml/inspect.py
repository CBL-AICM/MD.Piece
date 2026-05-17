"""Inspect what the trained model says about a few sample patients.

Usage:
    PYTHONPATH=. python -m ml.inspect                       # 3 diseases × 3 patients
    PYTHONPATH=. python -m ml.inspect --disease asthma --n 5
    PYTHONPATH=. python -m ml.inspect --seed 999 --days 120 --save report.md

Prints to terminal AND optionally writes the same content as a markdown report.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from md_piece.disease_loader import list_diseases, load_disease
from md_piece.patient import simulate_patient

from ml.insights import generate_insight
from ml.predict import load_checkpoint, predict_from_patient


# ANSI colours (no-op if not a TTY)
class C:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"


def _hr(char="─", width=72) -> str:
    return char * width


def _format_one(patient, ins) -> tuple[str, str]:
    """Return (coloured_terminal_text, plain_markdown_text)."""
    days = [p["day"] for p in ins.predictions]
    n_show = min(10, len(days))

    # build first-10-rows table
    header = f"{'day':>4s} {'act_pred':>9s} {'act_true':>9s} {'flare_p':>8s} {'flare_t':>8s}"
    rows = []
    for p in ins.predictions[:n_show]:
        rows.append(
            f"{p['day']:4d} {p['activity_pred']:9.3f} {p['activity_true']:9.3f} "
            f"{p['flare_prob']:8.3f} {p['flare_true']:8d}"
        )
    table = "\n".join([header] + rows)

    # error metrics summary line
    mae = ins.mae
    rec = (
        f"{ins.flare_recall * 100:.0f}%"
        if ins.flare_recall is not None else "—"
    )
    prec = (
        f"{ins.flare_precision * 100:.0f}%"
        if ins.flare_precision is not None else "—"
    )
    summary = f"MAE={mae:.3f} | flare 召回={rec} 準確={prec}"

    # terminal version (with colours)
    title = (
        f"{C.BOLD}{C.BLUE}━━ {patient.patient_id} "
        f"({patient.disease_id}, {patient.age}y {patient.sex}) ━━{C.END}"
    )
    term = "\n".join([
        title,
        f"{C.YELLOW}📊 預測 (首 {n_show} 個窗口){C.END}",
        f"{C.DIM}{table}{C.END}",
        f"{C.GREEN}📈 {summary}{C.END}",
        f"{C.BOLD}🤖 AI 心得{C.END}",
        ins.insight_zh,
        _hr(),
    ])

    # markdown version (no ANSI)
    md = "\n".join([
        f"## {patient.patient_id} ({patient.disease_id}, {patient.age}y {patient.sex})",
        "",
        f"**摘要**：{summary}",
        "",
        "**預測（首 10 個窗口）**：",
        "",
        "```",
        table,
        "```",
        "",
        "**🤖 AI 心得**：",
        "",
        ins.insight_zh.replace("\n", "  \n"),
        "",
    ])
    return term, md


def run(
    diseases: list[str] | None,
    n_per_disease: int,
    sim_days: int,
    base_seed: int,
    ckpt: Path,
    save: Path | None,
) -> None:
    if not ckpt.exists():
        raise FileNotFoundError(
            f"checkpoint missing — run `python -m ml.train` first.\n  expected: {ckpt}"
        )
    print(f"{C.BOLD}MD. Piece — model inspection{C.END}")
    print(f"  checkpoint: {ckpt}")
    load_checkpoint(ckpt)  # warm-load to fail fast if mismatched
    diseases = diseases or list_diseases()

    md_chunks: list[str] = [f"# MD. Piece Model Inspection Report\n\nCheckpoint: `{ckpt}`\n"]

    for did in diseases:
        cfg = load_disease(did)
        print(_hr("="))
        print(f"{C.BOLD}{C.BLUE}■ {cfg.name} ({did}) — {n_per_disease} 位患者{C.END}")
        md_chunks.append(f"\n# {cfg.name} (`{did}`)\n")
        for i in range(n_per_disease):
            seed = base_seed + i * 1000
            pid = f"{cfg.short}_{seed:06d}"
            patient = simulate_patient(pid, cfg, sim_days, seed=seed)
            try:
                pred = predict_from_patient(patient, ckpt)
            except ValueError as e:
                print(f"{C.RED}skip {pid}: {e}{C.END}")
                continue
            ins = generate_insight(patient, pred)
            term, md = _format_one(patient, ins)
            print(term)
            md_chunks.append(md)

    if save is not None:
        save.parent.mkdir(parents=True, exist_ok=True)
        save.write_text("\n".join(md_chunks), encoding="utf-8")
        print(f"{C.GREEN}✅ report -> {save}{C.END}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--disease", action="append",
                   help="repeat for multiple; default = all three")
    p.add_argument("--n", type=int, default=3, help="patients per disease")
    p.add_argument("--days", type=int, default=120, help="simulation days")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--ckpt", type=Path,
                   default=Path("output/mdpiece/checkpoints/best.pt"))
    p.add_argument("--save", type=Path,
                   help="also write a markdown report to this path")
    args = p.parse_args()
    run(args.disease, args.n, args.days, args.seed, args.ckpt, args.save)
