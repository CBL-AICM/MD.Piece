"""Export the trained Layer-3 checkpoint to ONNX for in-browser inference.

Outputs:
  pwa/model/model.onnx         — the model in ONNX format
  pwa/model/scaler.json        — scaler mean/std, feature names, hyperparams
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from ml.model import MDPieceModel


def export(
    ckpt_path: Path = Path("output/mdpiece/checkpoints/best.pt"),
    out_model: Path = Path("pwa/model/model.onnx"),
    out_scaler: Path = Path("pwa/model/scaler.json"),
) -> None:
    state = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    feature_names = state["feature_names"]
    mean = state["scaler_mean"]
    std = state["scaler_std"]
    cfg = state["config"]

    model = MDPieceModel(
        n_features=len(feature_names),
        hidden=cfg["model"]["hidden"],
        n_layers=cfg["model"]["n_layers"],
        dropout=cfg["model"]["dropout"],
    )
    model.load_state_dict(state["model_state"])
    model.eval()

    window = cfg["data"]["window_size"]
    n_feat = len(feature_names)
    dummy = torch.randn(1, window, n_feat, dtype=torch.float32)

    out_model.parent.mkdir(parents=True, exist_ok=True)

    # Use the old torchscript exporter — it's the most ONNX-runtime-web friendly,
    # especially for LSTM ops at opset 17.
    torch.onnx.export(
        model,
        (dummy,),
        str(out_model),
        input_names=["input"],
        output_names=["reg", "cls_logit"],
        dynamic_axes={
            "input": {0: "batch"},
            "reg": {0: "batch"},
            "cls_logit": {0: "batch"},
        },
        opset_version=17,
        dynamo=False,
    )

    # quick verification
    import onnx
    onnx_model = onnx.load(str(out_model))
    onnx.checker.check_model(onnx_model)
    print(f"[onnx] ok — {out_model} ({out_model.stat().st_size / 1024:.1f} KB)")

    scaler = {
        "feature_names": list(feature_names),
        "mean": list(map(float, mean)),
        "std": list(map(float, std)),
        "window_size": int(window),
        "horizon_days": int(cfg["data"]["horizon_days"]),
        "flare_horizon_days": int(cfg["data"]["flare_horizon_days"]),
        "diseases": cfg["data"]["diseases"],
    }
    with out_scaler.open("w", encoding="utf-8") as f:
        json.dump(scaler, f, ensure_ascii=False, indent=2)
    print(f"[onnx] scaler -> {out_scaler} ({out_scaler.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--ckpt", type=Path,
                   default=Path("output/mdpiece/checkpoints/best.pt"))
    p.add_argument("--out-model", type=Path, default=Path("pwa/model/model.onnx"))
    p.add_argument("--out-scaler", type=Path, default=Path("pwa/model/scaler.json"))
    args = p.parse_args()
    export(args.ckpt, args.out_model, args.out_scaler)
