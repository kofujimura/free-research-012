#!/usr/bin/env python3
"""Stricter number check between the original manuscript (paper.md) and the English LaTeX version.

Usage: python3 preprint/check_values.py   (no third-party packages; reads only, writes nothing)

1. Every "estimate [low, high]" triple in main.tex and tables/*.tex must occur verbatim in paper.md,
   except the 0- and 2-week values of tab_extended.tex, which the original showed only in a figure
   (they are listed and checked against tab_extended.tex itself).
2. Numbers in main.tex/tables that occur in none of the sources are listed. Unlike the skill's generic
   check_numbers.py, a number glued to Japanese text in paper.md is also found here (the boundary is
   ASCII-only), and the run's own records that the AI Declaration draws on are included as sources.
Every remaining number must be explained in preprint/README.md.
"""
import glob, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[1]
A = ROOT / "preprint" / "arxiv"
tex = (A / "main.tex").read_text()
tex = "\n".join(l.split("%")[0] if not l.lstrip().startswith("%") else "" for l in tex.replace("\\%", "PCT").splitlines())
tables = {p.name: p.read_text() for p in sorted((A / "tables").glob("*.tex"))}
paper = (ROOT / "paper.md").read_text()

TRIPLE = re.compile(r"(\$-\$|-)?(\d+\.\d+) \[(\$-\$|-)?(\d+\.\d+), (\$-\$|-)?(\d+\.\d+)\]")


def norm(m):
    s = lambda sign: "-" if sign else ""
    return f"{s(m.group(1))}{m.group(2)} [{s(m.group(3))}{m.group(4)}, {s(m.group(5))}{m.group(6)}]"


paper_triples = {norm(m) for m in TRIPLE.finditer(paper)}
ext_new = set()
for line in tables["tab_extended.tex"].splitlines():
    cells = [c.strip(" \\") for c in line.split("&")]
    if len(cells) == 7 and TRIPLE.fullmatch(cells[4]):
        ext_new |= {norm(TRIPLE.fullmatch(cells[4])), norm(TRIPLE.fullmatch(cells[6]))}
missing = []
for name, text in [("main.tex", tex)] + list(tables.items()):
    for m in TRIPLE.finditer(text):
        v = norm(m)
        if v not in paper_triples and not (name == "tab_extended.tex" and v in ext_new):
            missing.append((name, v))
print("interval triples checked:", sum(len(TRIPLE.findall(t)) for t in [tex] + list(tables.values())))
print("triples not in paper.md (must be empty):", missing)
print("new triples from the figure (tab_extended, 0 and 2 weeks):", sorted(ext_new - paper_triples))

NUM = re.compile(r"(?<![A-Za-z0-9_.])\d[\d,]*(?:\.\d+)?")
sources = paper + "".join((ROOT / f).read_text() for f in ["final_report.md", "manifest.json", "interventions.jsonl",
                                                             "requirements-lock.txt", "protocol/plan-v1.md"])
sources += "".join(open(f).read() for f in glob.glob(str(ROOT / "preprint/sources_check/*")))
src = {n.replace(",", "") for n in NUM.findall(sources)}
body = re.sub(r"\\url\{[^}]*\}|\\texttt\{[0-9a-f]{40}\}|\\usepackage(\[[^]]*\])?\{[^}]*\}|\\setlength\{[^}]*\}\{[^}]*\}|"
              r"\\begin\{thebibliography\}\{\d+\}|\\documentclass\[[^]]*\]|\\\\\[\d+pt\]|[\d.]+\\(lineheight|linewidth|textheight)", " ", tex)
body += "".join(tables.values())
lat = {n.replace(",", "") for n in NUM.findall(body)}
key = lambda v: float(v) if re.fullmatch(r"\d+(\.\d+)?", v) else 0
print("numbers in LaTeX not in any source:", sorted(lat - src, key=key))
