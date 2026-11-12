# Validation record

Validation performed for release 0.4.0. It records what was executed and, just as importantly, what was not.

## Executed

**103 tests passed; one optional Open3D triangle-distance test was skipped.** `ruff check .` reports no findings. Of the 103 tests, 93 cover the package `src/eyeinhand` and 10 cover the study.

The package tests use analytic or synthetic fixtures for geometry and metrics. The operating-point analysis is covered by tests that verify every printed candidate rounding, check the recovered grid identifiers against the enumerated grid, and recalculate the finite-set dominance and threshold selections. The registration CLI test uses an identity-transform protocol worker and checks file handling and transform composition; it is not a BUFFER-X benchmark. Scene tests validate the configuration and target-object requirement; they do not execute MoveIt collision checking.

The study tests rerun `study/analysis.py` on the bundled result tables and compare the outcome with the values published in the article: execution counts, F1 quantiles of the four settings, the direction that sets HD95, the parameter contrast, the non-dominated set above the 90th percentile and the threshold selections. The full study run (`study/run_all.py`), including the plotting notebook with its type-size check, was executed on Windows 11 with Python 3.14.

Statement coverage of `src/eyeinhand` was 87.44% (856/979 statements, excluding `adapters/`) at release 0.3.0. The package code is unchanged since then.

`tools/render_diagrams.py` regenerates the README overview figure from the trajectory equations and the stage graph.

## Runtime scope

No VGGT or BUFFER-X GPU inference, no ROS, MoveIt or Isaac Sim end-to-end run, and no physical-robot trial was executed for this release. The study tests guard the stored result tables and the analysis; they do not reproduce the simulation, the reconstruction or the registration that produced the tables. Exact Open3D triangle distance and the runtime OBB extraction require validation where Open3D is installed. The algebraic OBB transform is CPU-tested.

## Environment

Package tests: Python 3.13.5 with the pinned `requirements-analysis.txt` (versions in `validation_environment.json`), and Python 3.14 on Windows 11. The compatibility ranges in `pyproject.toml` are not a lockfile. The GitHub Actions workflow runs the package tests on Python 3.10 and 3.13 and the full study on Python 3.12; its current state is shown by the badge in the README.
