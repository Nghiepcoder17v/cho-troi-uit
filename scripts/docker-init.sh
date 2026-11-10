#!/usr/bin/env bash
set -euo pipefail

SQLCMD=/opt/mssql-tools18/bin/sqlcmd
SERVER=sqlserver

run_sql() {
  "$SQLCMD" -S "$SERVER" -U sa -P "$MSSQL_SA_PASSWORD" -C -b "$@"
}

echo "Waiting for SQL Server..."
for attempt in $(seq 1 60); do
  if run_sql -d master -Q "SELECT 1" >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 60 ]; then
    echo "SQL Server did not become ready in 120 seconds." >&2
    exit 1
  fi
  sleep 2
done

run_sql -d master -Q "IF DB_ID(N'ChoTroUIT') IS NULL CREATE DATABASE ChoTroUIT; IF DB_ID(N'ChoTroUIT_DWH') IS NULL CREATE DATABASE ChoTroUIT_DWH;"

table_count=$(run_sql -d ChoTroUIT -h -1 -W -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM sys.tables WHERE is_ms_shipped = 0;" | tr -d '[:space:]')
if [ "$table_count" = "0" ]; then
  echo "ChoTroUIT is empty: applying initial schema and reference data."
  run_sql -d ChoTroUIT -i /database_scripts/01_init_schema.sql
  run_sql -d ChoTroUIT -i /database_scripts/02_seed_reference_data.sql
else
  schema_ok=$(run_sql -d ChoTroUIT -h -1 -W -Q "SET NOCOUNT ON; SELECT CASE WHEN OBJECT_ID(N'dbo.USERS', N'U') IS NOT NULL AND OBJECT_ID(N'dbo.CATEGORIES', N'U') IS NOT NULL AND OBJECT_ID(N'dbo.PRODUCTS', N'U') IS NOT NULL AND OBJECT_ID(N'dbo.TRANSACTIONS', N'U') IS NOT NULL AND OBJECT_ID(N'dbo.REVIEWS', N'U') IS NOT NULL THEN 1 ELSE 0 END;" | tr -d '[:space:]')
  if [ "$schema_ok" != "1" ]; then
    echo "ChoTroUIT is non-empty but its core schema is incomplete. No schema script was run; inspect and migrate it manually." >&2
    exit 1
  fi
  echo "ChoTroUIT already has its core tables: leaving existing schema and data untouched."
fi

echo "Database initialization check completed. DWH tables are created by the ETL on its first run."
