import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_DARK = {
    "bg": "rgba(0,0,0,0)",
    "card": "rgba(0,0,0,0)",
    "border": "#2a2d3e",
    "green": "#00c896",
    "yellow": "#f5c842",
    "red": "#ff5c5c",
    "blue": "#4f8ef7",
    "text": "#e8eaf0",
    "muted": "#7b7f9e",
    "band_line": "rgba(79,142,247,0.30)",
}

_LIGHT = {
    "bg": "rgba(0,0,0,0)",
    "card": "rgba(0,0,0,0)",
    "border": "#dde1ee",
    "green": "#00a87a",
    "yellow": "#c49000",
    "red": "#d63c3c",
    "blue": "#2563eb",
    "text": "#1a1d27",
    "muted": "#6b7280",
    "band_line": "rgba(37,99,235,0.30)",
}

PALETTE = _DARK.copy()


def set_theme(is_dark: bool):
    global PALETTE
    PALETTE = (_DARK if is_dark else _LIGHT).copy()


def _prob_color(p: float) -> str:
    if p >= 0.70:
        return PALETTE["green"]
    if p >= 0.40:
        return PALETTE["yellow"]
    return PALETTE["red"]


def _base_layout(**kwargs) -> dict:
    base = dict(
        paper_bgcolor=PALETTE["bg"],
        plot_bgcolor=PALETTE["card"],
        font=dict(family="Inter, sans-serif", color=PALETTE["text"], size=12),
        margin=dict(l=40, r=24, t=40, b=40),
    )
    base.update(kwargs)
    return base


