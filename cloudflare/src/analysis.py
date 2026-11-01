from __future__ import annotations

import math
from typing import Any, Dict, List

from app.analysis.odds import build_odds_snapshot_for_fixture
from app.analysis.value_model import find_top_value_bets
from app.models import Fixture
from app.utils.team_names import normalize_team_name


def _average_goals(stats: Dict[str, Any], category: str, venue: str) -> float | None:
    goals = stats.get("goals")
    if not isinstance(goals, dict):
        return None
    category_stats = goals.get(category)
    if not isinstance(category_stats, dict):
        return None
    averages = category_stats.get("average")
    if not isinstance(averages, dict):
        return None
    value = averages.get(venue)
    try:
        average = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(average) or average < 0:
        return None
    return average


def create_fixture(
    event: Dict[str, Any],
    home_team_id: int,
    away_team_id: int,
    stats_by_team: Dict[int, Dict[str, Any]],
) -> Fixture | None:
    home_stats = stats_by_team.get(home_team_id)
    away_stats = stats_by_team.get(away_team_id)
    if home_stats is None or away_stats is None:
        return None

    home_for = _average_goals(home_stats, "for", "home")
    home_against = _average_goals(home_stats, "against", "home")
    away_for = _average_goals(away_stats, "for", "away")
    away_against = _average_goals(away_stats, "against", "away")
    if any(value is None for value in (home_for, home_against, away_for, away_against)):
        return None

    return Fixture(
        fixture_id=0,
        home_team=str(event.get("home_team", "Local")),
        away_team=str(event.get("away_team", "Visitante")),
        kickoff=str(event.get("commence_time", "")),
        league_name="Liga MX",
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        recent_home_form={
            "avg_goals_for": home_for,
            "avg_goals_against": home_against,
            "home_advantage": 1,
        },
        recent_away_form={
            "avg_goals_for": away_for,
            "avg_goals_against": away_against,
            "away_adversity": 1,
        },
    )


def build_fixture_candidates(
    fixture: Fixture,
    event: Dict[str, Any],
    threshold: float = 0.08,
) -> List[Dict[str, Any]]:
    event_id = str(event.get("id", ""))
    if not event_id:
        return []

    odds = build_odds_snapshot_for_fixture(fixture, event)
    offers_by_key = {
        (str(offer["market_name"]), str(offer["selection"])): offer
        for offer in odds
    }
    value_picks = find_top_value_bets(fixture, odds, threshold=threshold)
    candidates: List[Dict[str, Any]] = []
    for pick in value_picks:
        offer = offers_by_key[(pick.market_name, pick.selection)]
        candidates.append(
            {
                "event_id": event_id,
                "kickoff": fixture.kickoff,
                "home_team": fixture.home_team,
                "away_team": fixture.away_team,
                "market_key": offer["market_key"],
                "outcome_key": offer["outcome_key"],
                "selection": pick.selection,
                "line": offer["line"],
                "bookmaker": pick.bookmaker,
                "odds": pick.odds,
                "model_probability": pick.model_probability,
                "implied_probability": pick.implied_probability,
                "push_probability": pick.push_probability,
                "edge": pick.edge,
                "expected_value": pick.expected_value,
            }
        )
    return candidates


def rank_top_picks(candidates: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    ordered = sorted(
        candidates,
        key=lambda pick: (pick["edge"], pick["expected_value"], pick["model_probability"]),
        reverse=True,
    )
    selected: List[Dict[str, Any]] = []
    seen_events: set[str] = set()
    for pick in ordered:
        event_id = str(pick["event_id"])
        if event_id in seen_events:
            continue
        seen_events.add(event_id)
        selected.append(pick)
        if len(selected) == limit:
            break
    return selected


def settle_pick(pick: Dict[str, Any], score_event: Dict[str, Any]) -> Dict[str, Any] | None:
    if not score_event.get("completed"):
        return None

    scores = score_event.get("scores")
    if not scores:
        return {"status": "void", "home_score": None, "away_score": None}
    if not isinstance(scores, list) or any(not isinstance(score, dict) for score in scores):
        return None

    home_name = normalize_team_name(str(pick["home_team"]))
    away_name = normalize_team_name(str(pick["away_team"]))
    score_by_team: Dict[str, int] = {}
    for score in scores:
        name = normalize_team_name(str(score.get("name", "")))
        try:
            value = int(score.get("score"))
        except (TypeError, ValueError):
            continue
        if name:
            score_by_team[name] = value

    def find_score(team_name: str) -> int | None:
        exact = score_by_team.get(team_name)
        if exact is not None:
            return exact
        parts = set(team_name.split())
        matches = [
            score
            for name, score in score_by_team.items()
            if parts and (parts.issubset(name.split()) or set(name.split()).issubset(parts))
        ]
        return matches[0] if len(matches) == 1 else None

    home_score = find_score(home_name)
    away_score = find_score(away_name)
    if home_score is None or away_score is None:
        return None

    if pick["market_key"] == "h2h":
        outcome_key = pick["outcome_key"]
        won = (
            (outcome_key == "home" and home_score > away_score)
            or (outcome_key == "away" and away_score > home_score)
            or (outcome_key == "draw" and home_score == away_score)
        )
        status = "won" if won else "lost"
    elif pick["market_key"] == "totals":
        total_goals = home_score + away_score
        line = float(pick["line"])
        if math.isclose(total_goals, line, abs_tol=1e-9):
            status = "push"
        else:
            won = (
                (pick["outcome_key"] == "over" and total_goals > line)
                or (pick["outcome_key"] == "under" and total_goals < line)
            )
            status = "won" if won else "lost"
    else:
        return None

    return {"status": status, "home_score": home_score, "away_score": away_score}
