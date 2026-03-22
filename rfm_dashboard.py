import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.lines as mlines
import seaborn as sns
import pandas as pd
import numpy as np

# ── CONFIG ────────────────────────────────────────────────────────────────────
INPUT_FILE   = 'rfm_analysis.csv'
DASHBOARD_FILE = 'rfm_dashboard.png'

SEGMENT_STYLES = {
    'Champions':          {'color': '#0072B2', 'marker': 'o'},
    'Loyal':              {'color': '#009E73', 'marker': 's'},
    'Potential Loyalist': {'color': '#E69F00', 'marker': '^'},
    'Promising':          {'color': '#56B4E9', 'marker': 'D'},
    'Hibernating':        {'color': '#CC79A7', 'marker': 'P'},
    'Lost':               {'color': '#999999', 'marker': 'X'},
    'New Customer':       {'color': '#D55E00', 'marker': '*'},
}

BG          = '#FFFFFF'
SPINE_COLOR = '#CCCCCC'
TEXT_DARK   = '#111111'
TEXT_MID    = '#444444'

# ── LOAD ──────────────────────────────────────────────────────────────────────
df = pd.read_csv(INPUT_FILE)

segment_order = list(dict(sorted(
    df.groupby('segment')['clv'].mean().items(), key=lambda x: -x[1]
)).keys())

plt.rcParams.update({
    'font.family':      'DejaVu Sans',
    'text.color':       TEXT_DARK,
    'axes.labelcolor':  TEXT_MID,
    'xtick.color':      TEXT_MID,
    'ytick.color':      TEXT_MID,
    'axes.facecolor':   BG,
    'figure.facecolor': BG,
    'xtick.labelsize':  10,
    'ytick.labelsize':  10,
    'axes.labelsize':   11,
})

def clean_axes(ax, keep_left=True):
    ax.grid(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(SPINE_COLOR if keep_left else 'none')
    ax.spines['bottom'].set_color(SPINE_COLOR)
    ax.tick_params(axis='both', length=0)

def save(fig, name):
    fig.savefig(name, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    print(f'Saved: {name}')

# ── 1. HORIZONTAL BAR ─────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 6))
seg_summary = df.groupby('segment').agg(
    count=('customerid', 'count'), avg_clv=('clv', 'mean')
).reindex(reversed(segment_order))
y         = np.arange(len(seg_summary))
colors    = [SEGMENT_STYLES[s]['color'] for s in reversed(segment_order)]
max_count = seg_summary['count'].max()

ax.barh(y, seg_summary['count'], color=colors, edgecolor='none', height=0.55)
for i, (count, clv) in enumerate(zip(seg_summary['count'], seg_summary['avg_clv'])):
    ax.text(count + 0.4, i, str(count),
            va='center', ha='left', fontsize=10, color=TEXT_DARK, fontweight='bold')
    ax.text(count - 0.4, i, f'Avg CLV: ${clv:,.0f}',
            va='center', ha='right', fontsize=9, color='white', fontweight='bold')
ax.set_yticks(y)
ax.set_yticklabels(list(reversed(segment_order)), fontsize=10)
ax.set_xlim(0, max_count + 8)
ax.set_xlabel('Number of Customers')
ax.set_title('Customers per Segment', fontsize=13, fontweight='bold',
             color=TEXT_DARK, pad=12, loc='left')
clean_axes(ax, keep_left=False)
ax.spines['left'].set_visible(False)
ax.set_xticks([])
plt.tight_layout()
save(fig, 'rfm_chart_1_segments.png')

# ── 2. HEATMAP ────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 6))
heatmap_data = df.groupby(['r_score', 'f_score'])['clv'].mean().unstack(fill_value=np.nan)
heatmap_data = heatmap_data.sort_index(ascending=False)
annot = heatmap_data.copy().astype(object)
for i in range(annot.shape[0]):
    for j in range(annot.shape[1]):
        v = heatmap_data.iloc[i, j]
        annot.iloc[i, j] = f'${v:,.0f}' if not np.isnan(v) else '—'
mask = heatmap_data.isna()
sns.heatmap(heatmap_data, ax=ax, annot=annot, fmt='', mask=mask,
            cmap='Blues', linewidths=1, linecolor=BG,
            cbar_kws={'label': 'Avg CLV ($)', 'shrink': 0.8},
            annot_kws={'fontsize': 9.5, 'color': TEXT_DARK})
sns.heatmap(heatmap_data, ax=ax, mask=~mask, cmap=['#F0F0F0'],
            linewidths=1, linecolor=BG, cbar=False, annot=annot,
            fmt='', annot_kws={'fontsize': 10, 'color': '#AAAAAA'})
ax.set_title('Avg CLV by Recency × Frequency Score', fontsize=13,
             fontweight='bold', color=TEXT_DARK, pad=12, loc='left')
ax.set_xlabel('F Score (Frequency)')
ax.set_ylabel('R Score (Recency)')
ax.tick_params(left=False, bottom=False)
for sp in ax.spines.values():
    sp.set_visible(False)
plt.tight_layout()
save(fig, 'rfm_chart_2_heatmap.png')

# ── 3. SCATTER ────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 6))
for seg in segment_order:
    sub   = df[df['segment'] == seg]
    style = SEGMENT_STYLES[seg]
    ax.scatter(sub['recency'], sub['monetaryValue'],
               color=style['color'], marker=style['marker'],
               alpha=0.85, edgecolors='white', linewidth=0.4,
               s=80, zorder=3, label=seg)
ax.set_xlabel('Recency (days)')
ax.set_ylabel('Monetary Value ($)')
ax.set_title('Recency vs Monetary Value', fontsize=13, fontweight='bold',
             color=TEXT_DARK, pad=12, loc='left')
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'${v:,.0f}'))
handles = [
    mlines.Line2D([], [], color=SEGMENT_STYLES[s]['color'],
                  marker=SEGMENT_STYLES[s]['marker'], linestyle='None',
                  markersize=8, label=s)
    for s in segment_order
]
ax.legend(handles=handles, fontsize=9, frameon=False, loc='upper right', labelspacing=0.5)
clean_axes(ax)
plt.tight_layout()
save(fig, 'rfm_chart_3_scatter.png')

# ── 4. BOX PLOT ───────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 6))
df['seg_cat'] = pd.Categorical(df['segment'], categories=segment_order, ordered=True)
palette = {s: SEGMENT_STYLES[s]['color'] for s in segment_order}
sns.boxplot(data=df.sort_values('seg_cat'), x='seg_cat', y='clv', ax=ax,
            hue='seg_cat', palette=palette, order=segment_order,
            legend=False, linewidth=1.2, width=0.55,
            flierprops=dict(marker='o', markersize=4, alpha=0.5,
                            markerfacecolor=TEXT_MID, linestyle='none'))
ax.set_xticks(range(len(segment_order)))
ax.set_xticklabels(segment_order, rotation=35, ha='right', fontsize=10)
ax.set_xlabel('')
ax.set_ylabel('CLV ($)')
ax.set_title('CLV Distribution per Segment', fontsize=13, fontweight='bold',
             color=TEXT_DARK, pad=12, loc='left')
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'${v:,.0f}'))
clean_axes(ax)
plt.tight_layout()
save(fig, 'rfm_chart_4_clv_distribution.png')
