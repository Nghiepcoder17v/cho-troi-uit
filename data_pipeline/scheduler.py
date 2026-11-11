"""Run the SQL Server ETL on a fixed-delay schedule with safe retries."""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from contextlib import contextmanager
from typing import Iterator

import sqlalchemy as sa
from dotenv import load_dotenv

from etl.pipeline import DEFAULT_OVERLAP_MINUTES, RunResult, run_etl

log = logging.getLogger("etl.scheduler")
LOCK_RESOURCE = "cho-troi-uit:etl:scheduler"


def _positive_int(name: str, default: int, *, allow_zero: bool = False) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}.") from exc
    minimum = 0 if allow_zero else 1
    if value < minimum:
        comparator = "non-negative" if allow_zero else "greater than zero"
        raise ValueError(f"{name} must be {comparator}.")
    return value


@contextmanager
def _scheduler_lock(engine: sa.Engine) -> Iterator[bool]:
    """Hold a SQL Server session application lock across one ETL cycle."""
    if engine.dialect.name != "mssql":
        raise RuntimeError("The ETL scheduler requires SQL Server for its distributed run lock.")

    connection = engine.connect()
    acquired = False
    try:
        code = connection.scalar(
            sa.text(
                "DECLARE @lock_result int; "
                "EXEC @lock_result = sys.sp_getapplock "
                "@Resource = :resource, @LockMode = 'Exclusive', "
                "@LockOwner = 'Session', @LockTimeout = 0; "
                "SELECT @lock_result;"
            ),
            {"resource": LOCK_RESOURCE},
        )
        acquired = code is not None and code >= 0
        yield acquired
    finally:
        if acquired:
            try:
                connection.scalar(
                    sa.text(
                        "DECLARE @release_result int; "
                        "EXEC @release_result = sys.sp_releaseapplock "
                        "@Resource = :resource, @LockOwner = 'Session'; "
                        "SELECT @release_result;"
                    ),
                    {"resource": LOCK_RESOURCE},
                )
            except Exception:  # noqa: BLE001 - closing the SQL session releases the lock
                log.exception("Could not explicitly release the ETL scheduler lock.")
            connection.close()
        else:
            connection.close()


def _log_result(result: RunResult) -> None:
    message = (
        "ETL run_id=%s mode=%s status=%s extracted=%s loaded=%s rejected=%s reconciliation=%s"
    )
    args = (
        result.run_id,
        result.mode,
        result.status,
        result.extracted,
        result.loaded,
        result.rejected,
        result.reconciliation,
    )
    if result.status == "WARNING":
        log.warning(message, *args)
        for warning in result.warnings:
            log.warning("ETL run_id=%s: %s", result.run_id, warning)
    else:
        log.info(message, *args)


def run_cycle(
    source: sa.Engine,
    dwh: sa.Engine,
    *,
    retry_attempts: int,
    retry_delay_seconds: int,
    max_retry_delay_seconds: int,
    overlap_minutes: int,
    stop_event: threading.Event,
) -> None:
    with _scheduler_lock(dwh) as acquired:
        if not acquired:
            log.warning("Another scheduler owns the ETL lock; skipping this cycle.")
            return

        for retry_number in range(retry_attempts + 1):
            try:
                result = run_etl(
                    source,
                    dwh,
                    overlap_minutes=overlap_minutes,
                )
            except Exception as exc:  # noqa: BLE001 - retry failures and keep the scheduler alive
                if retry_number == retry_attempts:
                    log.error(
                        "ETL failed after %d attempt(s); next scheduled cycle will retry: %s",
                        retry_number + 1,
                        exc,
                    )
                    return

                delay = min(retry_delay_seconds * (2**retry_number), max_retry_delay_seconds)
                log.error(
                    "ETL attempt %d/%d failed; retrying in %d second(s): %s",
                    retry_number + 1,
                    retry_attempts + 1,
                    delay,
                    exc,
                )
                if stop_event.wait(delay):
                    log.info("Shutdown requested while waiting to retry ETL.")
                    return
            else:
                _log_result(result)
                return


def main() -> int:
    logging.basicConfig(
        stream=sys.stdout,
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    load_dotenv()

    try:
        interval_seconds = _positive_int("ETL_INTERVAL_SECONDS", 3600)
        retry_attempts = _positive_int("ETL_RETRY_ATTEMPTS", 3, allow_zero=True)
        retry_delay_seconds = _positive_int("ETL_RETRY_DELAY_SECONDS", 30)
        max_retry_delay_seconds = _positive_int("ETL_MAX_RETRY_DELAY_SECONDS", 300)
        overlap_minutes = _positive_int("ETL_OVERLAP_MINUTES", DEFAULT_OVERLAP_MINUTES, allow_zero=True)
        if max_retry_delay_seconds < retry_delay_seconds:
            raise ValueError("ETL_MAX_RETRY_DELAY_SECONDS must be >= ETL_RETRY_DELAY_SECONDS.")

        source_url = os.getenv("DATABASE_URL")
        dwh_url = os.getenv("DWH_DATABASE_URL")
        if not source_url or not dwh_url:
            raise ValueError("DATABASE_URL and DWH_DATABASE_URL must both be configured.")

        source = sa.create_engine(source_url, fast_executemany=True, pool_pre_ping=True)
        dwh = sa.create_engine(dwh_url, fast_executemany=True, pool_pre_ping=True)
    except Exception as exc:  # noqa: BLE001 - invalid settings should fail fast
        log.error("Invalid ETL scheduler configuration: %s", exc)
        return 2

    stop_event = threading.Event()

    def request_stop(signum, _frame) -> None:
        log.info("Received signal %s; stopping after the current ETL operation.", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    log.info(
        "ETL scheduler started: interval=%ss retries=%s initial_retry_delay=%ss max_retry_delay=%ss overlap=%sm.",
        interval_seconds,
        retry_attempts,
        retry_delay_seconds,
        max_retry_delay_seconds,
        overlap_minutes,
    )
    try:
        while not stop_event.is_set():
            run_cycle(
                source,
                dwh,
                retry_attempts=retry_attempts,
                retry_delay_seconds=retry_delay_seconds,
                max_retry_delay_seconds=max_retry_delay_seconds,
                overlap_minutes=overlap_minutes,
                stop_event=stop_event,
            )
            if not stop_event.is_set():
                log.info("Next ETL cycle in %d second(s).", interval_seconds)
                stop_event.wait(interval_seconds)
    except Exception:  # noqa: BLE001 - unexpected scheduler faults should be visible
        log.exception("ETL scheduler stopped by an unexpected error.")
        return 1
    finally:
        source.dispose()
        dwh.dispose()
        log.info("ETL scheduler stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
