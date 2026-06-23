import copy
import streamlit as st
import numpy as np
from pdf_export import generate_pdf
from simulation import run_simulation, percentile_paths, ALLOCATION_PARAMS
from goals import (
    Goal, InvestmentTargetGoal, RetirementGoal, HomePurchaseGoal, CollegeTuitionGoal, CustomGoal,
    compute_retirement_target, compute_college_target, evaluate_goals,
)
from charts import fan_chart, gauge_chart, sensitivity_chart, set_theme

CURRENT_YEAR = 2026

try:
    _theme_base = st.get_option("theme.base") or "dark"
except Exception:
    _theme_base = "dark"
IS_DARK = _theme_base != "light"
set_theme(IS_DARK)

st.set_page_config(
    page_title="Financial Planning Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Metric cards — adapt to Streamlit's CSS vars */
.metric-card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.18);
    border-radius: 12px;
    padding: 20px 24px;
    text-align: center;
    height: 100%;
}
.metric-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-color);
    opacity: 0.55;
    margin-bottom: 8px;
}
.metric-value {
    font-size: 38px;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 6px;
}
.metric-sub {
    font-size: 11px;
    color: var(--text-color);
    opacity: 0.5;
}

/* Callout box */
.callout {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.18);
    border-left: 3px solid #4f8ef7;
    border-radius: 10px;
    padding: 16px 20px;
    font-size: 13px;
    color: var(--text-color);
    line-height: 1.6;
}
.callout strong { color: var(--text-color); }

/* Sensitivity tagline */
.sensitivity-tagline {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
    margin-bottom: 4px;
}
.sensitivity-sub {
    font-size: 13px;
    color: var(--text-color);
    opacity: 0.55;
    margin-bottom: 16px;
}

/* Section headers */
.section-header {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-color);
    opacity: 0.5;
    margin: 24px 0 12px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid rgba(128,128,128,0.18);
}

/* Remove default streamlit padding */
.block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## Your Profile")

    current_age = st.number_input("Current Age", min_value=18, max_value=80, value=30)
    current_savings = st.number_input("Current Savings ($)", min_value=0, value=50_000, step=1_000)
    st.caption(f"${current_savings:,}")
    monthly_contribution = st.number_input("Monthly Contribution ($)", min_value=0, value=1_500, step=100)
    st.caption(f"${monthly_contribution:,}/mo")
    allocation = st.selectbox("Asset Allocation", list(ALLOCATION_PARAMS.keys()) + ["Custom"], index=1)
    custom_mu, custom_sigma = 0.0, 0.0
    if allocation == "Custom":
        with st.expander("Custom return assumptions", expanded=True):
            custom_mu = st.number_input("Expected Annual Return (%)", min_value=0.0, max_value=30.0, value=12.0, step=0.5) / 100
            custom_sigma = st.number_input("Annual Volatility / Std Dev (%)", min_value=0.0, max_value=50.0, value=20.0, step=0.5, help="S&P 500 historical volatility is ~15-17%. Individual stocks are typically 20-40%.") / 100

    st.markdown("---")
    st.markdown("## Goals")

    # Investment Target
    invest_enabled = st.checkbox("Investment Target", value=False)
    invest_amount, invest_year = 250_000, CURRENT_YEAR + 10
    if invest_enabled:
        with st.expander("Investment Target details", expanded=True):
            invest_amount = st.number_input("Target Amount ($)", min_value=1_000, value=250_000, step=5_000, key="invest_amount")
            st.caption(f"${invest_amount:,}")
            invest_year = st.number_input("Target Year", min_value=CURRENT_YEAR + 1, max_value=CURRENT_YEAR + 50, value=CURRENT_YEAR + 10, key="invest_year")

    # Retirement
    ret_enabled = st.checkbox("Retirement", value=False)
    ret_age, ret_income, ret_ss, ret_years = 65, 6_000, 1_800, 25
    if ret_enabled:
        with st.expander("Retirement details", expanded=True):
            ret_age = st.number_input("Retirement Age", min_value=current_age + 1, max_value=80, value=65)
            ret_income = st.number_input("Desired Monthly Income ($)", min_value=0, value=6_000, step=500)
            st.caption(f"${ret_income:,}/mo")
            ret_ss = st.number_input("Social Security ($/mo)", min_value=0, value=1_800, step=100)
            st.caption(f"${ret_ss:,}/mo")
            ret_years = st.number_input("Years in Retirement", min_value=5, max_value=50, value=25)

    # Home Purchase
    home_enabled = st.checkbox("Home Purchase", value=False)
    home_year, home_down = CURRENT_YEAR + 5, 100_000
    if home_enabled:
        with st.expander("Home Purchase details", expanded=True):
            home_year = st.number_input("Target Year", min_value=CURRENT_YEAR + 1, max_value=CURRENT_YEAR + 50, value=CURRENT_YEAR + 5)
            home_down = st.number_input("Down Payment ($)", min_value=10_000, value=100_000, step=5_000)
            st.caption(f"${home_down:,}")

    # College
    college_enabled = st.checkbox("College Tuition", value=False)
    college_year, college_base = CURRENT_YEAR + 18, 80_000
    if college_enabled:
        with st.expander("College details", expanded=True):
            college_year = st.number_input("Start Year", min_value=CURRENT_YEAR + 1, max_value=CURRENT_YEAR + 50, value=CURRENT_YEAR + 18)
            college_base = st.number_input("Total Cost Today ($)", min_value=10_000, value=80_000, step=5_000)
            st.caption(f"${college_base:,}")

    # Custom
    custom_enabled = st.checkbox("Custom Goal", value=False)
    custom_name, custom_year, custom_amount = "Custom Goal", CURRENT_YEAR + 10, 50_000
    if custom_enabled:
        with st.expander("Custom Goal details", expanded=True):
            custom_name = st.text_input("Goal Name", value="Sabbatical Fund")
            custom_year = st.number_input("Target Year ", min_value=CURRENT_YEAR + 1, max_value=CURRENT_YEAR + 50, value=CURRENT_YEAR + 10)
            custom_amount = st.number_input("Target Amount ($)", min_value=1_000, value=50_000, step=1_000)
            st.caption(f"${custom_amount:,}")



