"""The archived study must reproduce the numbers reported in the article.

These tests rerun `study/analysis.py` on the bundled result tables and compare the
outcome with the published values. They guard the result tables and the analysis code
against silent change; they do not rerun reconstruction or registration.
"""
import importlib.util
import json
from pathlib import Path

import pytest

STUDY = Path(__file__).resolve().parents[1] / "study"


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("study_analysis", STUDY / "analysis.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main()


def test_execution_counts(result):
    counts = result["execution_counts"]
    assert (counts["planned"], counts["retained"]) == (10000, 432)
    assert counts["retained"] + counts["low_completion"] + counts["crash_or_error"] == counts["planned"]


def test_run_identifiers_decode_to_the_archived_parameters(result):
    assert result["checks"]["decoded_parameters_match_archived_candidates"] is True
    assert result["checks"]["execution_time_over_path_length"] == pytest.approx(4.0, abs=1e-3)


@pytest.mark.parametrize("setting, p10, median, p90, best", [
    ("S", 0.12, 0.49, 0.73, 0.81), ("I", 0.33, 0.55, 0.68, 0.80),
    ("G", 0.30, 0.79, 0.84, 0.89), ("B", 0.41, 0.78, 0.84, 0.90)])
def test_f1_quantiles(result, setting, p10, median, p90, best):
    q = result["f1_quantiles"][setting]
    assert [round(q[k], 2) for k in ("p10", "p50_mid", "p90", "max")] == [p10, median, p90, best]


def test_context_image_turns_hd95_into_a_coverage_measure(result):
    direction = result["hd95_direction"]
    assert sum(d["ref_to_rec_is_larger"] for d in direction["S"].values()) == 1
    assert sum(d["ref_to_rec_is_larger"] for d in direction["B"].values()) == 114


def test_vertical_radius_separates_top_and_bottom_decile(result):
    contrast = {r["parameter"]: r for r in result["parameter_contrast"]["B"]}
    assert contrast["radius_z"]["cliffs_delta"] > 0.99
    assert contrast["radius_z"]["p_holm"] < 0.001


def test_front_and_threshold_selection_above_the_90th_percentile(result):
    top = result["top_decile_B"]
    assert (top["n"], top["front_length_f1"], top["front_length_f1_hd95"]) == (38, 6, 11)
    picks = [t["selected"]["run_id"] for t in result["threshold_selection_top_decile_B"]]
    assert picks == ["grid_run_8159", "grid_run_5208", "grid_run_5208", "grid_run_5159", "grid_run_5309"]


def test_committed_results_match_a_fresh_run(result):
    committed = json.loads((STUDY / "results" / "analysis.json").read_text(encoding="utf-8"))
    assert committed["f1_quantiles"] == result["f1_quantiles"]
    assert committed["top_decile_B"]["front_length_f1"] == result["top_decile_B"]["front_length_f1"]
