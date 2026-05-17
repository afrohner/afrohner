#%%

import shutil
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# FRED CSV for the CBOE VIX series (daily closes)
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"
# Where to save the cleaned VIX history on this machine
OUTPUT_FILE = r"C:\Users\andre\Downloads\vix_close.csv"
# Where to save the 2x2 chart image
CHART_FILE = r"C:\Users\andre\Downloads\vix_dashboard.png"
HTML_FILE = r"C:\Users\andre\Downloads\vix_dashboard_dynamic.html"
# Rolling window for the average and standard deviation bands
ROLLING_WINDOW = 20


def fetch_fred():
    df = pd.read_csv(FRED_CSV_URL)

    # Normalize column names to lower case so we can handle DATE vs observation_date
    cols = {c.lower().strip(): c for c in df.columns}
    date_col = cols.get("date") or cols.get("observation_date")
    value_col = cols.get("vixcls")

    # Fail fast if FRED ever changes the header names unexpectedly
    if not date_col or not value_col:
        raise RuntimeError(f"Unexpected FRED columns: {list(df.columns)}")

    # Keep only the date and VIX close columns, and rename for consistency
    out = df[[date_col, value_col]].copy()
    out.columns = ["date", "close"]

    # Convert to proper date/float types and drop any bad rows
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")

    out = out.dropna(subset=["date", "close"]).sort_values("date")
    return out


def add_bands(df, window=ROLLING_WINDOW):
    # Calculate the rolling mean and rolling standard deviation
    out = df.copy()
    out["ma"] = out["close"].rolling(window).mean()
    out["std"] = out["close"].rolling(window).std()

    # Create upper and lower 2-standard-deviation bands
    out["upper"] = out["ma"] + 2 * out["std"]
    out["lower"] = out["ma"] - 2 * out["std"]
    return out


def write_output(df, output_path):
    output_path = Path(output_path).expanduser()
    # Make sure the folder exists before we try to write the file
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Format dates as YYYY-MM-DD strings for a clean CSV
    df2 = df.copy()
    df2["date"] = df2["date"].dt.strftime("%Y-%m-%d")

    # Write to a temporary file first, then atomically move into place
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    df2.to_csv(tmp, index=False)
    shutil.move(str(tmp), str(output_path))


def add_panel(fig, data, row, col):
    show_legend = row == 1 and col == 1

    # Upper band line
    fig.add_trace(
        go.Scatter(
            x=data["date"],
            y=data["upper"],
            mode="lines",
            name="+2 SD",
            line=dict(color="#94a3b8", width=1),
            showlegend=show_legend,
        ),
        row=row,
        col=col,
    )

    # Lower band line and shaded area between the bands
    fig.add_trace(
        go.Scatter(
            x=data["date"],
            y=data["lower"],
            mode="lines",
            name="-2 SD",
            line=dict(color="#94a3b8", width=1),
            fill="tonexty",
            fillcolor="rgba(148,163,184,0.18)",
            showlegend=show_legend,
        ),
        row=row,
        col=col,
    )

    # Rolling average line
    fig.add_trace(
        go.Scatter(
            x=data["date"],
            y=data["ma"],
            mode="lines",
            name="20D Avg",
            line=dict(color="#f5900b", width=1.5, dash="dot"),
            showlegend=show_legend,
        ),
        row=row,
        col=col,
    )

    # Actual VIX close line
    fig.add_trace(
        go.Scatter(
            x=data["date"],
            y=data["close"],
            mode="lines",
            name="VIX",
            line=dict(color="black", width=2.2),
            showlegend=show_legend,
        ),
        row=row,
        col=col,
    )

    fig.update_xaxes(
    title_text="",
    title_font=dict(color="black"),
    tickfont=dict(color="black"),
    row=row,
    col=col
    )

    fig.update_yaxes(
    title_text="",
    title_font=dict(color="black"),
    tickfont=dict(color="black"),
    row=row,
    col=col
    )

    # fig.update_xaxes(title_text="Date", row=row, col=col)
    # fig.update_yaxes(title_text="VIX", row=row, col=col)

def add_panel_with_visibility(fig, data, row, col, visible):
    for yvals, name, line_dict, fill, fillcolor in [
        (data["upper"], "+2 SD", dict(color="#94a3b8", width=1), None, None),
        (data["lower"], "-2 SD", dict(color="#94a3b8", width=1), "tonexty", "rgba(148,163,184,0.18)"),
        (data["ma"], "20D Avg", dict(color="#f5900b", width=1.5, dash="dot"), None, None),
        (data["close"], "VIX", dict(color="black", width=2.2), None, None),
    ]:
        fig.add_trace(
            go.Scatter(
                x=data["date"],
                y=yvals,
                mode="lines",
                name=name,
                line=line_dict,
                fill=fill,
                fillcolor=fillcolor,
                showlegend=False,
                visible=visible,
            ),
            row=row,
            col=col,
        )

    fig.update_xaxes(
        title_text="",
        tickfont=dict(color="black"),
        row=row,
        col=col,
    )

    fig.update_yaxes(
        title_text="",
        tickfont=dict(color="black"),
        row=row,
        col=col,
    )

