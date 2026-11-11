"""撮影指示 JSON → ControlNet 用の下絵（深度 PNG と OpenPose PNG）。手元の CPU で動く。

    uv run --project tools/artgen python tools/artgen/artgen/underlay.py <shot.json> [-o 出力先]

撮影指示の形は tools/artgen/shots.schema.md、ポーズは tools/artgen/poses/。
座標: Blender の Z 上向き、単位 m。人形は向き 0 で -Y を向き、+X が人形の左。
"""

import argparse
import json
import math
import struct
import zlib
from pathlib import Path

import bpy  # bmesh・mathutils より先に読む
import bmesh
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Matrix, Vector

POSES = Path(__file__).resolve().parent.parent / "poses"
HEADS = 6.5  # 頭身

# (関節, 親, 親からの位置 [頭の高さ単位])。基本の姿勢は直立・腕は下ろす。
_RIGHT = [
    ("shoulder_r", "chest", (-0.62, 0, 0.6)),
    ("elbow_r", "shoulder_r", (0, 0, -1.25)),
    ("wrist_r", "elbow_r", (0, 0, -1.0)),
    ("hand_r", "wrist_r", (0, 0, -0.65)),
    ("hip_r", "pelvis", (-0.38, 0, -0.1)),
    ("knee_r", "hip_r", (0, 0, -1.55)),
    ("ankle_r", "knee_r", (0, 0, -1.45)),
    ("toe_r", "ankle_r", (0, -0.7, -0.22)),
]
JOINTS = [
    ("pelvis", None, (0, 0, 3.35)),
    ("spine", "pelvis", (0, 0, 0.35)),
    ("chest", "spine", (0, 0, 0.9)),
    ("neck", "chest", (0, 0, 0.65)),
    ("head", "neck", (0, 0, 0.3)),
    *_RIGHT,
    *[(n[:-1] + "l", p[:-1] + "l" if p.endswith("_r") else p, (-o[0], o[1], o[2])) for n, p, o in _RIGHT],
]
FACE = {"nose": (0, -0.5, 0.4), "eye_r": (-0.17, -0.42, 0.52), "eye_l": (0.17, -0.42, 0.52),
        "ear_r": (-0.44, 0, 0.45), "ear_l": (0.44, 0, 0.45)}
HEAD_CENTER = (0, -0.05, 0.45)

# OpenPose（COCO 18点）の並び・線・色。controlnet_aux の draw_bodypose と同じ。
COCO18 = ["nose", "neck", "shoulder_r", "elbow_r", "wrist_r", "shoulder_l", "elbow_l", "wrist_l",
          "hip_r", "knee_r", "ankle_r", "hip_l", "knee_l", "ankle_l", "eye_r", "eye_l", "ear_r", "ear_l"]
LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12),
         (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
COLORS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0),
          (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
          (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]

# 寄り引き → 画面の縦に収める範囲（身長に対する割合）
SHOTS = {"full": (-0.05, 1.05), "knee": (0.25, 1.04), "waist": (0.5, 1.04), "bust": (0.68, 1.03), "face": (0.8, 1.02)}


def solve(rotations, height, facing, position):
    """関節の回転（度、XYZ）→ 関節ごとの (位置, 向きの行列)。足の低い方を床に着ける。"""
    h = height / HEADS
    base = Euler((0, 0, math.radians(facing))).to_matrix()
    world = {}
    for name, parent, off in JOINTS:
        rot = Euler([math.radians(a) for a in rotations.get(name, (0, 0, 0))], "XYZ").to_matrix()
        pp, pm = (Vector((*position, 0)), base) if parent is None else world[parent]
        world[name] = (pp + pm @ (Vector(off) * h), pm @ rot)
    ground = min(min(world[f"ankle_{s}"][0].z - 0.25 * h, world[f"toe_{s}"][0].z - 0.03 * h) for s in "rl")
    return {n: (p - Vector((0, 0, ground)), m) for n, (p, m) in world.items()}, h


def keypoints(world, h):
    pts = {n: p for n, (p, _) in world.items()}
    hp, hm = world["head"]
    pts.update({n: hp + hm @ (Vector(v) * h) for n, v in FACE.items()})
    pts["head_center"] = hp + hm @ (Vector(HEAD_CENTER) * h)
    return pts


def build_doll(bm, world, h, hold):
    def ellipsoid(center, rot, radii):
        m = Matrix.Translation(center) @ rot.to_4x4() @ Matrix.Diagonal((*radii, 1))
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1, matrix=m)

    def capsule(a, b, r):
        d = b - a
        m = Matrix.Translation((a + b) / 2) @ Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r, radius2=r, depth=d.length, matrix=m)
        for p in (a, b):
            bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=r, matrix=Matrix.Translation(p))

    P = {n: p for n, (p, _) in world.items()}
    M = {n: m for n, (_, m) in world.items()}
    ellipsoid(P["pelvis"], M["pelvis"], (0.72 * h, 0.48 * h, 0.55 * h))
    ellipsoid(P["chest"] + M["chest"] @ Vector((0, 0, 0.1 * h)), M["chest"], (0.66 * h, 0.42 * h, 0.75 * h))
    capsule(P["spine"], P["chest"], 0.45 * h)
    capsule(P["neck"], P["head"], 0.2 * h)
    ellipsoid(P["head"] + M["head"] @ (Vector(HEAD_CENTER) * h), M["head"], (0.4 * h, 0.46 * h, 0.5 * h))
    for s in "rl":
        for a, b, r in (("shoulder", "elbow", 0.2), ("elbow", "wrist", 0.16), ("wrist", "hand", 0.12),
                        ("hip", "knee", 0.3), ("knee", "ankle", 0.22), ("ankle", "toe", 0.14)):
            capsule(P[f"{a}_{s}"], P[f"{b}_{s}"], r * h)
    if hold == "sword":  # 右手で握る。手を下ろしたとき刃が前を向く
        grip = P["wrist_r"] + M["wrist_r"] @ Vector((0, 0, -0.3 * h))
        d = M["wrist_r"] @ Vector((0, -1, 0))
        side = M["wrist_r"] @ Vector((1, 0, 0))
        capsule(grip - d * 0.15, grip + d * 0.05, 0.015)
        capsule(grip + d * 0.05 - side * 0.09, grip + d * 0.05 + side * 0.09, 0.012)
        capsule(grip + d * 0.05, grip + d * 0.85, 0.012)
        return [grip + d * 0.85, grip - d * 0.15]
    return []


def place_camera(scene, cam, spec, size, target, height):
    """カメラの高さと仰角を守ったまま、寄り引きの範囲が縦に収まる距離を探し、レンズのシフトで上下を合わせる。"""
    w, hgt = size
    lens = spec.get("lens", 50)
    cam.data.lens, cam.data.sensor_width, cam.data.sensor_fit = lens, 36, "AUTO"
    tan_v = 18 / lens * hgt / max(w, hgt)  # 縦の半画角の tan
    pitch, zc = math.radians(spec.get("pitch", 0)), spec["height"]
    z0, z1 = (f * height for f in SHOTS[spec.get("shot", "full")])

    def y(z, d):  # 前方の距離 d、高さ z の点の画面上の縦位置（tan 単位）
        u = z - zc
        return (u * math.cos(pitch) - d * math.sin(pitch)) / (d * math.cos(pitch) + u * math.sin(pitch))

    lo, hi = 0.3, 200.0
    for _ in range(60):  # 距離が遠いほど範囲は小さく写る
        d = (lo + hi) / 2
        lo, hi = (d, hi) if y(z1, d) - y(z0, d) > 2 * tan_v else (lo, d)
    yaw = math.radians(spec.get("yaw", 0))
    cam.location = Vector((*target, 0)) + Euler((0, 0, yaw)).to_matrix() @ Vector((0, -d, 0)) + Vector((0, 0, zc))
    cam.rotation_euler = (math.pi / 2 + pitch, 0, yaw)
    cam.data.shift_y = (y(z0, d) + y(z1, d)) / 2 * lens / 36
    scene.camera = cam


