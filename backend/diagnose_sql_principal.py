"""Read-only SQL Server identity check using the backend's configured DATABASE_URL.

Run this inside the same backend image/container and environment as the deployed API.
It never prints DATABASE_URL or credentials.
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import text

from database import engine


IDENTITY_QUERY = text(
    """
    SELECT
        @@SERVERNAME AS server_name,
        ORIGINAL_LOGIN() AS original_login,
        SUSER_SNAME() AS effective_server_login,
        USER_NAME() AS database_user,
        DB_NAME() AS database_name,
        IS_SRVROLEMEMBER('sysadmin') AS is_sysadmin,
        IS_MEMBER('db_owner') AS is_db_owner
    """
)


def main() -> int:
    expected_database = os.getenv("EXPECTED_OLTP_DATABASE", "").strip()
    if not expected_database:
        print("RESULT=BLOCKED: set EXPECTED_OLTP_DATABASE to the approved OLTP database name.")
        return 2

    with engine.connect() as connection:
        identity = connection.execute(IDENTITY_QUERY).mappings().one()

    for key, value in identity.items():
        print(f"{key}={value}")

    failures: list[str] = []
    if identity["database_name"] != expected_database:
        failures.append(
            f"connected database {identity['database_name']!r} does not match "
            f"EXPECTED_OLTP_DATABASE {expected_database!r}"
        )
    if identity["is_sysadmin"] == 1:
        failures.append("runtime principal is a member of sysadmin")
    if identity["is_db_owner"] == 1:
        failures.append("runtime principal is a member of db_owner")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        print("RESULT=BLOCKED: do not grant audit permissions or deploy DB-6 migrations.")
        return 2

    print("RESULT=PASS: target database matches and runtime principal is not sysadmin/db_owner.")
    print("This check does not grant permissions or prove that the principal has least privilege.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
