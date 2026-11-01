"""SQLite bootstrap, sessions, and repo enable/disable."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from api.db import (
    PostgresConnection,
    connect,
    get_conn,
    parse_database_url,
    parse_libsql_target,
    qmark_to_percent,
    reset_bootstrap_cache,
)
from api.store import (
    InstallationOwnershipError,
    adopt_installation,
    create_session,
    get_session_user,
    list_repos_for_installation,
    list_repos_for_user,
    record_delivery,
    session_github_token,
    lookup_repo,
    mock_github_repo_id,
    mock_installation_id_for_user,
    seed_mock_workspace,
    set_repo_enabled,
    upsert_installation,
    upsert_user,
)


class TestDatabaseUrl(unittest.TestCase):
    def test_default_sqlite(self) -> None:
        with mock.patch.dict(os.environ, {"DATABASE_URL": "", "VERCEL": ""}, clear=False):
            dialect, target = parse_database_url("")
        self.assertEqual(dialect, "sqlite")
        self.assertTrue(target.endswith("cascade.db"))

    def test_relative_sqlite(self) -> None:
        dialect, target = parse_database_url("sqlite:///./cascade.db")
        self.assertEqual(dialect, "sqlite")
        self.assertEqual(target, "./cascade.db")

    def test_absolute_sqlite(self) -> None:
        dialect, target = parse_database_url("sqlite:////tmp/cascade.db")
        self.assertEqual(dialect, "sqlite")
        self.assertEqual(target, "/tmp/cascade.db")

    def test_postgres_recognized(self) -> None:
        dialect, target = parse_database_url("postgres://user:pass@host/db")
        self.assertEqual(dialect, "postgres")
        self.assertIn("host", target)

    def test_libsql_recognized(self) -> None:
        dialect, target = parse_database_url("libsql://example.turso.io")
        self.assertEqual(dialect, "libsql")
        self.assertIn("turso.io", target)

    def test_connect_postgres_accepted(self) -> None:
        fake = mock.Mock(name="postgres_conn")
        with mock.patch("api.db._connect_postgres", return_value=fake) as patched:
            conn = connect("postgres://localhost/cascade")
        patched.assert_called_once()
        self.assertIs(conn, fake)

    def test_connect_libsql_accepted(self) -> None:
        fake = mock.Mock(name="libsql_conn")
        with mock.patch("api.db._connect_libsql", return_value=fake) as patched:
            conn = connect("libsql://example.turso.io?authToken=tok")
        patched.assert_called_once()
        self.assertIs(conn, fake)

    def test_connect_postgresql_alias_accepted(self) -> None:
        fake = mock.Mock(name="postgres_conn")
        with mock.patch("api.db._connect_postgres", return_value=fake) as patched:
            connect("postgresql://user:pass@host:5432/cascade")
        patched.assert_called_once()

    def test_qmark_to_percent(self) -> None:
        self.assertEqual(
            qmark_to_percent("SELECT * FROM repos WHERE id = ? AND owner = ?"),
            "SELECT * FROM repos WHERE id = %s AND owner = %s",
        )

    def test_parse_libsql_target_token(self) -> None:
        url, token = parse_libsql_target("libsql://db-org.turso.io?authToken=secret")
        self.assertEqual(token, "secret")
        self.assertTrue(url.startswith("https://db-org.turso.io"))
        self.assertTrue(url.endswith("/v2/pipeline"))

    def test_postgres_connection_rewrites_placeholders(self) -> None:
        class _Raw:
            def __init__(self) -> None:
                self.last: tuple[str, tuple[object, ...]] | None = None

            def execute(self, sql: str, params: tuple[object, ...] = ()) -> object:
                self.last = (sql, params)

                class _Cursor:
                    def fetchone(self) -> None:
                        return None

                    def fetchall(self) -> list[object]:
                        return []

                return _Cursor()

        raw = _Raw()
        conn = PostgresConnection(raw)
        conn.execute("SELECT * FROM t WHERE id = ?", (3,))
        assert raw.last is not None
        self.assertEqual(raw.last[0], "SELECT * FROM t WHERE id = %s")
        self.assertEqual(raw.last[1], (3,))


class TestStore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "t.db")
        self.env = mock.patch.dict(
            os.environ,
            {"DATABASE_URL": f"sqlite:///{self.db}"},
            clear=False,
        )
        self.env.start()
        reset_bootstrap_cache()

    def tearDown(self) -> None:
        self.env.stop()
        reset_bootstrap_cache()
        self.tmp.cleanup()

    def test_schema_and_toggle(self) -> None:
        with get_conn() as conn:
            user = upsert_user(conn, github_user_id=7, login="octocat", avatar_url="https://example/a.png")
            user_id = int(user["id"])
            seed_mock_workspace(conn, user_id)
            repos = list_repos_for_user(conn, user_id)
            self.assertEqual(len(repos), 2)
            self.assertFalse(repos[0]["enabled"])
            updated = set_repo_enabled(
                conn,
                user_id=user_id,
                repo_id=int(repos[0]["id"]),
                enabled=True,
            )
            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertTrue(updated["enabled"])
            found = lookup_repo(conn, owner=updated["owner"], name=updated["name"])
            self.assertTrue(found and found["enabled"])
            self.assertIsNone(
                lookup_repo(
                    conn,
                    owner=updated["owner"],
                    name=updated["name"],
                    github_repo_id=1001,
                )
            )
            other = set_repo_enabled(
                conn,
                user_id=int(user["id"]) + 99,
                repo_id=int(repos[0]["id"]),
                enabled=False,
            )
            self.assertIsNone(other)

        with get_conn() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            for name in (
                "users",
                "sessions",
                "installations",
                "repos",
                "webhook_deliveries",
            ):
                self.assertIn(name, tables)
            user_id = int(user["id"])
            inst = conn.execute(
                "SELECT installation_id FROM installations WHERE installer_user_id = ?",
                (user_id,),
            ).fetchone()
            self.assertEqual(inst[0], mock_installation_id_for_user(user_id))

    def test_old_mock_repo_ids_are_rewritten(self) -> None:
        with get_conn() as conn:
            user = upsert_user(conn, github_user_id=7, login="octocat")
            inst = seed_mock_workspace(conn, int(user["id"]))
            inst_id = int(inst["installation_id"])
            conn.execute(
                """
                UPDATE repos SET github_repo_id = 1001
                WHERE installation_id = ? AND name = 'analytics'
                """,
                (inst_id,),
            )
            seed_mock_workspace(conn, int(user["id"]))
            self.assertIsNone(
                lookup_repo(conn, owner="acme", name="analytics", github_repo_id=1001)
            )
            rewritten = lookup_repo(
                conn,
                owner="acme",
                name="analytics",
                github_repo_id=mock_github_repo_id(inst_id, 1),
            )
            self.assertIsNotNone(rewritten)
            self.assertEqual(len(list_repos_for_user(conn, int(user["id"]))), 2)

    def test_mock_workspaces_are_isolated_per_user(self) -> None:
        with get_conn() as conn:
            alice = upsert_user(conn, github_user_id=10, login="alice")
            bob = upsert_user(conn, github_user_id=11, login="bob")
            seed_mock_workspace(conn, int(alice["id"]))
            seed_mock_workspace(conn, int(bob["id"]))
            a_repos = list_repos_for_user(conn, int(alice["id"]))
            b_repos = list_repos_for_user(conn, int(bob["id"]))
            self.assertEqual(len(a_repos), 2)
            self.assertEqual(len(b_repos), 2)
            self.assertEqual(
                a_repos[0]["installation_id"],
                mock_installation_id_for_user(int(alice["id"])),
            )
            self.assertEqual(
                b_repos[0]["installation_id"],
                mock_installation_id_for_user(int(bob["id"])),
            )
            self.assertNotEqual(a_repos[0]["installation_id"], b_repos[0]["installation_id"])
            self.assertLess(a_repos[0]["github_repo_id"], 0)
            self.assertLess(b_repos[0]["github_repo_id"], 0)
            self.assertNotEqual(a_repos[0]["github_repo_id"], b_repos[0]["github_repo_id"])
            updated = set_repo_enabled(
                conn,
                user_id=int(alice["id"]),
                repo_id=int(a_repos[0]["id"]),
                enabled=True,
            )
            self.assertIsNotNone(updated)
            b_again = list_repos_for_user(conn, int(bob["id"]))
            self.assertFalse(any(row["enabled"] for row in b_again))
            a_again = list_repos_for_user(conn, int(alice["id"]))
            self.assertTrue(any(row["enabled"] for row in a_again))

    def test_ownership_reassignment_rejected(self) -> None:
        with get_conn() as conn:
            alice = upsert_user(conn, github_user_id=10, login="alice")
            bob = upsert_user(conn, github_user_id=11, login="bob")
            adopt_installation(
                conn,
                user_id=int(alice["id"]),
                installation_id=99,
                account_login="acme",
            )
            with self.assertRaises(InstallationOwnershipError):
                adopt_installation(
                    conn,
                    user_id=int(bob["id"]),
                    installation_id=99,
                    account_login="evil",
                )
            with self.assertRaises(InstallationOwnershipError):
                upsert_installation(
                    conn,
                    installation_id=99,
                    account_login="evil",
                    account_type="Organization",
                    installer_user_id=int(bob["id"]),
                )
            row = conn.execute(
                "SELECT installer_user_id, account_login FROM installations WHERE installation_id = 99"
            ).fetchone()
            self.assertEqual(int(row["installer_user_id"]), int(alice["id"]))
            self.assertEqual(row["account_login"], "acme")
            same = adopt_installation(
                conn,
                user_id=int(alice["id"]),
                installation_id=99,
                account_login="acme-renamed",
            )
            self.assertEqual(same["account_login"], "acme-renamed")
            self.assertEqual(int(same["installer_user_id"]), int(alice["id"]))
            self.assertEqual(list_repos_for_installation(conn, 99), [])

    def test_session_roundtrip(self) -> None:
        with mock.patch.dict(os.environ, {"SESSION_SECRET": "test-secret"}), get_conn() as conn:
            user = upsert_user(conn, github_user_id=0, login="dev")
            token = create_session(conn, int(user["id"]), github_access_token="gho_secret")
            loaded = get_session_user(conn, token)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["login"], "dev")
            self.assertNotIn("github_access_token", loaded)
            self.assertEqual(session_github_token(conn, token), "gho_secret")
            self.assertIsNone(get_session_user(conn, "nope"))
            stored = conn.execute(
                "SELECT github_access_token FROM sessions WHERE id = ?", (token,)
            ).fetchone()[0]
            self.assertNotIn("gho_secret", stored)

    def test_session_token_unreadable_without_matching_secret(self) -> None:
        with get_conn() as conn:
            user = upsert_user(conn, github_user_id=4, login="legacy")
            token = create_session(conn, int(user["id"]))
            # Plaintext rows from before encryption are treated as missing.
            conn.execute(
                "UPDATE sessions SET github_access_token = 'gho_plain' WHERE id = ?", (token,)
            )
            with mock.patch.dict(os.environ, {"SESSION_SECRET": "test-secret"}):
                self.assertIsNone(session_github_token(conn, token))
                sealed = create_session(conn, int(user["id"]), github_access_token="gho_x")
            with mock.patch.dict(os.environ, {"SESSION_SECRET": "rotated"}):
                self.assertIsNone(session_github_token(conn, sealed))

    def test_legacy_sample_repos_on_real_installs_are_dropped(self) -> None:
        with get_conn() as conn:
            user = upsert_user(conn, github_user_id=8, login="real")
            upsert_installation(
                conn,
                installation_id=555,
                account_login="acme",
                account_type="Organization",
                installer_user_id=int(user["id"]),
            )
            conn.execute(
                """
                INSERT INTO repos (installation_id, owner, name, github_repo_id, enabled)
                VALUES (555, 'acme', 'analytics', 1001, 1)
                """
            )
        reset_bootstrap_cache()
        with get_conn() as conn:
            self.assertIsNone(lookup_repo(conn, owner="x", name="y", github_repo_id=1001))

    def test_record_delivery_dedupes_without_raising(self) -> None:
        with get_conn() as conn:
            args = dict(
                delivery_id="d-1",
                event="ping",
                action=None,
                repo_full_name=None,
                status="received",
                reason=None,
            )
            self.assertTrue(record_delivery(conn, **args))
            self.assertFalse(record_delivery(conn, **args))
            # Connection is still usable after the conflict.
            self.assertIsNotNone(conn.execute("SELECT 1").fetchone())

    def test_session_token_column_migrates(self) -> None:
        path = Path(self.tmp.name) / "old.db"
        raw = sqlite3.connect(path)
        raw.execute(
            """
            CREATE TABLE sessions (
              id TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              expires_at TEXT NOT NULL
            )
            """
        )
        raw.commit()
        raw.close()
        reset_bootstrap_cache()
        with mock.patch.dict(os.environ, {"SESSION_SECRET": "test-secret"}), get_conn(
            f"sqlite:///{path}"
        ) as conn:
            user = upsert_user(conn, github_user_id=3, login="migrated")
            token = create_session(conn, int(user["id"]), github_access_token="gho_old")
            self.assertEqual(session_github_token(conn, token), "gho_old")


if __name__ == "__main__":
    unittest.main()
