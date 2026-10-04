"""Similar players (k-nearest neighbours, cosine) on shrunk per-90 percentile profiles within a
position group. The API filters the neighbours by price and age: "like X, cheaper, younger"."""

import pandas as pd
from sklearn.neighbors import NearestNeighbors

from app.ml.data import positions_config
from app.ml.shrinkage import MIN_MINUTES_RANKED

K = 15


def similar_players(pct: pd.DataFrame, totals: pd.DataFrame) -> pd.DataFrame:
    groups = positions_config()["groups"]
    rows = []
    for group, idx in totals.groupby("position_group").groups.items():
        idx = [i for i in idx if totals.at[i, "minutes"] >= MIN_MINUTES_RANKED]
        metrics = [m for m in groups.get(group, groups["MID"])["metrics"] if m in pct.columns]
        if len(idx) < 3 or not metrics:
            continue
        X = pct.loc[idx, metrics].fillna(50) - 50  # centre so cosine compares profile shape
        nn = NearestNeighbors(n_neighbors=min(K + 1, len(idx)), metric="cosine").fit(X)
        dist, ind = nn.kneighbors(X)
        for i, pid in enumerate(idx):
            rank = 0
            for d, j in zip(dist[i], ind[i], strict=True):
                other = idx[j]
                if other == pid:
                    continue
                rank += 1
                rows.append({"player_id": int(pid), "similar_player_id": int(other), "similarity": round(1 - float(d), 4), "rank": rank})
    return pd.DataFrame(rows)
