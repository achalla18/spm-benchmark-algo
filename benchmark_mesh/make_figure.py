"""
make_figure.py  —  Mesh query benchmark figure
Saves to: results/mesh_figure.png
"""

import os
import pandas as pd
from plotnine import (
    ggplot, aes, geom_line, geom_point,
    scale_y_log10, scale_color_manual, scale_shape_manual,
    facet_wrap, labs, theme_bw, theme,
    element_text, element_rect, element_blank, element_line,
)

_here = os.path.dirname(os.path.abspath(__file__))
_results = os.path.normpath(os.path.join(_here, '..', 'results'))

TIMEOUT_S = 1800

# ── Data ──────────────────────────────────────────────────────────────────────

# Query size sweep  (DB=1,000 fixed, Q varied)
QUERY_DATA = [
    ('20',  'MPJ',  0.1770,  False),
    ('20',  'MSJ',  0.0654,  False),
    ('20',  'ESPM', 0.6008,  False),
    ('40',  'MPJ',  0.0747,  False),
    ('40',  'MSJ',  0.0965,  False),
    ('40',  'ESPM', 0.3653,  False),
    ('60',  'MPJ',  0.1206,  False),
    ('60',  'MSJ',  0.1973,  False),
    ('60',  'ESPM', 0.3957,  False),
]

# DB size sweep  (Q=20 fixed, DB varied)
DB_DATA = [
    ('1,000',   'MPJ',   0.1920,    False),
    ('1,000',   'MSJ',   0.0661,    False),
    ('1,000',   'ESPM',  0.6215,    False),
    ('10,000',  'MPJ',   TIMEOUT_S, True),
    ('10,000',  'MSJ',  32.3728,    False),
    ('10,000',  'ESPM',  TIMEOUT_S, True),
    ('50,000',  'MPJ',   TIMEOUT_S, True),
    ('50,000',  'MSJ',  199.5623,   False),
    ('50,000',  'ESPM',  TIMEOUT_S, True),
]

# ── Build dataframe ────────────────────────────────────────────────────────────

df_q = pd.DataFrame(QUERY_DATA,  columns=['x_label', 'algorithm', 'time_s', 'timed_out'])
df_q['panel'] = 'Query Size (nodes)\n[DB fixed at 1,000]'

df_d = pd.DataFrame(DB_DATA, columns=['x_label', 'algorithm', 'time_s', 'timed_out'])
df_d['panel'] = 'Database Size (nodes)\n[Query fixed at 20 nodes, 40 edges]'

df = pd.concat([df_q, df_d], ignore_index=True)

x_order     = ['20', '40', '60', '1,000', '10,000', '50,000']
panel_order = [
    'Query Size (nodes)\n[DB fixed at 1,000]',
    'Database Size (nodes)\n[Query fixed at 20 nodes, 40 edges]',
]
df['x_label'] = pd.Categorical(df['x_label'], categories=x_order, ordered=True)
df['panel']   = pd.Categorical(df['panel'],   categories=panel_order, ordered=True)

# ── Plot ───────────────────────────────────────────────────────────────────────

ALG_COLORS = {'MPJ': '#E41A1C', 'MSJ': '#377EB8', 'ESPM': '#4DAF4A'}

p = (
    ggplot(df, aes(x='x_label', y='time_s', color='algorithm', group='algorithm'))
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
    + labs(x='', title='Mesh Query (Ring-Lattice k=4) — Algorithm Timing')
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

out_path = os.path.join(_results, 'mesh_figure.png')
p.save(out_path, dpi=150, verbose=False)
print(f'Saved -> {out_path}')
