from __future__ import annotations

import asyncio
import json
import math
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List
from urllib.parse import urlsplit

from js import AbortSignal, Object, Response, fetch
from pyodide.ffi import JsException, to_js
from workers import WorkerEntrypoint

from app.utils.team_names import find_api_team_id, get_api_teams_by_name

from analysis import (
    build_fixture_candidates,
    build_widget_dashboard,
    create_fixture,
    normalize_fixture_detail,
    rank_top_picks,
    settle_pick,
)
from providers import ProviderError, Providers
from store import D1Store


def _integer_env(env: Any, name: str, default: int) -> int:
    value = getattr(env, name, None)
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError) as error:
        raise ProviderError(f"La variable {name} debe ser un número entero.") from error


def _float_env(env: Any, name: str, default: float) -> float:
    value = getattr(env, name, None)
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError) as error:
        raise ProviderError(f"La variable {name} debe ser numérica.") from error


def _json_response(payload: Dict[str, Any], status: int = 200) -> Any:
    headers = to_js(
        {
            "status": status,
            "headers": {
                "content-type": "application/json; charset=utf-8",
                "cache-control": "no-store",
                "x-content-type-options": "nosniff",
            },
        },
        dict_converter=Object.fromEntries,
    )
    return Response.new(json.dumps(payload, ensure_ascii=False), headers)


async def _fetch_json(url: str, headers: Dict[str, str] | None = None) -> Any:
    hostname = urlsplit(url).hostname or "el proveedor"
    options = to_js(
        {
            "method": "GET",
            "headers": headers or {},
            "signal": AbortSignal.timeout(20_000),
        },
        dict_converter=Object.fromEntries,
    )
    try:
        response = await fetch(url, options)
    except JsException as error:
        raise ProviderError(
            f"No se pudo completar la solicitud a {hostname}; falló o excedió el tiempo de espera."
        ) from error

    if not response.ok:
        raise ProviderError(f"{hostname} respondió HTTP {int(response.status)}.")
    try:
        body = await response.text()
    except JsException as error:
        raise ProviderError(f"No se pudo leer la respuesta de {hostname}.") from error
    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise ProviderError(f"{hostname} devolvió una respuesta que no es JSON válido.") from error


def _store(env: Any) -> D1Store:
    return D1Store(env.DB, lambda value: value.to_py() if hasattr(value, "to_py") else value)


def _providers(env: Any) -> Providers:
    return Providers(
        fetch_json=_fetch_json,
        api_sports_key=str(getattr(env, "API_SPORTS_KEY", "")),
        odds_api_key=str(getattr(env, "ODDS_API_KEY", "")),
        odds_sport_key=str(getattr(env, "ODDS_SPORT_KEY", "soccer_mexico_ligamx")),
        odds_region=str(getattr(env, "ODDS_REGION", "us")),
    )


async def _cached_provider_response(
    store: D1Store,
    cache_key: str,
    max_age_seconds: int,
    fetch_response: Callable[[], Awaitable[Any]],
) -> Any:
    cached = await store.get_cached_json(cache_key, max_age_seconds)
    if cached is not None:
        return cached
    response = await fetch_response()
    await store.cache_json(cache_key, response)
    return response


async def _widget_dashboard(env: Any) -> Dict[str, Any]:
    league_id = _integer_env(env, "LEAGUE_ID", 262)
    season = _integer_env(env, "FIXTURES_SEASON", datetime.now(timezone.utc).year)
    if league_id <= 0 or season < 2000:
        raise ProviderError("La liga o la temporada de los widgets no es válida.")

    providers = _providers(env)
    store = _store(env)
    upcoming_key = f"api-sports:fixtures:next:{league_id}:{season}"
    recent_key = f"api-sports:fixtures:last:{league_id}:{season}"
    standings_key = f"api-sports:standings:{league_id}:{season}"
    upcoming, recent, standings = await asyncio.gather(
        _cached_provider_response(
            store,
            upcoming_key,
            900,
            lambda: providers.get_fixtures(league_id, season, {"next": 10}),
        ),
        _cached_provider_response(
            store,
            recent_key,
            21600,
            lambda: providers.get_fixtures(league_id, season, {"last": 100}),
        ),
        _cached_provider_response(
            store,
            standings_key,
            3600,
            lambda: providers.get_standings(league_id, season),
        ),
    )
    if not all(isinstance(value, list) for value in (upcoming, recent, standings)):
        raise ProviderError("La caché de widgets contiene datos con un formato inesperado.")
    return {
        **build_widget_dashboard(upcoming, recent, standings),
        "season": season,
        "form_matches": 5,
        "minimum_form_matches": 3,
    }


async def _widget_fixture_detail(env: Any, fixture_id: int) -> Dict[str, Any] | None:
    store = _store(env)
    cache_key = f"api-sports:fixture:{fixture_id}"
    fixtures = await _cached_provider_response(
        store,
        cache_key,
        300,
        lambda: _providers(env).get_fixture_details(fixture_id),
    )
    if not isinstance(fixtures, list):
        raise ProviderError("La caché del detalle de partido tiene un formato inesperado.")
    return normalize_fixture_detail(fixtures)


