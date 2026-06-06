"""
make_figure.py  —  Montevideo benchmark figures
================================================
Generates one two-panel figure per query topology (3 total):
  - Left  : query size sweep  (x = Q nodes; DB=1,000 fixed)
  - Right : DB size sweep     (x = DB nodes; Q=20 fixed)

Each panel has 3 lines (MPJ / MSJ / ESPM).
Timed-out points are plotted at the 1,800 s ceiling with a
downward-triangle marker.

Output:
  benchmark_montevideo/results/fully_connected_figure.png
  benchmark_montevideo/results/scale_free_figure.png
  benchmark_montevideo/results/mesh_figure.png

Run after the DB size sweeps complete (or anytime — missing DB data
is filled with the timeout ceiling automatically).
"""

import io, os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from plotnine import (
    ggplot, aes, geom_line, geom_point,
    scale_y_log10, scale_color_manual, scale_shape_manual,
    labs, theme_bw, theme,
    element_text, element_rect, element_blank, element_line,
)

_here    = os.path.dirname(os.path.abspath(__file__))
_results = os.path.join(_here, "results")
os.makedirs(_results, exist_ok=True)

TIMEOUT_S  = 1800
ALG_COLORS = {'MPJ': '#E41A1C', 'MSJ': '#377EB8', 'ESPM': '#4DAF4A'}

# ── Hardcoded results ─────────────────────────────────────────────────────────
# Source: query_size_sweep.py runs (DB=1,000 fixed, Q varied)
# Source: db_size_50k.py runs    (Q=20 fixed, DB varied)
#
# Format: (x_label, algorithm, time_s, timed_out)
# DB size results marked timed_out=True use TIMEOUT_S as the plotted value.
# Update the DB_DATA tables once the sweeps complete.

FC_QUERY_DATA = [
    ('20', 'MPJ',  1.1618, False), ('20', 'MSJ',  0.8529, False), ('20', 'ESPM', 13.4316, False),
    ('40', 'MPJ',  2.0434, False), ('40', 'MSJ',  1.7036, False), ('40', 'ESPM',  9.2348, False),
    ('60', 'MPJ',  0.3627, False), ('60', 'MSJ',  0.5410, False), ('60', 'ESPM', 10.5668, False),
]
FC_DB_DATA = [
    # filled in after db_size_50k.py completes — update times below
    ('1,000',  'MPJ',  0.5240,    False), ('1,000',  'MSJ',  0.4311,    False), ('1,000',  'ESPM',  6.9196,    False),
    ('10,000', 'MPJ',  TIMEOUT_S, True),  ('10,000', 'MSJ',  None,      False), ('10,000', 'ESPM',  TIMEOUT_S, True),
    ('50,000', 'MPJ',  TIMEOUT_S, True),  ('50,000', 'MSJ',  None,      False), ('50,000', 'ESPM',  TIMEOUT_S, True),
]

SF_QUERY_DATA = [
    ('20', 'MPJ', 0.5563, False), ('20', 'MSJ', 0.2355, False), ('20', 'ESPM', 4.2044, False),
    ('40', 'MPJ', 0.1603, False), ('40', 'MSJ', 0.2026, False), ('40', 'ESPM', 1.0378, False),
    ('60', 'MPJ', 0.3722, False), ('60', 'MSJ', 0.4291, False), ('60', 'ESPM', 0.7618, False),
]
SF_DB_DATA = [
    ('1,000',  'MPJ',  0.2015,    False), ('1,000',  'MSJ',  0.0887,    False), ('1,000',  'ESPM',  3.7051,    False),
    ('10,000', 'MPJ',  TIMEOUT_S, True),  ('10,000', 'MSJ',  None,      False), ('10,000', 'ESPM',  TIMEOUT_S, True),
    ('50,000', 'MPJ',  TIMEOUT_S, True),  ('50,000', 'MSJ',  None,      False), ('50,000', 'ESPM',  TIMEOUT_S, True),
]

MESH_QUERY_DATA = [
    ('20', 'MPJ', 0.6455, False), ('20', 'MSJ', 0.2492, False), ('20', 'ESPM', 1.3816, False),
    ('40', 'MPJ', 0.1852, False), ('40', 'MSJ', 0.2671, False), ('40', 'ESPM', 0.8988, False),
    ('60', 'MPJ', 0.2423, False), ('60', 'MSJ', 0.4149, False), ('60', 'ESPM', 0.7055, False),
]
MESH_DB_DATA = [
    ('1,000',  'MPJ',  0.3514,    False), ('1,000',  'MSJ',  0.1528,    False), ('1,000',  'ESPM',  1.1929,    False),
    ('10,000', 'MPJ',  TIMEOUT_S, True),  ('10,000', 'MSJ',  None,      False), ('10,000', 'ESPM',  TIMEOUT_S, True),
    ('50,000', 'MPJ',  TIMEOUT_S, True),  ('50,000', 'MSJ',  None,      False), ('50,000', 'ESPM',  TIMEOUT_S, True),
]


