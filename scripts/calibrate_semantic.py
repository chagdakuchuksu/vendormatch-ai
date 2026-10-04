"""Measure all-MiniLM-L6-v2 similarities on the calibration dataset and write a report.

Usage:  python -m scripts.calibrate_semantic [--out docs/M2-calibration-results.md]

The thresholds in ScoringConfig are NOT changed by this script; it only reports how the
current (provisional) thresholds classify each pair, plus a sensitivity table for context.
"""

import argparse
import json
import statistics
from pathlib import Path

from app.config import DEFAULT_SCORING_CONFIG as CFG
from app.services.semantic.embedder import SentenceTransformerEmbedder
from app.services.semantic.matcher import cosine_similarity, similarity_to_score

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "calibration" / "semantic_pairs.json"

# Verdict per (category, resulting strength): ok / borderline / wrong.
VERDICTS = {
    "strong": {"strong": "ok", "partial": "borderline", "none": "wrong"},
    "partial": {"strong": "borderline", "partial": "ok", "none": "borderline"},
    "unrelated": {"strong": "wrong", "partial": "borderline", "none": "ok"},
    "related_different": {"strong": "wrong", "partial": "ok", "none": "ok"},
    "keyword_trap": {"strong": "wrong", "partial": "ok", "none": "ok"},
}
EXPECTED = {
    "strong": "strong",
    "partial": "partial",
    "unrelated": "none",
    "related_different": "not strong",
    "keyword_trap": "not strong",
}
CATEGORY_ORDER = list(EXPECTED)


def load_pairs() -> list[dict]:
    return json.loads(DATASET.read_text(encoding="utf-8"))["pairs"]


def measure(pairs: list[dict], embedder) -> list[dict]:
    rows = []
    for p in pairs:
        req, ev = embedder.encode([p["requirement"], p["evidence"]])
        sim = cosine_similarity(req, ev)
        score, strength = similarity_to_score(sim, CFG.semantic_lower, CFG.semantic_upper)
        rows.append({**p, "similarity": sim, "score": score, "strength": strength,
                     "verdict": VERDICTS[p["category"]][strength]})
    return rows


def classify_counts(rows: list[dict], lower: float, upper: float) -> dict[str, int]:
    counts = {"ok": 0, "borderline": 0, "wrong": 0}
    for r in rows:
        _, strength = similarity_to_score(r["similarity"], lower, upper)
        counts[VERDICTS[r["category"]][strength]] += 1
    return counts


def render(rows: list[dict]) -> str:
    lines = [
        "# M2 — Semantic calibration results",
        "",
        f"Model: `{CFG.semantic_model_name}` (local, normalized embeddings, cosine similarity).",
        f"Thresholds under test (provisional): L = {CFG.semantic_lower:.2f}, U = {CFG.semantic_upper:.2f}.",
        "Dataset: `calibration/semantic_pairs.json` (fictional). Regenerate with `python -m scripts.calibrate_semantic`.",
        "",
        "Verdict rules: *strong* pairs should be strong (partial = borderline); *partial* pairs should be partial;",
        "*unrelated* pairs should be none (partial = borderline); *related_different* and *keyword_trap* pairs must",
        "not be strong.",
        "",
        "## Per-pair results",
        "",
        "| ID | Category | Expected | Requirement | Evidence | Cosine | Score | Result | Verdict |",
        "|---|---|---|---|---|--:|--:|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['category']} | {EXPECTED[r['category']]} | {r['requirement']} | {r['evidence']} | "
            f"{r['similarity']:.3f} | {r['score']:.2f} | {r['strength']} | {r['verdict']} |"
        )

    lines += ["", "## Per-category similarity", "", "| Category | n | min | mean | max |", "|---|--:|--:|--:|--:|"]
    for cat in CATEGORY_ORDER:
        sims = [r["similarity"] for r in rows if r["category"] == cat]
        lines.append(f"| {cat} | {len(sims)} | {min(sims):.3f} | {statistics.mean(sims):.3f} | {max(sims):.3f} |")

    totals = classify_counts(rows, CFG.semantic_lower, CFG.semantic_upper)
    lines += ["", f"**Current thresholds:** {totals['ok']} ok, {totals['borderline']} borderline, {totals['wrong']} wrong "
              f"out of {len(rows)} pairs.", "", "## Sensitivity (context only — thresholds were not tuned)", "",
              "| L | U | ok | borderline | wrong |", "|--:|--:|--:|--:|--:|"]
    for lower in (0.20, 0.25, 0.30, 0.35):
        for upper in (0.50, 0.55, 0.60, 0.65):
            c = classify_counts(rows, lower, upper)
            mark = " ← current" if (lower, upper) == (CFG.semantic_lower, CFG.semantic_upper) else ""
            lines.append(f"| {lower:.2f} | {upper:.2f} | {c['ok']} | {c['borderline']} | {c['wrong']}{mark} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "M2-calibration-results.md")
    args = parser.parse_args()
    rows = measure(load_pairs(), SentenceTransformerEmbedder())
    report = render(rows)
    args.out.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
