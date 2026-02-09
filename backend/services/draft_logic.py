import pandas as pd
from data.players import PLAYERS_BY_YEAR

# -----------------------
# Helpers
# -----------------------


def player_ids_by_year(year):
    return set(PLAYERS_BY_YEAR[year].index)


def draft_order_by_year(year):
    df = PLAYERS_BY_YEAR[year].dropna(subset=["overall"]).sort_values("overall")

    return [
        {
            "overall": int(row["overall"]),
            "round": int(row["round"]),
            "pick": int(row["pick"]),
            "team": row["team"],
            "player_id": None,
        }
        for _, row in df.iterrows()
    ]


def user_turn(draft):
    current = draft["draft_order"][draft["index"]]
    return current["team"] == draft["user_team"]


# -----------------------
# Core engine
# -----------------------


def update_status(draft):
    if draft["index"] >= len(draft["draft_order"]):
        draft["status"] = "complete"
        return

    draft["status"] = "waiting_for_user" if user_turn(draft) else "simulating"


def advance_metadata(draft):
    if draft["index"] >= len(draft["draft_order"]):
        return

    next_pick = draft["draft_order"][draft["index"]]
    draft["round"] = next_pick["round"]
    draft["pick"] = next_pick["pick"]


def draft_player(draft, player_id):
    draft["available_players"].remove(player_id)

    pick = draft["draft_order"][draft["index"]]
    pick["player_id"] = int(player_id)

    draft["index"] += 1
    advance_metadata(draft)
    update_status(draft)


def simulate_pick(draft):
    year_df = PLAYERS_BY_YEAR[draft["year"]]
    overall = draft["index"] + 1

    row = year_df[year_df["overall"] == overall]
    available = year_df.loc[year_df.index.intersection(draft["available_players"])]

    # Real pick if available
    if len(row) > 0:
        pid = row.index[0]
        if pid in draft["available_players"]:
            draft_player(draft, pid)
            return

    if available.empty:
        update_status(draft)
        return

    position = row.iloc[0]["position"] if len(row) > 0 else None

    same_position = (
        available[available["position"] == position] if position else pd.DataFrame()
    )

    best = (
        same_position.sort_values("pos_rk").iloc[0]
        if not same_position.empty
        else available.sort_values("ovr_rk").iloc[0]
    )

    draft_player(draft, best.name)
