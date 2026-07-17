import duckdb
import numpy
import pandas
# Connect to (or create) a persistent database file
con = duckdb.connect('data/processed/project.duckdb')

# Combine all 66 trade files into one table
# union_by_name=true means: match columns by name, not position — 
# handles files where column order differs slightly
con.execute("""
    CREATE OR REPLACE TABLE trades AS
    SELECT *,
           regexp_extract(filename, 'Campaign ([0-9]+)', 1) AS campaignId
    FROM read_csv_auto(
        'data/raw/user_trades/*.csv',
        union_by_name=true,
        filename=true
    )
""")

# Quick sanity check: how many rows, how many unique campaigns?
result = con.execute("""
    SELECT COUNT(*) AS total_rows, COUNT(DISTINCT campaignId) AS num_campaigns
    FROM trades
""").fetchdf()
print(result)

# Load user/account data too
con.execute("""
    CREATE OR REPLACE TABLE users AS
    SELECT * FROM read_csv_auto('data/raw/user_data/*.csv', union_by_name=true)
""")

# Save trades as a Parquet file too (handy for pandas/polars later)
con.execute("""
    COPY trades TO 'data/processed/trades_master.parquet' (FORMAT PARQUET)
""")

print("Done. Master dataset built.")
