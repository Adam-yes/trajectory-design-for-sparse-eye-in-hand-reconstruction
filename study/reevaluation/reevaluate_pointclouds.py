"""Re-scores registered reconstructions against the reference geometry.

OPTIONAL. The paper does not need this script. It becomes useful only if the registered
point clouds of the runs (one .ply per run, already in the metric cell frame) and the
reference surface sample (.ply) are still on disk. It then closes three gaps that the
stored tables leave open: F1 at several thresholds, the uncensored cloud-to-reference
distance, and scores restricted to the objects (table excluded).

    python reevaluate_pointclouds.py --reference ref.ply --runs "D:/results/*/aligned.ply" \
        --out rescored.csv [--crop xmin ymin zmin xmax ymax zmax] [--max-points 2000000]

One CSV row per run. Rows already in --out are skipped, so the job can be stopped and
restarted. CPU only; all cores are used for the nearest-neighbour search. About 1,700
clouds of 1.5 million points against a 1-million-point reference take a few hours on a
16-core workstation, so the laptop is sufficient.

Distances are point-to-point against the reference sample. With a 1-million-point sample
of a table-sized scene the spacing is about 1 mm, which is the resolution of the result.
"""
from __future__ import annotations

import argparse
import csv
import glob
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

THRESHOLDS_M = (0.005, 0.010, 0.020, 0.050)
C2M_CUTOFF_M = 0.10


def load_ply(path: str) -> np.ndarray:
    from plyfile import PlyData
    v = PlyData.read(path)["vertex"]
    pts = np.column_stack([v["x"], v["y"], v["z"]]).astype(np.float64)
    return pts[np.isfinite(pts).all(axis=1)]


def crop(pts: np.ndarray, box) -> np.ndarray:
    if box is None:
        return pts
    lo, hi = np.array(box[:3]), np.array(box[3:])
    return pts[((pts >= lo) & (pts <= hi)).all(axis=1)]


def score(rec: np.ndarray, ref: np.ndarray, ref_tree: cKDTree) -> dict:
    d_rec = ref_tree.query(rec, workers=-1)[0]             # reconstruction -> reference
    d_ref = cKDTree(rec).query(ref, workers=-1)[0]         # reference -> reconstruction
    row = {"n_points": len(rec),
           "cd_ref_to_rec_m": d_ref.mean(), "cd_rec_to_ref_m": d_rec.mean(),
           "hd95_m": max(np.percentile(d_rec, 95), np.percentile(d_ref, 95)),
           "dist_mean_uncensored_m": d_rec.mean(), "dist_median_m": np.median(d_rec),
           "dist_mean_censored_m": d_rec[d_rec <= C2M_CUTOFF_M].mean() if (d_rec <= C2M_CUTOFF_M).any() else np.nan,
           "inlier_ratio": (d_rec <= C2M_CUTOFF_M).mean()}
    for t in THRESHOLDS_M:
        p, r = (d_rec <= t).mean(), (d_ref <= t).mean()
        mm = int(round(t * 1000))
        row[f"precision_{mm}mm"], row[f"recall_{mm}mm"] = p, r
        row[f"f1_{mm}mm"] = 2 * p * r / (p + r) if p + r else 0.0
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--runs", required=True, help="glob pattern of registered .ply files")
    ap.add_argument("--out", default="rescored.csv")
    ap.add_argument("--crop", type=float, nargs=6, metavar=("X0", "Y0", "Z0", "X1", "Y1", "Z1"))
    ap.add_argument("--max-points", type=int, default=0, help="random subsample of each reconstruction")
    a = ap.parse_args()

    ref = crop(load_ply(a.reference), a.crop)
    tree = cKDTree(ref)
    files = sorted(glob.glob(a.runs))
    if not files:
        raise SystemExit(f"no files match {a.runs}")
    out = Path(a.out)
    done = set()
    if out.exists():
        with out.open(newline="", encoding="utf-8") as h:
            done = {r["file"] for r in csv.DictReader(h)}
    rng = np.random.default_rng(0)
    for i, f in enumerate(files, 1):
        if f in done:
            continue
        try:
            rec = crop(load_ply(f), a.crop)
            if a.max_points and len(rec) > a.max_points:
                rec = rec[rng.choice(len(rec), a.max_points, replace=False)]
            if len(rec) == 0:
                raise ValueError("no points inside the evaluation region")
            row = {"file": f, **score(rec, ref, tree)}
        except Exception as e:  # one unreadable cloud must not stop a long job
            print(f"[{i}/{len(files)}] SKIPPED {f}: {e}")
            continue
        new = not out.exists()
        with out.open("a", newline="", encoding="utf-8") as h:
            w = csv.DictWriter(h, fieldnames=list(row))
            if new:
                w.writeheader()
            w.writerow(row)
        print(f"[{i}/{len(files)}] {f}  F1@20mm={row['f1_20mm']:.3f}  HD95={row['hd95_m']:.3f} m")


if __name__ == "__main__":
    main()
