"""SyncRun table schema (DynamoDB).

Table: sync_runs
PK: id (N) — auto-increment via counters table
GSI: account-index (marketplace_account_id)

Fields:
    id: int
    marketplace_account_id: int
    sync_type: str  (full | incremental | mock)
    status: str  (running | completed | failed)
    started_at: str (ISO datetime)
    completed_at: str | None (ISO datetime)
    records_fetched: int
    records_upserted: int
    error_log: str | None
    cursor_state: str | None
"""
TABLE_NAME = "sync_runs"
