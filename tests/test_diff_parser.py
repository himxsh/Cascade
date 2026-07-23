import json
import unittest
from pathlib import Path

from cascade.diff_parser import parse_diff, load_changes

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "diffs"


class TestParseDiff(unittest.TestCase):

    def test_annotation_only(self):
        diff = """\
diff --git a/models/stg_orders.sql b/models/stg_orders.sql
index a..b 100644
--- a/models/stg_orders.sql
+++ b/models/stg_orders.sql
@@ -1,3 +1,4 @@
+-- cascade: rename user_id -> customer_id
 SELECT 1
"""
        changes = parse_diff(diff)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["type"], "FIELD_RENAMED")
        self.assertEqual(changes[0]["from"], "user_id")
        self.assertEqual(changes[0]["to"], "customer_id")
        self.assertEqual(changes[0]["detected_by"], "annotation")

    def test_annotation_hash_style(self):
        diff = """\
diff --git a/t.py b/t.py
--- a/t.py
+++ b/t.py
@@ -1 +1 @@
-foo
+# cascade: rename old_col -> new_col
"""
        changes = parse_diff(diff)
        renamed = [c for c in changes if c["type"] == "FIELD_RENAMED"]
        self.assertEqual(len(renamed), 1)
        self.assertEqual(renamed[0]["detected_by"], "annotation")

    def test_heuristic_rename_one_removed_one_added(self):
        diff = """\
diff --git a/schema/t.sql b/schema/t.sql
index a..b 100644
--- a/schema/t.sql
+++ b/schema/t.sql
@@ -1,5 +1,5 @@
 CREATE TABLE t (
     id INT NOT NULL,
-    user_id VARCHAR(128),
+    customer_id VARCHAR(128),
     amount DECIMAL
 );
"""
        changes = parse_diff(diff)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["type"], "FIELD_RENAMED")
        self.assertEqual(changes[0]["from"], "user_id")
        self.assertEqual(changes[0]["to"], "customer_id")
        self.assertEqual(changes[0]["detected_by"], "heuristic")

    def test_field_removed_alone(self):
        diff = """\
diff --git a/schema/t.sql b/schema/t.sql
--- a/schema/t.sql
+++ b/schema/t.sql
@@ -1,5 +1,4 @@
 CREATE TABLE t (
     id INT NOT NULL,
-    obsolete_flag INT,
     amount DECIMAL
 );
"""
        changes = parse_diff(diff)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["type"], "FIELD_REMOVED")
        self.assertEqual(changes[0]["from"], "obsolete_flag")
        self.assertIsNone(changes[0]["to"])
        self.assertEqual(changes[0]["detected_by"], "heuristic")

    def test_annotation_overrides_heuristic(self):
        diff = """\
diff --git a/schema/t.sql b/schema/t.sql
--- a/schema/t.sql
+++ b/schema/t.sql
@@ -1,5 +1,6 @@
+-- cascade: rename old_name -> new_name
 CREATE TABLE t (
-    old_name VARCHAR(64),
-    dropped_col INT,
+    new_name VARCHAR(128),
+    another_col INT,
+    extra_col DATE,
     id INT
 );
"""
        changes = parse_diff(diff)
        renamed = [c for c in changes if c["type"] == "FIELD_RENAMED"]
        self.assertEqual(len(renamed), 1)
        self.assertEqual(renamed[0]["from"], "old_name")
        self.assertEqual(renamed[0]["to"], "new_name")
        self.assertEqual(renamed[0]["detected_by"], "annotation")
        removed = [c for c in changes if c["type"] == "FIELD_REMOVED"]
        self.assertGreaterEqual(len(removed), 1)

    def test_sql_keywords_filtered(self):
        diff = """\
diff --git a/schema/t.sql b/schema/t.sql
--- a/schema/t.sql
+++ b/schema/t.sql
@@ -1,3 +1,3 @@
-SELECT foo,
+SELECT bar,
 FROM t
"""
        changes = parse_diff(diff)
        self.assertEqual(len(changes), 0)

    def test_no_changes(self):
        diff = """\
diff --git a/a.sql b/a.sql
--- a/a.sql
+++ b/a.sql
@@ -1,3 +1,4 @@
+-- cascade: rename x -> y
 SELECT 1
"""
        changes = parse_diff(diff)
        self.assertEqual(changes[0]["detected_by"], "annotation")

    def test_multi_file_diff(self):
        diff = """\
diff --git a/a.sql b/a.sql
--- a/a.sql
+++ b/a.sql
@@ -1,3 +1,3 @@
-    col_a INT,
+    col_b INT,

diff --git a/b.sql b/b.sql
--- a/b.sql
+++ b/b.sql
@@ -1,3 +1,2 @@
-    orphan INT,
"""
        changes = parse_diff(diff)
        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[0]["type"], "FIELD_RENAMED")
        self.assertEqual(changes[0]["from"], "col_a")
        self.assertEqual(changes[1]["type"], "FIELD_REMOVED")
        self.assertEqual(changes[1]["from"], "orphan")


class TestLoadChanges(unittest.TestCase):

    def test_json_file(self):
        json_path = FIXTURES / "raw_orders_rename_user_id.json"
        changes = load_changes(json_path)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["type"], "FIELD_RENAMED")
        self.assertEqual(changes[0]["from"], "user_id")

    def test_patch_file(self):
        patch_path = FIXTURES / "raw_orders_rename_user_id.patch"
        changes = load_changes(patch_path)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["type"], "FIELD_RENAMED")
        self.assertEqual(changes[0]["from"], "user_id")
        self.assertEqual(changes[0]["to"], "customer_id")
        self.assertEqual(changes[0]["detected_by"], "annotation")

    def test_json_list_direct(self):
        path = Path("/tmp/_test_json_list.json")
        try:
            path.write_text(json.dumps([
                {"type": "FIELD_REMOVED", "from": "x", "to": None,
                 "detected_by": "heuristic"},
            ]))
            changes = load_changes(path)
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0]["from"], "x")
        finally:
            path.unlink(missing_ok=True)

    def test_json_dict_with_changes_key(self):
        path = Path("/tmp/_test_json_dict.json")
        try:
            path.write_text(json.dumps({
                "changes": [
                    {"type": "FIELD_RENAMED", "from": "a", "to": "b",
                     "detected_by": "annotation"},
                ],
            }))
            changes = load_changes(path)
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0]["from"], "a")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
