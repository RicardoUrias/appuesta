import unittest

from src.analysis import (
    build_fixture_candidates,
    create_fixture,
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
