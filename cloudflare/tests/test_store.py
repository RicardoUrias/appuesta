import sqlite3
import unittest
from pathlib import Path
from typing import Any

from src.store import D1Store


class FakeResult:
    def __init__(self, results: Any = None, changes: int = 0) -> None:
        self.results = results
        self.meta = {"changes": changes}


class FakeStatement:
    def __init__(self, connection: sqlite3.Connection, sql: str) -> None:
        self.connection = connection
        self.sql = sql
        self.params: tuple[Any, ...] = ()

    def bind(self, *params: Any) -> "FakeStatement":
        self.params = params
        return self

    async def all(self) -> FakeResult:
        rows = self.connection.execute(self.sql, self.params).fetchall()
        return FakeResult([dict(row) for row in rows])

    async def first(self) -> dict[str, Any] | None:
        row = self.connection.execute(self.sql, self.params).fetchone()
        return dict(row) if row is not None else None

    async def run(self) -> FakeResult:
        cursor = self.connection.execute(self.sql, self.params)
        self.connection.commit()
        return FakeResult(changes=max(0, cursor.rowcount))


class FakeDatabase:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def prepare(self, sql: str) -> FakeStatement:
        return FakeStatement(self.connection, sql)


def make_pick(event_id: str = "event-1") -> dict[str, Any]:
    return {
        "event_id": event_id,
        "kickoff": "2026-11-01T20:00:00+00:00",
        "home_team": "America",
        "away_team": "Chivas",
        "market_key": "h2h",
        "outcome_key": "home",
        "selection": "Local",
        "line": -1.0,
        "bookmaker": "Casa",
        "odds": 2.1,
        "model_probability": 0.6,
        "implied_probability": 1 / 2.1,
        "push_probability": 0.0,
        "edge": 0.12,
        "expected_value": 0.26,
    }


class StoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        migration_path = Path(__file__).parents[1] / "migrations" / "0001_initial.sql"
        self.connection.executescript(migration_path.read_text(encoding="utf-8"))
        self.store = D1Store(FakeDatabase(self.connection), lambda value: value)
        await self.store.create_analysis_run("run-1", 2024, "us")

    async def asyncTearDown(self) -> None:
        self.connection.close()

    async def test_pick_persistence_is_unique_and_settlement_is_idempotent(self) -> None:
        pick = make_pick()
        self.assertEqual(await self.store.save_picks([pick], "run-1", 2024, "us"), 1)
        self.assertEqual(await self.store.save_picks([pick], "run-1", 2024, "us"), 0)

        settlement = {"status": "won", "home_score": 2, "away_score": 1}
        self.assertEqual(
            await self.store.settle_pick("event-1", "h2h", "home", -1.0, settlement),
            1,
        )
        self.assertEqual(
            await self.store.settle_pick("event-1", "h2h", "home", -1.0, settlement),
            0,
        )

        dashboard = await self.store.get_dashboard()
        self.assertEqual(dashboard["summary"]["won"], 1)
        self.assertEqual(dashboard["summary"]["settled"], 1)
        self.assertEqual(dashboard["summary"]["hit_rate"], 1.0)
        self.assertEqual(dashboard["history"][0]["final_home_score"], 2)

    async def test_hit_rate_excludes_pending_push_and_void(self) -> None:
        picks = [
            make_pick("won-event"),
            make_pick("lost-event"),
            make_pick("push-event"),
            make_pick("void-event"),
            make_pick("pending-event"),
        ]
        picks[1]["outcome_key"] = "away"
        picks[2]["market_key"] = "totals"
        picks[2]["outcome_key"] = "over"
        picks[2]["line"] = 2.0
        picks[3]["outcome_key"] = "draw"
        self.assertEqual(await self.store.save_picks(picks, "run-1", 2024, "us"), 5)
        await self.store.settle_pick(
            "won-event", "h2h", "home", -1.0,
            {"status": "won", "home_score": 2, "away_score": 0},
        )
        await self.store.settle_pick(
            "lost-event", "h2h", "away", -1.0,
            {"status": "lost", "home_score": 2, "away_score": 0},
        )
        await self.store.settle_pick(
            "push-event", "totals", "over", 2.0,
            {"status": "push", "home_score": 1, "away_score": 1},
        )
        await self.store.settle_pick(
            "void-event", "h2h", "draw", -1.0,
            {"status": "void", "home_score": None, "away_score": None},
        )

        summary = (await self.store.get_dashboard())["summary"]

        self.assertEqual(summary["settled"], 2)
        self.assertEqual(summary["hit_rate"], 0.5)
        self.assertEqual(summary["push"], 1)
        self.assertEqual(summary["void"], 1)
        self.assertEqual(summary["pending"], 1)

    async def test_team_and_statistics_caches_round_trip(self) -> None:
        teams = [{"team": {"id": 10, "name": "America"}}]
        stats = {"goals": {"for": {"average": {"home": "1.5"}}}}

        await self.store.cache_teams(262, 2024, teams)
        await self.store.cache_team_stats(262, 2024, 10, stats)

        self.assertEqual(await self.store.get_cached_teams(262, 2024), teams)
        self.assertEqual(await self.store.get_cached_team_stats(262, 2024, 10), stats)

    async def test_dashboard_top_picks_shows_only_one_selection_per_event(self) -> None:
        first = make_pick("same-event")
        second = make_pick("same-event")
        second["outcome_key"] = "away"
        second["edge"] = 0.2
        second["expected_value"] = 0.3
        await self.store.save_picks([first, second], "run-1", 2024, "us")

        top_picks = (await self.store.get_dashboard())["top_picks"]

        self.assertEqual(len(top_picks), 1)
        self.assertEqual(top_picks[0]["outcome_key"], "away")


if __name__ == "__main__":
    unittest.main()