# ── Simulation ─────────────────────────────────────────────────────────────────

ret_year = CURRENT_YEAR + (ret_age - current_age)
horizon_years = max(
    ret_year - CURRENT_YEAR + 5,
    (invest_year - CURRENT_YEAR + 2) if invest_enabled else 0,
    (home_year - CURRENT_YEAR + 2) if home_enabled else 0,
    (college_year - CURRENT_YEAR + 2) if college_enabled else 0,
    (custom_year - CURRENT_YEAR + 2) if custom_enabled else 0,
    30,
)

wealth = run_simulation(current_savings, monthly_contribution, allocation, horizon_years, custom_mu, custom_sigma)

# Build goal list
goals: list[Goal] = []

if invest_enabled:
    goals.append(InvestmentTargetGoal(name="Investment Target", target_amount=invest_amount, target_year=invest_year, enabled=True))

if ret_enabled:
    target = compute_retirement_target(ret_income, ret_ss, ret_years)
    goals.append(RetirementGoal(
        name="Retirement", target_amount=target, target_year=ret_year,
        monthly_income_needed=ret_income, social_security_monthly=ret_ss,
        years_in_retirement=ret_years, enabled=True,
    ))

if home_enabled:
    goals.append(HomePurchaseGoal(name="Home Purchase", target_amount=home_down, target_year=home_year, enabled=True))

if college_enabled:
    years_until = college_year - CURRENT_YEAR
    adj_cost = compute_college_target(college_base, years_until)
    goals.append(CollegeTuitionGoal(name="College Tuition", target_amount=adj_cost, target_year=college_year, enabled=True))

if custom_enabled:
    goals.append(CustomGoal(name=custom_name, target_amount=custom_amount, target_year=custom_year, enabled=True))

_, evaluated_goals = evaluate_goals(wealth, goals, CURRENT_YEAR)
goal_probs = {g.name: g.probability for g in evaluated_goals}

pcts = percentile_paths(wealth)
years_range = list(range(CURRENT_YEAR, CURRENT_YEAR + horizon_years + 1))

goal_markers = [(g.target_year, g.name) for g in evaluated_goals]


# ── Layout ─────────────────────────────────────────────────────────────────────

st.markdown("# Financial Planning Dashboard")
st.markdown(f"<p style='color:#7b7f9e;font-size:13px;margin-top:-12px;'>Monte Carlo projection · {5_000:,} simulations · {allocation}</p>", unsafe_allow_html=True)

# Metric cards
def prob_color_hex(p):
    if p >= 0.70: return "#00c896"
    if p >= 0.40: return "#f5c842"
    return "#ff5c5c"

def prob_label(p):
    if p >= 0.70: return "On track"
    if p >= 0.40: return "Needs attention"
    return "At risk"

all_goals = evaluated_goals if evaluated_goals else []

