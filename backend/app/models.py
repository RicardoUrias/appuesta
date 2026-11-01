from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Fixture:
    fixture_id: int
    home_team: str
    away_team: str
    kickoff: str
    league_name: str
    home_team_id: int
    away_team_id: int
    h2h: List[Dict[str, Any]] = field(default_factory=list)
    xg_home: float = 0.0
    xg_away: float = 0.0
    recent_home_form: Dict[str, float] = field(default_factory=dict)
    recent_away_form: Dict[str, float] = field(default_factory=dict)
    score_home: Optional[int] = None
    score_away: Optional[int] = None


@dataclass
class MarketOutcome:
    market_name: str
    selection: str
    bookmaker: str
    odds: float
    implied_probability: float
    model_probability: float
    edge: float
    expected_value: float
    push_probability: float = 0.0


@dataclass
class TopValuePick:
    fixture_id: int
    home_team: str
    away_team: str
    kickoff: str
    market_name: str
    selection: str
    bookmaker: str
    odds: float
    model_probability: float
    implied_probability: float
    edge: float
    expected_value: float
    confidence: float
    push_probability: float = 0.0
