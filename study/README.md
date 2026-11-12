# Study: data, analysis and figures of the article

Regenerates every table and figure of the article from the archived result tables. No
GPU, no simulator, no network access during the run. About a minute on a laptop.

## Run

Linux or macOS:

    bash run_all.sh

Windows:

    run_all.bat

Both create a virtual environment in `.venv`, install `requirements.txt` and run
`run_all.py`. By hand:

    python -m pip install -r requirements.txt
    python run_all.py

## What runs

| Step | Reads | Writes |
|---|---|---|
| `analysis.py` | `data/` | `results/analysis.json`, `results/*.csv`, `plots/plot_data.csv` |
| `plots/make_plots.ipynb` | `plots/plot_data.csv`, `plots/qualitative/` | `plots/out/*.pdf`, `*.png`, `font_report.csv` |
| `make_tables.py` | `results/` | `results/tables/*.tex` |

The generated files are committed, so the results can be read without running anything.
`tests/test_study.py` in the repository root reruns the analysis and compares it with
the published values.

## Figures

All plots and schematics are drawn with matplotlib in `plots/make_plots.ipynb`. The
notebook reads one file, `plots/plot_data.csv`, which `analysis.py` writes; its columns
are described in the first cell. `plots/build_notebook.py` holds the cell sources and
rewrites the notebook, so a change can be made there or directly in Jupyter.

Type size rule: the body text of the article is 10 pt and all text in all figures is
8 pt. Figures are written at the exact column width (252 pt) or text width (516 pt) and
are included in the article without rescaling. The notebook refuses to save a figure
that contains text of another size. Subscripts inside math symbols are set smaller by
the math typesetter, as in any typeset formula.

## Data

| File | Content |
|---|---|
| `data/raw/deciles_f1_dense.csv` | Complete metric record of the top, middle and bottom F1 decile of each setting (38 runs each) |
| `data/raw/deciles_all.csv` | Top, middle and bottom decile of seven measures, ranked per measure |
| `data/raw/deciles_analytics*.csv` | Summary statistics of the same deciles (not used by the scripts) |
| `data/archived/candidate_values.csv` | Eleven operating points of setting Both with explicit parameters |
| `data/archived/execution_counts.json` | Outcome counts of the 10,000 planned runs |
| `data/archived/teaser_summary.json` | Archived summary of the TEASER++ comparison and the plot it was read from |

Setting names in the raw tables: `attempt_06` = Simple, `attempt_06_initialAlign` =
InitialAlign, `attempt_06_augmentImgs` = GlobalAnchor,
`attempt_06_initialAlign_augmentImgs` = Both.

Two facts about the tables that the analysis relies on, both checked at start-up:

- The run identifier `grid_run_NNNN` is the index of the configuration in the Cartesian
  product of the grid with parameter names sorted alphabetically.
- The column `execution_time` equals four times the recorded path length in metres.

What the tables do not contain: images, point clouds, and metric records of runs between
the stored deciles.

## Optional: re-scoring point clouds

`reevaluation/reevaluate_pointclouds.py` computes F1 at 5, 10, 20 and 50 mm, the
uncensored distance and region-restricted scores from registered point clouds. It needs
the `.ply` files of the runs, which are not part of this repository. It is CPU-only and
resumable and was tested on synthetic clouds. See the docstring of the script.
