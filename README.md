# C22 x veNTUre Project

Behavioral analysis of retail trading data, done as an NTU veNTUre industry project in partnership with **C22** (Contrarian Thinking in Behavioral Finance). We take raw trade and account data from ~80 trading campaigns, join it into one clean master dataset, dig into how traders actually behave (biases, streaks, risk-taking), and build a real-time signal that flags trades worth betting against.

## What this does

Each campaign gives every trader a fresh $5,000 account and lets them trade (mainly gold) for a fixed window. We pull the raw per-campaign exports together into a single dataset keyed by trader (not account, since account IDs get recycled across campaigns), then use it to answer two questions:

1. **What do traders actually do wrong?** (Stage 1) — loss aversion, revenge trading, bet-size escalation on losing streaks, house money effect, and more.
2. **Can we flag a bad trade while it's still open?** (Stage 4) — a real-time risk score built only from information available before a trade closes, forward-tested on campaigns C22 never used to build it.

## Key features

- **PDPA-safe master dataset pipeline** (`Scripts/`) — joins raw trade exports with user registries per campaign, hashes emails into a `traderId` so no PII is ever stored, and incrementally appends new campaigns without touching existing data.
- **Campaign-aware feature engineering** — equity, drawdown, win/loss streaks, and re-entry gaps that correctly reset at each trader's campaign boundary instead of bleeding across their whole history.
- **Stage 1 — Exploratory analysis** (`notebooks/Stage1_EDA.ipynb`) — data quality checks, trader-level profiling, and hypothesis tests around known behavioral biases (house money effect, early profit-taking vs. own take-profit, bet escalation after losing streaks, re-entry haste after a loss, and more).
- **Stage 4 — Real-time risk scoring** (`notebooks/stage4.ipynb`) — flags large, stop-loss-free trades that are still open past a given time checkpoint, then ranks them by how "fadeable" (profitable to bet against) they are. Forward-tested, out-of-sample, on campaigns 67-82: the top-risk tier was profitable to fade in 13-14 out of 16 campaigns individually, with profit factor climbing to 1.45 at the 60-minute checkpoint.

## Project structure

```
Data/
  Raw/                  raw per-campaign trade + user exports (not tracked, see below)
  processed/            project.duckdb (master dataset) + derived CSV/parquet outputs
  requirements.txt
Scripts/
  rebuilt_master_ds.py   builds trades_with_trader from raw exports (campaigns 1-66)
  latest_master_ds.py    adds campaign-aware features (equity, drawdown, streaks)
  final_master_ds.py     appends new campaigns (67-82) to trades_with_trader
notebooks/
  Stage1_EDA.ipynb       data quality checks, trader profiling, bias analysis
  stage4.ipynb           checkpoint-based risk scoring + forward test on campaigns 67-82
```

## Installation

```bash
git clone <this-repo-url>
cd C22-veNTUre-project
python3 -m venv venv
source venv/bin/activate
pip install -r Data/requirements.txt
```

Raw campaign data (`Data/Raw/`) contains trader emails and is **not** included in this repo — it's gitignored for privacy. You'll need your own copy of the campaign exports (user registry + trade files, named `Campaign <N>.csv`/`.xlsx`) dropped into `Data/Raw/user_data/` and `Data/Raw/user_trades/` before running the pipeline scripts. Once loaded, all downstream analysis works off the hashed `traderId`, never the raw email.

## Quickstart

1. **Build (or update) the master dataset.** Run from inside `Scripts/`, in order, only as needed for the campaigns you're adding:
   ```bash
   python rebuilt_master_ds.py   # first build: raw exports -> trades_with_trader
   python latest_master_ds.py    # adds campaign-aware features (equity, drawdown, streaks)
   python final_master_ds.py     # appends newer campaigns to an existing trades_with_trader
   ```
   This populates `Data/processed/project.duckdb`, which every notebook reads from.

2. **Explore the behavioral analysis:**
   ```bash
   jupyter notebook notebooks/Stage1_EDA.ipynb
   ```

3. **Explore the risk-scoring system and forward test:**
   ```bash
   jupyter notebook notebooks/stage4.ipynb
   ```

## Contributors

- **Devanshi** — master dataset pipeline, Stage 1 data quality/profiling, Stage 4 risk-scoring system and forward test
- **Aanya** — one-variable sweeps and interaction-effect analysis (Stage 1)
- **Prisha** — campaign-aware feature design (equity/drawdown/streak reset logic)
- **Devanshi SG** — bias analysis: house money effect, early profit-taking vs. own take-profit, and related biases (Stage 1)

## License

Private project developed for the NTU veNTUre programme in collaboration with C22. Not licensed for external use or redistribution.
