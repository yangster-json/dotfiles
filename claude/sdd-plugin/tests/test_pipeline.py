"""tests for the sdd-pipeline resolver.

the resolver replaces an in-context Read of the whole pipeline file, so the
thing that matters is that it merges exactly like README's "profiles and project overrides"
says — outermost layer last, `config:` by key, `pipeline:` by stage name with
base order preserved and unknown names appended — and that it refuses a cycle
instead of looping. the real profile in sdd-profiles/ only exercises a
config-only layer, so the pipeline-merge and chaining cases are built here.
"""
import os
import subprocess
import sys
import tempfile
import unittest

import yaml

from helpers import SDD, load_module

pipeline = load_module("sdd_pipeline", "bin/sdd-pipeline")

CLI = os.path.join(SDD, "bin", "sdd-pipeline")


def write(path, doc):
    with open(path, "w") as fh:
        yaml.safe_dump(doc, fh, sort_keys=False)
    return path


def stages(*names):
    return [{"stage": n, "run_via": f"agent {n}"} for n in names]


class ConfigMerge(unittest.TestCase):
    def test_outer_key_replaces_whole_value(self):
        base = {"config": {"models": {"a": "opus", "b": "sonnet"}, "gates": 2}}
        layer = {"config": {"models": {"a": "haiku"}}}
        out = pipeline.merge(base, layer)
        # replaces the whole models map, not a deep merge of it
        self.assertEqual(out["config"]["models"], {"a": "haiku"})
        self.assertEqual(out["config"]["gates"], 2)

    def test_absent_key_inherits(self):
        base = {"config": {"gates": 2, "tier": "light"}}
        out = pipeline.merge(base, {"config": {"gates": 1}})
        self.assertEqual(out["config"], {"gates": 1, "tier": "light"})

    def test_extends_is_consumed(self):
        out = pipeline.merge({"config": {}}, {"extends": "plugin", "config": {"x": 1}})
        self.assertNotIn("extends", out)


class PipelineMerge(unittest.TestCase):
    def test_named_stage_replaced_in_place(self):
        base = stages("research", "spec", "plan")
        layer = [{"stage": "spec", "run_via": "workflow custom"}]
        out = pipeline.merge_pipeline(base, layer)
        self.assertEqual([s["stage"] for s in out], ["research", "spec", "plan"])
        self.assertEqual(out[1]["run_via"], "workflow custom")

    def test_absent_stage_inherits_unchanged(self):
        base = stages("research", "spec")
        out = pipeline.merge_pipeline(base, [{"stage": "spec", "optional": True}])
        self.assertEqual(out[0], base[0])

    def test_unknown_stage_appends_at_end(self):
        base = stages("research", "spec")
        out = pipeline.merge_pipeline(base, [{"stage": "deploy"}])
        self.assertEqual([s["stage"] for s in out], ["research", "spec", "deploy"])

    def test_replace_and_append_together(self):
        base = stages("a", "b")
        layer = [{"stage": "b", "x": 1}, {"stage": "c"}]
        out = pipeline.merge_pipeline(base, layer)
        self.assertEqual([s["stage"] for s in out], ["a", "b", "c"])
        self.assertEqual(out[1]["x"], 1)


