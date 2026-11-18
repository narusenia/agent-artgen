"""Weights kept on the Modal volume: (repo, file, subdirectory of the volume, revision)."""

CHECKPOINT = ("Laxhar/noobai-XL-1.1", "NoobAI-XL-v1.1.safetensors", "", None)
# Face and hand detectors for the FaceDetailer pass in sdxl_hires_detailer.json.
DETECTORS = [("Bingsu/adetailer", f, "ultralytics/bbox", None) for f in ("face_yolov8m.pt", "hand_yolov8s.pt")]
# IP-Adapter: the SDXL PLUS model and the ViT-H image encoder it pairs with.
IPA_PLUS = ("h94/IP-Adapter", "sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors", "ipadapter", None)
CLIP_VISION = ("h94/IP-Adapter", "models/image_encoder/model.safetensors", "clip_vision", None)
# IP-Adapter trained on NoobAI (kataragi, runs with ViT-H), pinned to a commit.
IPA_NOOB = ("kataragi/Noob_ipadapter", "ip_adapter_Noobtest_800000.bin", "ipadapter/noob", "8e2c039824185add88e917e7dfd350e8188f42b3")

ALL = [CHECKPOINT, *DETECTORS, IPA_PLUS, CLIP_VISION, IPA_NOOB]

# Names as ComfyUI sees them, chosen by a job's ref_model.
IPA_MODELS = {"plus": IPA_PLUS[1], "noob": f"noob/{IPA_NOOB[1]}"}
CLIP_VISION_NAME = f"ipa/{CLIP_VISION[1]}"
