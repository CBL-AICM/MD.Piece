"""LSTM with self-attention pooling + two heads (regression, classification)."""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class AttentionPool(nn.Module):
    """Learnable additive attention over the time dimension."""

    def __init__(self, hidden: int):
        super().__init__()
        self.score = nn.Linear(hidden, 1)

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        # h: (B, T, H)
        w = self.score(h)                          # (B, T, 1)
        a = F.softmax(w, dim=1)                    # (B, T, 1)
        return (a * h).sum(dim=1)                  # (B, H)


class MDPieceModel(nn.Module):
    """LSTM + attention with regression and classification heads."""

    def __init__(
        self,
        n_features: int,
        hidden: int = 64,
        n_layers: int = 2,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden,
            num_layers=n_layers,
            dropout=dropout if n_layers > 1 else 0.0,
            batch_first=True,
        )
        self.pool = AttentionPool(hidden)
        self.dropout = nn.Dropout(dropout)
        self.head_reg = nn.Linear(hidden, 1)
        self.head_cls = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """x: (B, T, F) → (reg, cls_logit) both (B,)."""
        h, _ = self.lstm(x)
        z = self.pool(h)
        z = self.dropout(z)
        reg = self.head_reg(z).squeeze(-1)
        cls = self.head_cls(z).squeeze(-1)
        return reg, cls

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
