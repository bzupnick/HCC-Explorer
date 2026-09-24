#!/usr/bin/env python3
"""Parse CMS risk-adjustment model software files into graph JSONs.

For each model, reads from source-data/:
  - hierarchy file (SAS macro with %SET0(CC=…, HIER=%STR(…)) rules)
  - labels file   (SAS LABEL block: HCC<n> ="…", case/zero-padding varies)
  - mapping file  (tab-separated: ICD10 code, CC)
  - coefficients  ("wide": one row of SEG_HCC<n> columns; "hhs": long rows of
                   Model,HHS_HCC<n>,used,<metal level values…>)
and writes <model>-hcc-graph.json with nodes (incl. per-HCC coefficient table),
edges_full, edges_reduced (transitive reduction, for diagrams), and icd_to_hcc.
"""
import collections
import csv
import json
import re
from pathlib import Path


def norm(tok):
    """Canonical HCC id: strip zero-padding, unify split spellings -> '35.1'."""
    m = re.fullmatch(r'0*(\d+)(?:[._](\d+))?', tok.strip())
    return m.group(1) + ("." + m.group(2) if m.group(2) else "")


def hcc_key(h):
    a, _, b = h.partition(".")
    return (int(a), int(b or 0))

root = Path(__file__).parent.parent
src = root / "source-data"

# friendly names for CMS coefficient segments (unknown codes pass through as-is)
SEGMENT_NAMES = {
    "CNA": "Community, non-dual, aged",
    "CND": "Community, non-dual, disabled",
    "CFA": "Community, full-benefit dual, aged",
    "CFD": "Community, full-benefit dual, disabled",
    "CPA": "Community, partial-benefit dual, aged",
    "CPD": "Community, partial-benefit dual, disabled",
    "INS": "Long-term institutional",
    "DI": "Dialysis, continuing enrollee",
    "DNE": "Dialysis, new enrollee",
    "GC": "Functioning graft, community",
    "GI": "Functioning graft, institutional",
    "GNE": "Functioning graft, new enrollee",
    "TRANSPLANT": "Transplant",
    "CE_NoLowAged": "Continuing enrollee, non-low-income, aged",
    "CE_NoLowNoAged": "Continuing enrollee, non-low-income, non-aged",
    "CE_LowAged": "Continuing enrollee, low-income, aged",
    "CE_LowNoAged": "Continuing enrollee, low-income, non-aged",
    "CE_LTI": "Continuing enrollee, long-term institutional",
    "CE_LTI_NonAged": "Continuing enrollee, long-term institutional, non-aged",
}

MODELS = {
    "v28": {
        "short": "V28",
        "title": "CMS-HCC V28 — 115 payment HCCs, FY2024 ICD-10-CM mapping",
        "hierarchy": "V28115H1.TXT",
        "labels": "V28115L3.TXT",
        "mapping": "F2824T1N.TXT",
        "coef": ("wide", "V28hcccoefn.csv"),
    },
    "v24": {
        "short": "V24",
        "title": "CMS-HCC V24 — 86 payment HCCs, FY2022 ICD-10-CM mapping",
        "hierarchy": "V24H86H1.TXT",
        "labels": "V24H86L1.TXT",
        "mapping": "F2422P1M.TXT",
        "coef": ("wide", "V24hcccoefn.csv"),
    },
    "esrd": {
        "short": "ESRD",
        "title": "CMS-HCC ESRD V21 (dialysis/functioning graft) — FY2019 ICD-10-CM mapping",
        "hierarchy": "V20H87H1.txt",
        "labels": "V20H87L1.txt",
        "mapping": "F2118H1R.txt",
        "coef": ("wide", "ESRDhcccoefn.csv"),
    },
    "hhs": {
        "short": "HHS",
        "title": "HHS-HCC V07 (commercial/ACA) — 141 payment HCCs incl. 4 age-split pairs, benefit year 2022 mapping",
        "hierarchy": "V07141H1.TXT",
        "labels": "V07141L1.TXT",
        "mapping": "CY22F07A_FY2022_ICD10.TXT",
        "coef": ("hhs", "HHS22hcccoefn.csv"),
    },
    "rx": {
        "short": "RxHCC",
        "unit": "RxHCC",
        "title": "RxHCC R08 (Part D) — 84 payment RxHCCs, PY2026 proposed model, FY2024/FY2025 ICD-10-CM mapping",
        "hierarchy": "R08X84H1.TXT",
        "labels": "R08X84L1.TXT",
        "mapping": "F0825X1O_FY24FY25.TXT",
        "coef": ("rx", "R0826X6O.csv"),
    },
}


