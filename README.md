# RFM Customer Analysis

A lightweight, dependency-minimal Python pipeline that scores customers using **Recency, Frequency, and Monetary (RFM)** analysis, segments them into 11 behavioural groups, estimates **Customer Lifetime Value (CLV)**, and produces a set of publication-quality charts.

---

## What It Does

1. **Scores** each customer 1–5 across R, F, and M dimensions
2. **Segments** customers into 11 groups (Champions, Loyal, At Risk, Lost, etc.)
3. **Estimates CLV** using a configurable lifespan and margin
4. **Visualises** the results across four charts

---

## Project Structure

```
.
├── rfm_mockup.csv                  # Sample input data
├── rfm_analysis.py                 # Core scoring, segmentation & CLV engine
├── rfm_analysis.csv                # Output: enriched customer data
├── rfm_dashboard.py                # Chart generation
├── rfm_chart_1_segments.png        # Customers per segment
├── rfm_chart_2_heatmap.png         # Avg CLV by R × F score
├── rfm_chart_3_scatter.png         # Recency vs Monetary Value
├── rfm_chart_4_clv_distribution.png# CLV distribution per segment
└── rfm_dashboard.png               # Combined dashboard
```

---

## Quickstart

### 1. Install dependencies

The analysis script uses only the Python standard library. The dashboard requires:

```bash
pip install matplotlib seaborn pandas numpy
```

### 2. Prepare your data

Your input CSV must have these columns:

| Column | Type | Description |
|---|---|---|
| `customerid` | string | Unique customer identifier |
| `recency` | int | Days since last purchase |
| `frequency` | int | Number of purchases |
| `monetaryValue` | float | Total spend |

### 3. Run the analysis

```bash
python rfm_analysis.py
```

Outputs `rfm_analysis.csv` with scores, segments, and CLV for each customer.

### 4. Generate charts

```bash
python rfm_dashboard.py
```

Saves four PNG charts to the working directory.

---

## Segmentation Logic

Segments are assigned based on R and F score combinations:

| Segment | Criteria |
|---|---|
| Champions | R ≥ 4 and F ≥ 4 |
| Loyal | F ≥ 3 and R ≥ 2 |
| Potential Loyalist | R ≥ 3 and F = 2 |
| Promising | R ≥ 3 and F = 1 |
| New Customer | R ≥ 4 and F = 1 |
| Need Attention | R = 3 and F in {2, 3} |
| About to Sleep | R = 2 and F = 2 |
| Hibernating | R = 2 and F = 1 |
| At Risk | R ≤ 2 and F ≥ 3 |
| Can't Lose Them | R = 1 and F ≥ 4 |
| Lost | R = 1 and F ≤ 2 |

---

## CLV Formula

```
CLV = avg_order_value × frequency × lifespan_years × margin
```

Default configuration (editable at the top of `rfm_analysis.py`):

| Parameter | Default |
|---|---|
| `LIFESPAN_YEARS` | 3 |
| `MARGIN` | 0.20 (20%) |

---

## Charts

### Customers per Segment
Horizontal bar ordered by avg CLV, with customer count and inline avg CLV labels.

![Customers per Segment](rfm_chart_1_segments.png)

### Avg CLV Heatmap
Average CLV across the R-score × F-score grid.

![CLV Heatmap](rfm_chart_2_heatmap.png)

### Recency vs Monetary Value
Scatter plot coloured and shaped by segment.

![Scatter](rfm_chart_3_scatter.png)

### CLV Distribution per Segment
Box plot showing CLV spread within each segment.

![CLV Distribution](rfm_chart_4_clv_distribution.png)

---

## License

MIT
