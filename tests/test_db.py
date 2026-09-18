"""SQLite bootstrap, sessions, and repo enable/disable."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from api.db import connect, get_conn, parse_database_url, reset_bootstrap_cache
from api.store import (
    MOCK_INSTALLATION_ID,
    create_session,
    get_session_user,
    list_repos_for_user,
    lookup_repo,
    seed_mock_workspace,
    set_repo_enabled,
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

    def test_connect_postgres_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            connect("postgres://localhost/cascade")


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
            self.assertEqual(inst[0], MOCK_INSTALLATION_ID)

    def test_session_roundtrip(self) -> None:
        with get_conn() as conn:
            user = upsert_user(conn, github_user_id=0, login="dev")
            token = create_session(conn, int(user["id"]))
            loaded = get_session_user(conn, token)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["login"], "dev")
            self.assertIsNone(get_session_user(conn, "nope"))


if __name__ == "__main__":
    unittest.main()
