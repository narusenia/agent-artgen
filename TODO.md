# artgen の作業予定

上から順に進める。終わったら [x] にして、日付を書く。

## 0. 環境

- [x] mise・uv でツールと依存を管理する（2026-11-11）
- [ ] Modal の認証（`mise run art:auth`）と疎通確認（`mise run art:check`）
- [ ] Modal の費用の上限を決める（ワークスペースの設定）

## 1. ComfyUI on Modal

- [ ] ComfyUI を Modal のイメージに載せ、API でワークフローを投げられるようにする（公式例は削除済み。削除前のコード: modal-labs/modal-examples@c7c0e3f の `06_gpu_and_ml/comfyui`）
- [ ] モデルの重みを Modal の Volume に置く
- [ ] 生成した画像を手元の `packages/<作品>/art/out/` に落とす

## 2. モデル選び

- [ ] 生成の候補（Illustrious / NoobAI 系、Krea 2、FLUX.2 klein）で、同じ人物を描き比べる。まずセレス
- [ ] 編集の候補（P-H3-Image、Qwen-Image-Edit-2511）で、表情の差し替えと部分修正を試す
- [ ] 採用したモデルを作品の `docs/visual.md` に書く

## 3. 下絵（Blender）

- [ ] Blender を Modal のイメージに載せ、画面なしで動かす
- [ ] デッサン人形（MPFB2 の体型を少し幼めに調整）
- [ ] 撮影指示の JSON からカメラとポーズを置き、深度と OpenPose の画像を書き出す
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
