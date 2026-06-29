import copy
import numpy as np
import streamlit as st

from auth import (
    load_profiles, save_profiles, make_key, make_display,
    get_settings, save_settings, add_participant, list_participants,
    DEFAULT_SETTINGS,
)
from simulation import run_simulation, percentile_paths, ALLOCATION_PARAMS
from goals import (
    Goal, InvestmentTargetGoal, RetirementGoal, HomePurchaseGoal,
    CollegeTuitionGoal, CustomGoal,
    compute_retirement_target, compute_college_target,
    evaluate_goals, goal_probability,
)
from charts import fan_chart, gauge_chart, sensitivity_chart, set_theme
from pdf_export import generate_pdf
from ai_advisor import build_context, stream_action_plan, stream_chat
from streamlit_float import float_init, float_css_helper

CURRENT_YEAR = 2026

# ── Theme ───────────────────────────────────────────────────────────────────────
try:
    _theme_base = st.get_option("theme.base") or "dark"
except Exception:
    _theme_base = "dark"
IS_DARK = _theme_base != "light"
set_theme(IS_DARK)

# ── Page config ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Financial Planning Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.metric-card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.18);
    border-radius: 12px;
    padding: 20px 24px;
    text-align: center;
    height: 100%;
}
.metric-label {
    font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--text-color); opacity: 0.55; margin-bottom: 8px;
}
.metric-value { font-size: 38px; font-weight: 700; line-height: 1; margin-bottom: 6px; }
.metric-sub   { font-size: 11px; color: var(--text-color); opacity: 0.5; }

.callout {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.18);
    border-left: 3px solid #4f8ef7;
    border-radius: 10px; padding: 16px 20px;
    font-size: 13px; color: var(--text-color); line-height: 1.6;
}
.callout strong { color: var(--text-color); }

.sensitivity-tagline { font-size: 18px; font-weight: 600; color: var(--text-color); margin-bottom: 4px; }
.sensitivity-sub     { font-size: 13px; color: var(--text-color); opacity: 0.55; margin-bottom: 16px; }

.section-header {
    font-size: 11px; font-weight: 600; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--text-color); opacity: 0.5;
    margin: 24px 0 12px 0; padding-bottom: 6px;
    border-bottom: 1px solid rgba(128,128,128,0.18);
}
.user-badge {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.18);
    border-radius: 8px; padding: 10px 14px;
    font-size: 13px; font-weight: 600; color: var(--text-color);
    margin-bottom: 8px;
}
.alloc-total-ok  { color: #00c896; font-weight: 600; font-size: 13px; }
.alloc-total-bad { color: #ff5c5c; font-weight: 600; font-size: 13px; }

/* Logout button — force single line */
[data-testid="stSidebar"] button {
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}

/* Floating chat FAB — bigger green pill */
.chat-fab button {
    font-size: 15px !important;
    padding: 14px 26px !important;
    border-radius: 50px !important;
    background: #00c896 !important;
    border: none !important;
    color: #fff !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 20px rgba(0,200,150,0.45) !important;
    min-width: 150px !important;
    letter-spacing: 0.01em !important;
}
.chat-fab button:hover {
    background: #00b085 !important;
    box-shadow: 0 6px 24px rgba(0,200,150,0.55) !important;
}

.login-card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.18);
    border-radius: 16px; padding: 40px 36px;
}
.block-container { padding-top: 2rem; }