def parse_coef_wide(path):
    """One header row of SEG_HCC<n> columns, one value row."""
    with open(src / path, encoding="latin-1") as f:
        rows = list(csv.reader(f))
    header, values = rows[0], rows[1]
    coef = collections.defaultdict(dict)
    for col, val in zip(header, values):
        m = re.fullmatch(r'"?([A-Za-z]+?)_HCC0*(\d+(?:[._]\d+)?)"?', col.strip())
        if m and val.strip():
            seg = m.group(1)
            label = SEGMENT_NAMES.get(seg, seg)
            coef[norm(m.group(2))][label] = [float(val)]
    return {"cols": ["Coefficient"], "rows": dict(coef)}


def parse_coef_hhs(path):
    """Long rows: Model,HHS_HCC<n>,used,Platinum,Gold,Silver,Bronze,Catastrophic."""
    with open(src / path, encoding="latin-1") as f:
        rows = list(csv.reader(f))
    cols = [c.replace(" Level", "") for c in rows[0][3:]]
    coef = collections.defaultdict(dict)
    for row in rows[1:]:
        if len(row) < 4:
            continue
        m = re.fullmatch(r'HHS_HCC0*(\d+(?:[._]\d+)?)', row[1].strip())
        if m:
            coef[norm(m.group(1))][row[0]] = [float(v) if v.strip() else None for v in row[3:]]
    return {"cols": cols, "rows": dict(coef)}


def parse_coef_rx(path):
    """Long rows: Rx_<segment>_RXHCC<n>,label,value."""
    with open(src / path, encoding="latin-1") as f:
        rows = list(csv.reader(f))
    coef = collections.defaultdict(dict)
    for row in rows[1:]:
        if len(row) < 3 or not row[2].strip():
            continue
        m = re.fullmatch(r'Rx_(.+)_RXHCC0*(\d+)', row[0].strip())
        if m:
            seg = SEGMENT_NAMES.get(m.group(1), m.group(1))
            coef[norm(m.group(2))][seg] = [float(row[2])]
    return {"cols": ["Coefficient"], "rows": dict(coef)}


COEF_PARSERS = {"wide": parse_coef_wide, "hhs": parse_coef_hhs, "rx": parse_coef_rx}


