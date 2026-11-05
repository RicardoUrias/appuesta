import unittest

from src.analysis import (
    build_widget_dashboard,
    build_fixture_candidates,
    create_fixture,
    normalize_fixture_detail,
    rank_top_picks,
    settle_pick,
)


def event() -> dict:
    return {
        "id": "odds-event-1",
        "home_team": "Club America",
        "away_team": "Chivas Guadalajara",
        "commence_time": "2026-11-01T20:00:00Z",
        "bookmakers": [
            {
                "title": "Casa de prueba",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "America", "price": 7.0},
                            {"name": "Draw", "price": 3.2},
                            {"name": "Chivas Guadalajara", "price": 3.8},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "point": 2.5, "price": 2.1},
                            {"name": "Under", "point": 2.5, "price": 1.9},
                        ],
                    },
                ],
            }
        ],
    }


def team_stats(home: bool) -> dict:
    venue = "home" if home else "away"
    return {
        "goals": {
            "for": {"average": {venue: "1.6" if home else "1.2"}},
            "against": {"average": {venue: "0.8" if home else "1.4"}},
        }
    }


class AnalysisTests(unittest.TestCase):
    def test_widget_dashboard_estimates_winner_from_recent_completed_fixtures(self) -> None:
        upcoming = [{
            "fixture": {"id": 99, "date": "2026-11-20T20:00:00+00:00", "status": {"short": "NS"}},
            "teams": {
                "home": {"id": 10, "name": "America", "logo": "https://example.test/a.png"},
                "away": {"id": 20, "name": "Chivas", "logo": "https://example.test/c.png"},
            },
            "goals": {"home": None, "away": None},
            "league": {"round": "Apertura - 15"},
        }]
        recent = []
        for timestamp, home_goals, away_goals in (
            (100, 2, 0),
            (200, 1, 0),
            (300, 3, 1),
        ):
            recent.append({
                "fixture": {"timestamp": timestamp, "status": {"short": "FT"}},
                "teams": {"home": {"id": 10}, "away": {"id": 20}},
                "goals": {"home": home_goals, "away": away_goals},
            })
        standings = [{
            "league": {
                "standings": [[{
                    "rank": 1,
                    "team": {"name": "America", "logo": "https://example.test/a.png"},
                    "all": {
                        "played": 10,
                        "win": 8,
                        "draw": 1,
                        "lose": 1,
                        "goals": {"for": 20, "against": 8},
                    },
                    "goalsDiff": 12,
                    "points": 25,
                    "form": "WWDWW",
                }]],
            },
        }]

        result = build_widget_dashboard(upcoming, recent, standings)

        fixture = result["fixtures"][0]
        self.assertEqual(fixture["form_sample"], {"home": 3, "away": 3})
        self.assertEqual(fixture["prediction"]["likely_outcome"], "home_win")
        self.assertAlmostEqual(
            sum(fixture["prediction"][key] for key in ("home_win", "draw", "away_win")),
            1.0,
        )
        self.assertEqual(result["standings"][0]["points"], 25)

    def test_widget_dashboard_withholds_prediction_without_minimum_recent_form(self) -> None:
        fixture = {
            "fixture": {"id": 1, "date": "2026-11-20T20:00:00Z"},
            "teams": {"home": {"id": 10, "name": "America"}, "away": {"id": 20, "name": "Chivas"}},
            "goals": {"home": None, "away": None},
        }
        recent = [{
            "fixture": {"timestamp": 1, "status": {"short": "FT"}},
            "teams": {"home": {"id": 10}, "away": {"id": 20}},
            "goals": {"home": 1, "away": 0},
        }]

        result = build_widget_dashboard([fixture], recent, [])

        self.assertIsNone(result["fixtures"][0]["prediction"])
        self.assertEqual(result["fixtures"][0]["form_sample"], {"home": 1, "away": 1})

    def test_normalize_fixture_detail_preserves_available_match_data(self) -> None:
        detail = normalize_fixture_detail([{
            "fixture": {
                "id": 123,
                "date": "2026-11-20T20:00:00Z",
                "status": {"long": "Not Started", "elapsed": None},
                "venue": {"name": "Estadio", "city": "CDMX"},
                "referee": None,
            },
            "teams": {"home": {"name": "America"}, "away": {"name": "Chivas"}},
            "goals": {"home": None, "away": None},
            "events": [],
            "statistics": [],
            "lineups": [],
        }])

        self.assertEqual(detail["id"], 123)
        self.assertEqual(detail["venue"], "Estadio")
        self.assertEqual(detail["home_team"], "America")
        self.assertEqual(detail["events"], [])

    def test_create_fixture_requires_historical_stats_for_both_teams(self) -> None:
        self.assertIsNone(create_fixture(event(), 10, 20, {10: team_stats(True)}))
        fixture = create_fixture(
            event(),
            10,
            20,
            {10: team_stats(True), 20: team_stats(False)},
        )

        self.assertIsNotNone(fixture)
        self.assertEqual(fixture.home_team_id, 10)
        self.assertEqual(fixture.recent_away_form["avg_goals_against"], 1.4)

    def test_candidates_use_configured_edge_threshold_and_keep_snapshot_details(self) -> None:
        fixture = create_fixture(
            event(),
            10,
            20,
            {10: team_stats(True), 20: team_stats(False)},
        )
        self.assertIsNotNone(fixture)

        candidates = build_fixture_candidates(fixture, event(), threshold=0.08)

        self.assertTrue(candidates)
        self.assertTrue(all(pick["edge"] > 0.08 for pick in candidates))
        self.assertTrue(all(pick["event_id"] == "odds-event-1" for pick in candidates))
        self.assertTrue(all(pick["bookmaker"] == "Casa de prueba" for pick in candidates))

    def test_rank_top_picks_limits_results_and_avoids_repeating_fixture(self) -> None:
        candidates = [
            {"event_id": "same", "edge": 0.4, "expected_value": 0.2, "model_probability": 0.8},
            {"event_id": "same", "edge": 0.3, "expected_value": 0.3, "model_probability": 0.7},
            {"event_id": "other", "edge": 0.2, "expected_value": 0.1, "model_probability": 0.6},
            {"event_id": "third", "edge": 0.1, "expected_value": 0.2, "model_probability": 0.5},
        ]

        top = rank_top_picks(candidates, limit=2)

        self.assertEqual([pick["event_id"] for pick in top], ["same", "other"])

    def test_settlement_handles_home_win_draw_loss_and_unresolved_scores(self) -> None:
        pick = {
            "home_team": "Club America",
            "away_team": "Chivas Guadalajara",
            "market_key": "h2h",
            "outcome_key": "home",
        }
        score_event = {
            "completed": True,
            "scores": [{"name": "America", "score": "2"}, {"name": "Chivas", "score": "1"}],
        }

        self.assertEqual(settle_pick(pick, score_event)["status"], "won")
        score_event["scores"][0]["score"] = "0"
        self.assertEqual(settle_pick(pick, score_event)["status"], "lost")
        score_event["scores"][1]["score"] = "0"
        self.assertEqual(settle_pick(pick, score_event)["status"], "lost")
        pick["outcome_key"] = "draw"
        self.assertEqual(settle_pick(pick, score_event)["status"], "won")
        self.assertIsNone(settle_pick(pick, {"completed": False, "scores": []}))
        self.assertIsNone(settle_pick(pick, {"completed": True, "scores": [{"name": "America", "score": "0"}]}))

    def test_settlement_handles_total_over_under_push_and_missing_score(self) -> None:
        pick = {
            "home_team": "America",
            "away_team": "Chivas Guadalajara",
            "market_key": "totals",
            "outcome_key": "over",
            "line": 2.0,
        }
        score_event = {
            "completed": True,
            "scores": [{"name": "America", "score": "1"}, {"name": "Chivas", "score": "1"}],
        }

        self.assertEqual(settle_pick(pick, score_event)["status"], "push")
        pick["outcome_key"] = "under"
        score_event["scores"][0]["score"] = "2"
        self.assertEqual(settle_pick(pick, score_event)["status"], "lost")
        score_event["scores"][0]["score"] = "0"
        self.assertEqual(settle_pick(pick, score_event)["status"], "won")
        self.assertEqual(settle_pick(pick, {"completed": True, "scores": []})["status"], "void")


if __name__ == "__main__":
    unittest.main()