def build_chart_grid(df, output_path):
    output_path = Path(output_path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    periods = [
        (21, "1 month"),
        (63, "3 months"),
        (126, "6 months"),
        (252, "1 year"),
    ]

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[label for _, label in periods],
        horizontal_spacing=0.08,
        vertical_spacing=0.14,
    )

    fig.for_each_annotation(
    lambda a: a.update(
        text=f"<b><u>{a.text}</u></b>",
        font=dict(color="black", size=18)
    )
    )

    positions = [(1, 1), (1, 2), (2, 1), (2, 2)]
    for (days, _label), (row, col) in zip(periods, positions):
        panel = df.tail(days).copy()
        add_panel(fig, panel, row, col)

    fig.update_layout(
        title=(
            "<b>VIX with ±2 SD bands (1M, 3M, 6M, 1Y)<b><br>"
            "<span style='font-size: 12px;'>Source: FRED | 20dma & standard deviation</span>"
        ),
        # legend=dict(
        #    orientation="v",
        #    yanchor="top",
        #    y=.99,
        #    xanchor="right",
        #    x=.99,
        #),
        showlegend=False,
        template="plotly_white",
        width=1600,
        height=1100,
    )

   
    
    # Requires kaleido for PNG export: pip install kaleido
    fig.write_image(str(output_path))

def build_dynamic_html(df, output_path):
    output_path = Path(output_path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    month_periods = [
        (21, "1 month"),
        (63, "3 months"),
        (126, "6 months"),
        (252, "1 year"),
    ]

    week_periods = [
        (5, "1 week"),
        (15, "3 weeks"),
        (25, "5 weeks"),
        (50, "10 weeks"),
    ]

    positions = [(1, 1), (1, 2), (2, 1), (2, 2)]

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[label for _, label in month_periods],
        horizontal_spacing=0.08,
        vertical_spacing=0.14,
    )

    fig.for_each_annotation(
        lambda a: a.update(
            text=f"<b><u>{a.text}</u></b>",
            font=dict(color="black", size=18)
        )
    )

    # First 16 traces = monthly view, visible at startup
    for (days, _label), (row, col) in zip(month_periods, positions):
        panel = df.tail(days).copy()
        add_panel_with_visibility(fig, panel, row, col, True)

    # Next 16 traces = weekly view, hidden at startup
    for (days, _label), (row, col) in zip(week_periods, positions):
        panel = df.tail(days).copy()
        add_panel_with_visibility(fig, panel, row, col, False)

    visible_months = [True] * 16 + [False] * 16
    visible_weeks = [False] * 16 + [True] * 16

    month_titles = [f"<b><u>{label}</u></b>" for _, label in month_periods]
    week_titles = [f"<b><u>{label}</u></b>" for _, label in week_periods]

    fig.update_layout(
        title=(
            "<b>VIX with ±2 SD bands</b><br>"
            "<span style='font-size: 12px;'>Source: FRED | 20dma & standard deviation</span>"
        ),
        showlegend=False,
        template="plotly_white",
        width=1600,
        height=1100,
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                x=0.5,
                y=1.12,
                xanchor="center",
                yanchor="top",
                buttons=[
                    dict(
                        label="Monthly view",
                        method="update",
                        args=[
                            {"visible": visible_months},
                            {"annotations": [
                                {**a.to_plotly_json(), "text": t}
                                for a, t in zip(fig.layout.annotations, month_titles)]},
                                                    ],),
                    dict(
                        label="Weekly view",
                        method="update",
                        args=[
                            {"visible": visible_weeks},
                            {"annotations": [
                                {**a.to_plotly_json(), "text": t}
                                for a, t in zip(fig.layout.annotations, week_titles)]},
                        ],
                    ),
                ],
            )
        ],
    )

    fig.write_html(str(output_path), include_plotlyjs=True)


def main():
    try:
        df = fetch_fred()
        df = add_bands(df)
        write_output(df, OUTPUT_FILE)
        build_chart_grid(df, CHART_FILE)
        build_dynamic_html(df, HTML_FILE)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    latest = df.iloc[-1]
    print(f"Saved {len(df):,} rows to {OUTPUT_FILE}")
    print(f"Latest close: {latest['date'].date()} = {latest['close']}")
    print(f"Saved chart grid to {CHART_FILE}")
    print(f"Saved dynamic HTML to {HTML_FILE}")

if __name__ == "__main__":
    main()