def parse_model(key, cfg):
    labels = {}
    for m in re.finditer(r'HCC0*(\d+(?:[._]\d+)?)\s*=\s*"([^"]*)"',
                         (src / cfg["labels"]).read_text(encoding="latin-1"), re.I):
        labels.setdefault(norm(m.group(1)), m.group(2).strip())

    rules, families = {}, {}
    htxt = (src / cfg["hierarchy"]).read_text(encoding="latin-1")
    for m in re.finditer(r'/\*([^*]*)\*/\s*%SET0\(\s*CC=(\d+(?:[._]\d+)?)\s*,\s*HIER=%STR\(([^)]*)\)', htxt, re.S):
        parent = norm(m.group(2))
        rules[parent] = [norm(x) for x in re.findall(r'\d+(?:[._]\d+)?', m.group(3))]
        families[parent] = re.sub(r'\s*\d+\s*$', '', m.group(1).strip())

    icd2cc = collections.defaultdict(set)
    for line in (src / cfg["mapping"]).read_text(encoding="latin-1").splitlines():
        parts = line.split()
        if len(parts) >= 2 and re.fullmatch(r'\d+(?:[._]\d+)?', parts[1]):
            icd2cc[parts[0]].add(norm(parts[1]))

    # keep only payment-model HCCs (mappings can include CCs outside the label set)
    nonpayment = {cc for ccs in icd2cc.values() for cc in ccs} - set(labels)
    if nonpayment:
        print(f"  {key}: dropping {len(nonpayment)} non-payment CCs from mapping: "
              f"{sorted(nonpayment)[:8]}{'…' if len(nonpayment) > 8 else ''}")
        icd2cc = {c: ccs & set(labels) for c, ccs in icd2cc.items()}
        icd2cc = {c: ccs for c, ccs in icd2cc.items() if ccs}
    icd_counts = collections.Counter(cc for ccs in icd2cc.values() for cc in ccs)

    dropped = sorted({x for p_, kids in rules.items() for x in [p_, *kids]} - set(labels))
    if dropped:
        print(f"  {key}: hierarchy references HCCs outside label set (dropped): {dropped}")
    edges = [(p_, c) for p_, kids in rules.items() for c in kids
             if p_ in labels and c in labels]
    in_hier = set(u for u, _ in edges) | set(v for _, v in edges)

    # propagate family names from hierarchy comments to all member HCCs
    fam = dict(families)
    for p, kids in rules.items():
        for c in kids:
            fam.setdefault(c, fam.get(p))

    # transitive reduction: drop (u,v) when v is reachable from u via another child
    adj = collections.defaultdict(set)
    for u, v in edges:
        adj[u].add(v)

    def reachable(start):
        seen, stack = set(), [start]
        while stack:
            x = stack.pop()
            for w in adj[x]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        return seen

    reduced = [
        (u, v) for u, v in edges
        if not any(w != v and v in reachable(w) for w in adj[u])
    ]

    kind, coef_file = cfg["coef"]
    coef = COEF_PARSERS[kind](coef_file)
    coef_missing = set(coef["rows"]) - set(labels)
    if coef_missing:
        print(f"  {key}: coefficient HCCs outside label set (ignored): {sorted(coef_missing)}")
        coef["rows"] = {n: v for n, v in coef["rows"].items() if n in labels}

    graph = {
        "model": cfg["title"],
        "short": cfg["short"],
        "unit": cfg.get("unit", "HCC"),
        "source": f"CMS risk adjustment model software: {cfg['hierarchy']} (hierarchy), "
                  f"{cfg['labels']} (labels), {cfg['mapping']} (ICD mapping), "
                  f"{coef_file} (coefficients), via hccpy mirror",
        "coef_cols": coef["cols"],
        "nodes": [
            {"hcc": n, "label": labels[n], "family": fam.get(n),
             "icd_count": icd_counts.get(n, 0), "in_hierarchy": n in in_hier,
             "coef": coef["rows"].get(n)}
            for n in sorted(labels, key=hcc_key)
        ],
        "edges_full": [{"supersedes": u, "zeroes_out": v}
                       for u, v in sorted(edges, key=lambda e: (hcc_key(e[0]), hcc_key(e[1])))],
        "edges_reduced": [{"supersedes": u, "zeroes_out": v}
                          for u, v in sorted(reduced, key=lambda e: (hcc_key(e[0]), hcc_key(e[1])))],
        "icd_to_hcc": {k: sorted(v) for k, v in sorted(icd2cc.items())},
    }
    (root / "graphs").mkdir(exist_ok=True)
    out = root / "graphs" / f"{key}-hcc-graph.json"
    out.write_text(json.dumps(graph, indent=1))
    n_coef = sum(1 for n in graph["nodes"] if n["coef"])
    print(f"{out.name}: {len(labels)} HCCs ({n_coef} with coefficients), "
          f"{len(edges)} edges ({len(reduced)} reduced), {len(icd2cc)} ICDs")


if __name__ == "__main__":
    for key, cfg in MODELS.items():
        parse_model(key, cfg)
