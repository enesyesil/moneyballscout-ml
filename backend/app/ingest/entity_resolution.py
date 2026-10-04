"""Link API-Football players to Transfermarkt players.

Exact date of birth narrows the candidates; rapidfuzz name similarity picks the best one.
Manual fixes in `player_link_overrides` always win.
"""

import re
import unicodedata

from rapidfuzz import fuzz
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Player, PlayerLink, PlayerLinkOverride, TMPlayer

MIN_SCORE_WITH_DOB = 60
MIN_SCORE_NO_DOB = 92


TRANSLIT = str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "Ae", "ß": "ss", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ı": "i"})


def normalize(name: str) -> str:
    name = unicodedata.normalize("NFKD", name.translate(TRANSLIT))
    name = name.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", name.lower().replace("-", " ")).strip()


def name_score(api_names: list[str], tm_name: str) -> float:
    """Best match over the API's display name ("B. Saka") and full name ("Bukayo Saka")."""
    tm = normalize(tm_name)
    best = 0.0
    for n in api_names:
        n = normalize(n)
        if not n:
            continue
        best = max(best, fuzz.token_sort_ratio(n, tm), fuzz.partial_token_set_ratio(n, tm) * 0.95)
        # "B. Saka" style: initial + surname
        parts = n.split()
        tm_parts = tm.split()
        if len(parts) >= 2 and len(parts[0]) == 1 and tm_parts and tm_parts[0].startswith(parts[0]):
            best = max(best, fuzz.ratio(" ".join(parts[1:]), " ".join(tm_parts[1:])))
    return best


def resolve(session: Session) -> dict:
    overrides = {o.player_id: o.tm_player_id for o in session.scalars(select(PlayerLinkOverride))}
    tm_players = list(session.scalars(select(TMPlayer)))
    by_dob: dict = {}
    for t in tm_players:
        by_dob.setdefault(t.birth_date, []).append(t)

    session.execute(delete(PlayerLink))
    linked, manual, unmatched = 0, 0, 0
    used: set[int] = set()
    for p in session.scalars(select(Player)):
        if p.id in overrides:
            if overrides[p.id] is not None:
                session.add(PlayerLink(player_id=p.id, tm_player_id=overrides[p.id], confidence=1.0, method="manual"))
                used.add(overrides[p.id])
                manual += 1
            continue
        names = [p.name] + ([f"{p.firstname} {p.lastname}"] if p.firstname and p.lastname else [])
        if p.lastname:
            names.append(p.lastname)
        if p.birth_date and p.birth_date in by_dob:
            candidates, threshold, method = by_dob[p.birth_date], MIN_SCORE_WITH_DOB, "dob+name"
        else:
            candidates, threshold, method = tm_players, MIN_SCORE_NO_DOB, "name"
        best, best_score = None, 0.0
        for t in candidates:
            if t.id in used:
                continue
            sc = name_score(names, t.name)
            if sc > best_score:
                best, best_score = t, sc
        if best is not None and best_score >= threshold:
            session.add(PlayerLink(player_id=p.id, tm_player_id=best.id, confidence=round(best_score / 100, 3), method=method))
            used.add(best.id)
            linked += 1
        else:
            unmatched += 1
    session.flush()
    return {"linked": linked, "manual": manual, "unmatched": unmatched}
