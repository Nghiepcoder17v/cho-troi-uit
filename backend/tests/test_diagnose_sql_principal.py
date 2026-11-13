import pytest

import diagnose_sql_principal


class _FakeResult:
    def __init__(self, identity):
        self.identity = identity

    def mappings(self):
        return self

    def one(self):
        return self.identity


class _FakeConnection:
    def __init__(self, identity):
        self.identity = identity

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, _query):
        return _FakeResult(self.identity)


class _FakeEngine:
    def __init__(self, identity):
        self.identity = identity

    def connect(self):
        return _FakeConnection(self.identity)


def _identity(**overrides):
    values = {
        "server_name": "UIT-SQL-TEST",
        "original_login": "cho_troi_app",
        "effective_server_login": "cho_troi_app",
        "database_user": "cho_troi_app",
        "database_name": "ChoTroUIT_Test",
        "is_sysadmin": 0,
        "is_db_owner": 0,
    }
    return {**values, **overrides}


def test_diagnostic_requires_expected_database_before_connecting(monkeypatch, capsys):
    monkeypatch.delenv("EXPECTED_OLTP_DATABASE", raising=False)
    monkeypatch.setattr(
        diagnose_sql_principal,
        "engine",
        object(),
    )

    assert diagnose_sql_principal.main() == 2
    assert "EXPECTED_OLTP_DATABASE" in capsys.readouterr().out


def test_diagnostic_blocks_wrong_database(monkeypatch, capsys):
    monkeypatch.setenv("EXPECTED_OLTP_DATABASE", "ChoTroUIT")
    monkeypatch.setattr(diagnose_sql_principal, "engine", _FakeEngine(_identity()))

    assert diagnose_sql_principal.main() == 2
    output = capsys.readouterr().out
    assert "does not match EXPECTED_OLTP_DATABASE" in output
    assert "RESULT=BLOCKED" in output


@pytest.mark.parametrize(
    ("column", "value"),
    [("is_sysadmin", 1), ("is_db_owner", 1)],
)
def test_diagnostic_blocks_elevated_principal(monkeypatch, capsys, column, value):
    monkeypatch.setenv("EXPECTED_OLTP_DATABASE", "ChoTroUIT_Test")
    monkeypatch.setattr(
        diagnose_sql_principal,
        "engine",
        _FakeEngine(_identity(**{column: value})),
    )

    assert diagnose_sql_principal.main() == 2
    output = capsys.readouterr().out
    assert "FAIL:" in output
    assert "RESULT=BLOCKED" in output


def test_diagnostic_passes_least_privileged_identity_check(monkeypatch, capsys):
    monkeypatch.setenv("EXPECTED_OLTP_DATABASE", "ChoTroUIT_Test")
    monkeypatch.setattr(diagnose_sql_principal, "engine", _FakeEngine(_identity()))

    assert diagnose_sql_principal.main() == 0
    assert "RESULT=PASS" in capsys.readouterr().out
