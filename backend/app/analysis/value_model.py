from __future__ import annotations

from typing import Dict, List

from app.models import Fixture, MarketOutcome, TopValuePick


def implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 0:
        return 0.0
    return 1.0 / decimal_odds


def poisson_probabilities(lambda_home: float, lambda_away: float) -> Dict[str, float]:
    import math

    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    for goals_home in range(0, 8):
        for goals_away in range(0, 8):
            p = (math.exp(-lambda_home) * (lambda_home ** goals_home) / math.factorial(goals_home)) * (
                math.exp(-lambda_away) * (lambda_away ** goals_away) / math.factorial(goals_away)
            )
            if goals_home > goals_away:
                home_win += p
            elif goals_home < goals_away:
                away_win += p
            else:
                draw += p

    total = home_win + draw + away_win
    if total <= 0:
        return {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}

    return {
        "home_win": home_win / total,
        "draw": draw / total,
        "away_win": away_win / total,
    }


def estimate_goal_rates(fixture: Fixture) -> Dict[str, float]:
    home_form = fixture.recent_home_form
    away_form = fixture.recent_away_form

    home_attack = home_form.get("avg_goals_for", 1.25)
    away_defense = away_form.get("avg_goals_against", 1.35)
    away_attack = away_form.get("avg_goals_for", 1.15)
    home_defense = home_form.get("avg_goals_against", 1.20)

    # Ajuste simple por localía + factor de México, sin seguir promesas absolutas.
    lambda_home = max(0.25, (home_attack + (1.12 if home_form.get("home_advantage", 0) > 0 else 1.0)) * 0.63)
    lambda_away = max(0.25, (away_attack + (0.94 if away_form.get("away_adversity", 0) > 0 else 1.0)) * 0.57)

    # Se incorporan defensas para mantener el modelo más realista.
    lambda_home *= max(0.75, min(1.25, 1.2 / max(0.8, home_defense)))
    lambda_away *= max(0.75, min(1.25, 1.2 / max(0.8, away_defense)))

    return {"home": lambda_home, "away": lambda_away}


def estimate_match_probabilities(fixture: Fixture) -> Dict[str, float]:
    goal_rates = estimate_goal_rates(fixture)
    return poisson_probabilities(goal_rates["home"], goal_rates["away"])


def over_under_probability(fixture: Fixture, goal_line: float, over: bool) -> float:
    probabilities = over_under_outcome_probabilities(fixture, goal_line)
    return probabilities["over_win"] if over else probabilities["under_win"]


def over_under_outcome_probabilities(fixture: Fixture, goal_line: float) -> Dict[str, float]:
    import math

    if goal_line < 0:
        raise ValueError("La línea de goles debe ser mayor o igual a cero.")
    if not math.isclose(goal_line * 2, round(goal_line * 2), abs_tol=1e-9):
        raise ValueError("Solo se soportan líneas de goles enteras o medias.")

    total_goal_rate = sum(estimate_goal_rates(fixture).values())
    probabilities: List[float] = []
    probability = math.exp(-total_goal_rate)
    cumulative = 0.0
    for goals in range(100):
        if goals:
            probability *= total_goal_rate / goals
        probabilities.append(probability)
        cumulative += probability
        if cumulative >= 1.0 - 1e-12:
            break

    def at_most(max_goals: int) -> float:
        return sum(probabilities[: max_goals + 1])

    if math.isclose(goal_line, round(goal_line), abs_tol=1e-9):
        exact_line = int(round(goal_line))
        push_probability = probabilities[exact_line] if exact_line < len(probabilities) else 0.0
        under_probability = at_most(exact_line - 1)
        over_probability = max(0.0, 1.0 - under_probability - push_probability)
    else:
        under_probability = at_most(math.floor(goal_line))
        push_probability = 0.0
        over_probability = max(0.0, 1.0 - under_probability)

    return {
        "over_win": over_probability,
        "push": push_probability,
        "under_win": under_probability,
    }


def over_2_5_probability(fixture: Fixture) -> float:
    return over_under_probability(fixture, goal_line=2.5, over=True)


def score_market_value(
    fixture: Fixture,
    bookmaker: str,
    market_name: str,
    selection: str,
    odds: float,
    model_probability: float,
    push_probability: float = 0.0,
) -> MarketOutcome:
    imp_prob = implied_probability(odds)
    decisive_probability = max(0.0, 1.0 - push_probability)
    conditional_model_probability = (
        model_probability / decisive_probability if decisive_probability > 0 else 0.0
    )
    edge = conditional_model_probability - imp_prob
    expected_value = (model_probability * odds) + push_probability - 1.0

    return MarketOutcome(
        market_name=market_name,
        selection=selection,
        bookmaker=bookmaker,
        odds=odds,
        implied_probability=imp_prob,
        model_probability=model_probability,
        edge=edge,
        expected_value=expected_value,
        push_probability=push_probability,
    )


def find_top_value_bets(fixture: Fixture, odds_snapshots: List[Dict[str, object]], threshold: float = 0.08) -> List[TopValuePick]:
    results: List[TopValuePick] = []
    model = estimate_match_probabilities(fixture)

    for item in odds_snapshots:
        bookmaker = str(item.get("bookmaker", "N/A"))
        market_name = str(item.get("market_name", "N/A"))
        selection = str(item.get("selection", "N/A"))
        odds = float(item.get("odds", 0.0))
        model_prob = float(item.get("model_probability", 0.0))
        push_prob = float(item.get("push_probability", 0.0))

        outcome = score_market_value(
            fixture,
            bookmaker,
            market_name,
            selection,
            odds,
            model_prob,
            push_probability=push_prob,
        )
        if outcome.edge <= threshold:
            continue

        confidence = max(0.0, min(1.0, outcome.edge / 0.2))
        results.append(
            TopValuePick(
                fixture_id=fixture.fixture_id,
                home_team=fixture.home_team,
                away_team=fixture.away_team,
                kickoff=fixture.kickoff,
                market_name=outcome.market_name,
                selection=outcome.selection,
                bookmaker=outcome.bookmaker,
                odds=outcome.odds,
                model_probability=outcome.model_probability,
                implied_probability=outcome.implied_probability,
                edge=outcome.edge,
                expected_value=outcome.expected_value,
                confidence=confidence,
                push_probability=outcome.push_probability,
            )
        )

    # Reordenar por mejor combinación de edge y EV.
    results.sort(key=lambda pick: (pick.edge, pick.expected_value, pick.confidence), reverse=True)
    return results
