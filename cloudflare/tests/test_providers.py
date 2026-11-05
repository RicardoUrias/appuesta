import unittest
from typing import Any
from urllib.parse import parse_qs, urlsplit

from src.providers import ProviderError, Providers


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_sports_widget_requests_use_the_private_key_header(self) -> None:
        requests: list[tuple[str, dict[str, str] | None]] = []

        async def fetch_json(url: str, headers: dict[str, str] | None) -> Any:
            requests.append((url, headers))
            return {"errors": [], "response": []}

        providers = Providers(fetch_json, "sports-secret", "", "", "")
        self.assertEqual(await providers.get_fixtures(262, 2026, {"next": 10}), [])
        self.assertEqual(await providers.get_fixtures(262, 2026, {"last": 100}), [])
        self.assertEqual(await providers.get_standings(262, 2026), [])
        self.assertEqual(await providers.get_fixture_details(1234), [])

        self.assertEqual(
            [urlsplit(url).path.rsplit("/", 1)[-1] for url, _ in requests],
            ["fixtures", "fixtures", "standings", "fixtures"],
        )
        self.assertEqual(parse_qs(urlsplit(requests[0][0]).query), {"league": ["262"], "season": ["2026"], "next": ["10"]})
        self.assertEqual(requests[0][1]["x-apisports-key"], "sports-secret")
        self.assertEqual(parse_qs(urlsplit(requests[3][0]).query), {"id": ["1234"]})

    async def test_odds_and_score_requests_use_configured_sport_and_region(self) -> None:
        requests: list[tuple[str, dict[str, str] | None]] = []

        async def fetch_json(url: str, headers: dict[str, str] | None) -> Any:
            requests.append((url, headers))
            return []

        providers = Providers(fetch_json, "", "odds-secret", "soccer_mexico_ligamx", "us")
        await providers.get_odds()
        await providers.get_scores(["event-a", "event-b"])

        odds_query = parse_qs(urlsplit(requests[0][0]).query)
        scores_query = parse_qs(urlsplit(requests[1][0]).query)
        self.assertEqual(odds_query["regions"], ["us"])
        self.assertEqual(odds_query["markets"], ["h2h,totals"])
        self.assertEqual(scores_query["eventIds"], ["event-a,event-b"])
        self.assertEqual(scores_query["daysFrom"], ["3"])
        self.assertIsNone(requests[0][1])

    async def test_score_sync_does_not_require_api_sports_key(self) -> None:
        async def fetch_json(_: str, __: dict[str, str] | None) -> Any:
            return []

        providers = Providers(fetch_json, "", "odds-secret", "soccer_mexico_ligamx", "us")

        self.assertEqual(await providers.get_scores([]), [])
        with self.assertRaisesRegex(ProviderError, "API_SPORTS_KEY"):
            await providers.get_team_stats(10, 262, 2024)

    async def test_api_sports_requests_send_key_in_header_and_surface_provider_errors(self) -> None:
        captured_headers: dict[str, str] | None = None

        async def fetch_json(_: str, headers: dict[str, str] | None) -> Any:
            nonlocal captured_headers
            captured_headers = headers
            return {"errors": [], "response": []}

        providers = Providers(
            fetch_json,
            "sports-secret",
            "odds-secret",
            "soccer_mexico_ligamx",
            "us",
        )
        teams = await providers.get_teams(262, 2024)

        self.assertEqual(teams, [])
        self.assertEqual(captured_headers["x-apisports-key"], "sports-secret")

        async def rejected(_: str, __: dict[str, str] | None) -> Any:
            return {"errors": {"token": "Invalid API key"}, "response": []}

        rejected_provider = Providers(
            rejected,
            "sports-secret",
            "odds-secret",
            "soccer_mexico_ligamx",
            "us",
        )
        with self.assertRaisesRegex(ProviderError, "rechazó la consulta"):
            await rejected_provider.get_teams(262, 2024)

    async def test_provider_rejects_malformed_event_records(self) -> None:
        async def malformed(_: str, __: dict[str, str] | None) -> Any:
            return ["not-an-event"]

        providers = Providers(
            malformed,
            "sports-secret",
            "odds-secret",
            "soccer_mexico_ligamx",
            "us",
        )
        with self.assertRaisesRegex(ProviderError, "formato de eventos"):
            await providers.get_odds()
        with self.assertRaisesRegex(ProviderError, "formato de resultados"):
            await providers.get_scores([])


if __name__ == "__main__":
    unittest.main()
