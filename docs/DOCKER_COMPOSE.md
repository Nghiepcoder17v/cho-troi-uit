# Docker Compose local environment

Step 8 packages the API, web app, SQL Server OLTP database, and ETL utilities into a repeatable local setup. Compose runs one SQL Server instance with separate `ChoTroUIT` and `ChoTroUIT_DWH` databases. SQL Server stores its files in a named Docker volume.

## Requirements

- Docker Desktop with Docker Compose v2 or later.
- At least 4 GB of memory available to Docker Desktop; SQL Server needs several GB for a comfortable local run.

## Start the app

From the repository root in PowerShell:

```powershell
Copy-Item .env.compose.example .env.compose
```

Edit `.env.compose` and replace `MSSQL_SA_PASSWORD` and `JWT_SECRET`. The SQL Server password must meet SQL Server complexity rules. Keep the password URL-safe because it is included in the SQLAlchemy connection URL. `.env.compose` is ignored by Git and separate from the existing `.env` and `backend/.env` files.

Then build and start the services:

```powershell
docker compose --env-file .env.compose up --build
```

Open `http://localhost:8080` (or the configured `APP_PORT`). The frontend serves the built app and proxies `/api/` requests to FastAPI. SQL Server is also reachable from the host on `localhost:1433` (or `SQLSERVER_PORT`).

Stop the containers while keeping database files:

```powershell
docker compose --env-file .env.compose down
```

The `sqlserver-data` named volume persists OLTP and DWH databases across container restarts and `down`. Removing the volume deletes both databases; make a backup before doing so.

## Initialization behavior

On first start, `db-init` creates both databases. It runs `01_init_schema.sql` and `02_seed_reference_data.sql` only when `ChoTroUIT` has no user tables. If the database already contains tables, the initializer verifies the core application tables and leaves existing schema and data alone. A non-empty incomplete schema causes startup to stop with an error. This avoids silently running the destructive development schema script against an existing database.

The initializer does not run migrations automatically. Back up an existing database, inspect its migration state, and apply the required scripts under `database_scripts/migrations/` in order before pointing an application at it. The DWH schema is created by the ETL when ETL first runs.

## Run ETL and analytics

The ETL and analytics commands are opt-in tools, not started with the web app:

```powershell
docker compose --env-file .env.compose --profile tools run --rm etl
docker compose --env-file .env.compose --profile tools run --rm analytics
```

The default ETL run is incremental after its first load. It does not pass `--drop-dwh` and does not delete the warehouse.

## Service map

| Service | Purpose | Host port |
| --- | --- | --- |
| `frontend` | Production Vite build served by Nginx; proxies API calls | `APP_PORT` (8080) |
| `backend` | FastAPI API; waits for initialized database and health check | Internal 8000 |
| `sqlserver` | SQL Server Developer with OLTP and DWH databases | `SQLSERVER_PORT` (1433) |
| `etl`, `analytics` | One-shot data pipeline tools under the `tools` profile | None |

## Step 8 verification record

Verified locally with Docker Desktop and a separate Compose project/volume:

- All four images built: backend, frontend, ETL, and analytics. The frontend TypeScript/Vite production build passed inside its image.
- `docker compose up --wait` completed. SQL Server, FastAPI, and Nginx became healthy; the initializer created the OLTP tables and five reference categories.
- `GET /` through Nginx returned HTTP 200, and `GET /api/categories` returned all five categories.
- The first ETL run completed with `SUCCESS`, created the DWH schema, and reconciled the empty source tables.
- All four analytics queries ran against that DWH and returned empty result sets, as expected for an empty OLTP database.

The first container run exposed that SQL Server requires `ANSI_NULLS` and `QUOTED_IDENTIFIER` enabled when creating the filtered unique index. Those settings are now explicit at the start of `01_init_schema.sql`; the clean-volume startup then completed successfully.
