import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cascade.agent import choose_and_rewrite
from cascade.cli import _safe_output_path

SRC = "urn:li:dataset:(urn:li:dataPlatform:postgres,db.public.src,PROD)"
A = "urn:li:dataset:(urn:li:dataPlatform:postgres,db.public.a,PROD)"
B = "urn:li:dataset:(urn:li:dataPlatform:postgres,db.public.b,PROD)"

def response(reply):
    body = json.dumps({"choices": [{"message": {"content": json.dumps(reply)}}]}).encode()
    cm = mock.MagicMock()
    cm.__enter__.return_value = cm
    cm.read.return_value = body
    return cm

class TestLlmRewrite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.root = Path(self.tmp.name)
        self.models = self.root / "models"; self.models.mkdir()
        self.a = self.models / "a.sql"; self.a.write_text("select a")
        self.b = self.models / "b.sql"; self.b.write_text("select b")
        self.catalog = {"downstream_map": {SRC: [A, B]}}
        self.env = mock.patch.dict(os.environ, {"LLM_API_KEY":"k", "LLM_MODEL":"m", "LLM_BASE_URL":"https://example.test"}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        os.chdir(self.old)
        self.tmp.cleanup()

    def run_call(self, mode="llm", **kw):
        return choose_and_rewrite([], self.catalog, self.root, SRC, rewrite_mode=mode, **kw)

    def test_off_and_legacy_deterministic(self):
        with mock.patch("cascade.agent.urlopen") as u:
            self.assertEqual(self.run_call("off"), []); self.assertEqual(self.run_call("deterministic"), []); u.assert_not_called()

    def test_valid_reply_and_unchanged_skipped_single_call(self):
        reply={"files":[{"path":str(self.a),"content":"select aa","reason":"edit"},{"path":str(self.b),"content":"select b","reason":"same"}],"notes":"ok"}
        with mock.patch("cascade.agent.urlopen", return_value=response(reply)) as u:
            out=self.run_call(diff_text="DIFF HERE")
        self.assertEqual(len(out),1); self.assertEqual(out[0]["path"],str(self.a)); self.assertEqual(out[0]["agent"],"llm"); u.assert_called_once()
        req=u.call_args.args[0]; body=json.loads(req.data); self.assertNotIn("temperature",body)
        prompt=body["messages"][0]["content"]; self.assertIn(f'<file path="{self.a}">',prompt); self.assertIn(f'<file path="{self.b}">',prompt); self.assertIn("DIFF HERE",prompt)

    def test_multiple_sources_share_one_prompt(self):
        src_b = "urn:li:dataset:(urn:li:dataPlatform:postgres,db.public.src_b,PROD)"
        cat = {"downstream_map": {SRC: [A], src_b: [B]}}
        with mock.patch("cascade.agent.urlopen", return_value=response({"files": [], "notes": ""})) as u:
            choose_and_rewrite([], cat, self.root, source_urns=[SRC, src_b], rewrite_mode="llm")
        u.assert_called_once()
        prompt = json.loads(u.call_args.args[0].data)["messages"][0]["content"]
        self.assertIn(f'<file path="{self.a}">', prompt)
        self.assertIn(f'<file path="{self.b}">', prompt)

    def test_bad_path(self):
        with mock.patch("cascade.agent.urlopen", return_value=response({"files":[{"path":"outside.sql","content":"x","reason":"x"}],"notes":""})):
            self.assertEqual(self.run_call(),[])

    def test_retries_invalid_json(self):
        good=response({"files":[],"notes":""})
        bad=mock.MagicMock(); bad.__enter__.return_value=bad; bad.read.return_value=b"bad"
        with mock.patch("cascade.agent.urlopen", side_effect=[bad,good]) as u:
            self.assertEqual(self.run_call(),[]); self.assertEqual(u.call_count,2)
        with mock.patch("cascade.agent.urlopen", side_effect=[bad,bad]) as u:
            self.assertEqual(self.run_call(),[]); self.assertEqual(u.call_count,2)

    def test_context_limit(self):
        self.a.write_text("x"*400001)
        with mock.patch("cascade.agent.urlopen") as u:
            self.assertEqual(self.run_call(),[]); u.assert_not_called()

    def test_no_resolved_files_skips_llm(self):
        with mock.patch("cascade.agent.urlopen") as u:
            self.assertEqual(choose_and_rewrite([], {"downstream_map": {SRC: ["missing"]}}, self.root, SRC, rewrite_mode="llm"), [])
            u.assert_not_called()

    def test_safe_output_paths(self):
        out=self.root/"out"
        self.assertNotEqual(_safe_output_path(out,"models/staging/schema.yml"),_safe_output_path(out,"models/marts/schema.yml"))
        for path in ("../escape.sql",str(self.root/"abs.sql")):
            with self.assertRaises(ValueError): _safe_output_path(out,path)

if __name__ == "__main__": unittest.main()