async def _analyze(env: Any) -> Dict[str, Any]:
    providers = _providers(env)
    store = _store(env)
    league_id = _integer_env(env, "LEAGUE_ID", 262)
    season = _integer_env(env, "STATS_SEASON", 2024)
    max_stats = _integer_env(env, "MAX_TEAM_STATS_PER_SCAN", 8)
    edge_threshold = _float_env(env, "MODEL_EDGE_THRESHOLD", 0.08)
    stats_request_interval = _float_env(env, "API_SPORTS_REQUEST_INTERVAL_SECONDS", 6.1)
    region = str(getattr(env, "ODDS_REGION", "us"))
    if (
        max_stats < 0
        or not math.isfinite(edge_threshold)
        or not 0 <= edge_threshold < 1
        or not math.isfinite(stats_request_interval)
        or stats_request_interval < 0
    ):
        raise ProviderError("La configuración del modelo o el límite de consultas no es válido.")

    odds_events = await providers.get_odds()
    teams = await store.get_cached_teams(league_id, season)
    if teams is None:
        teams = await providers.get_teams(league_id, season)
        await store.cache_teams(league_id, season, teams)
    teams_by_name = get_api_teams_by_name(teams)
    if not teams_by_name:
        raise ProviderError(f"API-Sports no devolvió equipos para la temporada {season}.")

    stats_by_team: Dict[int, Dict[str, Any]] = {}
    stats_requests = 0
    last_stats_request_at: float | None = None
    candidates: List[Dict[str, Any]] = []
    events_analyzed = 0
    for event in odds_events:
        home_team = str(event.get("home_team", ""))
        away_team = str(event.get("away_team", ""))
        home_team_id = find_api_team_id(home_team, teams_by_name)
        away_team_id = find_api_team_id(away_team, teams_by_name)
        if home_team_id is None or away_team_id is None:
            continue

        stats_available = True
        for team_id in (home_team_id, away_team_id):
            if team_id in stats_by_team:
                continue
            cached_stats = await store.get_cached_team_stats(league_id, season, team_id)
            if cached_stats is not None:
                stats_by_team[team_id] = cached_stats
                continue
            if stats_requests >= max_stats:
                stats_available = False
                break
            if last_stats_request_at is not None:
                wait_seconds = stats_request_interval - (time.monotonic() - last_stats_request_at)
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
            stats = await providers.get_team_stats(team_id, league_id, season)
            last_stats_request_at = time.monotonic()
            await store.cache_team_stats(league_id, season, team_id, stats)
            stats_by_team[team_id] = stats
            stats_requests += 1
        if not stats_available:
            continue
        fixture = create_fixture(event, home_team_id, away_team_id, stats_by_team)
        if fixture is not None:
            events_analyzed += 1
            candidates.extend(build_fixture_candidates(fixture, event, edge_threshold))

    top_picks = rank_top_picks(candidates)
    run_id = secrets.token_hex(16)
    await store.create_analysis_run(run_id, season, region)
    saved = await store.save_picks(top_picks, run_id, season, region)
    await store.finish_analysis_run(run_id, len(odds_events), saved)
    return {
        "picks": top_picks,
        "events_seen": len(odds_events),
        "events_analyzed": events_analyzed,
        "picks_saved": saved,
        "stats_requests": stats_requests,
        "stats_season": season,
        "odds_region": region,
        "experimental": str(getattr(env, "EXPERIMENTAL", "true")).casefold() == "true",
    }


async def _sync_scores(env: Any) -> Dict[str, int]:
    store = _store(env)
    event_ids = await store.get_pending_event_ids()
    if not event_ids:
        return {"events_checked": 0, "picks_settled": 0}

    providers = _providers(env)
    score_events = await providers.get_scores(event_ids)
    picks_settled = 0
    for score_event in score_events:
        event_id = str(score_event.get("id", ""))
        if not event_id:
            continue
        pending_picks = await store.get_pending_picks(event_id)
        for pick in pending_picks:
            settlement = settle_pick(pick, score_event)
            if settlement is None:
                continue
            picks_settled += await store.settle_pick(
                event_id,
                str(pick["market_key"]),
                str(pick["outcome_key"]),
                float(pick["line"]),
                settlement,
            )
    return {"events_checked": len(score_events), "picks_settled": picks_settled}


class Default(WorkerEntrypoint):
    async def fetch(self, request: Any) -> Any:
        path = urlsplit(str(request.url)).path
        method = str(request.method).upper()
        try:
            if path == "/api/health" and method == "GET":
                await _store(self.env)._first("SELECT 1 AS ready")
                return _json_response({"status": "ok"})
            if path == "/api/dashboard" and method == "GET":
                return _json_response(await _store(self.env).get_dashboard())
            if path == "/api/widgets/dashboard" and method == "GET":
                return _json_response(await _widget_dashboard(self.env))
            if path.startswith("/api/widgets/fixtures/") and method == "GET":
                fixture_id_text = path.removeprefix("/api/widgets/fixtures/")
                if not fixture_id_text.isdecimal() or int(fixture_id_text) <= 0:
                    return _json_response({"error": "El identificador del partido no es válido."}, 400)
                detail = await _widget_fixture_detail(self.env, int(fixture_id_text))
                if detail is None:
                    return _json_response({"error": "No se encontró el detalle de ese partido."}, 404)
                return _json_response(detail)
            if path == "/api/analyze" and method == "POST":
                return _json_response(await _analyze(self.env))
            if path == "/api/sync" and method == "POST":
                return _json_response(await _sync_scores(self.env))
            if path.startswith("/api/"):
                return _json_response({"error": "Ruta API no encontrada."}, 404)
            return await self.env.ASSETS.fetch(request)
        except ProviderError as error:
            return _json_response({"error": str(error)}, 503)

    async def scheduled(self, controller: Any, env: Any, ctx: Any) -> None:
        await _sync_scores(env)