.ai-plan-card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(79,142,247,0.25);
    border-left: 3px solid #4f8ef7;
    border-radius: 10px;
    padding: 20px 24px;
    font-size: 14px;
    line-height: 1.75;
    color: var(--text-color);
}
.ai-plan-card p { margin: 0; }
.chat-bubble-user {
    background: rgba(79,142,247,0.12);
    border-radius: 10px 10px 2px 10px;
    padding: 10px 14px;
    font-size: 13.5px;
    margin-bottom: 8px;
    color: var(--text-color);
}
.chat-bubble-ai {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.18);
    border-radius: 10px 10px 10px 2px;
    padding: 10px 14px;
    font-size: 13.5px;
    margin-bottom: 8px;
    color: var(--text-color);
}
</style>
""", unsafe_allow_html=True)

# ── Session state bootstrap ─────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "profiles" not in st.session_state:
    st.session_state.profiles = load_profiles()
if "user_key" not in st.session_state:
    st.session_state.user_key = None
if "active_key" not in st.session_state:
    st.session_state.active_key = None
if "active_display" not in st.session_state:
    st.session_state.active_display = None
if "_form_epoch" not in st.session_state:
    st.session_state._form_epoch = 0
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "ai_plan" not in st.session_state:
    st.session_state.ai_plan = None
if "_last_ai_participant" not in st.session_state:
    st.session_state._last_ai_participant = None
if "chat_open" not in st.session_state:
    st.session_state.chat_open = False


# ── Helpers ─────────────────────────────────────────────────────────────────────
def alloc_key(goal_name: str) -> str:
    ep = st.session_state.get("_form_epoch", 0)
    return f"s_alloc_{goal_name.replace(' ', '_')}_v{ep}"


def apply_settings(settings: dict) -> None:
    ep = st.session_state.get("_form_epoch", 0)
    for k, v in {**DEFAULT_SETTINGS, **settings}.items():
        if k != "goal_allocations":
            st.session_state[f"s_{k}_v{ep}"] = v
    for goal_name, pct in settings.get("goal_allocations", {}).items():
        st.session_state[alloc_key(goal_name)] = pct


def collect_settings() -> dict:
    ep = st.session_state.get("_form_epoch", 0)
    s = {}
    for k in DEFAULT_SETTINGS:
        if k != "goal_allocations":
            s[k] = st.session_state.get(f"s_{k}_v{ep}", DEFAULT_SETTINGS[k])
    allocations = {}
    prefix = "s_alloc_"
    suffix = f"_v{ep}"
    for k, v in st.session_state.items():
        if k.startswith(prefix) and k.endswith(suffix):
            goal_name = k[len(prefix):-len(suffix)].replace("_", " ")
            allocations[goal_name] = v
    s["goal_allocations"] = allocations
    return s


def _ss(key: str, default=None):
    ep = st.session_state.get("_form_epoch", 0)
    return st.session_state.get(f"s_{key}_v{ep}", default if default is not None else DEFAULT_SETTINGS.get(key))


# ── Login screen ────────────────────────────────────────────────────────────────
def show_login():
    st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center;margin-bottom:6px'>Financial Planning Dashboard</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;opacity:0.5;font-size:13px;margin-bottom:28px'>Sign in or create an account to get started</p>", unsafe_allow_html=True)

        with st.form("login_form"):
            first = st.text_input("First Name")
            last  = st.text_input("Last Initial", max_chars=1)
            go    = st.form_submit_button("Continue →", use_container_width=True)

        if go:
            if not first.strip() or not last.strip():
                st.error("Please enter both your first name and last initial.")
            else:
                key     = make_key(first, last)
                display = make_display(first, last)
                profiles = st.session_state.profiles

                if key not in profiles:
                    profiles[key] = {
                        "display_name": display,
                        "settings": dict(DEFAULT_SETTINGS),
                        "participants": {},
                    }
                    save_profiles(profiles)

                st.session_state.user_key      = key
                st.session_state.active_key    = None
                st.session_state.active_display = display
                st.session_state.logged_in     = True
                apply_settings(get_settings(profiles, key))
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


# ── Guard ───────────────────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    show_login()
    st.stop()

float_init(theme=False, include_unstable_primary=False)


# ── Participant switch callback ──────────────────────────────────────────────────
def _on_participant_change():
    selected = st.session_state.get("_participant_selector", "Myself")
    profiles = load_profiles()
    st.session_state.profiles = profiles
    user_key = st.session_state.user_key

    # Bump epoch so all widgets remount with fresh values
    st.session_state._form_epoch = st.session_state.get("_form_epoch", 0) + 1
    # Clear AI state for new participant
    st.session_state.chat_messages = []
    st.session_state.ai_plan = None
    st.session_state.chat_open = False

    if selected == "Myself":
        st.session_state.active_key     = None
        st.session_state.active_display = profiles[user_key]["display_name"]
        apply_settings(get_settings(profiles, user_key))
    else:
        for p_key, p_display in list_participants(profiles, user_key):
            if p_display == selected:
                st.session_state.active_key     = p_key
                st.session_state.active_display = p_display
                apply_settings(get_settings(profiles, user_key, p_key))
                break


# ── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:

    # User header — badge + Logout on one line
    active_display = st.session_state.active_display or st.session_state.user_key
    col_name, col_out = st.columns([3, 2])
    with col_name:
        st.markdown(
            f"<div class='user-badge' style='margin-bottom:0;font-size:12px;padding:9px 12px'>"
            f"👤 {active_display}</div>",
            unsafe_allow_html=True,
        )
    with col_out:
        if st.button("Logout", use_container_width=True, key="_logout_btn"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # Participant selector
    profiles  = st.session_state.profiles
    user_key  = st.session_state.user_key
    participants = list_participants(profiles, user_key)
    participant_options = ["Myself"] + [d for _, d in participants]

    current_active_display = st.session_state.active_display or profiles[user_key]["display_name"]
    default_selector = current_active_display if current_active_display in participant_options else "Myself"

    st.selectbox(
        "Viewing",
        options=participant_options,
        index=participant_options.index(default_selector),
        key="_participant_selector",
        on_change=_on_participant_change,
    )

    with st.expander("＋ Add Participant"):
        p_first = st.text_input("First Name", key="_p_first")
        p_last  = st.text_input("Last Initial", max_chars=1, key="_p_last")
        if st.button("Add Participant"):
            if p_first.strip() and p_last.strip():
                p_key, p_display = add_participant(profiles, user_key, p_first, p_last)
                st.session_state.profiles = profiles
                # Auto-switch to the new participant
                st.session_state._form_epoch = st.session_state.get("_form_epoch", 0) + 1
                st.session_state.active_key = p_key
                st.session_state.active_display = p_display
                st.session_state._participant_selector = p_display
                apply_settings(get_settings(profiles, user_key, p_key))
                st.rerun()
            else:
                st.error("Enter a name and initial.")

    st.markdown("---")
    st.markdown("## Your Profile")

    ep = st.session_state.get("_form_epoch", 0)

    st.number_input("Current Age", min_value=18, max_value=80, step=1, key=f"s_current_age_v{ep}")
    st.number_input("Current Savings ($)", min_value=0, step=1000, key=f"s_current_savings_v{ep}")
    st.caption(f"${_ss('current_savings', 50000):,.0f}")
    st.number_input("Monthly Contribution ($)", min_value=0, step=100, key=f"s_monthly_contribution_v{ep}")
    st.caption(f"${_ss('monthly_contribution', 1500):,.0f}/mo")

    alloc_options = list(ALLOCATION_PARAMS.keys()) + ["Custom"]
    current_alloc = _ss("allocation", "Moderate (60/40)")
    alloc_idx = alloc_options.index(current_alloc) if current_alloc in alloc_options else 1
    st.selectbox("Asset Allocation", alloc_options, index=alloc_idx, key=f"s_allocation_v{ep}")

    if _ss("allocation") == "Custom":
        with st.expander("Custom return assumptions", expanded=True):
            st.number_input("Expected Annual Return (%)", min_value=0.0, max_value=30.0, step=0.5, key=f"s_custom_mu_v{ep}")
            st.number_input("Annual Volatility / Std Dev (%)", min_value=0.0, max_value=50.0, step=0.5,
                            help="S&P 500 historical volatility is ~15–17%. Individual stocks are typically 20–40%.",
                            key=f"s_custom_sigma_v{ep}")

    st.markdown("---")
    st.markdown("## Goals")

    # Investment Target
    st.checkbox("Investment Target", key=f"s_invest_enabled_v{ep}")
    if _ss("invest_enabled"):
        with st.expander("Investment Target details", expanded=True):
            st.number_input("Target Amount ($)", min_value=1_000, step=5_000, key=f"s_invest_amount_v{ep}")
            st.caption(f"${_ss('invest_amount', 250000):,.0f}")
            st.number_input("Target Year", min_value=CURRENT_YEAR + 1, max_value=CURRENT_YEAR + 50, step=1, key=f"s_invest_year_v{ep}")

    # Retirement
    st.checkbox("Retirement", key=f"s_ret_enabled_v{ep}")
    if _ss("ret_enabled"):
        with st.expander("Retirement details", expanded=True):
            st.number_input("Retirement Age", min_value=_ss("current_age", 30) + 1, max_value=80, step=1, key=f"s_ret_age_v{ep}")
            st.number_input("Desired Monthly Income ($)", min_value=0, step=500, key=f"s_ret_income_v{ep}")
            st.caption(f"${_ss('ret_income', 6000):,.0f}/mo")
            st.number_input("Social Security ($/mo)", min_value=0, step=100, key=f"s_ret_ss_v{ep}")
            st.caption(f"${_ss('ret_ss', 1800):,.0f}/mo")
            st.number_input("Years in Retirement", min_value=5, max_value=50, step=1, key=f"s_ret_years_v{ep}")

    # Home Purchase
    st.checkbox("Home Purchase", key=f"s_home_enabled_v{ep}")
    if _ss("home_enabled"):
        with st.expander("Home Purchase details", expanded=True):
            st.number_input("Target Year", min_value=CURRENT_YEAR + 1, max_value=CURRENT_YEAR + 50, step=1, key=f"s_home_year_v{ep}")
            st.number_input("Down Payment ($)", min_value=10_000, step=5_000, key=f"s_home_down_v{ep}")
            st.caption(f"${_ss('home_down', 100000):,.0f}")

    # College Tuition
    st.checkbox("College Tuition", key=f"s_college_enabled_v{ep}")
    if _ss("college_enabled"):
        with st.expander("College details", expanded=True):
            st.number_input("Start Year", min_value=CURRENT_YEAR + 1, max_value=CURRENT_YEAR + 50, step=1, key=f"s_college_year_v{ep}")
            st.number_input("Total Cost Today ($)", min_value=10_000, step=5_000, key=f"s_college_base_v{ep}")
            st.caption(f"${_ss('college_base', 80000):,.0f}")

    # Custom Goal
    st.checkbox("Custom Goal", key=f"s_custom_enabled_v{ep}")
    if _ss("custom_enabled"):
        with st.expander("Custom Goal details", expanded=True):
            st.text_input("Goal Name", key=f"s_custom_name_v{ep}")
            st.number_input("Target Year ", min_value=CURRENT_YEAR + 1, max_value=CURRENT_YEAR + 50, step=1, key=f"s_custom_year_v{ep}")
            st.number_input("Target Amount ($)", min_value=1_000, step=1_000, key=f"s_custom_amount_v{ep}")
            st.caption(f"${_ss('custom_amount', 50000):,.0f}")

    # ── Goal Priorities ─────────────────────────────────────────────────────────
    enabled_goal_names = []
    if _ss("invest_enabled"):  enabled_goal_names.append("Investment Target")
    if _ss("ret_enabled"):     enabled_goal_names.append("Retirement")
    if _ss("home_enabled"):    enabled_goal_names.append("Home Purchase")
    if _ss("college_enabled"): enabled_goal_names.append("College Tuition")
    if _ss("custom_enabled"):  enabled_goal_names.append(_ss("custom_name", "Custom Goal") or "Custom Goal")

    use_bucket = False
    allocations: dict[str, int] = {}

    if len(enabled_goal_names) >= 2:
        st.markdown("---")
        st.markdown("## Goal Priorities")
        monthly = _ss("monthly_contribution", 1500)
        st.markdown(f"<p style='font-size:12px;opacity:0.6;margin-bottom:12px'>How should your <b>${monthly:,.0f}/mo</b> be divided?</p>", unsafe_allow_html=True)

        # Init missing slider keys to equal split
        equal = 100 // len(enabled_goal_names)
        for name in enabled_goal_names:
            k = alloc_key(name)
            if k not in st.session_state:
                st.session_state[k] = equal

        for name in enabled_goal_names:
            st.slider(name, min_value=0, max_value=100, step=5, key=alloc_key(name))
            allocations[name] = st.session_state[alloc_key(name)]

        alloc_total = sum(allocations.values())
        if alloc_total == 100:
            st.markdown(f"<p class='alloc-total-ok'>Total: {alloc_total}% ✓</p>", unsafe_allow_html=True)
            use_bucket = True
        else:
            st.markdown(f"<p class='alloc-total-bad'>Total: {alloc_total}% — must equal 100%</p>", unsafe_allow_html=True)
            st.caption("Adjust sliders to 100% for independent goal projections.")

    st.markdown("---")
    if st.button("Save Profile", use_container_width=True, type="primary"):
        s = collect_settings()
        save_settings(profiles, user_key, s, st.session_state.active_key)
        st.session_state.profiles = load_profiles()
        label = st.session_state.active_display or "profile"
        st.success(f"Saved {label}!")
        st.rerun()


# ── Read current values ─────────────────────────────────────────────────────────
current_age          = _ss("current_age", 30)
current_savings      = _ss("current_savings", 50000)
monthly_contribution = _ss("monthly_contribution", 1500)
allocation           = _ss("allocation", "Moderate (60/40)")
custom_mu_frac       = _ss("custom_mu", 7.0) / 100
custom_sigma_frac    = _ss("custom_sigma", 10.0) / 100

invest_enabled = _ss("invest_enabled", False)
invest_amount  = _ss("invest_amount", 250000)
invest_year    = _ss("invest_year", CURRENT_YEAR + 10)

ret_enabled = _ss("ret_enabled", False)
ret_age     = _ss("ret_age", 65)
ret_income  = _ss("ret_income", 6000)
ret_ss_amt  = _ss("ret_ss", 1800)
ret_years   = _ss("ret_years", 25)

home_enabled = _ss("home_enabled", False)
home_year    = _ss("home_year", CURRENT_YEAR + 5)
home_down    = _ss("home_down", 100000)

college_enabled = _ss("college_enabled", False)
college_year    = _ss("college_year", CURRENT_YEAR + 18)
college_base    = _ss("college_base", 80000)

custom_enabled = _ss("custom_enabled", False)
custom_name    = _ss("custom_name", "Sabbatical Fund") or "Custom Goal"
custom_year    = _ss("custom_year", CURRENT_YEAR + 10)
custom_amount  = _ss("custom_amount", 50000)

ret_year = CURRENT_YEAR + (ret_age - current_age)

# ── Build goal list ─────────────────────────────────────────────────────────────
goals: list[Goal] = []

if invest_enabled:
    goals.append(InvestmentTargetGoal(name="Investment Target", target_amount=invest_amount, target_year=invest_year, enabled=True))

if ret_enabled:
    goals.append(RetirementGoal(
        name="Retirement",
        target_amount=compute_retirement_target(ret_income, ret_ss_amt, ret_years),
        target_year=ret_year,
        monthly_income_needed=ret_income, social_security_monthly=ret_ss_amt,
        years_in_retirement=ret_years, enabled=True,
    ))

if home_enabled:
    goals.append(HomePurchaseGoal(name="Home Purchase", target_amount=home_down, target_year=home_year, enabled=True))

if college_enabled:
    adj_cost = compute_college_target(college_base, college_year - CURRENT_YEAR)
    goals.append(CollegeTuitionGoal(name="College Tuition", target_amount=adj_cost, target_year=college_year, enabled=True))

if custom_enabled:
    goals.append(CustomGoal(name=custom_name, target_amount=custom_amount, target_year=custom_year, enabled=True))

# ── Horizon ─────────────────────────────────────────────────────────────────────
horizon_years = max(
    ret_year - CURRENT_YEAR + 5,
    (invest_year  - CURRENT_YEAR + 2) if invest_enabled  else 0,
    (home_year    - CURRENT_YEAR + 2) if home_enabled    else 0,
    (college_year - CURRENT_YEAR + 2) if college_enabled else 0,
    (custom_year  - CURRENT_YEAR + 2) if custom_enabled  else 0,
    30,
)

# ── Simulation ──────────────────────────────────────────────────────────────────
if use_bucket and goals:
    # Independent bucket per goal
    goal_wealth_map: dict[str, np.ndarray] = {}
    for g in goals:
        pct = allocations.get(g.name, 0) / 100
        g_wealth = run_simulation(
            current_savings * pct, monthly_contribution * pct,
            allocation, horizon_years, custom_mu_frac, custom_sigma_frac,
        )
        goal_wealth_map[g.name] = g_wealth
        year_index = g.target_year - CURRENT_YEAR
        g.probability = goal_probability(g_wealth, year_index, g.target_amount)

    evaluated_goals = goals
    # Total wealth for fan chart = sum of buckets
    wealth_arrays = list(goal_wealth_map.values())
    total_wealth = wealth_arrays[0].copy()
    for w in wealth_arrays[1:]:
        total_wealth = total_wealth + w
else:
    # Single combined simulation (1 goal or allocations not set)
    total_wealth = run_simulation(
        current_savings, monthly_contribution,
        allocation, horizon_years, custom_mu_frac, custom_sigma_frac,
    )
    _, evaluated_goals = evaluate_goals(total_wealth, goals, CURRENT_YEAR)
    goal_wealth_map = {g.name: total_wealth for g in evaluated_goals}

goal_probs   = {g.name: g.probability for g in evaluated_goals}
pcts         = percentile_paths(total_wealth)
years_range  = list(range(CURRENT_YEAR, CURRENT_YEAR + horizon_years + 1))
goal_markers = [(g.target_year, g.name) for g in evaluated_goals]


# ── Layout ──────────────────────────────────────────────────────────────────────
st.markdown(f"# Financial Planning Dashboard")
st.markdown(
    f"<p style='color:var(--text-color);opacity:0.4;font-size:13px;margin-top:-12px;'>"
    f"Monte Carlo projection · 5,000 simulations · {allocation}"
    f"{'  ·  Viewing: ' + active_display if st.session_state.active_key else ''}</p>",
    unsafe_allow_html=True,
)

def _prob_color(p):
    if p >= 0.70: return "#00c896"
    if p >= 0.40: return "#f5c842"
    return "#ff5c5c"

def _prob_label(p):
    if p >= 0.70: return "On track"
    if p >= 0.40: return "Needs attention"
    return "At risk"

if evaluated_goals:
    cols = st.columns(len(evaluated_goals))
    for col, g in zip(cols, evaluated_goals):
        color = _prob_color(g.probability)
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{g.name}</div>
                <div class="metric-value" style="color:{color}">{g.probability*100:.0f}%</div>
                <div class="metric-sub">{_prob_label(g.probability)}</div>
            </div>""", unsafe_allow_html=True)
