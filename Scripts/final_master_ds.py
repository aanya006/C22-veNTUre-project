import duckdb
import pandas as pd
import numpy as np
import glob
import re
import hashlib

def hash_identifier(value):
    if pd.isna(value):
        return None
    return hashlib.sha256(str(value).encode()).hexdigest()[:12]

con = duckdb.connect("/Users/devanshii/Documents/c22-veNTUre-project/Data/processed/project.duckdb")

# ============================================================
# Load raw trade files for campaigns 67-82
# ============================================================
folder_trades = "/Users/devanshii/Documents/c22-veNTUre-project/Data/raw/user_trades/"
all_trade_files_new = []
for f in glob.glob(folder_trades + "*.csv") + glob.glob(folder_trades + "*.xlsx"):
    match = re.search(r"Campaign (\d+)", f)
    if match and 67 <= int(match.group(1)) <= 82:
        all_trade_files_new.append(f)

dfs_trades = []
for f in all_trade_files_new:
    temp = pd.read_csv(f) if f.endswith(".csv") else pd.read_excel(f)
    temp["campaignId"] = re.search(r"Campaign (\d+)", f).group(1)
    temp["filename"] = f
    dfs_trades.append(temp)
raw_trades_new = pd.concat(dfs_trades, ignore_index=True)
print("Raw trade rows loaded:", len(raw_trades_new))

# ============================================================
# Load raw registry files for campaigns 67-82, build traderId
# ============================================================
folder_users = "/Users/devanshii/Documents/c22-veNTUre-project/Data/raw/user_data/"
all_user_files_new = []
for f in glob.glob(folder_users + "*.csv") + glob.glob(folder_users + "*.xlsx"):
    match = re.search(r"Campaign (\d+)", f)
    if match and 67 <= int(match.group(1)) <= 82:
        all_user_files_new.append(f)

dfs_users = []
for f in all_user_files_new:
    temp = pd.read_csv(f) if f.endswith(".csv") else pd.read_excel(f)
    temp.columns = [c.strip().lower().replace(" ", "_") for c in temp.columns]
    if "account_id" in temp.columns and "account" not in temp.columns:
        temp = temp.rename(columns={"account_id": "account"})
    temp["campaignId"] = re.search(r"Campaign (\d+)", f).group(1)
    dfs_users.append(temp)

users_new = pd.concat(dfs_users, ignore_index=True)
users_new["traderId"] = users_new["email"].apply(hash_identifier)
users_new_clean = users_new[["account", "campaignId", "traderId"]].copy()

# ============================================================
# Join trades to traderId, on accountId + campaignId
# ============================================================
constant_cols = ["instrument", "lotSize", "swap", "currency", "openTradeCrossPrice", "closeTradeCrossPrice"]
trades_clean_new = raw_trades_new.drop(columns=[c for c in constant_cols if c in raw_trades_new.columns]).copy()
trades_clean_new["has_SL"] = trades_clean_new["slPrice"].notna()
trades_clean_new["has_TP"] = trades_clean_new["tpPrice"].notna()

trades_with_trader_new = trades_clean_new.merge(
    users_new_clean, left_on=["accountId", "campaignId"], right_on=["account", "campaignId"], how="left"
)
print("Matched to traderId:", trades_with_trader_new["traderId"].notna().sum(), "of", len(trades_with_trader_new))

# ============================================================
# Remove any previously-inserted 67-82 rows, insert corrected version
# ============================================================
before_delete = con.execute("SELECT COUNT(*) FROM trades_with_trader").fetchone()[0]
con.execute("DELETE FROM trades_with_trader WHERE CAST(campaignId AS INTEGER) BETWEEN 67 AND 82")
after_delete = con.execute("SELECT COUNT(*) FROM trades_with_trader").fetchone()[0]
print(f"Removed existing 67-82 rows: {before_delete} -> {after_delete}")

existing_cols = con.execute("DESCRIBE trades_with_trader").fetchdf()["column_name"].tolist()
for col in set(existing_cols) - set(trades_with_trader_new.columns):
    trades_with_trader_new[col] = np.nan
trades_with_trader_new_aligned = trades_with_trader_new[existing_cols]

con.register("trades_with_trader_fixed_df", trades_with_trader_new_aligned)
con.execute("INSERT INTO trades_with_trader SELECT * FROM trades_with_trader_fixed_df")

after_insert = con.execute("SELECT COUNT(*) FROM trades_with_trader").fetchone()[0]
print(f"Row count after insert: {after_insert}")

verify = con.execute("""
    SELECT 
        COUNT(*) AS total_rows,
        COUNT(traderId) AS rows_with_traderId,
        SUM(CASE WHEN traderId IS NULL THEN 1 ELSE 0 END) AS rows_missing_traderId
    FROM trades_with_trader
""").fetchdf()
print(verify)

print("\nMissing traderId, by campaign:")
missing_by_campaign = con.execute("""
    SELECT campaignId, COUNT(*) AS missing_count
    FROM trades_with_trader
    WHERE traderId IS NULL
    GROUP BY campaignId
    ORDER BY CAST(campaignId AS INTEGER)
""").fetchdf()
print(missing_by_campaign)

print("\nDone. Campaigns 67-82 added to trades_with_trader.")

con.close()