class Chain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_plugin_sentinel_resolves_to_bundled(self):
        got = pipeline.resolve_extends("plugin", os.path.join(self.tmp, "p.yaml"))
        self.assertEqual(got, pipeline.PLUGIN_PIPELINE)

    def test_relative_path_resolves_against_referrer(self):
        ref = os.path.join(self.tmp, "sub", "child.yaml")
        got = pipeline.resolve_extends("../base.yaml", ref)
        self.assertEqual(got, os.path.join(self.tmp, "base.yaml"))

    def test_chain_returns_terminal_base_first(self):
        b = write(os.path.join(self.tmp, "b.yaml"),
                  {"config": {"tier": "light"}, "pipeline": stages("a")})
        m = write(os.path.join(self.tmp, "m.yaml"),
                  {"extends": b, "config": {"tier": "heavy"}})
        t = write(os.path.join(self.tmp, "t.yaml"),
                  {"extends": m, "config": {"gates": 1}})
        chain = pipeline.load_chain(t)
        self.assertEqual([os.path.basename(p) for p, _ in chain],
                         ["b.yaml", "m.yaml", "t.yaml"])

    def test_outermost_layer_wins(self):
        b = write(os.path.join(self.tmp, "b.yaml"), {"config": {"tier": "light"}})
        m = write(os.path.join(self.tmp, "m.yaml"),
                  {"extends": b, "config": {"tier": "medium"}})
        t = write(os.path.join(self.tmp, "t.yaml"),
                  {"extends": m, "config": {"tier": "heavy"}})
        chain = pipeline.load_chain(t)
        doc = chain[0][1]
        for _, layer in chain[1:]:
            doc = pipeline.merge(doc, layer)
        self.assertEqual(doc["config"]["tier"], "heavy")

    def test_cycle_is_an_error_not_a_loop(self):
        a = os.path.join(self.tmp, "a.yaml")
        b = os.path.join(self.tmp, "b.yaml")
        write(a, {"extends": b, "config": {}})
        write(b, {"extends": a, "config": {}})
        with self.assertRaises(SystemExit) as cm:
            pipeline.load_chain(a)
        self.assertIn("cycle", str(cm.exception))

    def test_missing_file_is_an_error(self):
        with self.assertRaises(SystemExit):
            pipeline.load_chain(os.path.join(self.tmp, "nope.yaml"))


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        r = subprocess.run([sys.executable, CLI, *args],
                           capture_output=True, text=True)
        return r

    def test_bundled_pipeline_resolves_and_round_trips(self):
        r = self.run_cli()
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = yaml.safe_load(r.stdout)
        self.assertIn("config", doc)
        self.assertIn("pipeline", doc)
        self.assertNotIn("extends", doc)

    def test_every_scripted_stage_names_a_workflow_that_exists(self):
        """`run_via: workflow X` is a promise the orchestrator acts on — a
        missing entry or file sends a whole stage down its inline fallback,
        silently and every time."""
        doc = yaml.safe_load(self.run_cli().stdout)
        declared = doc["config"]["workflows"]
        scripted = [s for s in doc["pipeline"]
                    if "workflow" in (s.get("run_via") or "")]
        self.assertGreaterEqual(len(scripted), 5)   # every fan-out stage
        for stage in scripted:
            name = stage["run_via"].split("workflow", 1)[1].split()[0]
            self.assertIn(name, declared, f"{stage['stage']} names workflow {name}")
            self.assertTrue(os.path.isfile(os.path.join(SDD, declared[name])),
                            f"{declared[name]} missing")

    def test_output_is_smaller_than_the_source_it_replaces(self):
        # the whole point: fewer bytes into context than Reading the file
        src = os.path.getsize(pipeline.PLUGIN_PIPELINE)
        self.assertLess(len(self.run_cli().stdout), src)
        self.assertLess(len(self.run_cli("--section", "config").stdout), src // 4)

    def test_section_and_stage_selection(self):
        cfg = yaml.safe_load(self.run_cli("--section", "config").stdout)
        self.assertEqual(list(cfg), ["config"])
        one = yaml.safe_load(self.run_cli("--stage", "implement").stdout)
        self.assertEqual([s["stage"] for s in one["pipeline"]], ["implement"])
        # config: is read once up front, so a bare --stage must not repeat it
        self.assertNotIn("config", one)
        both = yaml.safe_load(
            self.run_cli("--stage", "implement", "--section", "config").stdout)
        self.assertEqual(set(both), {"config", "pipeline"})

    def test_unknown_stage_lists_the_real_ones(self):
        r = self.run_cli("--stage", "nope")
        self.assertEqual(r.returncode, 1)
        self.assertIn("implement", r.stderr)

    def test_json_matches_yaml(self):
        import json
        self.assertEqual(json.loads(self.run_cli("--json").stdout),
                         yaml.safe_load(self.run_cli().stdout))

    def test_chain_lists_files_without_the_body(self):
        r = self.run_cli("--chain")
        self.assertIn("pipeline.yaml", r.stdout)
        self.assertNotIn("stage:", r.stdout)


if __name__ == "__main__":
    unittest.main()
