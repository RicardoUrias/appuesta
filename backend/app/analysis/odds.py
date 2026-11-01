from __future__ import annotations

import math
from typing import Any, Dict, List

from app.analysis.value_model import estimate_match_probabilities, over_under_outcome_probabilities
from app.models import Fixture
from app.utils.team_names import normalize_team_name


def _result_selection(name: str, fixture: Fixture, probabilities: Dict[str, float]) -> tuple[str, str, float] | None:
    normalized = normalize_team_name(name)
    if normalized in {"draw", "tie", "empate"}:
        return "Empate", "draw", probabilities["draw"]
    if normalized == normalize_team_name(fixture.home_team):
        return "Local", "home", probabilities["home_win"]
    if normalized == normalize_team_name(fixture.away_team):
        return "Visitante", "away", probabilities["away_win"]
    return None


def build_odds_snapshot_for_fixture(
    fixture: Fixture,
    odds_event: Dict[str, Any],
) -> List[Dict[str, object]]:
    best_offers: Dict[tuple[str, str], Dict[str, object]] = {}
    result_probabilities = estimate_match_probabilities(fixture)

    for bookmaker in odds_event.get("bookmakers", []):
        bookmaker_name = str(bookmaker.get("title", "N/A"))
        for market in bookmaker.get("markets", []):
            market_key = market.get("key")
            for outcome in market.get("outcomes", []):
                try:
                    price = float(outcome.get("price", 0))
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(price) or price <= 1:
                    continue

                if market_key == "h2h":
                    result = _result_selection(str(outcome.get("name", "")), fixture, result_probabilities)
                    if result is None:
                        continue
                    selection, outcome_key, model_probability = result
                    market_name = "Resultado 1X2"
                    line = -1.0
                    push_probability = 0.0
                elif market_key == "totals":
                    outcome_name = str(outcome.get("name", "")).casefold()
                    if outcome_name not in {"over", "under"}:
                        continue
                    try:
                        goal_line = float(outcome.get("point"))
                    except (TypeError, ValueError):
                        continue
                    if not math.isfinite(goal_line) or goal_line < 0:
                        continue
                    if not math.isclose(goal_line * 2, round(goal_line * 2), abs_tol=1e-9):
                        continue
                    is_over = outcome_name == "over"
                    selection = f"{'Más' if is_over else 'Menos'} de {goal_line:g}"
                    outcome_key = outcome_name
                    probabilities = over_under_outcome_probabilities(fixture, goal_line)
                    model_probability = probabilities["over_win" if is_over else "under_win"]
                    push_probability = probabilities["push"]
                    market_name = f"Total goles {goal_line:g}"
                    line = goal_line
                else:
                    continue

                offer_key = (market_name, selection)
                if price <= float(best_offers.get(offer_key, {}).get("odds", 0.0)):
                    continue
                best_offers[offer_key] = {
                    "bookmaker": bookmaker_name,
                    "market_name": market_name,
                    "market_key": str(market_key),
                    "outcome_key": outcome_key,
                    "selection": selection,
                    "odds": price,
                    "model_probability": model_probability,
                    "push_probability": push_probability,
                    "line": line,
                }

    return list(best_offers.values())
