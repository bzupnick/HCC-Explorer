#!/usr/bin/env python3
"""Build index.html: embed all models' graph data into template.html.

Inputs:  <model>-hcc-graph.json for each model in parse_cms.MODELS,
         source-data/icd-descriptions.json, template.html
Output:  index.html (self-contained, open directly in a browser)
"""
import json
from pathlib import Path

from parse_cms import MODELS

root = Path(__file__).parent.parent
descriptions = json.loads((root / "source-data" / "icd-descriptions.json").read_text())

data = {}
for model in MODELS:
    graph = json.loads((root / "graphs" / f"{model}-hcc-graph.json").read_text())
    data[model] = {
        "model": graph["model"],
        "short": graph["short"],
        "unit": graph["unit"],
        "coefCols": graph["coef_cols"],
        "hccs": {
            n["hcc"]: {"label": n["label"], "family": n["family"],
                       "icdCount": n["icd_count"], "coef": n["coef"]}
            for n in graph["nodes"]
        },
        "edgesFull": [[e["supersedes"], e["zeroes_out"]] for e in graph["edges_full"]],
        "edgesReduced": [[e["supersedes"], e["zeroes_out"]] for e in graph["edges_reduced"]],
        "icds": [[code, descriptions.get(code, ""), hccs]
                 for code, hccs in sorted(graph["icd_to_hcc"].items())],
    }

template = (root / "template.html").read_text()
payload = json.dumps(data, separators=(",", ":"))
html = template.replace("/*__DATA__*/null", payload)
(root / "index.html").write_text(html)
print(f"wrote index.html ({len(html)//1024} KB): " + ", ".join(
    f"{m}: {len(d['hccs'])} HCCs / {len(d['edgesFull'])} edges / {len(d['icds'])} ICDs"
    for m, d in data.items()))
