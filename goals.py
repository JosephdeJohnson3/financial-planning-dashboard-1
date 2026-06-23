from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from simulation import apply_withdrawal, goal_probability

COLLEGE_INFLATION = 0.05


@dataclass
class Goal:
    name: str
    target_amount: float
    target_year: int
    enabled: bool = True
    probability: float = 0.0


@dataclass
class RetirementGoal(Goal):
    monthly_income_needed: float = 5_000.0
    years_in_retirement: int = 25
    social_security_monthly: float = 1_500.0


@dataclass
class InvestmentTargetGoal(Goal):
    pass


@dataclass
class HomePurchaseGoal(Goal):
    pass


@dataclass
class CollegeTuitionGoal(Goal):
    pass


@dataclass
class CustomGoal(Goal):
    pass


def compute_retirement_target(
    monthly_income: float,
    social_security: float,
    years_in_retirement: int,
    withdrawal_rate: float = 0.04,
) -> float:
    """4% rule: portfolio must fund (income - SS) * 12 / withdrawal_rate."""
    annual_gap = (monthly_income - social_security) * 12
    annual_gap = max(annual_gap, 0)
    return annual_gap / withdrawal_rate


def compute_college_target(base_cost: float, years_until: int) -> float:
    return base_cost * (1 + COLLEGE_INFLATION) ** years_until


def evaluate_goals(
    wealth: np.ndarray,
    goals: list[Goal],
    current_year: int,
) -> tuple[np.ndarray, list[Goal]]:
    """
    Evaluate goals in chronological order, applying withdrawals and computing
    probabilities. Returns updated wealth array and goals with probabilities set.
    """
    sorted_goals = sorted(
        [g for g in goals if g.enabled],
        key=lambda g: g.target_year,
    )

    w = wealth.copy()
    for goal in sorted_goals:
        year_index = goal.target_year - current_year
        goal.probability = goal_probability(w, year_index, goal.target_amount)
        w = apply_withdrawal(w, year_index, goal.target_amount)

    return w, sorted_goals
