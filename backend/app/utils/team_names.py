from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


def normalize_team_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").casefold()
    ignored_words = {"cf", "club", "deportivo", "fc"}
    return " ".join(word for word in re.findall(r"[a-z0-9]+", normalized) if word not in ignored_words)


def find_api_team_id(name: str, teams_by_name: Dict[str, int]) -> int | None:
    normalized_name = normalize_team_name(name)
    if normalized_name in teams_by_name:
        return teams_by_name[normalized_name]

    name_parts = set(normalized_name.split())
    matches = [
        team_id
        for team_name, team_id in teams_by_name.items()
        if name_parts and name_parts.issubset(team_name.split())
    ]
    return matches[0] if len(matches) == 1 else None


def get_api_teams_by_name(teams_raw: List[Dict[str, Any]]) -> Dict[str, int]:
    teams_by_name: Dict[str, int] = {}
    for item in teams_raw:
        team = item.get("team")
        if not isinstance(team, dict) or not team.get("name") or not team.get("id"):
            continue
        teams_by_name[normalize_team_name(str(team["name"]))] = int(team["id"])
    return teams_by_name
