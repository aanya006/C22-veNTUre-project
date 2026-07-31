import duckdb
import pandas as pd
import glob
import re
import hashlib

# ---------------------------------------------------------
# Step 0: Connect to the database, load raw trades
# ---------------------------------------------------------
con = duckdb.connect("../Data/processed/project.duckdb")
df = con.execute("SELECT * FROM trades").fetchdf()

# ---------------------------------------------------------
# Step 1: Load all 34 registry files (csv + xlsx), fix column names
# ---------------------------------------------------------
folder = "../Data/raw/user_data/"
all_files = glob.glob(folder + "*.csv") + glob.glob(folder + "*.xlsx")

dfs = []
for f in all_files:
    if f.endswith(".csv"):
        temp = pd.read_csv(f)
    else:
        temp = pd.read_excel(f)
    temp.columns = [c.strip().lower().replace(" ", "_") for c in temp.columns]
    match = re.search(r"Campaign (\d+)", f)
    temp["campaignId"] = match.group(1) if match else None
    temp["filename"] = f
    dfs.append(temp)

users_2_df = pd.concat(dfs, ignore_index=True)
print("Loaded rows:", len(users_2_df))
print("Missing account values:", users_2_df["account"].isna().sum())

# ---------------------------------------------------------
# Step 2: Hash email into PDPA-safe traderId
# ---------------------------------------------------------
def hash_identifier(value):
    if pd.isna(value):
        return None
    return hashlib.sha256(str(value).encode()).hexdigest()[:12]

users_2_df["traderId"] = users_2_df["email"].apply(hash_identifier)
users_2_clean = users_2_df[["account", "campaignId", "traderId"]].copy()
con.register("users_2_clean", users_2_clean)

print("Missing traderId:", users_2_clean["traderId"].isna().sum())

# ---------------------------------------------------------
# Step 3: Build trades2_clean (fresh clean, no old accountId merge)
# ---------------------------------------------------------
constant_cols = ["instrument", "lotSize", "swap", "currency", "openTradeCrossPrice", "closeTradeCrossPrice"]
trades2_clean = df.drop(columns=constant_cols).copy()
trades2_clean["side"] = trades2_clean["side"].astype("category")
trades2_clean["has_SL"] = trades2_clean["slPrice"].notna()
trades2_clean["has_TP"] = trades2_clean["tpPrice"].notna()
con.register("trades2_clean", trades2_clean)

print(con.execute("DESCRIBE trades2_clean").fetchdf())

# ---------------------------------------------------------
# Step 4: Join trades to traderId on BOTH accountId and campaignId
# ---------------------------------------------------------
con.execute("""
    CREATE OR REPLACE TABLE trades_with_trader AS
    SELECT t.*, u.traderId
    FROM trades2_clean t
    LEFT JOIN users_2_clean u
        ON t.accountId = u.account
       AND t.campaignId = u.campaignId
""")

print(con.execute("""
    SELECT COUNT(*) AS total_trades,
           COUNT(traderId) AS matched,
           COUNT(DISTINCT traderId) AS distinct_traders
    FROM trades_with_trader
""").fetchdf())

# ---------------------------------------------------------
# Step 5: Build rebuilt_account_summary
# ---------------------------------------------------------
rebuilt_account_summary = con.execute("""
    SELECT traderId,
           COUNT(*) AS n_trades,
           SUM(netProfit) AS total_netProfit,
           AVG(netProfit) AS avg_netProfit,
           STDDEV(netProfit) AS profit_volatility,
           AVG(amount) AS avg_amount,
           MEDIAN(durationSec) AS median_durationSec,
           SUM(commission) AS total_commission,
           100.0 * SUM(CASE WHEN NOT has_SL THEN 1 ELSE 0 END) / COUNT(*) AS no_sl_pct,
           100.0 * SUM(CASE WHEN NOT has_TP THEN 1 ELSE 0 END) / COUNT(*) AS no_tp_pct
    FROM trades_with_trader
    WHERE traderId IS NOT NULL
    GROUP BY traderId
""").fetchdf()

rebuilt_account_summary["outcome"] = rebuilt_account_summary["total_netProfit"].apply(
    lambda x: "winner" if x > 0 else "loser"
)

print("Shape:", rebuilt_account_summary.shape)
print(rebuilt_account_summary.describe())

# ---------------------------------------------------------
# Step 6: Save so you don't have to rebuild this every session
# ---------------------------------------------------------
rebuilt_account_summary.to_csv("../Data/processed/rebuilt_account_summary.csv", index=False)
print("Saved rebuilt_account_summary.csv")