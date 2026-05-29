# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

Main CLI entry point is `main.py`.

- **Start Frontend Dashboard**: `python main.py --frontend` (or `streamlit run frontend/app.py`)
- **Run Full Pipeline**: `python main.py --all --train-mode all --with-rag --rag-force`
- **Initialize/Download Datasets**: `python main.py --download`
- **Parse Logs (Drain3)**: `python main.py --parse`
- **Extract Features**: `python main.py --extract`
- **Train Multi-View Models**: `python main.py --train --train-mode all`
- **Build RAG Index**: `python main.py --build-rag --rag-force`
- **Evaluate All Views**: `python main.py --evaluate-views --eval-datasets harrison,santos,fox`
- **Syntax Check**: `python -m py_compile <file_path>` or `python -m compileall src/`

## Code Architecture

The **Security Log Analysis Assistant** is structured as a multi-view fusion system for log anomaly detection.

### Core Pipeline
1.  **Ingestion & Parsing** (`src/data_processing/`): Uses Drain3 to convert raw log lines into template IDs and parameter variables.
2.  **Multi-View Feature Extraction** (`src/feature_extraction/`):
    - **Statistical**: Frequency and distribution features (Isolation Forest).
    - **Temporal**: Log sequence patterns (Bi-LSTM + Attention).
    - **Semantic**: Log text distillation and hash-based representation.
3.  **Fusion Layer** (`src/fusion/`): An XGBoost classifier that integrates scores from all views into a final risk assessment.
4.  **Enrichment** (`src/rag/`): RAG retrieves similar historical security cases (FAISS + Sentence-Transformers), and an AI Judge (LLM) generates Chinese investigation reports.
5.  **Interface** (`frontend/`): A Streamlit-based dashboard for interactive analysis, visualization, and incident triage.

### Key Components
- `src/models/`: Implementation of sequence models (Bi-LSTM, DeepLog, GRU).
- `src/utils/`: Global configuration management via `config.yaml` and logging.
- `scripts/`: Automated experiment reruns and paper asset (table/figure) generation.
- `configs/config.yaml`: The central configuration for all pipeline parameters.

## Guidelines
- **Modifications**: Record every meaningful repo change in `FUNCTION_UPDATE_LOG.md`.
- **Thesis Content**: For thesis-related work, create Markdown files in `reports/` directly rather than providing copy-paste text in conversation.
- **Frontend Style**: Maintain a clean, professional, enterprise-grade light theme using CSS in `frontend/theme.py`.
- **Naming**: Prefer clear, simplified Chinese terms for UI labels (e.g., "事件分析" instead of "智能研判中心").
