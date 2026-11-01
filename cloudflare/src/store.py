from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List


ToPython = Callable[[Any], Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class D1Store:
    def __init__(self, database: Any, to_python: ToPython) -> None:
        self.database = database
        self.to_python = to_python

    async def _all(self, sql: str, params: List[Any] | None = None) -> List[Dict[str, Any]]:
        statement = self.database.prepare(sql)
        if params:
            statement = statement.bind(*params)
        result = await statement.all()
        rows = self.to_python(result.results)
        return rows if isinstance(rows, list) else []

    async def _first(self, sql: str, params: List[Any] | None = None) -> Dict[str, Any] | None:
        statement = self.database.prepare(sql)
        if params:
            statement = statement.bind(*params)
        result = await statement.first()
        row = self.to_python(result) if result is not None else None
        return row if isinstance(row, dict) else None

    async def _run(self, sql: str, params: List[Any] | None = None) -> Any:
        statement = self.database.prepare(sql)
        if params:
            statement = statement.bind(*params)
        return await statement.run()

    async def get_cached_teams(self, league_id: int, season: int) -> List[Dict[str, Any]] | None:
        row = await self._first(
            "SELECT teams_json FROM team_directory_cache WHERE league_id = ? AND season = ?",
            [league_id, season],
        )
        if row is None:
            return None
        teams = json.loads(row["teams_json"])
        if not isinstance(teams, list):
            raise RuntimeError("La caché D1 del catálogo de equipos tiene un formato inesperado.")
        return teams

    async def cache_teams(self, league_id: int, season: int, teams: List[Dict[str, Any]]) -> None:
        await self._run(
            """
            INSERT INTO team_directory_cache (league_id, season, teams_json, fetched_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (league_id, season) DO UPDATE SET
                teams_json = excluded.teams_json,
                fetched_at = excluded.fetched_at
            """,
            [league_id, season, json.dumps(teams, separators=(",", ":")), _utc_now()],
        )

    async def get_cached_team_stats(
        self,
        league_id: int,
        season: int,
        team_id: int,
    ) -> Dict[str, Any] | None:
        row = await self._first(
            """
            SELECT stats_json FROM team_stats_cache
            WHERE league_id = ? AND season = ? AND team_id = ?
            """,
            [league_id, season, team_id],
        )
        if row is None:
            return None
        stats = json.loads(row["stats_json"])
        if not isinstance(stats, dict):
            raise RuntimeError("La caché D1 de estadísticas tiene un formato inesperado.")
        return stats

    async def cache_team_stats(
        self,
        league_id: int,
        season: int,
        team_id: int,
        stats: Dict[str, Any],
    ) -> None:
        await self._run(
            """
            INSERT INTO team_stats_cache (league_id, season, team_id, stats_json, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (league_id, season, team_id) DO UPDATE SET
                stats_json = excluded.stats_json,
                fetched_at = excluded.fetched_at
            """,
            [league_id, season, team_id, json.dumps(stats, separators=(",", ":")), _utc_now()],
        )

    async def create_analysis_run(self, run_id: str, season: int, region: str) -> None:
        await self._run(
            """
            INSERT INTO analysis_runs (id, created_at, stats_season, odds_region)
            VALUES (?, ?, ?, ?)
            """,
            [run_id, _utc_now(), season, region],
        )

    async def finish_analysis_run(self, run_id: str, events_seen: int, picks_saved: int) -> None:
        await self._run(
            """
            UPDATE analysis_runs SET events_seen = ?, picks_saved = ? WHERE id = ?
            """,
            [events_seen, picks_saved, run_id],
        )

    async def save_picks(
        self,
        picks: List[Dict[str, Any]],
        run_id: str,
        season: int,
        region: str,
    ) -> int:
        saved = 0
        created_at = _utc_now()
        for pick in picks:
            result = await self._run(
                """
                INSERT INTO picks (
                    id, event_id, kickoff, home_team, away_team, market_key,
                    outcome_key, selection, line, bookmaker, odds, model_probability,
                    implied_probability, push_probability, edge, expected_value,
                    stats_season, odds_region, status, created_at, run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                ON CONFLICT (event_id, market_key, outcome_key, line) DO NOTHING
                """,
                [
                    secrets.token_hex(16),
                    pick["event_id"],
                    pick["kickoff"],
                    pick["home_team"],
                    pick["away_team"],
                    pick["market_key"],
                    pick["outcome_key"],
                    pick["selection"],
                    pick["line"],
                    pick["bookmaker"],
                    pick["odds"],
                    pick["model_probability"],
                    pick["implied_probability"],
                    pick["push_probability"],
                    pick["edge"],
                    pick["expected_value"],
                    season,
                    region,
                    created_at,
                    run_id,
                ],
            )
            meta = self.to_python(result.meta)
            if isinstance(meta, dict) and meta.get("changes", 0) > 0:
                saved += int(meta["changes"])
        return saved

    async def get_pending_event_ids(self) -> List[str]:
        rows = await self._all(
            """
            SELECT DISTINCT event_id FROM picks
            WHERE status = 'pending' AND julianday(kickoff) >= julianday('now', '-3 days')
            """
        )
        return [str(row["event_id"]) for row in rows]

    async def get_pending_picks(self, event_id: str) -> List[Dict[str, Any]]:
        return await self._all(
            """
            SELECT event_id, home_team, away_team, market_key, outcome_key, line
            FROM picks WHERE event_id = ? AND status = 'pending'
            """,
            [event_id],
        )

    async def settle_pick(
        self,
        event_id: str,
        market_key: str,
        outcome_key: str,
        line: float,
        settlement: Dict[str, Any],
    ) -> int:
        result = await self._run(
            """
            UPDATE picks SET
                status = ?, final_home_score = ?, final_away_score = ?, settled_at = ?
            WHERE event_id = ? AND market_key = ? AND outcome_key = ? AND line = ?
              AND status = 'pending'
            """,
            [
                settlement["status"],
                settlement["home_score"],
                settlement["away_score"],
                _utc_now(),
                event_id,
                market_key,
                outcome_key,
                line,
            ],
        )
        meta = self.to_python(result.meta)
        return int(meta.get("changes", 0)) if isinstance(meta, dict) else 0

    async def get_dashboard(self) -> Dict[str, Any]:
        summary = await self._first(
            """
            SELECT
                COUNT(*) AS total_picks,
                SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) AS won,
                SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) AS lost,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = 'push' THEN 1 ELSE 0 END) AS push,
                SUM(CASE WHEN status = 'void' THEN 1 ELSE 0 END) AS void
            FROM picks
            """
        ) or {}
        won = int(summary.get("won") or 0)
        lost = int(summary.get("lost") or 0)
        settled = won + lost
        history = await self._all(
            """
            SELECT
                id, event_id, kickoff, home_team, away_team, market_key, outcome_key,
                selection, line, bookmaker, odds, model_probability, push_probability,
                edge, expected_value, stats_season, odds_region, status,
                final_home_score, final_away_score, created_at, settled_at
            FROM picks ORDER BY created_at DESC LIMIT 100
            """
        )
        top_picks = await self._all(
            """
            SELECT
                id, event_id, kickoff, home_team, away_team, market_key, outcome_key,
                selection, line, bookmaker, odds, model_probability, implied_probability,
                push_probability, edge, expected_value, stats_season, odds_region, status
            FROM (
                SELECT
                    picks.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY event_id
                        ORDER BY edge DESC, expected_value DESC, created_at DESC
                    ) AS event_rank
                FROM picks WHERE status = 'pending'
            )
            WHERE event_rank = 1
            ORDER BY edge DESC, expected_value DESC, created_at DESC LIMIT 5
            """
        )
        return {
            "summary": {
                "total_picks": int(summary.get("total_picks") or 0),
                "won": won,
                "lost": lost,
                "pending": int(summary.get("pending") or 0),
                "push": int(summary.get("push") or 0),
                "void": int(summary.get("void") or 0),
                "settled": settled,
                "hit_rate": won / settled if settled else None,
            },
            "top_picks": top_picks,
            "history": history,
        }
