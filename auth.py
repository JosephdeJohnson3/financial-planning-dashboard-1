import json
import os
from typing import Optional

PROFILES_FILE = os.path.join(os.path.dirname(__file__), "profiles.json")
CURRENT_YEAR = 2026

DEFAULT_SETTINGS: dict = {
    "current_age": 30,
    "current_savings": 50000,
    "monthly_contribution": 1500,
    "allocation": "Moderate (60/40)",
    "custom_mu": 7.0,
    "custom_sigma": 10.0,
    "invest_enabled": False,
    "invest_amount": 250000,
    "invest_year": CURRENT_YEAR + 10,
    "ret_enabled": False,
    "ret_age": 65,
    "ret_income": 6000,
    "ret_ss": 1800,
    "ret_years": 25,
    "home_enabled": False,
    "home_year": CURRENT_YEAR + 5,
    "home_down": 100000,
    "college_enabled": False,
    "college_year": CURRENT_YEAR + 18,
    "college_base": 80000,
    "custom_enabled": False,
    "custom_name": "Sabbatical Fund",
    "custom_year": CURRENT_YEAR + 10,
    "custom_amount": 50000,
    "goal_allocations": {},
}


def load_profiles() -> dict:
    if os.path.exists(PROFILES_FILE):
        with open(PROFILES_FILE, "r") as f:
            return json.load(f)
    return {}


def save_profiles(profiles: dict) -> None:
    with open(PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=2)


def make_key(first_name: str, last_initial: str) -> str:
    return f"{first_name.strip().capitalize()}{last_initial.strip()[0].upper()}"


def make_display(first_name: str, last_initial: str) -> str:
    return f"{first_name.strip().capitalize()} {last_initial.strip()[0].upper()}."


def get_settings(profiles: dict, user_key: str, participant_key: Optional[str] = None) -> dict:
    base = dict(DEFAULT_SETTINGS)
    profile = profiles.get(user_key, {})
    if participant_key:
        stored = profile.get("participants", {}).get(participant_key, {}).get("settings", {})
    else:
        stored = profile.get("settings", {})
    base.update(stored)
    return base


def save_settings(profiles: dict, user_key: str, settings: dict, participant_key: Optional[str] = None) -> None:
    if user_key not in profiles:
        profiles[user_key] = {"display_name": user_key, "settings": dict(DEFAULT_SETTINGS), "participants": {}}
    if participant_key:
        profiles[user_key].setdefault("participants", {}).setdefault(
            participant_key, {"display_name": participant_key, "settings": {}}
        )["settings"] = settings
    else:
        profiles[user_key]["settings"] = settings
    save_profiles(profiles)


def add_participant(profiles: dict, user_key: str, first_name: str, last_initial: str) -> tuple[str, str]:
    key = make_key(first_name, last_initial)
    display = make_display(first_name, last_initial)
    profiles[user_key].setdefault("participants", {})[key] = {
        "display_name": display,
        "settings": dict(DEFAULT_SETTINGS),
    }
    save_profiles(profiles)
    return key, display


def list_participants(profiles: dict, user_key: str) -> list[tuple[str, str]]:
    return [
        (k, v["display_name"])
        for k, v in profiles.get(user_key, {}).get("participants", {}).items()
    ]