def fan_chart(
    percentiles: dict,
    years_range: list[int],
    goal_markers: list[tuple[int, str]],  # [(year, label), ...]
    current_age: int = 0,
) -> go.Figure:
    fig = go.Figure()

    x = years_range

    # Shaded bands (outer first so they layer correctly)
    band_pairs = [(10, 90), (25, 75)]
    opacities = ["rgba(79,142,247,0.07)", "rgba(79,142,247,0.13)"]
    for (lo, hi), fill_color in zip(band_pairs, opacities):
        fig.add_trace(go.Scatter(
            x=x + x[::-1],
            y=list(percentiles[hi]) + list(percentiles[lo])[::-1],
            fill="toself",
            fillcolor=fill_color,
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
        ))

    # Percentile lines — include age in hover if current_age provided
    age_suffix = ""
    for pct, dash, width, label in [
        (10, "dot", 1, "10th"),
        (90, "dot", 1, "90th"),
        (25, "dash", 1.2, "25th"),
        (75, "dash", 1.2, "75th"),
        (50, "solid", 2.5, "Median"),
    ]:
        color = PALETTE["blue"] if pct == 50 else PALETTE["band_line"]
        if current_age:
            hover = (
                "<b>%{x}</b>  (Age " +
                "<b>%{customdata}</b>)<br>" +
                f"{label}: $%{{y:,.0f}}<extra></extra>"
            )
            ages = [current_age + (yr - years_range[0]) for yr in x]
            fig.add_trace(go.Scatter(
                x=x, y=percentiles[pct],
                customdata=ages,
                mode="lines", name=label,
                line=dict(color=color, width=width, dash=dash),
                hovertemplate=hover,
            ))
        else:
            fig.add_trace(go.Scatter(
                x=x, y=percentiles[pct],
                mode="lines", name=label,
                line=dict(color=color, width=width, dash=dash),
                hovertemplate=f"{label}: $%{{y:,.0f}}<extra></extra>",
            ))

    # Goal vertical lines
    for yr, label in goal_markers:
        fig.add_vline(
            x=yr,
            line=dict(color=PALETTE["muted"], width=1, dash="dot"),
            annotation_text=label,
            annotation_position="top",
            annotation_font=dict(color=PALETTE["muted"], size=10),
        )

    # Build age tick overlay on x-axis if age provided
    age_layout = {}
    if current_age:
        start_year = years_range[0]
        # Tick every 5 years, show "YYYY (Age XX)"
        tick_years = [yr for yr in years_range if (yr - start_year) % 5 == 0]
        tickvals = tick_years
        ticktext = [f"{yr}<br><span style='font-size:9px;opacity:0.6'>Age {current_age + (yr - start_year)}</span>" for yr in tick_years]
        age_layout["xaxis"] = dict(
            title="",
            gridcolor=PALETTE["border"],
            showgrid=True,
            zeroline=False,
            tickvals=tickvals,
            ticktext=ticktext,
            tickfont=dict(size=10),
        )
    else:
        age_layout["xaxis"] = dict(
            title="Year",
            gridcolor=PALETTE["border"],
            showgrid=True,
            zeroline=False,
        )

    fig.update_layout(
        **_base_layout(height=380),
        title=dict(text="Projected Wealth Over Time", font=dict(size=15, color=PALETTE["text"]), x=0),
        **age_layout,
        yaxis=dict(
            title="Portfolio Value ($)",
            gridcolor=PALETTE["border"],
            showgrid=True,
            zeroline=False,
            tickformat="$,.0f",
        ),
        legend=dict(
            orientation="h",
            x=0, y=-0.22,
            font=dict(size=10, color=PALETTE["muted"]),
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
    )
    return fig


def gauge_chart(probability: float, label: str) -> go.Figure:
    pct = probability * 100
    color = _prob_color(probability)

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number=dict(suffix="%", font=dict(size=28, color=color)),
        gauge=dict(
            axis=dict(
                range=[0, 100],
                tickwidth=1,
                tickcolor=PALETTE["border"],
                tickfont=dict(color=PALETTE["muted"], size=9),
                nticks=6,
            ),
            bar=dict(color=color, thickness=0.6),
            bgcolor=PALETTE["border"],
            borderwidth=0,
            steps=[
                dict(range=[0, 40], color="rgba(255,92,92,0.10)"),
                dict(range=[40, 70], color="rgba(245,200,66,0.10)"),
                dict(range=[70, 100], color="rgba(0,200,150,0.10)"),
            ],
            threshold=dict(
                line=dict(color=color, width=2),
                thickness=0.75,
                value=pct,
            ),
        ),
        title=dict(text=label, font=dict(size=12, color=PALETTE["muted"])),
        domain=dict(x=[0, 1], y=[0, 1]),
    ))
    fig.update_layout(
        **_base_layout(height=200, margin=dict(l=20, r=20, t=40, b=10)),
    )
    return fig


def sensitivity_chart(base_probs: dict[str, float], boosted_probs: dict[str, float], boost_amount: int) -> go.Figure:
    goals = list(base_probs.keys())
    base_vals = [base_probs[g] * 100 for g in goals]
    boost_vals = [boosted_probs[g] * 100 for g in goals]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Current",
        x=goals,
        y=base_vals,
        marker_color=PALETTE["blue"],
        marker_line_width=0,
        opacity=0.8,
    ))
    fig.add_trace(go.Bar(
        name=f"+${boost_amount:,}/mo savings",
        x=goals,
        y=boost_vals,
        marker_color=PALETTE["green"],
        marker_line_width=0,
        opacity=0.8,
    ))

    fig.update_layout(
        **_base_layout(height=260),
        title=dict(text=f"Impact of +${boost_amount:,}/mo Additional Savings", font=dict(size=13, color=PALETTE["text"]), x=0),
        barmode="group",
        bargap=0.25,
        bargroupgap=0.08,
        xaxis=dict(gridcolor=PALETTE["border"], showgrid=False),
        yaxis=dict(
            title="Probability (%)",
            gridcolor=PALETTE["border"],
            range=[0, 105],
            ticksuffix="%",
        ),
        legend=dict(
            orientation="h", x=0, y=-0.22,
            font=dict(size=10, color=PALETTE["muted"]),
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    return fig
