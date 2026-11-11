# 撮影指示 JSON（最小の形）

一枚の絵につき一つ。`packages/<作品>/art/shots/<id>.json` に置き、`artgen/underlay.py` が読む。

```json
{
  "id": "seres_stance",
  "note": "セレスが剣を構えて立つ。少しあおりの全身",
  "size": [832, 1216],
  "camera": { "shot": "full", "height": 0.5, "pitch": 8, "yaw": 0, "lens": 85 },
  "figures": [
    { "name": "セレス", "pose": "sword_guard", "position": [0, 0], "facing": -20, "height": 1.55, "hold": "sword" }
  ]
}
```

| キー | 意味 |
| --- | --- |
| `id` | 出力のファイル名の頭（`<id>_depth.png`、`<id>_openpose.png`） |
| `note` | 場面の一行。読むのは人と Claude だけ |
| `size` | 幅と高さ（px）。縦長は 832x1216、横長は 1216x832 |
| `camera.shot` | 寄り引き。`full` 全身／`knee` 膝上／`waist` 腰上／`bust` 胸上／`face` 顔。主役（`figures` の最初）がこの範囲で縦に収まるよう距離を決める |
| `camera.height` | カメラの床からの高さ（m）。目の高さは身長の 9 割ほど |
| `camera.pitch` | 上下の角度（度）。正はあおり、負は俯瞰 |
| `camera.yaw` | 主役の周りの方位（度）。0 は主役の正面側（-Y）。正で主役の左側へ回る |
| `camera.lens` | 焦点距離（mm、36mm 判の長辺）。既定 50。手前に伸びる物があるときは 85 前後で誇張を抑える |
| `figures[].name` | 人物の名前（警告の表示に使う） |
| `figures[].pose` | `tools/artgen/poses/<pose>.json` |
| `figures[].adjust` | ポーズの関節の回転の上書き（任意。ポーズと同じ形） |
| `figures[].position` | 床の上の位置 [x, y]（m）。主役は [0, 0] |
| `figures[].facing` | 向き（度）。0 でカメラの方位 0 の側を向く。正で左へ回る |
| `figures[].height` | 身長（m）。既定 1.55。体は 6.5 頭身 |
| `figures[].hold` | 持ち物（任意）。今は `sword`（右手で握る。全長約 1m） |

- 横は主役の体の左右の端が画面の中央に来るように合わせる。持ち物は数えないので、はみ出すときは向きか `lens` で直す。
- 光源・視線・文字の余白は、生成（ComfyUI）の段で足す。下絵では使わない。
