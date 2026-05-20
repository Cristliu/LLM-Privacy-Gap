# TP/TN/FP/FN Definitions for Ground-truth and Post-hoc Matrices

## 1. Ground-truth vs. LLM Pipeline

### 1.1 Binary Confusion Matrices

Applies to:

- `ground-truth_pipeline/concern_detection.csv`
- `ground-truth_pipeline/gap_detection.csv`
- `ground-truth_pipeline/necessity.csv`

| Term | Definition                                                  |
| ---- | ----------------------------------------------------------- |
| TP   | Ground Truth is positive, and the LLM Pipeline is positive. |
| TN   | Ground Truth is negative, and the LLM Pipeline is negative. |
| FP   | Ground Truth is negative, but the LLM Pipeline is positive. |
| FN   | Ground Truth is positive, but the LLM Pipeline is negative. |

### 1.2 Category Assignment Matrices

Applies to:

- `ground-truth_pipeline/topic_coverage.csv`
- `ground-truth_pipeline/gap_types.csv`

These matrices are not ordinary binary confusion matrices. The reported `N` is the number of evaluated samples:

| Matrix                 | Meaning of `N`                                                     |
| ---------------------- | -------------------------------------------------------------------- |
| `topic_coverage.csv` | Number of records where Ground Truth has `concern_detection=True`. |
| `gap_types.csv`      | Number of Ground Truth concern instances where `necessity=True`.   |

The TP/FP/FN counts are computed after expanding each evaluated sample into category label events.

| Term | Definition                                                                              |
| ---- | --------------------------------------------------------------------------------------- |
| TP   | The category appears in both Ground Truth and the LLM Pipeline.                         |
| FP   | The category appears only in the LLM Pipeline.                                          |
| FN   | The category appears only in Ground Truth.                                              |
| TN   | N/A. Categories absent from both sides are not counted as meaningful negative evidence. |

Why TN is marked as `N/A` here:

- Counting TN would require treating every category that neither side selected as a negative event.
- This negative space is large and depends on the chosen category universe, so it can dominate the table without reflecting extraction quality.
- Therefore, the original metric report computes precision, recall, and F1 from TP/FP/FN only.

Precision, recall, and F1 are computed from the expanded label-event counts:

```text
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * Precision * Recall / (Precision + Recall)
```

## 2. Post-hoc Expert Review

### 2.1 Binary Expert Agreement Matrices

Applies to binary accepted/rejected expert-review comparisons.

| Term | Definition                                                        |
| ---- | ----------------------------------------------------------------- |
| TP   | Expert 1 is positive/accepted, and Expert 2 is positive/accepted. |
| TN   | Expert 1 is negative/rejected, and Expert 2 is negative/rejected. |
| FP   | Expert 1 is negative/rejected, but Expert 2 is positive/accepted. |
| FN   | Expert 1 is positive/accepted, but Expert 2 is negative/rejected. |
