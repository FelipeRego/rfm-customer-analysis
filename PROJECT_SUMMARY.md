# RFM Customer Analysis Pipeline

## Overview

A complete, end-to-end RFM (Recency, Frequency, Monetary) analysis system built in Python, consisting of a core analysis engine and a visualisation layer.

---

## Files

| File | Description |
|---|---|
| `rfm_mockup.csv` | Raw input data — customer transaction records |
| `rfm_analysis.py` | Core analysis engine |
| `rfm_analysis.csv` | Output — scored, segmented, and CLV-enriched customer data |
| `rfm_dashboard.py` | Visualisation layer |
| `rfm_chart_1_segments.png` | Chart: Customers per segment |
| `rfm_chart_2_heatmap.png` | Chart: Avg CLV by R-score × F-score |
| `rfm_chart_3_scatter.png` | Chart: Recency vs Monetary Value |
| `rfm_chart_4_clv_distribution.png` | Chart: CLV distribution per segment |
| `rfm_dashboard.png` | Combined dashboard |

---

## `rfm_analysis.py` — Core Analysis Engine

### RFM Scoring
Each customer is scored 1–5 on all three dimensions:
- **Recency (R):** Percentile-based — lower recency (more recent) scores higher
- **Frequency (F):** Ladder-based — 1 purchase = score 1, 5+ purchases = score 5
- **Monetary (M):** Percentile-based — higher spend scores higher

### Segmentation
11 segments assigned based on R and F score combinations:

| Segment | Description |
|---|---|
| Champions | High R, high F — best customers |
| Loyal | Consistent buyers |
| Potential Loyalist | Recent with moderate frequency |
| Promising | Recent but low frequency |
| New Customer | Very recent, first-time buyers |
| Need Attention | Mid-range R and F |
| About to Sleep | Declining engagement |
| Hibernating | Low recency, low frequency |
| At Risk | Previously frequent, now lapsing |
| Can't Lose Them | High frequency but not recent |
| Lost | Low R, low F |

### CLV Calculation
Customer Lifetime Value estimated as:

```
CLV = (monetaryValue / frequency) × frequency × lifespan_years × margin
```

- **Lifespan:** 3 years
- **Margin:** 20%

### Output
`rfm_analysis.csv` with fields: `customerid`, `recency`, `frequency`, `monetaryValue`, `r_score`, `f_score`, `m_score`, `rfm_score`, `segment`, `clv`

---

## `rfm_dashboard.py` — Visualisation Layer

Four publication-quality charts with a consistent clean style (white background, colour-blind-friendly palette):

### Chart 1 — Customers per Segment (`rfm_chart_1_segments.png`)
Horizontal bar chart ordered by avg CLV, with customer count and inline avg CLV labels per segment.

### Chart 2 — Avg CLV Heatmap (`rfm_chart_2_heatmap.png`)
Heatmap of average CLV across the R-score × F-score grid, using a Blues colour scale with dollar annotations in each cell.

### Chart 3 — Recency vs Monetary Value (`rfm_chart_3_scatter.png`)
Scatter plot of recency (days) vs monetary value ($), coloured and shaped by segment with a legend.

### Chart 4 — CLV Distribution per Segment (`rfm_chart_4_clv_distribution.png`)
Box plot showing the spread and median CLV within each segment, ordered by avg CLV descending.

---

## Configuration

Both scripts expose top-level constants for easy adjustment:

| Constant | Default | Description |
|---|---|---|
| `INPUT_FILE` | `rfm_mockup.csv` | Source data file |
| `OUTPUT_FILE` | `rfm_analysis.csv` | Analysis output file |
| `LIFESPAN_YEARS` | `3` | Assumed customer lifespan for CLV |
| `MARGIN` | `0.20` | Profit margin used in CLV formula |
