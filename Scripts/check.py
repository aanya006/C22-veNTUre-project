import duckdb
con = duckdb.connect('data/processed/project.duckdb')
result = con.execute("SELECT campaignId, COUNT(*) FROM trades GROUP BY campaignId ORDER BY campaignId").fetchdf()
print(result) 

