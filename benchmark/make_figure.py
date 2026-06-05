"""
make_figure.py
==============
Standalone plotting script — just run it, no arguments needed.

Two-panel figure (plotnine):
  Left  : query size sweep  — x = query nodes (20, 40, 60), DB fixed at 1,000
  Right : DB size sweep     — x = DB nodes (1,000 / 10,000), Q fixed at 20

Y-axis: time in seconds, log scale.
Timed-out points (> 30 min) are plotted at the 1,800 s ceiling with a
downward-triangle marker.

Output: benchmark/results_figure.png
"""

import os
import pandas as pd
from plotnine import (
    ggplot, aes,
    geom_line, geom_point,
    scale_y_log10,
    scale_color_manual, scale_shape_manual,
    facet_wrap,
    labs, theme_bw, theme,
    element_text, element_rect, element_blank, element_line,
)

_here = os.path.dirname(os.path.abspath(__file__))

TIMEOUT_S = 1800   # 30-minute ceiling

# ── Hardcoded results ─────────────────────────────────────────────────────────

# Query size sweep  (DB = 1,000 fixed, Q varied)
# Source: benchmark/results/query_size_sweep.md
QUERY_DATA = [
    #  Q    algo    time_s   timed_out
    ('20',  'MPJ',   0.8065,  False),
    ('20',  'MSJ',   0.4742,  False),
    ('20',  'ESPM',  9.5500,  False),
    ('40',  'MPJ',   1.9226,  False),
    ('40',  'MSJ',   1.7922,  False),
    ('40',  'ESPM', 10.1648,  False),
    ('60',  'MPJ',   0.6441,  False),
    ('60',  'MSJ',   0.9549,  False),
    ('60',  'ESPM', 16.0021,  False),
]

# DB size sweep  (Q = 20 fixed, DB varied)
# Source: benchmark/results/db_size_results.md
DB_DATA = [
    #  DB nodes   algo    time_s       timed_out
    ('1,000',   'MPJ',   0.8683,       False),
    ('1,000',   'MSJ',   1.5290,       False),
    ('1,000',   'ESPM',  6.3224,       False),
    ('10,000',  'MPJ',   TIMEOUT_S,    True),
    ('10,000',  'MSJ',  71.8108,       False),
    ('10,000',  'ESPM',  TIMEOUT_S,    True),
]

# ── Build dataframe ───────────────────────────────────────────────────────────

df_q = pd.DataFrame(QUERY_DATA,  columns=['x_label', 'algorithm', 'time_s', 'timed_out'])
df_q['panel'] = 'Query Size (nodes)\n[DB fixed at 1,000]'

df_d = pd.DataFrame(DB_DATA, columns=['x_label', 'algorithm', 'time_s', 'timed_out'])
df_d['panel'] = 'Database Size (nodes)\n[Query fixed at 20 nodes]'

df = pd.concat([df_q, df_d], ignore_index=True)

x_order     = ['20', '40', '60', '1,000', '10,000']
panel_order = [
    'Query Size (nodes)\n[DB fixed at 1,000]',
    'Database Size (nodes)\n[Query fixed at 20 nodes]',
]

df['x_label'] = pd.Categorical(df['x_label'], categories=x_order, ordered=True)
df['panel']   = pd.Categorical(df['panel'],   categories=panel_order, ordered=True)

# ── Plot ──────────────────────────────────────────────────────────────────────

ALG_COLORS = {'MPJ': '#E41A1C', 'MSJ': '#377EB8', 'ESPM': '#4DAF4A'}

p = (
    ggplot(df, aes(x='x_label', y='time_s',
                   color='algorithm', group='algorithm'))
    + geom_line(size=1.1)
    + geom_point(aes(shape='timed_out'), size=4, stroke=0.7)
    + scale_y_log10(
        name='Time (seconds)',
        breaks=[0.1, 1, 10, 100, 1000],
        labels=['0.1', '1', '10', '100', '1000'],
    )
    + scale_color_manual(name='Algorithm', values=ALG_COLORS)
    + scale_shape_manual(
        name='',
        values={False: 'o', True: 'v'},
        labels={False: 'completed', True: 'timed out  (> 30 min)'},
    )
    + facet_wrap('~ panel', scales='free_x', nrow=1)
    + labs(x='', title='SPMBench — Algorithm Timing by Query Size and Database Size')
    + theme_bw()
    + theme(
        figure_size=(12, 5),
        plot_title=element_text(size=12, ha='center', margin={'b': 12}),
        strip_background=element_rect(fill='#f2f2f2'),
        strip_text=element_text(size=10, face='bold'),
        axis_title_y=element_text(size=11, margin={'r': 8}),
        axis_text_x=element_text(size=9),
        axis_text_y=element_text(size=9),
        legend_position='right',
        legend_title=element_text(size=10),
        legend_text=element_text(size=9),
        panel_grid_minor=element_blank(),
        panel_grid_major=element_line(color='#dddddd'),
        panel_spacing=0.4,
    )
)

out_path = os.path.join(_here, 'results_figure.png')
p.save(out_path, dpi=150, verbose=False)
print(f'Saved -> {out_path}')