if all_goals:
    cols = st.columns(len(all_goals))
    for col, g in zip(cols, all_goals):
        color = prob_color_hex(g.probability)
        label = prob_label(g.probability)
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{g.name}</div>
                <div class="metric-value" style="color:{color}">{g.probability*100:.0f}%</div>
                <div class="metric-sub">{label}</div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("Enable at least one goal in the sidebar to begin.")

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

# Fan chart
st.plotly_chart(
    fan_chart(pcts, years_range, goal_markers, current_age=current_age),
    use_container_width=True,
    config={"displayModeBar": False},
)

# Gauges + sensitivity
if all_goals:
    st.markdown("<div class='section-header'>Goal Probability Detail</div>", unsafe_allow_html=True)
    gauge_cols = st.columns(len(all_goals))
    for col, g in zip(gauge_cols, all_goals):
        with col:
            st.plotly_chart(
                gauge_chart(g.probability, g.name),
                use_container_width=True,
                config={"displayModeBar": False},
            )

    st.markdown("<div class='section-header'>Sensitivity Analysis</div>", unsafe_allow_html=True)

    @st.fragment
    def sensitivity_section(base_goals, base_wealth, allocation, horizon_years, custom_mu, custom_sigma):
        st.markdown("<div class='sensitivity-tagline'>Is it worth saving a little more each month?</div>", unsafe_allow_html=True)
        st.markdown("<div class='sensitivity-sub'>Drag the slider to see how a small increase in monthly savings shifts the odds on every goal.</div>", unsafe_allow_html=True)
        boost = st.select_slider(
            "Extra savings per month",
            options=[250, 500, 1_000, 2_000],
            value=500,
            format_func=lambda x: f"+${x:,}/mo",
        )
        base_monthly = base_wealth  # passed as monthly_contribution for clarity
        base_probs = {g.name: g.probability for g in base_goals}
        boosted_wealth = run_simulation(base_monthly[0], base_monthly[1] + boost, allocation, horizon_years, custom_mu, custom_sigma)
        _, boosted_goals = evaluate_goals(boosted_wealth, copy.deepcopy(base_goals), CURRENT_YEAR)
        boost_probs = {g.name: g.probability for g in boosted_goals}

        s_col, c_col = st.columns([3, 2])
        with s_col:
            st.plotly_chart(
                sensitivity_chart(base_probs, boost_probs, boost),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        with c_col:
            st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
            lines = []
            for g in base_goals:
                base_p = base_probs.get(g.name, 0)
                boost_p = boost_probs.get(g.name, 0)
                delta = boost_p - base_p
                sign = "+" if delta >= 0 else ""
                lines.append(f"<b>{g.name}</b>: {base_p*100:.0f}% → {boost_p*100:.0f}% <span style='color:#00c896'>({sign}{delta*100:.0f}pp)</span>")
            callout_body = "<br>".join(lines)
            st.markdown(f"""
            <div class="callout">
                <strong>What if you saved ${boost:,}/mo more?</strong><br><br>
                {callout_body}
            </div>
            """, unsafe_allow_html=True)

    sensitivity_section(
        evaluated_goals,
        (current_savings, monthly_contribution),
        allocation, horizon_years, custom_mu, custom_sigma,
    )

# ── PDF Export ─────────────────────────────────────────────────────────────────
if all_goals:
    st.markdown("<div class='section-header'>Export</div>", unsafe_allow_html=True)

    @st.fragment
    def pdf_section(goals, boost_probs_snapshot):
        if st.button("Download PDF Report", type="primary"):
            pdf_bytes = generate_pdf(
                current_age=current_age,
                current_savings=current_savings,
                monthly_contribution=monthly_contribution,
                allocation=allocation,
                goals=goals,
                boost_amount=500,
                boost_probs=boost_probs_snapshot,
            )
            st.download_button(
                label="Click to save your report",
                data=pdf_bytes,
                file_name="financial_plan.pdf",
                mime="application/pdf",
            )

    snap_boosted_wealth = run_simulation(current_savings, monthly_contribution + 500, allocation, horizon_years, custom_mu, custom_sigma)
    _, snap_boosted_goals = evaluate_goals(snap_boosted_wealth, copy.deepcopy(evaluated_goals), CURRENT_YEAR)
    snap_boost_probs = {g.name: g.probability for g in snap_boosted_goals}
    pdf_section(evaluated_goals, snap_boost_probs)

# Footer
st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center;font-size:11px;opacity:0.3;'>For educational purposes only. Not financial advice.</p>",
    unsafe_allow_html=True,
)
