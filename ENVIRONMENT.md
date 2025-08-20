# Environment and data setup for StudyPipeline

This repo uses only relative paths. To reproduce, install the pinned environment and place data resources as described below.

## Quickstart
1. Create a virtual environment (recommended) and install requirements:
   - Windows PowerShell (example):
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     pip install -r requirements.txt
2. Open `StudyPipeline.ipynb` and Run All.

## Packages
See `requirements.txt` for exact versions. Versions are pinned to match the project notebooks.

## Data and resources
- The eye-tracking dataset (GCTG clean) is downloaded automatically via `pymovements` into `data-clean/downloads`. If you cannot enable downloads, place the ZIP file at:
  - `data-clean/downloads/gctg-data-clean.zip`
  - Source: please see the dataset’s official page or OSF entry.
- Configuration files (already in repo):
  - `gctg.yaml` and `gctg-clean.yaml` (used by the pipeline for dataset structure).

## Outputs
All artifacts are saved under `data-clean/processed`:
- Tables: `trt_by_word.csv`, `trt_with_features.parquet`, `condition_marginal_means.csv`, etc.
- Figures: `report_fig_feature_means_heatmap.png`, `report_fig_feature_effects.png`, `report_fig_condition_means.png`.

## Notes
- Only relative paths are used; do not edit to absolute paths.
- If you update packages, re-pin `requirements.txt` to maintain reproducibility.
