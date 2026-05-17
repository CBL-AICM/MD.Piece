"""Layer-3 training loop with early stopping, checkpointing and model card."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader

from ml.dataset import DataBundle, WindowDataset, build_databundle
from ml.evaluate import classification_report, predict, regression_report
from ml.model import MDPieceModel

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def _device(setting: str) -> torch.device:
    if setting == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(setting)


def _seed_all(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _run_epoch(
    model, loader, *, train: bool, optimizer, loss_w, device,
) -> dict[str, float]:
    """Single train or eval epoch. Returns mean losses."""
    model.train(train)
    mse_fn = nn.MSELoss()
    bce_fn = nn.BCEWithLogitsLoss()
    tot, tot_reg, tot_cls = 0.0, 0.0, 0.0
    n = 0
    for X, yr, yc in loader:
        X, yr, yc = X.to(device), yr.to(device), yc.to(device)
        with torch.set_grad_enabled(train):
            reg_pred, cls_pred = model(X)
            loss_reg = mse_fn(reg_pred, yr)
            loss_cls = bce_fn(cls_pred, yc)
            loss = loss_w["activity_mse"] * loss_reg + loss_w["flare_bce"] * loss_cls
        if train:
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        bs = X.size(0)
        n += bs
        tot += loss.item() * bs
        tot_reg += loss_reg.item() * bs
        tot_cls += loss_cls.item() * bs
    return {"loss": tot / n, "reg": tot_reg / n, "cls": tot_cls / n}


def train_from_config(cfg_path: Path = CONFIG_PATH) -> dict:
    """Top-level entrypoint. Returns final test metrics dict."""
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    _seed_all(cfg["train"]["seed"])
    device = _device(cfg["train"]["device"])

    paths = {k: Path(v) for k, v in cfg["paths"].items()}
    for p in [paths["data_cache"], paths["ckpt_dir"], paths["log_dir"]]:
        p.mkdir(parents=True, exist_ok=True)

    print(f"[train] device={device}")
    t0 = time.time()

    bundle: DataBundle = build_databundle(
        diseases=cfg["data"]["diseases"],
        n_patients_per_disease=cfg["data"]["n_patients_per_disease"],
        sim_days=cfg["data"]["sim_days"],
        window_size=cfg["data"]["window_size"],
        horizon_days=cfg["data"]["horizon_days"],
        flare_horizon_days=cfg["data"]["flare_horizon_days"],
        base_seed=cfg["data"]["base_seed"],
        split_ratios=(
            cfg["split"]["train_ratio"],
            cfg["split"]["val_ratio"],
            cfg["split"]["test_ratio"],
        ),
        split_seed=cfg["split"]["split_seed"],
        cache_dir=paths["data_cache"],
    )
    print(f"[train] data ready in {time.time() - t0:.1f}s | "
          f"train={len(bundle.train.X)} val={len(bundle.val.X)} test={len(bundle.test.X)} "
          f"| n_features={len(bundle.feature_names)}")
    print(f"[train] flare positive rate: train={bundle.train.y_cls.mean():.3f} "
          f"val={bundle.val.y_cls.mean():.3f} test={bundle.test.y_cls.mean():.3f}")

    bs = cfg["train"]["batch_size"]
    train_loader = DataLoader(WindowDataset(bundle.train), batch_size=bs, shuffle=True)
    val_loader = DataLoader(WindowDataset(bundle.val), batch_size=bs)
    test_loader = DataLoader(WindowDataset(bundle.test), batch_size=bs)

    model = MDPieceModel(
        n_features=len(bundle.feature_names),
        hidden=cfg["model"]["hidden"],
        n_layers=cfg["model"]["n_layers"],
        dropout=cfg["model"]["dropout"],
    ).to(device)
    print(f"[train] model params = {model.count_params():,}")

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=cfg["train"]["lr"],
        weight_decay=cfg["train"]["weight_decay"],
    )

    best_val = float("inf")
    best_epoch = -1
    patience = cfg["train"]["early_stop_patience"]
    bad_epochs = 0
    history = []

    ckpt_path = paths["ckpt_dir"] / "best.pt"

    for epoch in range(1, cfg["train"]["epochs"] + 1):
        tr = _run_epoch(model, train_loader, train=True, optimizer=optimizer,
                        loss_w=cfg["train"]["loss_weights"], device=device)
        va = _run_epoch(model, val_loader, train=False, optimizer=optimizer,
                        loss_w=cfg["train"]["loss_weights"], device=device)
        history.append({"epoch": epoch, "train": tr, "val": va})
        if va["loss"] < best_val - 1e-4:
            best_val = va["loss"]
            best_epoch = epoch
            bad_epochs = 0
            torch.save({"model_state": model.state_dict(),
                        "feature_names": bundle.feature_names,
                        "scaler_mean": bundle.scaler_mean.tolist(),
                        "scaler_std": bundle.scaler_std.tolist(),
                        "config": cfg}, ckpt_path)
        else:
            bad_epochs += 1

        print(f"  epoch {epoch:3d} | tr loss={tr['loss']:.4f} "
              f"(reg={tr['reg']:.3f} cls={tr['cls']:.3f}) | "
              f"va loss={va['loss']:.4f} (reg={va['reg']:.3f} cls={va['cls']:.3f}) "
              f"{'*' if epoch == best_epoch else ''}")

        if bad_epochs >= patience:
            print(f"[train] early stop at epoch {epoch} (best={best_epoch})")
            break

    # load best
    state = torch.load(ckpt_path, map_location=device, weights_only=False)
    model.load_state_dict(state["model_state"])

    test_pred = predict(model, test_loader, device)
    reg = regression_report(test_pred["yr_true"], test_pred["yr_pred"])
    cls = classification_report(test_pred["yc_true"], test_pred["yc_prob"])
    train_pred = predict(model, train_loader, device)
    reg_tr = regression_report(train_pred["yr_true"], train_pred["yr_pred"])

    overfit_gap_mae = reg_tr["mae"]["point"] - reg["mae"]["point"]
    if abs(overfit_gap_mae) > 0.15 * max(reg["mae"]["point"], 1e-6) * 100:
        print(f"[warn] train/test MAE differ by >15%: "
              f"train={reg_tr['mae']['point']:.3f} test={reg['mae']['point']:.3f}")

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "device": str(device),
        "n_train": int(len(bundle.train.X)),
        "n_val": int(len(bundle.val.X)),
        "n_test": int(len(bundle.test.X)),
        "best_epoch": best_epoch,
        "best_val_loss": float(best_val),
        "test_regression": reg,
        "test_classification": cls,
        "train_regression": reg_tr,
        "history": history,
        "model_params": model.count_params(),
        "n_features": len(bundle.feature_names),
        "feature_names": bundle.feature_names,
        "diseases": cfg["data"]["diseases"],
    }

    log_path = paths["log_dir"] / f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with log_path.open("w") as f:
        json.dump(report, f, indent=2)
    print(f"[train] report -> {log_path}")

    _write_model_card(report, cfg, paths["model_card"], ckpt_path)
    return report


def _write_model_card(report: dict, cfg: dict, path: Path, ckpt_path: Path) -> None:
    """Emit a human-readable model card alongside the JSON log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    reg = report["test_regression"]
    cls = report["test_classification"]
    md = f"""# MD. Piece — Layer-3 Model Card

**Generated**: {report["generated_at"]}
**Checkpoint**: `{ckpt_path}`

## Intended use
Predict next-day immune activity (regression) and next-{cfg['data']['flare_horizon_days']}-day flare risk
(binary classification) for chronic immune-mediated diseases, using the past
{cfg['data']['window_size']} days of self-monitored signals.

**NOT FOR CLINICAL USE.** Trained entirely on synthetic data from the
MD. Piece Layer-2 simulator. Intended for science-fair research,
methodological demonstration, and educational discussion only.

## Training data
- Diseases: {report["diseases"]}
- Cohort size per disease: {cfg["data"]["n_patients_per_disease"]} virtual patients
- Simulated horizon: {cfg["data"]["sim_days"]} days
- Window size (input): {cfg["data"]["window_size"]} days
- Prediction horizon: {cfg["data"]["horizon_days"]} day (activity), {cfg["data"]["flare_horizon_days"]} days (flare)
- Split: {cfg["split"]["train_ratio"]}/{cfg["split"]["val_ratio"]}/{cfg["split"]["test_ratio"]} **by patient** (no leakage)
- Final sample counts: train={report["n_train"]}, val={report["n_val"]}, test={report["n_test"]}

## Architecture
- Type: {cfg["model"]["type"]}
- Hidden: {cfg["model"]["hidden"]}, Layers: {cfg["model"]["n_layers"]}, Dropout: {cfg["model"]["dropout"]}
- Parameters: {report["model_params"]:,}
- Input features ({report["n_features"]}): see JSON log

## Training
- Optimizer: AdamW (lr={cfg["train"]["lr"]}, weight_decay={cfg["train"]["weight_decay"]})
- Batch size: {cfg["train"]["batch_size"]}
- Loss weights: activity MSE={cfg["train"]["loss_weights"]["activity_mse"]}, flare BCE={cfg["train"]["loss_weights"]["flare_bce"]}
- Early stopping patience: {cfg["train"]["early_stop_patience"]} epochs
- Best epoch: {report["best_epoch"]} (val loss {report["best_val_loss"]:.4f})
- Random seed: {cfg["train"]["seed"]}

## Test-set performance (95% CI from bootstrap)

### Activity regression (immune activity score)
- MAE  = {reg["mae"]["point"]:.3f}  CI95=[{reg["mae"]["ci95"][0]:.3f}, {reg["mae"]["ci95"][1]:.3f}]
- RMSE = {reg["rmse"]["point"]:.3f} CI95=[{reg["rmse"]["ci95"][0]:.3f}, {reg["rmse"]["ci95"][1]:.3f}]
- R^2  = {reg["r2"]["point"]:.3f}   CI95=[{reg["r2"]["ci95"][0]:.3f}, {reg["r2"]["ci95"][1]:.3f}]
- Baseline (mean predictor) MAE: {reg["baseline_mean_predictor_mae"]:.3f}

### Flare classification (any flare in next {cfg["data"]["flare_horizon_days"]} days)
"""
    if cls.get("auroc") is None:
        md += f"- Skipped (single class in test set, positive rate={cls.get('positive_rate', 0):.3f})\n"
    else:
        md += (
            f"- AUROC = {cls['auroc']['point']:.3f} CI95=[{cls['auroc']['ci95'][0]:.3f}, {cls['auroc']['ci95'][1]:.3f}]\n"
            f"- AUPRC = {cls['auprc']['point']:.3f} CI95=[{cls['auprc']['ci95'][0]:.3f}, {cls['auprc']['ci95'][1]:.3f}]\n"
            f"- F1@0.5 = {cls['f1@0.5']['point']:.3f} CI95=[{cls['f1@0.5']['ci95'][0]:.3f}, {cls['f1@0.5']['ci95'][1]:.3f}]\n"
            f"- Positive class rate: {cls['positive_rate']:.3f}\n"
        )

    md += """
## Known limitations
1. **Synthetic data only** — no real patient signals; biomarker formulas are
   stylized and not clinically validated.
2. **No external validation** — generalization to real-world wearable data is unknown.
3. **Disease-agnostic but small set** — three reference diseases only; behavior on
   unseen YAML profiles is untested.
4. **Treatment effects are simplified** — single-dose exponential decay rather than
   real pharmacokinetics.
5. **Not for medical decision-making**. See README disclaimer.

## References
- Lillie EO et al. (2011) *Personalized Medicine* — N-of-1 trials.
- Zucker DR et al. (1997) *Stat Med* — Bayesian hierarchical N-of-1.
- Walonoski J et al. (2018) *JAMIA* — Synthea synthetic patients.
- Topol EJ (2019) *Nature Medicine* — Digital twins.
- FDA guidance (2023) — In silico clinical trials.
"""
    with path.open("w", encoding="utf-8") as f:
        f.write(md)
    print(f"[train] model card -> {path}")


if __name__ == "__main__":
    train_from_config()
