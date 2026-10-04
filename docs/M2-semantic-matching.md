# M2 — Semantic matching & threshold calibration

## How it works

1. **Only `text` criteria** are routed to `SemanticCriterionScorer` (`app/services/scoring/text.py`).
   It returns a result for that one criterion, so it cannot change budget, duration, experience or
   technology results, nor any other criterion's hard-requirement outcome.
2. **Requirement text** = the criterion's `description` (the name is only a label).
3. **Evidence chunks** = the vendor's proposal text and each previous-project entry, split into
   sentences (newlines and bullets also split; `e.g.`, `Node.js` etc. do not).
4. All texts are embedded locally with `all-MiniLM-L6-v2` (normalized). The best sentence by
   cosine similarity `σ` is the evidence; ties go to the earliest sentence.
5. Score ramp (provisional constants in `ScoringConfig`):

```
σ ≤ L (0.30)       → score 0, "none",    status fail     (hard text criterion → hard failure)
L < σ < U (0.60)   → score (σ − L)/(U − L), "partial", status warning
σ ≥ U              → score 1, "strong",  status pass
no proposal text   → score 0, status missing
```

Every result carries: requirement text, matched sentence + source, raw cosine, normalized score,
strength, thresholds used, status, a short summary and a full explanation.

## Calibration

Dataset: `calibration/semantic_pairs.json` — 33 fictional pairs in five categories, written to be
representative, not derived from the demo vendors. Full per-pair table:
[M2-calibration-results.md](M2-calibration-results.md) (regenerate with
`python -m scripts.calibrate_semantic`).

| Category | n | min | mean | max | Outcome at L=0.30 / U=0.60 |
|---|--:|--:|--:|--:|---|
| strong | 9 | 0.378 | 0.509 | 0.660 | 1 strong, 8 partial (scores 0.26–0.90), 0 none |
| partial | 7 | 0.147 | 0.359 | 0.534 | 5 partial, 2 none |
| unrelated | 5 | −0.035 | 0.043 | 0.108 | all none |
| related_different | 6 | 0.149 | 0.198 | 0.285 | all none |
| keyword_trap | 6 | 0.274 | 0.482 | 0.690 | 1 strong (negation), 4 partial, 1 none |

### Findings

- **L = 0.30 separates well.** Every unrelated (max 0.108) and every "related but different"
  pair (max 0.285) falls below it; every strong pair (min 0.378) is above it.
- **U = 0.60 is conservative.** MiniLM rarely exceeds 0.60 even for clear paraphrases (strong
  mean 0.509), so genuine matches usually receive partial credit (≈ 0.5–0.9) rather than full
  credit. Both spec examples (e-commerce ↔ "online retail platforms" 0.504, payments ↔ "Stripe,
  PayPal and Adyen" 0.507) are *partial*, ≈ 0.68 score.
- **Strong matches and keyword traps overlap** (means 0.509 vs 0.482). No choice of U separates
  them: lowering U to 0.50–0.55 turns a keyword trap (K3, "team members use iOS and Android
  phones", 0.570) into a full-score match and raises the wrong count from 1 to 2.
- **Negation is not understood** (K1, "We have *no* previous e-commerce experience", 0.690 →
  strong). This is a known limitation of bi-encoder sentence embeddings, not a threshold issue.
  The evidence sentence is shown verbatim, so a reader sees it immediately.

### Decision

**Keep L = 0.30 and U = 0.60** (unchanged). Calibration shows no change that clearly improves
results: lowering U makes keyword traps score fully, and the strong/trap overlap is inherent to the
model. A conservative U fits the principle that semantic similarity is supplementary — it rarely
awards full credit, and structured/hard criteria remain decisive.

Caveats: the dataset is small (33 pairs) and hand-written; the thresholds remain provisional
calibration constants, not validated values.

## Tests

- `tests/unit/test_semantic_matcher.py`, `tests/unit/test_text_scoring.py` — fake embedders
  (`tests/fakes.py`), no torch, run by default.
- `tests/model/test_semantic_model.py` — real MiniLM, marked `model`, excluded by default.
  Run with `pytest -m model`. Skipped automatically if the model cannot be loaded.