def _load_db_file(path):
    """
    Parse a db_size_50k.md results table into a dict:
      {(db_label, algo): (time_s, timed_out)}
    Returns empty dict if file missing.
    """
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.startswith("|"):
                continue
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) < 8 or parts[0] in ("DB nodes", "---", ""):
                continue
            try:
                db_label = parts[0].replace(",", "")
                # re-format with commas for display
                db_int   = int(db_label)
                db_str   = f"{db_int:,}"
                for col_algo, col_m, col_t in [
                    ("MPJ", parts[2], parts[3]),
                    ("MSJ", parts[4], parts[5]),
                    ("ESPM", parts[6], parts[7]),
                ]:
                    timed_out = "timeout" in col_m.lower()
                    if timed_out:
                        t = TIMEOUT_S
                    else:
                        t = float(col_t.replace("s", "").strip(">"))
                    out[(db_str, col_algo)] = (t, timed_out)
            except (ValueError, IndexError):
                continue
    return out


def _patch_db_data(raw_data, live):
    """Replace None time_s entries in raw_data with values from live dict."""
    result = []
    for (x, algo, t, to) in raw_data:
        if t is None:
            key = (x, algo)
            if key in live:
                t, to = live[key]
            else:
                t, to = TIMEOUT_S, True
        result.append((x, algo, t, to))
    return result


def _panel(df, title, show_legend):
    return (
        ggplot(df, aes('x_label', 'time_s', color='algorithm', group='algorithm'))
        + geom_line(size=1.1)
        + geom_point(aes(shape='timed_out'), size=4, stroke=0.7)
        + scale_y_log10(
            name='Time (seconds)',
            breaks=[0.01, 0.1, 1, 10, 100, 1000],
            labels=['0.01', '0.1', '1', '10', '100', '1000'],
        )
        + scale_color_manual(name='Algorithm', values=ALG_COLORS)
        + scale_shape_manual(
            name='',
            values={False: 'o', True: 'v'},
            labels={False: 'completed', True: f'timed out  (> {TIMEOUT_S//60} min)'},
        )
        + labs(x='', title=title)
        + theme_bw()
        + theme(
            figure_size=(7, 5),
            plot_title=element_text(size=10, face='bold', ha='center', margin={'b': 8}),
            axis_title_y=element_text(size=11, margin={'r': 8}),
            axis_text_x=element_text(size=9),
            axis_text_y=element_text(size=9),
            legend_position='right' if show_legend else 'none',
            legend_title=element_text(size=10),
            legend_text=element_text(size=9),
            panel_grid_minor=element_blank(),
            panel_grid_major=element_line(color='#dddddd'),
            panel_background=element_rect(fill='white'),
        )
    )


def _to_img(plot):
    buf = io.BytesIO()
    plot.save(buf, format='png', dpi=150, verbose=False)
    buf.seek(0)
    return mpimg.imread(buf)


def make_figure(q_data, db_data_raw, db_file_path, title, out_name):
    # Try to fill in live DB results from file
    live = _load_db_file(db_file_path)
    db_data = _patch_db_data(db_data_raw, live)

    df_q = pd.DataFrame(q_data,  columns=['x_label', 'algorithm', 'time_s', 'timed_out'])
    df_d = pd.DataFrame(db_data, columns=['x_label', 'algorithm', 'time_s', 'timed_out'])

    df_q['x_label'] = pd.Categorical(df_q['x_label'], categories=['20','40','60'], ordered=True)
    df_d['x_label'] = pd.Categorical(df_d['x_label'],
                                      categories=['1,000','10,000','50,000'], ordered=True)

    img1 = _to_img(_panel(df_q, 'Query Size (nodes)\n[DB fixed at 1,000]',            show_legend=False))
    img2 = _to_img(_panel(df_d, 'Database Size (nodes)\n[Query fixed at 20 nodes]',   show_legend=True))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))
    fig.suptitle(f'Montevideo — {title} — Algorithm Timing', fontsize=13, y=1.01)
    ax1.imshow(img1); ax1.axis('off')
    ax2.imshow(img2); ax2.axis('off')
    plt.tight_layout()

    out = os.path.join(_results, out_name)
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'Saved -> {out}')
    return out


if __name__ == '__main__':
    make_figure(
        FC_QUERY_DATA, FC_DB_DATA,
        os.path.join(_here, 'fully_connected', 'results', 'db_size_50k.md'),
        'Fully-Connected Query (190 edges)', 'fully_connected_figure.png',
    )
    make_figure(
        SF_QUERY_DATA, SF_DB_DATA,
        os.path.join(_here, 'scale_free', 'results', 'db_size_50k.md'),
        'Scale-Free Query (BA m=2, 37 edges)', 'scale_free_figure.png',
    )
    make_figure(
        MESH_QUERY_DATA, MESH_DB_DATA,
        os.path.join(_here, 'mesh', 'results', 'db_size_50k.md'),
        'Mesh Query (Ring-Lattice k=4, 40 edges)', 'mesh_figure.png',
    )
