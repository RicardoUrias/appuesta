from __future__ import annotations

import math
from typing import Any, Dict, List

from app.analysis.odds import build_odds_snapshot_for_fixture
from app.analysis.value_model import estimate_match_probabilities, find_top_value_bets
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


def build_widget_dashboard(
    fixtures: List[Dict[str, Any]],
    recent_fixtures: List[Dict[str, Any]],
    standings_response: List[Dict[str, Any]],
    form_matches: int = 5,
    minimum_form_matches: int = 3,
) -> Dict[str, Any]:
    recent_by_team: Dict[int, List[tuple[int, int, int]]] = {}
    for item in recent_fixtures:
        teams = item.get("teams")
        goals = item.get("goals")
        fixture_data = item.get("fixture")
        if not isinstance(teams, dict) or not isinstance(goals, dict) or not isinstance(fixture_data, dict):
            continue
        status = fixture_data.get("status")
        if not isinstance(status, dict) or status.get("short") not in {"FT", "AET", "PEN"}:
            continue
        try:
            timestamp = int(fixture_data.get("timestamp", 0))
            home_goals = int(goals["home"])
            away_goals = int(goals["away"])
            home_id = int(teams["home"]["id"])
            away_id = int(teams["away"]["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if home_goals < 0 or away_goals < 0:
            continue
        recent_by_team.setdefault(home_id, []).append((timestamp, home_goals, away_goals))
        recent_by_team.setdefault(away_id, []).append((timestamp, away_goals, home_goals))

    team_form: Dict[int, Dict[str, float | int]] = {}
    for team_id, results in recent_by_team.items():
        latest = sorted(results, key=lambda result: result[0], reverse=True)[:form_matches]
        if not latest:
            continue
        team_form[team_id] = {
            "games": len(latest),
            "goals_for": sum(result[1] for result in latest) / len(latest),
            "goals_against": sum(result[2] for result in latest) / len(latest),
        }

    upcoming: List[Dict[str, Any]] = []
    for item in fixtures:
        fixture_data = item.get("fixture")
        teams = item.get("teams")
        if not isinstance(fixture_data, dict) or not isinstance(teams, dict):
            continue
        home = teams.get("home")
        away = teams.get("away")
        if not isinstance(home, dict) or not isinstance(away, dict):
            continue
        try:
            fixture_id = int(fixture_data["id"])
            home_id = int(home["id"])
            away_id = int(away["id"])
        except (KeyError, TypeError, ValueError):
            continue
        home_name = str(home.get("name", ""))
        away_name = str(away.get("name", ""))
        if not home_name or not away_name:
            continue

        home_form = team_form.get(home_id)
        away_form = team_form.get(away_id)
        prediction = None
        sample = {
            "home": int(home_form["games"]) if home_form else 0,
            "away": int(away_form["games"]) if away_form else 0,
        }
        if (
            home_form is not None
            and away_form is not None
            and sample["home"] >= minimum_form_matches
            and sample["away"] >= minimum_form_matches
        ):
            model_fixture = Fixture(
                fixture_id=fixture_id,
                home_team=home_name,
                away_team=away_name,
                kickoff=str(fixture_data.get("date", "")),
                league_name="Liga MX",
                home_team_id=home_id,
                away_team_id=away_id,
                recent_home_form={
                    "avg_goals_for": float(home_form["goals_for"]),
                    "avg_goals_against": float(home_form["goals_against"]),
                    "home_advantage": 1,
                },
                recent_away_form={
                    "avg_goals_for": float(away_form["goals_for"]),
                    "avg_goals_against": float(away_form["goals_against"]),
                    "away_adversity": 1,
                },
            )
            probabilities = estimate_match_probabilities(model_fixture)
            outcome = max(probabilities, key=lambda key: probabilities[key])
            prediction = {
                "home_win": probabilities["home_win"],
                "draw": probabilities["draw"],
                "away_win": probabilities["away_win"],
                "likely_outcome": outcome,
                "likely_probability": probabilities[outcome],
            }

        league = item.get("league") if isinstance(item.get("league"), dict) else {}
        venue = fixture_data.get("venue") if isinstance(fixture_data.get("venue"), dict) else {}
        status = fixture_data.get("status") if isinstance(fixture_data.get("status"), dict) else {}
        goals = item.get("goals") if isinstance(item.get("goals"), dict) else {}
        upcoming.append(
            {
                "id": fixture_id,
                "kickoff": str(fixture_data.get("date", "")),
                "status": str(status.get("long", "Por jugar")),
                "status_short": str(status.get("short", "")),
                "venue": venue.get("name"),
                "round": league.get("round"),
                "home_team": {"id": home_id, "name": home_name, "logo": home.get("logo")},
                "away_team": {"id": away_id, "name": away_name, "logo": away.get("logo")},
                "home_goals": goals.get("home"),
                "away_goals": goals.get("away"),
                "prediction": prediction,
                "form_sample": sample,
            }
        )

    table: List[Dict[str, Any]] = []
    for response in standings_response:
        league = response.get("league")
        if not isinstance(league, dict):
            continue
        groups = league.get("standings")
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, list):
                continue
            for row in group:
                if not isinstance(row, dict) or not isinstance(row.get("team"), dict):
                    continue
                team = row["team"]
                all_stats = row.get("all") if isinstance(row.get("all"), dict) else {}
                goals = all_stats.get("goals") if isinstance(all_stats.get("goals"), dict) else {}
                table.append(
                    {
                        "rank": row.get("rank"),
                        "team": str(team.get("name", "")),
                        "logo": team.get("logo"),
                        "played": all_stats.get("played"),
                        "won": all_stats.get("win"),
                        "drawn": all_stats.get("draw"),
                        "lost": all_stats.get("lose"),
                        "goals_for": goals.get("for"),
                        "goals_against": goals.get("against"),
                        "goal_difference": row.get("goalsDiff"),
                        "points": row.get("points"),
                        "form": row.get("form"),
                        "group": row.get("group"),
                    }
                )

    return {"standings": table, "fixtures": upcoming}


def normalize_fixture_detail(fixtures: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not fixtures:
        return None
    item = fixtures[0]
    fixture = item.get("fixture")
    teams = item.get("teams")
    if not isinstance(fixture, dict) or not isinstance(teams, dict):
        return None
    home = teams.get("home") if isinstance(teams.get("home"), dict) else {}
    away = teams.get("away") if isinstance(teams.get("away"), dict) else {}
    venue = fixture.get("venue") if isinstance(fixture.get("venue"), dict) else {}
    status = fixture.get("status") if isinstance(fixture.get("status"), dict) else {}
    goals = item.get("goals") if isinstance(item.get("goals"), dict) else {}
    return {
        "id": fixture.get("id"),
        "kickoff": fixture.get("date"),
        "status": status.get("long"),
        "elapsed": status.get("elapsed"),
        "venue": venue.get("name"),
        "city": venue.get("city"),
        "referee": fixture.get("referee"),
        "home_team": home.get("name"),
        "away_team": away.get("name"),
        "home_logo": home.get("logo"),
        "away_logo": away.get("logo"),
        "home_goals": goals.get("home"),
        "away_goals": goals.get("away"),
        "events": item.get("events") if isinstance(item.get("events"), list) else [],
        "statistics": item.get("statistics") if isinstance(item.get("statistics"), list) else [],
        "lineups": item.get("lineups") if isinstance(item.get("lineups"), list) else [],
    }
