"""Demo data: a synthetic league in API-Football's response shapes, with known team and player quality.

Lets the full pipeline run in tests (and locally without an API key) with zero quota.
"""

from datetime import UTC, datetime, timedelta

import numpy as np

POS = ["G"] + ["D"] * 4 + ["M"] * 4 + ["F"] * 3 + ["D", "M", "F"]  # 12 starters-ish + 3 bench
LEAGUE = {"id": 39, "name": "Premier League", "country": "England", "logo": None, "season": 2025}


def make_league(n_teams: int = 10, rounds: int = 2, played_frac: float = 0.85, seed: int = 7):
    rng = np.random.default_rng(seed)
    team_strength = np.linspace(-0.5, 0.5, n_teams)
    rng.shuffle(team_strength)
    teams = [{"id": 1000 + i, "name": f"Team {i}", "code": f"T{i}", "logo": None} for i in range(n_teams)]
    players = []
    for i, t in enumerate(teams):
        for j, pos in enumerate(POS):
            skill = rng.normal(0, 1)
            players.append({
                "id": 50000 + i * 100 + j, "name": f"P{i}-{j}", "firstname": f"First{i}{j}", "lastname": f"Last{i}{j}",
                "team_id": t["id"], "pos": pos, "skill": skill, "team_strength": team_strength[i],
                "birth": (datetime(1994, 1, 1) + timedelta(days=int(rng.integers(0, 3650)))).date().isoformat(),
            })

    # double round robin
    pairs = [(h, a) for h in range(n_teams) for a in range(n_teams) if h != a]
    rng.shuffle(pairs)
    start = datetime(2025, 8, 16, 14, tzinfo=UTC)
    fixtures, fixture_players = [], {}
    n_played = int(len(pairs) * played_frac)
    per_round = n_teams // 2
    for k, (h, a) in enumerate(pairs):
        fid = 900000 + k
        rnd = k // per_round + 1
        date = start + timedelta(days=7 * (k // per_round))
        played = k < n_played
        lam_h = np.exp(0.25 + team_strength[h] - 0.6 * team_strength[a])
        lam_a = np.exp(0.0 + team_strength[a] - 0.6 * team_strength[h])
        gh, ga = (int(rng.poisson(lam_h)), int(rng.poisson(lam_a))) if played else (None, None)
        fixtures.append({
            "fixture": {"id": fid, "date": date.isoformat(), "status": {"short": "FT" if played else "NS"}},
            "league": {**LEAGUE, "round": f"Regular Season - {rnd}"},
            "teams": {"home": teams[h], "away": teams[a]},
            "goals": {"home": gh, "away": ga},
        })
        if played:
            fixture_players[fid] = {"response": [
                _team_block(rng, teams[h], [p for p in players if p["team_id"] == teams[h]["id"]], gh, ga),
                _team_block(rng, teams[a], [p for p in players if p["team_id"] == teams[a]["id"]], ga, gh),
            ]}
    return {"teams": teams, "players": players, "fixtures": {"response": fixtures}, "fixture_players": fixture_players}


def _team_block(rng, team, squad, gf, ga):
    out = []
    scorers = rng.choice([p for p in squad if p["pos"] in "MF"], size=gf, replace=True) if gf else []
    for idx, p in enumerate(squad):
        sub = idx >= 12
        minutes = int(rng.integers(10, 35)) if sub else int(rng.choice([90, 90, 90, 75, 60]))
        if sub and rng.random() < 0.4:
            continue
        q = p["skill"] * 0.6 + p["team_strength"]
        f = minutes / 90
        pois = lambda base: int(rng.poisson(max(0.01, base * f * np.exp(0.3 * q))))  # noqa: E731
        goals = int(sum(1 for s in scorers if s["id"] == p["id"]))
        passes = pois({"G": 25, "D": 50, "M": 55, "F": 25}[p["pos"]])
        stats = {
            "games": {"minutes": minutes, "position": p["pos"], "substitute": sub, "captain": idx == 1,
                      "rating": f"{np.clip(6.7 + 0.5 * q + 0.8 * goals + rng.normal(0, 0.4), 4, 10):.1f}"},
            "offsides": pois(0.3 if p["pos"] == "F" else 0.02),
            "shots": {"total": pois({"G": 0.01, "D": 0.4, "M": 1.2, "F": 2.5}[p["pos"]]) + goals, "on": None},
            "goals": {"total": goals, "conceded": ga if p["pos"] == "G" else 0,
                      "assists": int(rng.random() < 0.1 * gf / 3) if p["pos"] != "G" else 0,
                      "saves": pois(3) if p["pos"] == "G" else 0},
            "passes": {"total": passes, "key": pois({"G": 0.01, "D": 0.4, "M": 1.3, "F": 1.0}[p["pos"]]),
                       "accuracy": str(int(passes * np.clip(0.8 + 0.04 * q, 0.5, 0.95)))},
            "tackles": {"total": pois({"G": 0.05, "D": 2.2, "M": 1.8, "F": 0.6}[p["pos"]]),
                        "blocks": pois(0.6 if p["pos"] == "D" else 0.1),
                        "interceptions": pois(1.2 if p["pos"] == "D" else 0.6)},
            "duels": {"total": None, "won": pois({"G": 0.3, "D": 5, "M": 5, "F": 4}[p["pos"]])},
            "dribbles": {"attempts": None, "success": pois(1.2 if p["pos"] in "MF" else 0.3), "past": pois(0.8)},
            "fouls": {"drawn": pois(1.0), "committed": pois(1.0)},
            "cards": {"yellow": int(rng.random() < 0.1), "red": int(rng.random() < 0.005)},
            "penalty": {"won": None, "commited": None, "scored": 0, "missed": 0, "saved": 0},
        }
        stats["shots"]["on"] = min(stats["shots"]["total"], goals + pois(0.4 if p["pos"] != "G" else 0.01))
        stats["duels"]["total"] = stats["duels"]["won"] + pois(4)
        stats["dribbles"]["attempts"] = stats["dribbles"]["success"] + pois(0.8)
        out.append({"player": {"id": p["id"], "name": p["name"], "photo": None}, "statistics": [stats]})
    return {"team": team, "players": out}


def players_payload(players):
    pos = {"G": "Goalkeeper", "D": "Defender", "M": "Midfielder", "F": "Attacker"}
    return [
        {
            "player": {"id": p["id"], "name": p["name"], "firstname": p["firstname"], "lastname": p["lastname"],
                       "birth": {"date": p["birth"]}, "nationality": "England", "height": "180 cm", "photo": None},
            "statistics": [{"team": {"id": p["team_id"]}, "league": {"id": 39}, "games": {"position": pos[p["pos"]], "minutes": 900}}],
        }
        for p in players
    ]


def coaches_payload(teams):
    return {"response": [
        {"id": 7000 + i, "name": f"Coach {i}", "nationality": "Spain", "birth": {"date": "1970-01-01"}, "photo": None,
         "career": [{"team": {"id": t["id"]}, "start": "2023-07-01", "end": None}]}
        for i, t in enumerate(teams)
    ]}


def seed(session, seed: int = 7) -> dict:
    """Load a synthetic league through the real loaders, plus Transfermarkt-style market values."""
    from datetime import date

    from app.ingest import entity_resolution, loaders
    from app.models import MarketValue, TMPlayer

    league = make_league(n_teams=20, seed=seed)
    rng = np.random.default_rng(seed + 1)
    loaders.load_fixtures(session, league["fixtures"])
    loaders.load_teams(session, {"response": [{"team": t} for t in league["teams"]]}, LEAGUE["id"])
    for fid, payload in league["fixture_players"].items():
        loaders.load_fixture_players(session, fid, payload)
    loaders.load_players(session, players_payload(league["players"]), LEAGUE["id"], LEAGUE["season"])
    loaders.load_coaches(session, coaches_payload(league["teams"]))
    for p in league["players"]:
        q = p["skill"] * 0.6 + p["team_strength"] * 2
        value = float(np.exp(16 + 0.8 * q + rng.normal(0, 0.4)))
        session.merge(TMPlayer(id=p["id"] + 1, name=f"{p['firstname']} {p['lastname']}", birth_date=date.fromisoformat(p["birth"]),
                               market_value=value, competition_id="GB1", contract_expiration=date(2027, 6, 30)))
        for d, f in ((date(2024, 6, 1), 0.7), (date(2024, 12, 1), 0.8), (date(2025, 6, 1), 0.9), (date(2025, 9, 1), 1.0)):
            session.add(MarketValue(tm_player_id=p["id"] + 1, date=d, value_eur=value * f * float(np.exp(rng.normal(0, 0.1)))))
    session.commit()
    links = entity_resolution.resolve(session)
    session.commit()
    return {"fixtures": len(league["fixtures"]["response"]), "players": len(league["players"]), **links}
