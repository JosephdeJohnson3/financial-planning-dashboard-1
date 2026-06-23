import numpy as np

ALLOCATION_PARAMS = {
    "Aggressive (90/10)": {"mu": 0.09, "sigma": 0.15},
    "Moderate (60/40)":   {"mu": 0.07, "sigma": 0.10},
    "Conservative (30/70)": {"mu": 0.05, "sigma": 0.06},
}

N_SIMS = 5_000
INFLATION = 0.025


import streamlit as st

@st.cache_data
def run_simulation(
    current_savings: float,
    monthly_contribution: float,
    allocation: str,
    years: int,
    custom_mu: float = 0.0,
    custom_sigma: float = 0.0,
    seed: int = 42,
) -> np.ndarray:
    """Return wealth paths array of shape (N_SIMS, years+1)."""
    rng = np.random.default_rng(seed)
    if allocation == "Custom":
        mu, sigma = custom_mu, custom_sigma
    else:
        params = ALLOCATION_PARAMS[allocation]
        mu, sigma = params["mu"], params["sigma"]

    # Log-normal parameters
    log_mu = np.log(1 + mu) - 0.5 * sigma ** 2
    log_sigma = sigma

    # Shape: (N_SIMS, years)
    annual_returns = rng.lognormal(log_mu, log_sigma, size=(N_SIMS, years))

    # Annual contribution grows with inflation each year
    annual_contrib = monthly_contribution * 12
    contrib_schedule = annual_contrib * (1 + INFLATION) ** np.arange(years)  # (years,)

    wealth = np.zeros((N_SIMS, years + 1))
    wealth[:, 0] = current_savings

    for t in range(years):
        wealth[:, t + 1] = wealth[:, t] * annual_returns[:, t] + contrib_schedule[t]

    return wealth


def apply_withdrawal(wealth: np.ndarray, year_index: int, amount: float) -> np.ndarray:
    """Subtract a lump-sum withdrawal at year_index and propagate forward."""
    wealth = wealth.copy()
    wealth[:, year_index:] -= amount
    wealth[:, year_index:] = np.maximum(wealth[:, year_index:], 0)
    return wealth


def goal_probability(wealth: np.ndarray, year_index: int, target: float) -> float:
    """Fraction of simulations where wealth at year_index >= target."""
    if year_index <= 0 or year_index >= wealth.shape[1]:
        return 0.0
    return float(np.mean(wealth[:, year_index] >= target))


def percentile_paths(wealth: np.ndarray) -> dict:
    """Return dict of percentile wealth paths for fan chart."""
    pcts = [10, 25, 50, 75, 90]
    return {p: np.percentile(wealth, p, axis=0) for p in pcts}
