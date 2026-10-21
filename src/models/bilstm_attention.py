from __future__ import annotations

import torch
import torch.nn as nn

from src.utils import Config


class BiLSTMAttention(nn.Module):
    """Simple Bi-LSTM with additive attention for sequence anomaly scoring."""

    def __init__(self, config: Config, vocab_size: int):
        super().__init__()
        embed_dim = int(config.get("models.bilstm.input_size", 128))
        hidden_size = int(config.get("models.bilstm.hidden_size", 128))
        num_layers = int(config.get("models.bilstm.num_layers", 2))
        dropout = float(config.get("models.bilstm.dropout", 0.3))
        attention_size = int(config.get("models.bilstm.attention_size", 64))
        bidirectional = bool(config.get("models.bilstm.bidirectional", True))

        self.embedding = nn.Embedding(max(2, int(vocab_size)), embed_dim, padding_idx=0)
        self.encoder = nn.LSTM(
            input_size=embed_dim,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=bidirectional,
        )
        out_dim = hidden_size * (2 if bidirectional else 1)
        self.attn_proj = nn.Sequential(
            nn.Linear(out_dim, attention_size),
            nn.Tanh(),
            nn.Linear(attention_size, 1),
        )
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(out_dim, 1)

    def forward(self, x: torch.Tensor):
        emb = self.embedding(x)
        out, _ = self.encoder(emb)
        attn_logits = self.attn_proj(out).squeeze(-1)
        attn = torch.softmax(attn_logits, dim=1)
        context = torch.sum(out * attn.unsqueeze(-1), dim=1)
        logits = self.classifier(self.dropout(context))
        return logits, attn
