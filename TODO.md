# artgen の作業予定

上から順に進める。終わったら [x] にして、日付を書く。

## 0. 環境

- [x] mise・uv でツールと依存を管理する（2026-11-11）
- [x] Modal の認証（`mise run art:auth`）と疎通確認（`mise run art:check`。T4 を借りられた）（2026-11-11）
- [ ] Modal の費用の上限を決める（ワークスペースの設定）

## 1. ComfyUI on Modal

- [x] ComfyUI v0.3.71 を Modal のイメージに載せ、API でワークフローを投げられるようにする（T4。2026-11-11）
- [x] モデルの重みを Modal の Volume `artgen-models` に置く（2026-11-11）
- [x] 生成した画像を手元の `packages/<作品>/art/out/` に落とす（2026-11-11）
- [ ] `comfy.py` の名前を変える（ComfyUI の `comfy` パッケージを隠すので、今は起動時に PYTHONPATH を外して避けている）
- [ ] Modal の Image Builder の版を上げる（今は古い版で debian_slim が bullseye になるため、python:3.11-slim-bookworm を使っている）

## 2. モデル選び

- [ ] 生成の候補（Illustrious / NoobAI 系、Krea 2、FLUX.2 klein）で、同じ人物を描き比べる。まずセレス
- [ ] 編集の候補（P-H3-Image、Qwen-Image-Edit-2511）で、表情の差し替えと部分修正を試す
- [ ] 採用したモデルを作品の `docs/visual.md` に書く

- [ ] ControlNet の回で、同じ4枚を T4 と L4 で1回ずつ出し、1枚あたりの費用を比べて既定の GPU を決める（作者了承 2026-11-11）
- [ ] `comfy.py` に文章で直す指示（`edit <画像> "指示"`）を足す。P-H3-Image（L4）と Qwen-Image-Edit-2511 を同じ1枚で試し比べ、出来と費用で既定を決める（作者了承 2026-11-11）
- [ ] `comfy.py` に `--preset <人物>/<name>` を足し、`packages/<作品>/art/prompts/` の採用プロンプト（`_style.toml` と合わせて）で生成できるようにする

## 3. 下絵（Blender）

- [x] bpy 5.2 LTS を uv で固定し、手元の CPU で画面なしに動かす（2026-11-11）
- [ ] Blender を Modal の CPU 関数に載せる（`render()` をそのまま呼ぶ見込み）
- [ ] デッサン人形を MPFB2 に差し替える（今は基本図形の6.5頭身。関節の名前と撮影指示はそのまま使える）
- [x] 撮影指示の JSON からカメラとポーズを置き、深度と OpenPose の画像を書き出す（手元。2026-11-11）
- [ ] 持ち物（剣など）も画面の収まりに数える。複数人の場面を試す
- [ ] 深度の濃淡が弱ければ、測る範囲を縮める（ControlNet で効きを見てから）
- [ ] ポーズの棚: 既存の素材（Mixamo、CMU のモーションキャプチャ等）を取り込む。素材ごとの利用条件を確かめて `poses/README.md` に書く

## 4. 一周

- [ ] セレス一人で「撮影指示 → 下絵 → 生成 → 選別」を回す
- [ ] 撮影指示の JSON の形を固め、`README.md` に書く

## 5. 人物の一貫性

- [ ] 設定画（正面・横・後ろ、表情の差分、衣装と小物）を出し、作者が採用を選ぶ
- [ ] 採用した設定画でキャラの LoRA を学習する（Modal）
- [ ] 複数人の場面で、人物ごとの領域指定を試す

## 6. 逃げ道

- [ ] RunPod で同じワークフローを動かす
- [ ] Modal の上限に近づいたら切り替える仕組み
