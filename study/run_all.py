"""Runs the whole analysis: statistics, figures and tables of the article.

    python run_all.py            analysis, plots, tables
    python run_all.py --pdf      the same, then compiles ../paper/main.pdf (needs pdflatex)

Steps: analysis.py -> plots/make_plots.ipynb -> make_tables.py
If the manuscript sources are present in ../paper, the tables and figures are copied
there and check_paper.py verifies the manuscript against the results.
Takes about a minute on a laptop. No GPU, simulator or network access is used.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAPER = ROOT.parent / "paper"
PLOTS = ROOT / "plots"


def run(*cmd, cwd=ROOT):
    print("==", " ".join(str(c) for c in cmd[1:] if not str(c).startswith("--")) or cmd[0])
    subprocess.run(cmd, check=True, cwd=cwd)


run(sys.executable, ROOT / "analysis.py")
run(sys.executable, PLOTS / "build_notebook.py", cwd=PLOTS)
run(sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
    "--log-level=ERROR", "make_plots.ipynb", cwd=PLOTS)
run(sys.executable, ROOT / "make_tables.py")

if not (PAPER / "main.tex").exists():
    # Stand-alone use (public repository): the manuscript sources are not present.
    print("== done; results are in", ROOT / "results", "and", PLOTS / "out")
    sys.exit(0)

(PAPER / "tables").mkdir(parents=True, exist_ok=True)
(PAPER / "figures").mkdir(parents=True, exist_ok=True)
for f in (ROOT / "results" / "tables").glob("*.tex"):
    shutil.copy2(f, PAPER / "tables" / f.name)
for f in (PLOTS / "out").glob("*.pdf"):
    shutil.copy2(f, PAPER / "figures" / f.name)
print("== copied tables and figures to", PAPER)

if "--pdf" in sys.argv:
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        sys.exit("pdflatex not found on PATH; install a TeX distribution or compile on Overleaf")
    for cmd in (["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main"], ["bibtex", "main"],
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main"],
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main"]):
        print("==", " ".join(cmd))
        r = subprocess.run(cmd, cwd=PAPER, capture_output=True, text=True, errors="replace")
        if r.returncode:
            print(r.stdout[-3000:])
            sys.exit(f"{cmd[0]} failed")
    print("== wrote", PAPER / "main.pdf")

print("== check_paper.py")
sys.exit(subprocess.run([sys.executable, str(ROOT / "check_paper.py")]).returncode)
