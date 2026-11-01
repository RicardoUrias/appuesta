import unittest
from unittest.mock import Mock, patch

from app.analysis.value_model import (
    estimate_match_probabilities,
    over_2_5_probability,
    over_under_outcome_probabilities,
    over_under_probability,
    score_market_value,
)
from app.models import Fixture
from app.services.odds_api_client import OddsApiClient
from run_analysis import (
    attach_fixture_statistics,
    build_odds_snapshot_for_fixture,
    get_api_teams_by_name,
    find_api_team_id,
    find_odds_event,
)


def make_fixture() -> Fixture:
    return Fixture(
        fixture_id=1,
        home_team="Club America",
        away_team="Chivas Guadalajara",
        kickoff="2026-11-01T20:00:00+00:00",
        league_name="Liga MX",
        home_team_id=10,
        away_team_id=20,
        recent_home_form={"avg_goals_for": 1.6, "avg_goals_against": 0.8, "home_advantage": 1},
        recent_away_form={"avg_goals_for": 1.2, "avg_goals_against": 1.4, "away_adversity": 1},
    )


class AnalysisTests(unittest.TestCase):
    def test_goal_probabilities_are_bounded_and_totals_are_not_always_one(self) -> None:
        fixture = make_fixture()
        result_probabilities = estimate_match_probabilities(fixture)
        over_probability = over_2_5_probability(fixture)
        under_probability = over_under_probability(fixture, 2.5, over=False)

        self.assertAlmostEqual(sum(result_probabilities.values()), 1.0)
        self.assertGreater(over_probability, 0.0)
        self.assertLess(over_probability, 1.0)
        self.assertAlmostEqual(over_probability + under_probability, 1.0)

    def test_whole_goal_total_includes_push_and_correct_expected_value(self) -> None:
        fixture = make_fixture()
        outcomes = over_under_outcome_probabilities(fixture, 3.0)
        under = score_market_value(
            fixture,
            "Casa",
            "Total goles 3",
            "Menos de 3",
            odds=2.0,
            model_probability=outcomes["under_win"],
            push_probability=outcomes["push"],
        )

        self.assertAlmostEqual(sum(outcomes.values()), 1.0)
        self.assertGreater(outcomes["push"], 0.0)
        self.assertAlmostEqual(
            under.expected_value,
            outcomes["under_win"] - outcomes["over_win"],
        )
        self.assertAlmostEqual(
            under.edge,
            outcomes["under_win"] / (1.0 - outcomes["push"]) - 0.5,
        )

    def test_quarter_goal_total_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            over_under_probability(make_fixture(), 2.75, over=True)

    def test_odds_event_matches_team_names_without_accents_or_club_prefix(self) -> None:
        fixture = make_fixture()
        events = [
            {
                "home_team": "América",
                "away_team": "Chivas Guadalajara",
                "bookmakers": [],
            }
        ]

        self.assertIs(find_odds_event(fixture, events), events[0])

    def test_api_team_match_handles_ambiguous_substring(self) -> None:
        teams = {"pumas unam": 1, "pumas tabasco": 2}

        self.assertIsNone(find_api_team_id("Pumas", teams))
        self.assertEqual(find_api_team_id("Pumas UNAM", teams), 1)

    def test_api_team_directory_uses_normalized_team_names(self) -> None:
        teams = get_api_teams_by_name(
            [
                {"team": {"id": 10, "name": "Club América"}},
                {"team": {"id": 20, "name": "Guadalajara Chivas"}},
            ]
        )

        self.assertEqual(find_api_team_id("América", teams), 10)
        self.assertEqual(find_api_team_id("Chivas Guadalajara", teams), 20)

    def test_statistics_are_loaded_and_cached_per_team(self) -> None:
        fixture = make_fixture()
        client = Mock()
        client.get_team_stats.side_effect = [
            {
                "goals": {
                    "for": {"average": {"home": "1.6"}},
                    "against": {"average": {"home": "0.8"}},
                }
            },
            {
                "goals": {
                    "for": {"average": {"away": "1.2"}},
                    "against": {"average": {"away": "1.4"}},
                }
            },
        ]
        cache = {}

        self.assertTrue(attach_fixture_statistics(fixture, client, cache))
        self.assertTrue(attach_fixture_statistics(fixture, client, cache))
        self.assertEqual(client.get_team_stats.call_count, 2)
        self.assertEqual(fixture.recent_home_form["avg_goals_for"], 1.6)
        self.assertEqual(fixture.recent_away_form["avg_goals_against"], 1.4)

    def test_missing_statistics_do_not_fall_back_to_demo_values(self) -> None:
        fixture = make_fixture()
        fixture.recent_home_form = {}
        fixture.recent_away_form = {}
        client = Mock()
        client.get_team_stats.return_value = {}

        self.assertFalse(attach_fixture_statistics(fixture, client, {}))
        self.assertEqual(fixture.recent_home_form, {})
        self.assertEqual(fixture.recent_away_form, {})

    def test_snapshot_uses_best_bookmaker_price_for_each_selection(self) -> None:
        fixture = make_fixture()
        fixture.recent_home_form["avg_goals_for"] = 1.6
        event = {
            "bookmakers": [
                {
                    "title": "Casa A",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "America", "price": 2.0},
                                {"name": "Draw", "price": 3.2},
                                {"name": "Chivas Guadalajara", "price": 3.8},
                            ],
                        },
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "point": 2.5, "price": 2.0},
                                {"name": "Under", "point": 2.5, "price": 1.9},
                            ],
                        },
                    ],
                },
                {
                    "title": "Casa B",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [{"name": "Club América", "price": 2.1}],
                        }
                    ],
                },
            ]
        }

        snapshot = build_odds_snapshot_for_fixture(fixture, event)
        local_offer = next(offer for offer in snapshot if offer["selection"] == "Local")

        self.assertEqual(local_offer["odds"], 2.1)
        self.assertEqual(local_offer["bookmaker"], "Casa B")
        self.assertEqual(len(snapshot), 5)

    def test_odds_client_requests_configured_mexican_soccer_market(self) -> None:
        response = Mock(status_code=200)
        response.json.return_value = []
        client = OddsApiClient(api_key="test-key")

        with patch("app.services.odds_api_client.requests.get", return_value=response) as request:
            self.assertEqual(client.get_market_odds(), [])

        self.assertTrue(request.call_args.args[0].endswith("/sports/soccer_mexico_ligamx/odds"))
        self.assertEqual(request.call_args.kwargs["params"]["regions"], "us")
        self.assertEqual(request.call_args.kwargs["params"]["markets"], "h2h,totals")


if __name__ == "__main__":
    unittest.main()
