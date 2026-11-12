"""Writes the LaTeX tables of the paper from results/analysis.json.

Every number in a table comes from this file, so a table can never drift from the data.
Output: results/tables/*.tex (plain tabular bodies, included with \\input).
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RES = ROOT / "results"
TAB = RES / "tables"
NAME = {"S": "Simple", "I": "InitialAlign", "G": "GlobalAnchor", "B": "Both"}


def f2(x):  # .85 style
    return f"{x:.2f}".replace("0.", ".", 1) if x < 1 else f"{x:.2f}"


def p_fmt(p):
    return "$<$.001" if p < 0.001 else f"{p:.3f}".replace("0.", ".", 1)


def delta_fmt(d):
    if abs(d) > 0.99:  # 0.998 must not be printed as 1.00
        return "$>0.99$" if d > 0 else "$<-0.99$"
    return f"${d:+.2f}$"


def population(res):
    c, p = res["execution_counts"], res["population"]
    rows = [("Grid configurations", f'{c["planned"]:,}'),
            ("Admitted by the completion threshold", f'{c["retained"]:,}'),
            ("Below the completion threshold", f'{c["low_completion"]:,}'),
            ("Planner or simulator error", f'{c["crash_or_error"]:,}'),
            ("Evaluated reconstructions per setting", p["implied_population_per_setting"].replace(" to ", "--")),
            ("Runs per stored decile", p["decile_size"]),
            ("Runs with complete record per setting", p["runs_with_complete_record_per_setting"]),
            ("Distinct configurations with complete record", p["distinct_run_ids_with_complete_record"]),
            ("Distinct configurations in any stored table", p["distinct_run_ids_in_tables"])]
    out = [r"\begin{tabular}{@{}lr@{}}", r"\toprule", r"Set & Size \\", r"\midrule"]
    out += [f"{a} & {str(b).replace(',', '{,}')}" + r" \\" for a, b in rows]
    out += [r"\bottomrule", r"\end{tabular}"]
    write("population.tex", out)


def write(name, lines):
    TAB.mkdir(parents=True, exist_ok=True)
    (TAB / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def deciles(res):
    out = [r"\begin{tabular}{@{}llcccccccc@{}}", r"\toprule",
           r"Decile & Setting & F1 & Prec. & Rec. & AUCC & C2M & HD95 & CD$_{\mathrm{r}\to\mathrm{p}}$ & CD$_{\mathrm{p}\to\mathrm{r}}$ \\",
           r" & & & & & & (mm) & (cm) & (mm) & (mm) \\", r"\midrule"]
    for d in ("top", "middle", "bottom"):
        for i, s in enumerate("SIGB"):
            r = next(x for x in res["decile_summary"] if x["setting"] == s and x["decile"] == d)
            out.append(" & ".join([
                (d.capitalize() if i == 0 else ""), s,
                f'{f2(r["f1_median"])} [{f2(r["f1_min"])}, {f2(r["f1_max"])}]',
                f2(r["precision_median"]), f2(r["recall_median"]), f2(r["aucc_median"]),
                f'{1e3 * r["c2m_mean_m_median"]:.1f}', f'{1e2 * r["hd95_m_median"]:.1f}',
                f'{1e3 * r["cd_ref_to_rec_m_median"]:.1f}', f'{1e3 * r["cd_rec_to_ref_m_median"]:.1f}']) + r" \\")
        if d != "bottom":
            out.append(r"\midrule")
    out += [r"\bottomrule", r"\end{tabular}"]
    write("deciles.tex", out)


def quantiles(res):
    mm = res["metric_medians"]
    out = [r"\begin{tabular}{@{}lccccccc@{}}", r"\toprule",
           r" & \multicolumn{4}{c}{F1 at 20 mm} & \multicolumn{3}{c}{Population median} \\",
           r"\cmidrule(lr){2-5}\cmidrule(l){6-8}",
           r"Setting & P10 & Med. & P90 & Max & Rec. & C2M & HD95 \\",
           r" & & & & & & (mm) & (cm) \\", r"\midrule"]
    for s in "SIGB":
        q = res["f1_quantiles"][s]
        out.append(" & ".join([NAME[s], f2(q["p10"]), f2(q["p50_mid"]), f2(q["p90"]), f2(q["max"]),
                               f2(mm[f"{s}:completeness_ratio"]["median_of_middle_decile"]),
                               f'{1e3 * mm[f"{s}:c2m_mean_distance_m"]["median_of_middle_decile"]:.1f}',
                               f'{1e2 * mm[f"{s}:hd95_distance_m"]["median_of_middle_decile"]:.1f}']) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    write("quantiles.tex", out)


def contrast(res):
    lab = {"radius_xy": r"$r_{xy}$ (m)", "radius_z": r"$r_z$ (m)", "azimuth_span": r"$\Delta\phi$ (deg)",
           "elevation_min": r"$\theta_{\min}$ (deg)", "elevation_max": r"$\theta_{\max}$ (deg)",
           "path_length_m": r"$L$ (m)"}
    out = [r"\begin{tabular}{@{}lcccccccc@{}}", r"\toprule",
           r" & \multicolumn{4}{c}{Both} & \multicolumn{4}{c}{Simple} \\",
           r"\cmidrule(lr){2-5}\cmidrule(l){6-9}",
           r"Parameter & Top & Bottom & $\delta$ & $p$ & Top & Bottom & $\delta$ & $p$ \\", r"\midrule"]
    for i, k in enumerate(lab):
        cells = [lab[k]]
        for s in "BS":
            r = res["parameter_contrast"][s][i]
            assert r["parameter"] == k
            digs = 3 if k.startswith("radius") else (2 if k == "path_length_m" else 1)
            cells += [f'{r["top_mean"]:.{digs}f}', f'{r["bottom_mean"]:.{digs}f}',
                      delta_fmt(r["cliffs_delta"]), p_fmt(r["p_holm"])]
        out.append(" & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    write("contrast.tex", out)


def feasibility(res):
    g = res["feasibility_rz_by_elevation_max"]
    out = [r"\begin{tabular}{@{}lccccc@{}}", r"\toprule",
           r" & \multicolumn{5}{c}{$\theta_{\max}$ (deg)} \\", r"\cmidrule(l){2-6}",
           r"$r_z$ (m) & " + " & ".join(f"{c:g}" for c in g["cols_elevation_max"]) + r" \\", r"\midrule"]
    for rz, row in zip(g["rows_radius_z"], g["evaluated_of_400"]):
        out.append(f"{rz:.2f} & " + " & ".join(str(v) for v in row) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    write("feasibility_rz_thetamax.tex", out)


def operating_points(res):
    with (ROOT / "data/archived/candidate_values.csv").open(newline="", encoding="utf-8") as h:
        c = sorted(csv.DictReader(h), key=lambda x: float(x["path_length_m"]))
    p90 = res["f1_quantiles"]["B"]["p90"]
    out = [r"\begin{tabular}{@{}lcccccccccc@{}}", r"\toprule",
           r"Run & $L$ & F1 & C2M & HD95 & $r_{xy}$ & $r_z$ & $\Delta\phi$ & $\theta_{\min}$ & $\theta_{\max}$ & $\beta$ range \\",
           r" & (m) & & (mm) & (cm) & (m) & (m) & (deg) & (deg) & (deg) & (deg) \\", r"\midrule"]
    for r in c:
        b = lambda t: math.degrees(math.atan(float(r["radius_xy_m"]) / float(r["radius_z_m"]) * math.tan(math.radians(t))))
        mark = "" if float(r["f1_score"]) >= p90 else r"$^{\ast}$"
        out.append(" & ".join([
            r["run_id"][-4:] + mark, f'{float(r["path_length_m"]):.3f}', f'{float(r["f1_score"]):.3f}'.replace("0.", ".", 1),
            f'{1e3 * float(r["c2m_conditional_mean_m"]):.1f}', f'{1e2 * float(r["hd95_m"]):.1f}',
            f'{float(r["radius_xy_m"]):.2f}', f'{float(r["radius_z_m"]):.2f}', f'{float(r["azimuth_span_deg"]):.0f}',
            f'{float(r["polar_min_deg"]):.0f}', f'{float(r["polar_max_deg"]):.0f}',
            f'{b(float(r["polar_min_deg"])):.1f}--{b(float(r["polar_max_deg"])):.1f}']) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    write("operating_points.tex", out)


def thresholds(res):
    out = [r"\begin{tabular}{@{}cccccc@{}}", r"\toprule",
           r"$f_{\min}$ & $h_{\max}$ (cm) & Run & $L$ (m) & F1 & HD95 (cm) \\", r"\midrule"]
    for t in res["threshold_selection_top_decile_B"]:
        s = t["selected"]
        out.append(" & ".join([f2(t["f_min"]), f'{100 * t["h_max_m"]:.0f}', s["run_id"][-4:],
                               f'{s["path_length_m"]:.3f}', f'{s["f1"]:.3f}'.replace("0.", ".", 1),
                               f'{100 * s["hd95_m"]:.1f}']) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    write("thresholds.tex", out)


if __name__ == "__main__":
    res = json.loads((RES / "analysis.json").read_text(encoding="utf-8"))
    population(res); deciles(res); quantiles(res); contrast(res); feasibility(res); operating_points(res); thresholds(res)
    print("tables written to", TAB)
