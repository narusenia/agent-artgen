import tempfile
import unittest
from pathlib import Path

from artgen import gen, presets, project, workflow

STYLE = 'style = { positive = "masterpiece", negative = "lowres" }\n[uniform]\nfemale = { positive = "blazer" }\n'
WHO = '''
[[preset]]
name = "stance"
uses = ["uniform.female"]
positive = "1girl, standing"
negative = "bad hands"
replace = [["standing", "kneeling"]]
ref = "refs/a.png"
seeds = [3, 4]
width = 640
'''


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "artgen.toml").write_text('out = "art/out"\nprompts = "art/prompts"\n[modal]\ngpu = "L4"\n[gen]\nn = 1\n')
        (root / "art/prompts").mkdir(parents=True)
        (root / "art/prompts/_style.toml").write_text(STYLE)
        (root / "art/prompts/mia.toml").write_text(WHO)
        (root / "refs").mkdir()
        (root / "refs/a.png").write_bytes(b"png")
        (root / "deep/er").mkdir(parents=True)
        self.p = project.load(project.find(root / "deep/er"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_project_found_from_subdirectory(self):
        self.assertEqual(self.p.out, self.p.root / "art/out")
        self.assertEqual(self.p.modal["gpu"], "L4")
        self.assertEqual(self.p.gen["n"], 1)
        with self.assertRaises(SystemExit):
            self.p.check_gpu("H100")

    def test_preset_joins_style_and_character(self):
        jobs = presets.load(self.p, "mia/stance")
        self.assertEqual([j["seed"] for j in jobs], [3, 4])
        self.assertEqual(jobs[0]["prompt"], "masterpiece, blazer, 1girl, kneeling")
        self.assertEqual(jobs[0]["negative"], "lowres, bad hands")
        self.assertEqual(jobs[0]["ref"], str(self.p.root.resolve() / "refs/a.png"))
        self.assertEqual(jobs[0]["tag"], "mia_stance")

    def test_command_line_seed_replaces_preset_seeds(self):
        jobs = gen.plan(self.p, self.p.gen, {"preset": "mia/stance", "seed": 9})
        self.assertEqual([(j["seed"], j["width"]) for j in jobs], [(9, 640)])

    def test_workflow_gets_job_values_and_reference(self):
        job = gen.plan(self.p, self.p.gen | {"workflow": "sdxl_hires_detailer"}, {"preset": "mia/stance"})[0]
        wf, inputs = workflow.build(job)
        self.assertEqual(wf[workflow.POS]["inputs"]["text"], job["prompt"])
        self.assertEqual(wf[workflow.SAMPLER]["inputs"]["model"], ["23", 0])
        self.assertTrue(all(n["inputs"]["seed"] == 3 for n in wf.values() if "seed" in n["inputs"]))
        self.assertEqual(list(inputs), ["a.png"])

    def test_prompt_required(self):
        with self.assertRaises(SystemExit):
            gen.plan(self.p, self.p.gen, {})


if __name__ == "__main__":
    unittest.main()