def depth_material(near, far):
    mat = bpy.data.materials.new("depth")
    nt = mat.node_tree
    nt.nodes.clear()
    cd, mr = nt.nodes.new("ShaderNodeCameraData"), nt.nodes.new("ShaderNodeMapRange")
    em, out = nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = near, far
    mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1.0, 0.0  # 近いほど白
    nt.links.new(cd.outputs["View Z Depth"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def write_png(path, rgb):
    h, w, _ = rgb.shape
    raw = b"".join(b"\0" + rgb[i].tobytes() for i in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def draw_openpose(people, w, h, stick=4, radius=4):
    """people: 人ごとに 18 点の (x, y) か None。controlnet_aux と同じく線は色の 6 割、点は元の色。"""
    canvas = np.zeros((h, w, 3), np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    for pts in people:
        for (a, b), color in zip(LIMBS, COLORS):
            if pts[a] is None or pts[b] is None:
                continue
            (xa, ya), (xb, yb) = pts[a], pts[b]
            cx, cy, half = (xa + xb) / 2, (ya + yb) / 2, max(math.dist(pts[a], pts[b]) / 2, 1)
            ux, uy = (xb - xa) / (2 * half), (yb - ya) / (2 * half)
            u, v = (xx - cx) * ux + (yy - cy) * uy, -(xx - cx) * uy + (yy - cy) * ux
            canvas[(u / half) ** 2 + (v / stick) ** 2 <= 1] = [int(c * 0.6) for c in color]
        for p, color in zip(pts, COLORS):
            if p is not None:
                canvas[(xx - int(p[0])) ** 2 + (yy - int(p[1])) ** 2 <= radius**2] = color
    return canvas


def render(shot, out_dir):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    w, h = shot["size"]
    figs = []
    bm = bmesh.new()
    extra = []
    for fig in shot["figures"]:
        pose = json.loads((POSES / f"{fig['pose']}.json").read_text())
        rot = {**pose["joints"], **fig.get("adjust", {})}
        world, hu = solve(rot, fig.get("height", 1.55), fig.get("facing", 0), fig.get("position", (0, 0)))
        extra += build_doll(bm, world, hu, fig.get("hold"))
        figs.append((fig, keypoints(world, hu)))
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=30)  # 床
    mesh = bpy.data.meshes.new("doll")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("doll", mesh)
    scene.collection.objects.link(obj)

    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    main = shot["figures"][0]
    place_camera(scene, cam, shot["camera"], (w, h), main.get("position", (0, 0)), main.get("height", 1.55))
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = w, h, 100
    bpy.context.view_layer.update()  # matrix_world を置いた位置に合わせる
    # 横は主役の人形の左右の端が真ん中に来るようにずらす（小道具は数えない）
    xs = [world_to_camera_view(scene, cam, p).x for p in figs[0][1].values()]
    cam.data.shift_x = ((min(xs) + max(xs)) / 2 - 0.5) * w / max(w, h)

    inv = cam.matrix_world.inverted()
    zs = [-(inv @ p).z for _, pts in figs for p in pts.values()] + [-(inv @ p).z for p in extra]
    obj.data.materials.append(depth_material(min(zs) - 0.3, max(zs) + 2.0))
    scene.render.engine = "CYCLES"
    scene.cycles.device, scene.cycles.samples, scene.cycles.use_denoising = "CPU", 8, False
    scene.cycles.max_bounces = 0
    scene.view_settings.view_transform = "Raw"  # 深度の値を色の変換なしで書く
    scene.render.image_settings.file_format, scene.render.image_settings.color_mode = "PNG", "BW"

    out_dir.mkdir(parents=True, exist_ok=True)
    depth = out_dir / f"{shot['id']}_depth.png"
    scene.render.filepath = str(depth)
    bpy.ops.render.render(write_still=True)

    people = []
    for fig, pts in figs:
        cam_pos = cam.matrix_world.translation
        row = []
        for name in COCO18:
            p = pts[name]
            if name in FACE:  # 頭の陰に入った顔の点は OpenPose と同じく出さない
                out, view = (p - pts["head_center"]).normalized(), (cam_pos - p).normalized()
                if out.dot(view) < -0.3:
                    row.append(None)
                    continue
            x, y, _ = world_to_camera_view(scene, cam, p)
            if not (0 <= x <= 1 and 0 <= y <= 1):
                print(f"warning: {fig.get('name', '?')} の {name} が画面の外")
            row.append((x * w, (1 - y) * h))
        people.append(row)
    pose_png = out_dir / f"{shot['id']}_openpose.png"
    write_png(pose_png, draw_openpose(people, w, h))
    return depth, pose_png


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("shot", type=Path)
    ap.add_argument("-o", "--out", type=Path, help="既定: <作品>/art/out/underlay/")
    a = ap.parse_args()
    shot = json.loads(a.shot.read_text())
    out = a.out or a.shot.resolve().parent.parent / "out" / "underlay"
    for p in render(shot, out):
        print(p)


if __name__ == "__main__":
    main()
