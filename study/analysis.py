"""Statistical analysis of the archived trajectory study.

Reads the result tables in data/, writes results/analysis.json and results/*.csv.
Needs NumPy and SciPy only. Runs in a few seconds on a laptop.

What the tables contain (and what they do not):
  data/raw/deciles_f1_dense.csv   For each of the four pipeline settings, the runs of the
                                  top, middle and bottom F1 decile (38 runs each) with all
                                  metrics. Runs between these deciles are not stored.
  data/raw/deciles_all.csv        The same three deciles, ranked separately per metric.
  data/archived/*                 The eleven operating points and the execution counts.

Because a decile is a contiguous block of the ranked population, its edges are
population quantiles: min(top decile) is the 90th percentile, max(bottom decile) the
10th, and the middle decile brackets the median. Every statement this script makes is
restricted to what follows from that.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from itertools import product
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
ARCHIVED = ROOT / "data" / "archived"
OUT = ROOT / "results"

SETTINGS = {  # archive name -> (short, long)
    "attempt_06": ("S", "Simple"),
    "attempt_06_initialAlign": ("I", "InitialAlign"),
    "attempt_06_augmentImgs": ("G", "GlobalAnchor"),
    "attempt_06_initialAlign_augmentImgs": ("B", "Both"),
}
SPLITS = {"best": "top", "median": "middle", "worst": "bottom"}

GRID = {
    "radius_xy": [0.18, 0.20, 0.22, 0.24, 0.26],
    "radius_z": [0.35, 0.40, 0.45, 0.50, 0.55],
    "azimuth_start": [-160.0, -140.0, -120.0, -100.0],
    "azimuth_end": [60.0, 80.0, 100.0, 120.0],
    "elevation_min": [5.0, 10.0, 15.0, 20.0, 25.0],
    "elevation_max": [60.0, 65.0, 70.0, 75.0, 80.0],
}
PARAMS = ["radius_xy", "radius_z", "azimuth_span", "elevation_min", "elevation_max"]
FOCUS = np.array([0.35, -0.36, 0.04])
SLICES, POINTS_PER_SLICE = 10, 8
SPEED_FACTOR = 4.0  # archived "execution_time" equals 4 x recorded path length (checked below)


def grid_table() -> dict[str, dict[str, float]]:
    """run_id -> parameters, enumerated in sorted-key order as the archive did."""
    keys = sorted(GRID)
    table = {}
    for i, combo in enumerate(product(*(GRID[k] for k in keys))):
        p = dict(zip(keys, combo))
        p["azimuth_span"] = p["azimuth_end"] - p["azimuth_start"]
        table[f"grid_run_{i:04d}"] = p
    return table


def waypoints(p: dict[str, float]) -> np.ndarray:
    """Nominal camera positions of the lawnmower scan, Eq. (1) of the paper."""
    az = np.radians(np.linspace(p["azimuth_start"], p["azimuth_end"], SLICES))
    el = np.radians(np.linspace(p["elevation_min"], p["elevation_max"], POINTS_PER_SLICE))
    pts = []
    for i, a in enumerate(az):
        for t in (el if i % 2 == 0 else el[::-1]):
            pts.append(FOCUS + [p["radius_xy"] * math.sin(t) * math.cos(a),
                                p["radius_xy"] * math.sin(t) * math.sin(a),
                                p["radius_z"] * math.cos(t)])
    return np.array(pts)


def nominal_length(p: dict[str, float]) -> float:
    w = waypoints(p)
    return float(np.linalg.norm(np.diff(w, axis=0), axis=1).sum())


def sightline(p: dict[str, float]) -> tuple[float, float]:
    """Inclination from vertical at both ends of the polar sweep, Eq. (3), in degrees."""
    f = lambda t: math.degrees(math.atan(p["radius_xy"] / p["radius_z"] * math.tan(math.radians(t))))
    return f(p["elevation_min"]), f(p["elevation_max"])


def read(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def num(x: str) -> float:
    return float(x) if x not in ("", None) else float("nan")


def q(v, p):
    return float(np.percentile(np.asarray(v, float), p))


def cliffs_delta(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float((np.sign(a[:, None] - b[None, :])).mean())


def holm(pvals: list[float]) -> list[float]:
    order = np.argsort(pvals)
    out, running = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        out[i] = running
    return out


def pareto(cost: np.ndarray, gain: np.ndarray) -> np.ndarray:
    """Mask of points not dominated in (minimise cost, maximise gain)."""
    keep = np.ones(len(cost), bool)
    for i in range(len(cost)):
        dom = (cost <= cost[i]) & (gain >= gain[i]) & ((cost < cost[i]) | (gain > gain[i]))
        keep[i] = not dom.any()
    return keep


def main() -> dict:
    OUT.mkdir(exist_ok=True)
    grid = grid_table()
    dense = read(RAW / "deciles_f1_dense.csv")
    sparse = read(RAW / "deciles_all.csv")
    cand = read(ARCHIVED / "candidate_values.csv")
    counts = json.loads((ARCHIVED / "execution_counts.json").read_text(encoding="utf-8"))
    res: dict = {"execution_counts": counts}

    # ---- consistency checks on the archive -------------------------------------------
    by_id = {(r["modality"], r["run_id"]): r for r in dense}
    ratios, mismatches = [], 0
    for c in cand:
        g = grid[c["run_id"]]
        for key, col in [("radius_xy", "radius_xy_m"), ("radius_z", "radius_z_m"),
                         ("azimuth_span", "azimuth_span_deg"), ("elevation_min", "polar_min_deg"),
                         ("elevation_max", "polar_max_deg")]:
            mismatches += not math.isclose(g[key], float(c[col]), abs_tol=1e-9)
        d = by_id.get(("attempt_06_initialAlign_augmentImgs", c["run_id"]))
        if d:
            ratios.append(num(d["execution_time"]) / float(c["path_length_m"]))
            mismatches += not math.isclose(num(d["f1_score"]), float(c["f1_score"]), abs_tol=1e-6)
    if mismatches or not np.allclose(ratios, SPEED_FACTOR, atol=1e-3):
        raise SystemExit("Archive check failed: run-id decoding or path-length scaling is off")
    res["checks"] = {"decoded_parameters_match_archived_candidates": True,
                     "candidates_found_in_dense_table": len(ratios),
                     "execution_time_over_path_length": float(np.mean(ratios))}

    # ---- per-run table with decoded geometry -----------------------------------------
    runs = []
    for r in dense:
        g = grid[r["run_id"]]
        b0, b1 = sightline(g)
        runs.append({
            "setting": SETTINGS[r["modality"]][0], "decile": SPLITS[r["split"]],
            "rank": int(r["rank"]), "run_id": r["run_id"],
            "f1": num(r["f1_score"]), "precision": num(r["f1_precision"]), "recall": num(r["f1_recall"]),
            "hd95_m": num(r["hd95_distance_m"]), "c2m_mean_m": num(r["c2m_mean_distance_m"]),
            "c2m_inlier_ratio": num(r["c2m_inlier_ratio"]), "aucc": num(r["aucc"]),
            "chamfer_m": num(r["cd_chamfer_distance_m"]),
            "cd_ref_to_rec_m": num(r["cd_forward_mean_m"]), "cd_rec_to_ref_m": num(r["cd_backward_mean_m"]),
            # "forward" in the archive is reference -> reconstruction, as for the Chamfer terms
            "hd_ref_to_rec_m": num(r["hd_forward_m"]), "hd_rec_to_ref_m": num(r["hd_backward_m"]),
            "path_length_m": num(r["execution_time"]) / SPEED_FACTOR,
            "nominal_length_m": nominal_length(g),
            **{k: g[k] for k in PARAMS}, "azimuth_start": g["azimuth_start"], "azimuth_end": g["azimuth_end"],
            "beta_min_deg": b0, "beta_max_deg": b1,
        })
    with (OUT / "runs_decoded.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(runs[0])); w.writeheader(); w.writerows(runs)
    sel = lambda s, d: [r for r in runs if r["setting"] == s and r["decile"] == d]

    # ---- population size --------------------------------------------------------------
    ids = defaultdict(set)
    for r in sparse:
        ids[SETTINGS[r["modality"]][0]].add(r["run_id"])
    union = set().union(*ids.values())
    res["population"] = {"decile_size": 38, "implied_population_per_setting": "380 to 389",
                         "distinct_run_ids_in_tables": len(union),
                         "distinct_run_ids_with_complete_record": len({r["run_id"] for r in runs}),
                         "runs_with_complete_record_per_setting": len(sel("B", "top")) * 3,
                         "distinct_run_ids_per_setting": {s: len(v) for s, v in ids.items()}}

    # ---- Table: decile summaries (median and range, not single runs) -------------------
    metrics = ["f1", "precision", "recall", "c2m_mean_m", "c2m_inlier_ratio", "hd95_m",
               "cd_ref_to_rec_m", "cd_rec_to_ref_m", "aucc", "path_length_m"]
    table = []
    for s in "SIGB":
        for d in ("top", "middle", "bottom"):
            rr = sel(s, d)
            row = {"setting": s, "decile": d, "n": len(rr)}
            for m in metrics:
                v = [r[m] for r in rr]
                row[f"{m}_median"], row[f"{m}_min"], row[f"{m}_max"] = q(v, 50), min(v), max(v)
            table.append(row)
    with (OUT / "decile_summary.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(table[0])); w.writeheader(); w.writerows(table)
    res["decile_summary"] = table

    # ---- which directional term sets HD95 ----------------------------------------------
    res["hd95_direction"] = {
        s: {d: {"n": len(sel(s, d)),
                "ref_to_rec_is_larger": sum(r["hd_ref_to_rec_m"] >= r["hd_rec_to_ref_m"] for r in sel(s, d)),
                "median_ref_to_rec_m": q([r["hd_ref_to_rec_m"] for r in sel(s, d)], 50),
                "median_rec_to_ref_m": q([r["hd_rec_to_ref_m"] for r in sel(s, d)], 50)}
            for d in ("top", "middle", "bottom")} for s in "SIGB"}

    # ---- TEASER++ summary (archived values, not recomputable from the tables) ----------
    res["teaser_archived"] = json.loads((ARCHIVED / "teaser_summary.json").read_text(encoding="utf-8"))

    # ---- population quantiles of F1 implied by the decile edges ------------------------
    res["f1_quantiles"] = {
        s: {"p10": max(r["f1"] for r in sel(s, "bottom")),
            "p50_bracket": [min(r["f1"] for r in sel(s, "middle")), max(r["f1"] for r in sel(s, "middle"))],
            "p50_mid": q([r["f1"] for r in sel(s, "middle")], 50),
            "p90": min(r["f1"] for r in sel(s, "top")),
            "max": max(r["f1"] for r in sel(s, "top")),
            "min": min(r["f1"] for r in sel(s, "bottom"))} for s in "SIGB"}

    # per-metric quantiles from the per-metric deciles
    pm = defaultdict(lambda: defaultdict(list))
    for r in sparse:
        for k, v in r.items():
            if k not in ("modality", "split", "run_id") and v:
                pm[(SETTINGS[r["modality"]][0], k)][r["split"]].append(float(v))
    res["metric_medians"] = {f"{s}:{k}": {"median_of_middle_decile": q(v["median"], 50),
                                          "median_of_best_decile": q(v["best"], 50),
                                          "median_of_worst_decile": q(v["worst"], 50)}
                             for (s, k), v in sorted(pm.items())}

    # ---- F1 does not order HD95 inside the top decile ----------------------------------
    res["f1_vs_hd95_top_decile"] = {}
    for s in "SIGB":
        rr = sel(s, "top")
        f, h_, L = (np.array([r[k] for r in rr]) for k in ("f1", "hd95_m", "path_length_m"))
        rho, p = stats.spearmanr(f, h_)
        rho_l, p_l = stats.spearmanr(L, h_)
        rho_f, p_f = stats.spearmanr(L, f)
        res["f1_vs_hd95_top_decile"][s] = {
            "n": len(rr), "f1_range": [float(f.min()), float(f.max())],
            "hd95_range_m": [float(h_.min()), float(h_.max())], "hd95_median_m": float(np.median(h_)),
            "spearman_f1_hd95": float(rho), "p_f1_hd95": float(p),
            "spearman_length_hd95": float(rho_l), "p_length_hd95": float(p_l),
            "spearman_length_f1": float(rho_f), "p_length_f1": float(p_f)}

    # ---- which parameter values separate the top from the bottom decile -----------------
    res["parameter_contrast"] = {}
    for s in "SIGB":
        top, bot = sel(s, "top"), sel(s, "bottom")
        rows, pv = [], []
        for k in PARAMS + ["path_length_m"]:
            a, b = [r[k] for r in top], [r[k] for r in bot]
            u = stats.mannwhitneyu(a, b, alternative="two-sided")
            rows.append({"parameter": k, "top_mean": float(np.mean(a)), "bottom_mean": float(np.mean(b)),
                         "top_median": q(a, 50), "bottom_median": q(b, 50),
                         "cliffs_delta": cliffs_delta(a, b), "p": float(u.pvalue)})
            pv.append(float(u.pvalue))
        for row, ph in zip(rows, holm(pv)):
            row["p_holm"] = ph
        res["parameter_contrast"][s] = rows

    # ---- which grid levels reach evaluation ---------------------------------------------
    feas = {}
    for k in ["radius_xy", "radius_z", "azimuth_start", "azimuth_end", "elevation_min", "elevation_max"]:
        levels = GRID[k]
        hit = np.array([sum(grid[i][k] == lv for i in union) for lv in levels])
        tot = np.array([sum(g[k] == lv for g in grid.values()) for lv in levels])
        feas[k] = {"levels": levels, "evaluated": hit.tolist(), "proposed": tot.tolist(),
                   "rate_percent": (100 * hit / tot).round(2).tolist()}
    res["feasibility_by_level"] = feas
    rz55 = {i for i in union if grid[i]["radius_z"] == 0.55}
    res["radius_z_055"] = {"recorded_configurations": len(rz55),
                           **{f"B_{d}": sum(r["run_id"] in rz55 for r in sel("B", d)) for d in ("top", "middle", "bottom")}}
    pair = np.zeros((5, 5), int)
    for i in union:
        pair[GRID["radius_z"].index(grid[i]["radius_z"]), GRID["elevation_max"].index(grid[i]["elevation_max"])] += 1
    res["feasibility_rz_by_elevation_max"] = {"rows_radius_z": GRID["radius_z"], "cols_elevation_max": GRID["elevation_max"],
                                              "evaluated_of_400": pair.tolist()}

    # ---- path length: recorded against nominal ------------------------------------------
    uniq = {r["run_id"]: r for r in runs}
    rec = np.array([r["path_length_m"] for r in uniq.values()])
    nom = np.array([r["nominal_length_m"] for r in uniq.values()])
    slope, icpt, rval, _, _ = stats.linregress(nom, rec)
    res["path_length_model"] = {"n_runs": len(rec), "pearson_r": float(rval), "slope": float(slope),
                                "intercept_m": float(icpt), "ratio_median": float(np.median(rec / nom)),
                                "ratio_range": [float((rec / nom).min()), float((rec / nom).max())],
                                "ratio_range_without_lowest": [float(np.sort(rec / nom)[1]), float((rec / nom).max())],
                                "runs_above_nominal": int((rec > nom).sum()),
                                "recorded_range_m": [float(rec.min()), float(rec.max())]}

    # ---- exact length/F1 front above the 90th F1 percentile (setting B) -----------------
    top = sorted(sel("B", "top"), key=lambda r: r["path_length_m"])
    L, F, H = (np.array([r[k] for r in top]) for k in ("path_length_m", "f1", "hd95_m"))
    m2 = pareto(L, F)
    m3 = np.ones(len(top), bool)
    for i in range(len(top)):
        dom = (L <= L[i]) & (F >= F[i]) & (H <= H[i]) & ((L < L[i]) | (F > F[i]) | (H < H[i]))
        m3[i] = not dom.any()
    front = [{"run_id": r["run_id"], "path_length_m": r["path_length_m"], "f1": r["f1"], "hd95_m": r["hd95_m"],
              "c2m_mean_m": r["c2m_mean_m"], **{k: r[k] for k in PARAMS},
              "beta_min_deg": r["beta_min_deg"], "beta_max_deg": r["beta_max_deg"],
              "front_length_f1": bool(a), "front_length_f1_hd95": bool(b)}
             for r, a, b in zip(top, m2, m3)]
    with (OUT / "top_decile_B.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(front[0])); w.writeheader(); w.writerows(front)
    res["top_decile_B"] = {"n": len(top), "f1_floor": float(F.min()),
                           "front_length_f1": int(m2.sum()), "front_length_f1_hd95": int(m3.sum()),
                           "front_length_f1_runs": [f for f in front if f["front_length_f1"]]}

    # threshold rule, Eq. (10), on the top decile
    def pick(fmin, hmax):
        ok = [f for f in front if f["f1"] >= fmin and f["hd95_m"] <= hmax]
        return min(ok, key=lambda f: f["path_length_m"]) if ok else None
    res["threshold_selection_top_decile_B"] = [
        {"f_min": a, "h_max_m": b, "selected": pick(a, b)} for a, b in
        [(0.85, 0.20), (0.85, 0.15), (0.85, 0.12), (0.88, 0.12), (0.85, 0.10)]]

    # ---- the two-run comparison quoted in the text --------------------------------------
    c = {r["run_id"]: r for r in cand}
    a, b, mx = c["grid_run_6904"], c["grid_run_5208"], c["grid_run_5279"]
    fl = lambda r, k: float(r[k])
    res["two_run_comparison"] = {
        "length_increase_percent": 100 * (fl(b, "path_length_m") / fl(a, "path_length_m") - 1),
        "f1_difference": fl(b, "f1_score") - fl(a, "f1_score"),
        "hd95_reduction_percent": 100 * (1 - fl(b, "hd95_m") / fl(a, "hd95_m")),
        "vs_max_f1_length_reduction_percent": 100 * (1 - fl(b, "path_length_m") / fl(mx, "path_length_m")),
        "vs_max_f1_f1_ratio_percent": 100 * fl(b, "f1_score") / fl(mx, "f1_score"),
        "vs_max_f1_hd95_increase_mm": 1000 * (fl(b, "hd95_m") - fl(mx, "hd95_m"))}

    (OUT / "analysis.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    export_plot_data(res, runs, front, cand)
    return res


def export_plot_data(res, runs, front, cand) -> None:
    """One long-format CSV with every value the notebook plots/make_plots.ipynb draws.

    Columns: figure, series, label, x, y, c, flag. Their meaning per figure is listed
    in the first cell of the notebook.
    """
    rows = []
    add = lambda fig, series="", label="", x="", y="", c="", flag="": rows.append(
        {"figure": fig, "series": series, "label": label, "x": x, "y": y, "c": c, "flag": flag})
    for s, qv in res["f1_quantiles"].items():
        for k in ("min", "p10", "p50_mid", "p90", "max"):
            add("f1_quantiles", s, k, y=qv[k])
    for r in res["decile_summary"]:
        add("precision_recall", r["setting"], r["decile"], x=r["recall_median"], y=r["precision_median"])
    for k, v in res["feasibility_by_level"].items():
        for lv, rate, n in zip(v["levels"], v["rate_percent"], v["evaluated"]):
            add("feasibility", k, x=lv, y=rate, c=n)
    for s, v in res["parameter_contrast"].items():
        for r in v:
            add("parameter_contrast", s, r["parameter"], y=r["cliffs_delta"], flag=int(r["p_holm"] < 0.05))
    for f in front:
        add("top_decile", "B", f["run_id"], x=f["path_length_m"], y=f["f1"], c=f["hd95_m"],
            flag=int(f["front_length_f1"]))
    for r in {r["run_id"]: r for r in runs}.values():
        add("length_model", "", r["run_id"], x=r["nominal_length_m"], y=r["path_length_m"])
    for r in cand:
        add("candidates", "B", r["run_id"], x=r["path_length_m"], y=r["f1_score"], c=r["hd95_m"])
    plots = ROOT / "plots"
    plots.mkdir(exist_ok=True)
    with (plots / "plot_data.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    r = main()
    print("wrote", OUT / "analysis.json")
    print("population:", r["population"])
    print("F1 quantiles:", json.dumps(r["f1_quantiles"], indent=1))
