import duckdb
import pandas as pd

# ---------------------------------------------------------
# Additive, campaign-boundary-aware features on top of trades_with_trader.
# Does NOT modify trades_with_trader (or any other existing table/file) —
# writes a brand new table, trades_campaign_features, instead.
#
# Each campaign is a fresh $5000 account, so equity/peak/streak/re-entry-gap
# must all reset at the (traderId, campaignId) boundary, not just per trader.
# ---------------------------------------------------------

STARTING_BALANCE = 5000

con = duckdb.connect("../Data/processed/project.duckdb")
df = con.execute("SELECT * FROM trades_with_trader").fetchdf()

df = df.sort_values(["traderId", "campaignId", "openDateTime"], na_position="last").reset_index(drop=True)
df["_row_id"] = df.index

# Rows with no traderId can't be placed in a coherent per-trader sequence —
# leave their new columns as NULL rather than guessing.
mask = df["traderId"].notna()
sub = df[mask].copy()
group_keys = ["traderId", "campaignId"]
g = sub.groupby(group_keys)

# Trade order within each trader's campaign, restarting at 1 each campaign
sub["trade_seq_in_campaign"] = g.cumcount() + 1

# Equity: starting balance + running P&L, reset to STARTING_BALANCE each campaign
sub["equity"] = STARTING_BALANCE + g["netProfit"].cumsum()

# Peak equity reached so far this campaign, and drawdown from that peak
sub["running_peak"] = sub.groupby(group_keys)["equity"].cummax()
sub["drawdown"] = sub["equity"] - sub["running_peak"]


def signed_streak(is_win_series):
    # +N = N wins in a row, -N = N losses in a row, restarts on each flip
    streaks = []
    current = 0
    for is_win in is_win_series:
        if is_win:
            current = current + 1 if current > 0 else 1
        else:
            current = current - 1 if current < 0 else -1
        streaks.append(current)
    return pd.Series(streaks, index=is_win_series.index)


sub["is_win"] = sub["netProfit"] >= 0
sub["streak"] = sub.groupby(group_keys)["is_win"].transform(signed_streak)

# Seconds since this trader's previous trade closed, within the same campaign only.
# First trade of each campaign gets NULL — no gap computed across the boundary.
sub["prev_closeDateTime"] = sub.groupby(group_keys)["closeDateTime"].shift(1)
sub["reentry_gap_sec"] = (sub["openDateTime"] - sub["prev_closeDateTime"]).dt.total_seconds()

new_cols = ["trade_seq_in_campaign", "equity", "running_peak", "drawdown", "streak", "reentry_gap_sec"]
feature_cols = sub[["_row_id"] + new_cols]

df = df.merge(feature_cols, on="_row_id", how="left").drop(columns=["_row_id"])

con.register("trades_campaign_features_df", df)
con.execute("CREATE OR REPLACE TABLE trades_campaign_features AS SELECT * FROM trades_campaign_features_df")

print("Rows total:", len(df))
print("Rows with campaign features computed:", df["equity"].notna().sum())
print("\nExample — a trader active in multiple campaigns:")
multi_campaign_trader = (
    df.dropna(subset=["equity"])
    .groupby("traderId")["campaignId"]
    .nunique()
    .loc[lambda s: s > 1]
    .index[0]
)
print(df[df["traderId"] == multi_campaign_trader][
    ["traderId", "campaignId", "trade_seq_in_campaign", "netProfit", "equity", "running_peak", "drawdown", "streak", "reentry_gap_sec"]
].to_string(index=False))

con.close()
print("\nDone. trades_campaign_features table written to project.duckdb.")
