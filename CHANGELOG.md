# Changelog

## 0.4.0

Aligns the repository with the journal version of the article.

### Added

- `study/`: the result tables of the 10,000-configuration study, the analysis
  (`analysis.py`), the plotting notebook (`plots/make_plots.ipynb`), the table generator
  and the generated figures and tables. One command regenerates all of them.
- `docs/RESULTS.md`: the findings of the article with tables and figures.
- `tests/test_study.py`: reruns the analysis on the bundled tables and compares the
  outcome with the published values.
- `.github/workflows/tests.yml`: package tests on Python 3.10 and 3.13, and a full run
  of the study.

### Changed

- README rewritten around the question, the outcome and the evidence, with a key-results
  table and a statement of scope.
- HD95 is described as what it measures in the context-enabled settings: the extent of
  reference surface that the reconstruction does not cover. Earlier text called it a
  boundary error.
- Decile results are reported as medians with range. Earlier summaries showed single
  runs.

### Tests

103 tests pass and one optional Open3D test is skipped; `ruff check .` is clean.

## 0.3.0

### Added

- `prepare-study`: builds the four input manifests from one acquisition, with explicit
  input order, a single selected context frame, total-frame budgeting, duplicate-byte
  rejection and active masks. The context mask is independent, because a top-down image
  can contain the gripper too.
- `register`: a composable two-pass CLI over the isolated backend protocol, with an
  explicit initializer choice (`none`, `obb` or `pca-search`).
- A synchronous MoveIt planning-scene adapter and an explicit scene configuration,
  including the target-object exclusion box and three attached protection zones.
- `eyeinhand.operating_points`: finite-set selection over recorded runs, covering Pareto
  dominance in any number of objectives, threshold-based selection of the shortest
  feasible run, the subset a weighted sum can return, and the sightline geometry implied
  by each configuration.

### Changed

- The evaluator saves uncensored distance arrays alongside the metrics and the aligned
  points, and reuses one directional-distance summarizer instead of repeating
  nearest-neighbor work. The C2M cutoff and the outlier threshold are independent.
- Scene box quaternions are valid identities, and target objects receive no collision
  exemption, so the arm plans around the objects it is scanning.
- Transform composition applies the initializer once; the two incremental rigid updates
  are composed after it.

### Tests

93 tests pass and one optional Open3D test is skipped; `ruff check .` is clean. Coverage
and the exact runtime scope are recorded in `docs/VALIDATION.md`.

## 0.2.0

Modular research core with explicit transforms, masks, metric conventions, integrity
checks and bounded subprocess execution.