else:
    st.info("Enable at least one goal in the sidebar to begin.")

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

# Fan chart
st.plotly_chart(
    fan_chart(pcts, years_range, goal_markers, current_age=current_age),
    use_container_width=True,
    config={"displayModeBar": False},
)

# Gauges
if evaluated_goals:
    st.markdown("<div class='section-header'>Goal Probability Detail</div>", unsafe_allow_html=True)
    gcols = st.columns(len(evaluated_goals))
    for col, g in zip(gcols, evaluated_goals):
        with col:
            st.plotly_chart(gauge_chart(g.probability, g.name), use_container_width=True, config={"displayModeBar": False})

    # Allocation note (bucket model only)
    if use_bucket:
        st.markdown("<div class='section-header'>Goal Funding Split</div>", unsafe_allow_html=True)
        alloc_cols = st.columns(len(evaluated_goals))
        for col, g in zip(alloc_cols, evaluated_goals):
            pct = allocations.get(g.name, 0)
            share = monthly_contribution * pct / 100
            with col:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">{g.name}</div>
                    <div class="metric-value" style="color:#4f8ef7;font-size:28px">{pct}%</div>
                    <div class="metric-sub">${share:,.0f}/mo</div>
                </div>""", unsafe_allow_html=True)

    # Sensitivity
    st.markdown("<div class='section-header'>Sensitivity Analysis</div>", unsafe_allow_html=True)

    @st.fragment
    def sensitivity_section(base_goals, current_savings, monthly_contribution,
                              allocation, horizon_years, custom_mu_frac, custom_sigma_frac,
                              allocations, use_bucket):
        st.markdown("<div class='sensitivity-tagline'>Is it worth saving a little more each month?</div>", unsafe_allow_html=True)
        st.markdown("<div class='sensitivity-sub'>Drag the slider to see how extra savings shifts the odds on every goal.</div>", unsafe_allow_html=True)

        boost = st.select_slider(
            "Extra savings per month",
            options=[250, 500, 1_000, 2_000],
            value=500,
            format_func=lambda x: f"+${x:,}/mo",
        )

        base_probs = {g.name: g.probability for g in base_goals}

        if use_bucket:
            boosted_goals = copy.deepcopy(base_goals)
            for g in boosted_goals:
                pct = allocations.get(g.name, 0) / 100
                bw = run_simulation(
                    current_savings * pct,
                    (monthly_contribution + boost) * pct,
                    allocation, horizon_years, custom_mu_frac, custom_sigma_frac,
                )
                year_index = g.target_year - CURRENT_YEAR
                g.probability = goal_probability(bw, year_index, g.target_amount)
            boost_probs = {g.name: g.probability for g in boosted_goals}
        else:
            bw = run_simulation(
                current_savings, monthly_contribution + boost,
                allocation, horizon_years, custom_mu_frac, custom_sigma_frac,
            )
            _, bg = evaluate_goals(bw, copy.deepcopy(base_goals), CURRENT_YEAR)
            boost_probs = {g.name: g.probability for g in bg}

        s_col, c_col = st.columns([3, 2])
        with s_col:
            st.plotly_chart(sensitivity_chart(base_probs, boost_probs, boost),
                            use_container_width=True, config={"displayModeBar": False})
        with c_col:
            st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
            lines = []
            for g in base_goals:
                bp   = boost_probs.get(g.name, 0)
                base = base_probs.get(g.name, 0)
                delta = bp - base
                sign  = "+" if delta >= 0 else ""
                lines.append(f"<b>{g.name}</b>: {base*100:.0f}% → {bp*100:.0f}% <span style='color:#00c896'>({sign}{delta*100:.0f}pp)</span>")
            st.markdown(f"""<div class="callout"><strong>What if you saved ${boost:,}/mo more?</strong><br><br>{"<br>".join(lines)}</div>""", unsafe_allow_html=True)

    sensitivity_section(
        evaluated_goals, current_savings, monthly_contribution,
        allocation, horizon_years, custom_mu_frac, custom_sigma_frac,
        allocations, use_bucket,
    )

    # ── AI Action Plan ───────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>AI Analysis</div>", unsafe_allow_html=True)

    _ai_context = build_context(
        name=active_display,
        current_age=current_age,
        current_savings=current_savings,
        monthly_contribution=monthly_contribution,
        allocation=allocation,
        goals=evaluated_goals,
        allocations=allocations if use_bucket else None,
    )

    @st.fragment
    def ai_plan_section(context: str):
        btn_label = "✦ Generate AI Analysis" if st.session_state.ai_plan is None else "↺ Regenerate Analysis"
        clicked = st.button(btn_label, type="primary", use_container_width=True)
        st.markdown(
            "<p style='font-size:11px;opacity:0.4;margin-top:4px;margin-bottom:12px'>"
            "Claude reviews your goal probabilities and surfaces specific, numbered actions</p>",
            unsafe_allow_html=True,
        )

        if clicked:
            st.session_state.ai_plan = None
            placeholder = st.empty()
            full_text = ""
            placeholder.markdown("<div class='ai-plan-card'>Analyzing your plan…</div>", unsafe_allow_html=True)
            try:
                for chunk in stream_action_plan(context):
                    full_text += chunk
                    placeholder.markdown(
                        f"<div class='ai-plan-card'>{full_text.replace(chr(10), '<br>')}</div>",
                        unsafe_allow_html=True,
                    )
                st.session_state.ai_plan = full_text
            except ValueError as e:
                placeholder.error(str(e))
        elif st.session_state.ai_plan:
            st.markdown(
                f"<div class='ai-plan-card'>{st.session_state.ai_plan.replace(chr(10), '<br>')}</div>",
                unsafe_allow_html=True,
            )

    ai_plan_section(_ai_context)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── PDF Export ───────────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Export</div>", unsafe_allow_html=True)

    @st.fragment
    def pdf_section(goals, current_age, current_savings, monthly_contribution,
                     allocation, use_bucket, allocations):
        if st.button("Download PDF Report", type="primary"):
            snap_bw = run_simulation(
                current_savings, monthly_contribution + 500,
                allocation, horizon_years, custom_mu_frac, custom_sigma_frac,
            )
            _, snap_bg = evaluate_goals(snap_bw, copy.deepcopy(goals), CURRENT_YEAR)
            snap_boost_probs = {g.name: g.probability for g in snap_bg}

            pdf_bytes = generate_pdf(
                current_age=current_age,
                current_savings=current_savings,
                monthly_contribution=monthly_contribution,
                allocation=allocation,
                goals=goals,
                boost_amount=500,
                boost_probs=snap_boost_probs,
                allocation_pcts=allocations if use_bucket else {},
            )
            st.download_button(
                label="Click to save your report",
                data=pdf_bytes,
                file_name=f"financial_plan_{active_display.replace(' ', '_').replace('.', '')}.pdf",
                mime="application/pdf",
            )

    pdf_section(evaluated_goals, current_age, current_savings, monthly_contribution,
                 allocation, use_bucket, allocations)

# Footer
st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center;font-size:11px;opacity:0.3;'>For educational purposes only. Not financial advice.</p>",
    unsafe_allow_html=True,
)

# ── Floating Chat Widget ─────────────────────────────────────────────────────────
if evaluated_goals:
    _ai_ctx_chat = build_context(
        name=active_display,
        current_age=current_age,
        current_savings=current_savings,
        monthly_contribution=monthly_contribution,
        allocation=allocation,
        goals=evaluated_goals,
        allocations=allocations if use_bucket else None,
    )

    # Toggle button (always visible bottom-right)
    toggle_col = st.container()
    with toggle_col:
        st.markdown("<div class='chat-fab'>", unsafe_allow_html=True)
        toggle_label = "✕ Close" if st.session_state.chat_open else "💬 AI Advisor"
        if st.button(toggle_label, key="_chat_toggle", type="primary"):
            st.session_state.chat_open = not st.session_state.chat_open
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    toggle_col.float(
        "bottom: 24px; right: 24px; z-index: 1000;"
    )

    # Chat panel (slides up above toggle button when open)
    if st.session_state.chat_open:
        chat_panel = st.container()
        with chat_panel:
            st.markdown(
                "<div style='font-weight:600;font-size:14px;margin-bottom:10px;'>"
                "💬 AI Advisor</div>",
                unsafe_allow_html=True,
            )

            # Message history
            msg_area = st.container(height=320)
            with msg_area:
                if not st.session_state.chat_messages:
                    st.markdown(
                        "<p style='font-size:12px;opacity:0.45;text-align:center;padding-top:60px'>"
                        "Ask anything about your financial plan.<br>"
                        "<em>e.g. \"Why is my retirement probability low?\"</em></p>",
                        unsafe_allow_html=True,
                    )
                for msg in st.session_state.chat_messages:
                    if msg["role"] == "user":
                        st.markdown(
                            f"<div class='chat-bubble-user'>🧑 {msg['content']}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div class='chat-bubble-ai'>🤖 {msg['content']}</div>",
                            unsafe_allow_html=True,
                        )

            user_input = st.chat_input("Ask about your plan…", key="_float_chat_input")

            if user_input:
                st.session_state.chat_messages.append({"role": "user", "content": user_input})
                full_reply = ""
                try:
                    api_messages = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.chat_messages
                    ]
                    for chunk in stream_chat(_ai_ctx_chat, api_messages):
                        full_reply += chunk
                    st.session_state.chat_messages.append({"role": "assistant", "content": full_reply})
                except ValueError as e:
                    st.session_state.chat_messages.append({"role": "assistant", "content": f"Error: {e}"})
                st.rerun()

            if st.session_state.chat_messages:
                if st.button("Clear", key="_float_clear"):
                    st.session_state.chat_messages = []
                    st.rerun()

        chat_panel.float(
            "bottom: 80px; right: 24px; width: 400px; z-index: 999; "
            "background: var(--background-color); "
            "border: 1px solid rgba(128,128,128,0.2); "
            "border-radius: 16px; padding: 20px 18px 4px 18px; "
            "box-shadow: 0 8px 32px rgba(0,0,0,0.25);"
        )

    # JS: style the floating chat toggle button (CSS can't reach inside float containers)
    import streamlit.components.v1 as components
    components.html("""
    <script>
    function styleAdvisorBtn() {
        const btns = window.parent.document.querySelectorAll('button');
        btns.forEach(btn => {
            const txt = btn.innerText.trim();
            if (txt.includes('AI Advisor') || txt === '✕ Close') {
                btn.style.backgroundColor = '#00c896';
                btn.style.borderColor = '#00c896';
                btn.style.color = '#ffffff';
                btn.style.fontSize = '15px';
                btn.style.fontWeight = '700';
                btn.style.padding = '14px 28px';
                btn.style.borderRadius = '50px';
                btn.style.minWidth = '158px';
                btn.style.boxShadow = '0 4px 20px rgba(0,200,150,0.45)';
                btn.style.border = 'none';
            }
        });
    }
    styleAdvisorBtn();
    setTimeout(styleAdvisorBtn, 400);
    setTimeout(styleAdvisorBtn, 1200);
    new MutationObserver(styleAdvisorBtn).observe(
        window.parent.document.body, { childList: true, subtree: true }
    );
    </script>
    """, height=0)
