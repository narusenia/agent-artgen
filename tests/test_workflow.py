import tempfile
import unittest
from pathlib import Path

from artgen import models, workflow

BASE = {"prompt": "1girl", "negative": "", "seed": 5, "width": 832, "height": 1216, "n": 2, "tag": "", "workflow": "sdxl_hires_detailer"}


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        for n in ("src.png", "mask.png", "depth.png", "pose.png"):
            (d / n).write_bytes(n.encode())
        self.d = d

    def tearDown(self):
        self.tmp.cleanup()

    def test_inpaint_feeds_masked_latent_to_first_sampler(self):
        wf, inputs = workflow.build(BASE | {"image": str(self.d / "src.png"), "mask": str(self.d / "mask.png")})
        s = wf[workflow.SAMPLER]["inputs"]
        self.assertEqual(s["latent_image"], ["42", 0])
        self.assertEqual(wf["42"]["inputs"]["samples"], ["44", 0])
        self.assertEqual(s["denoise"], 0.9)
        self.assertNotIn(workflow.LATENT, wf)
        self.assertEqual(sorted(inputs), ["mask.png", "src.png"])

    def test_controls_chain_onto_every_sampler(self):
        control = [{"image": str(self.d / "depth.png")}, {"image": str(self.d / "pose.png"), "type": "openpose", "strength": 0.5}]
        wf, _ = workflow.build(BASE | {"control": control})
        self.assertEqual(wf["55"]["inputs"]["positive"], ["52", 0])
        self.assertEqual(wf["54"]["inputs"]["control_net_name"], "$controlnet_openpose")
        for n in wf.values():
            if n["class_type"] in ("KSampler", "FaceDetailer"):
                self.assertEqual((n["inputs"]["positive"], n["inputs"]["negative"]), (["55", 0], ["55", 1]))

    def test_post_upscales_then_cuts_out(self):
        wf, inputs = workflow.build(BASE | {"workflow": "post", "image": str(self.d / "src.png"), "upscale": 2, "rembg": True})
        self.assertEqual(wf["9"]["inputs"]["images"], ["73", 0])
        self.assertEqual(wf["71"]["inputs"]["image"], ["62", 0])
        self.assertEqual(wf["62"]["inputs"]["scale_by"], 0.5)
        self.assertEqual(list(inputs), ["src.png"])

    def test_ph3_edit_takes_instruction_and_extra_pictures(self):
        job = BASE | {"workflow": "ph3_edit", "prompt": "Put the hat from <Picture 2> on her.", "image": str(self.d / "src.png"),
                      "images": [str(self.d / "pose.png")]}
        wf, inputs = workflow.build(job)
        c = wf["30"]["inputs"]
        self.assertEqual((c["prompt"], c["images.image_2"]), (job["prompt"], ["82", 0]))
        self.assertEqual(wf["33"]["inputs"]["noise_seed"], 5)
        self.assertEqual(sorted(m["key"] for m in models.resolve(wf, models.catalog())), ["ph3_model", "ph3_text_encoder", "ph3_vae"])
        self.assertEqual(sorted(inputs), ["pose.png", "src.png"])

    def test_resolve_names_models_and_reports_them(self):
        cat = models.catalog([{"key": "checkpoint", "folder": "checkpoints", "repo": "me/other", "file": "other.safetensors"}])
        wf, _ = workflow.build(BASE, cat)
        used = models.resolve(wf, cat)
        self.assertEqual(wf[workflow.CKPT]["inputs"]["ckpt_name"], "other.safetensors")
        self.assertEqual(wf["15"]["inputs"]["model_name"], "bbox/face_yolov8m.pt")
        self.assertEqual(sorted(m["key"] for m in used), ["checkpoint", "detector_face", "detector_hand"])

    def test_catalog_rejects_url_without_sha256(self):
        with self.assertRaises(SystemExit):
            models.catalog([{"key": "x", "folder": "loras", "url": "https://e.x/a", "file": "a"}])


class ExamplesTest(unittest.TestCase):
    def test_sample_config_and_presets_load(self):
        from artgen import presets, project

        root = Path(__file__).parent.parent / "examples"
        p = project.load(root / "artgen.toml")
        self.assertEqual(models.catalog(p.models)["checkpoint"]["file"], "Illustrious-XL-v2.0.safetensors")
        p = project.Project(**{**p.__dict__, "prompts": root / "prompts"})
        self.assertEqual(len(presets.load(p, "mia/stance")), 2)
        self.assertEqual(presets.load(p, "mia/stance_underlay")[0]["control"][1]["type"], "openpose")


if __name__ == "__main__":
    unittest.main()
