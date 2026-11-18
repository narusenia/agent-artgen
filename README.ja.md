# artgen

[English](README.md)

設定画と構図の参照を作る、コマンドラインの画像パイプライン。ComfyUI を [Modal](https://modal.com) の GPU で動かし、ポーズの下絵は手元の CPU で Blender を使って描く。特定の作品には依存しない。作品ごとの設定は `artgen.toml` に書く。

## 入れ方

Python 3.13 が要る（bpy 5.2 LTS が 3.13 用しかないため）。

mise を使う場合は、作品の `mise.toml` に次を書いて `mise install` する。

```toml
[tools]
"pipx:git+ssh://git@github.com/narusenia/artgen-cli.git" = { version = "latest", uvx_args = "--python 3.13" }
```

uv で直接入れる場合:

```bash
uv tool install --python 3.13 git+ssh://git@github.com/narusenia/artgen-cli.git
```

マシンごとに 1 回だけ:

```bash
artgen auth    # Modal の認証（対話）
artgen check   # T4 を数秒借りて、使えるか確かめる
```

## コマンド

| コマンド | すること |
| --- | --- |
| `artgen gen` | Modal の ComfyUI で生成する。`--backend local` で手元の ComfyUI でも生成できる。`--preset <人物>/<名前>`、`--prompt`、まとめて流すなら `--jobs <file.json>`。`--dry-run` で展開したジョブを表示する |
| `artgen edit <画像> "<指示>"` | P-H3-Image（`ph3_edit`）で、指示どおりに画像を直す。`--images` で、指示の中で `<Picture 2>` … と呼ぶ画像を足す。初回に約 20GB の重みを取得する。T4 で `--megapixels 1` なら約 3 分半 |
| `artgen wait` | 裏で動かした `gen` が終わるまで待ち、出力先のフォルダを表示する。エージェント向け |
| `artgen stop` | Modal のアカウントで動いている artgen の App をすべて止める |
| `artgen underlay <shot.json>` | 撮影指示から深度と OpenPose の下絵を描く（手元の CPU） |
| `artgen sheet <sheet.toml>` | 設定画に見出し・注記・項目表・配色見本を重ねる |
| `artgen show <path>...` | 画像やフォルダを OS のビューアで開く |
| `artgen auth` / `artgen check` | Modal の認証 / GPU の確認 |
| `artgen skill [--install DIR]` | エージェント向けの Skill を表示する。`DIR/artgen/SKILL.md`（例: `.claude/skills`）に書き出すこともできる |

オプションは `artgen <コマンド> --help` で見られる。

## 作品の設定

artgen は今のフォルダから上へたどって `artgen.toml` を探す。パスはこのファイルからの相対で書く。どのキーも省ける。

```toml
out = "art/out"            # 生成した画像
prompts = "art/prompts"    # 採用したプロンプト（_style.toml と <人物>.toml）
poses = "art/poses"        # 追加のポーズの棚。同梱の棚より先に探す

[comfy]
backend = "modal"          # "modal" か "local"（自分で起動した ComfyUI）
url = "http://127.0.0.1:8188"  # 手元の ComfyUI

[modal]
gpu = "T4"                 # 既定の GPU
gpus = ["T4", "L4"]        # --gpu やプリセットの gpu で使ってよい GPU
max_apps = 1               # Modal のアカウントで同時に動かしてよい artgen の App の数
timeout = 900              # ComfyUI のコンテナ 1 つの制限時間（秒）
scaledown = 30             # 使っていないコンテナを残す時間（秒）

[gen]                      # artgen gen の既定値。コマンドで指定した値が優先
workflow = "sdxl_txt2img"  # か sdxl_hires_detailer
width = 832
height = 1216
n = 2
negative = ""
```

`max_apps` は、どのマシン・どの作品から起動した App も数える。上限に達していると、`gen` と `check` は起動しない。`artgen wait` で待つか、`artgen stop` で止める。

### 手元の ComfyUI

`backend = "local"`（または `--backend local`）にすると、`gen` は `url` の ComfyUI にワークフローを送り、Modal の App は使わない。その ComfyUI には、Modal のイメージ（`src/artgen/remote.py`）と同じ custom node と、使うモデルを下のモデル一覧の名前で置いておく。

### モデル

同梱のモデル一覧は [src/artgen/models.toml](src/artgen/models.toml)。ワークフローはモデルをキー（`$checkpoint`）で参照するので、作品の `artgen.toml` に同じキーの `[[model]]` を書けば差し替えられる。新しいキーも足せる。

```toml
[[model]]
key = "checkpoint"                       # 同梱の checkpoint を差し替える
folder = "checkpoints"                   # ComfyUI のモデルフォルダの種類
repo = "OnomaAIResearch/Illustrious-XL-v2.0"
file = "Illustrious-XL-v2.0.safetensors"
# rev = "<commit>"                       # 版の固定。url = "https://…" と sha256 = "…" でも書ける
```

Modal では、実行ごとにワークフローが使うモデルだけを、`artgen-models` の volume の `/models/<folder>/<file>` に一度だけ取得する。

## ジョブのキー

ジョブ（`--jobs`、プリセット、コマンド）には、プロンプト・大きさ・シードのほかに次のキーを書ける。

| キー | すること |
| --- | --- |
| `ref`、`ref_*` | IP-Adapter の参照画像 |
| `image`、`denoise` | img2img。`image` を `denoise`（既定 0.55）で描き直す |
| `mask` | `image` の中を塗り直す（inpaint）。白い所を描き直す（`denoise` の既定は 0.9） |
| `control` | 下絵。`[{image, type = "depth" \| "openpose", strength, start_at, end_at}]` |
| `upscale` | アップスケーラーで、この倍率に大きくする |
| `rembg` | 背景を抜いて透過 PNG にする |
| `style` | `<prompts>/styles/<名前>.toml`（positive、negative、loras）の画風。プロンプトの前に付く |
| `loras` | `[{model, strength}]`。`folder = "loras"` の `[[model]]` で宣言した LoRA。`trigger` の語がプロンプトに入る |
| `images`、`megapixels` | `ph3_edit` だけ。追加の画像と、直す大きさ（既定 4 メガピクセル） |

`post` ワークフローは `image` を読んで `upscale` と `rembg` だけをかける。例: `artgen gen --workflow post --image a.png --upscale 2 --rembg`

## サンプル

[examples/](examples/) に、`artgen.toml`、`prompts/_style.toml`、`prompts/<人物>.toml`、ジョブファイル、撮影指示、設定画のサンプルを置いた。

## プリセット

採用したプロンプトは、もう一度生成できるように保存しておく。`<prompts>/_style.toml` に全員に共通する部分を、`<prompts>/<人物>.toml` に採用した絵ごとの `[[preset]]` を書く。

```toml
[[preset]]
name = "stance"
uses = ["uniform.female"]      # _style.toml から追加で使う表。style の後ろにつなぐ
positive = "1girl, standing"   # 人物の部分だけ
negative = "..."
seeds = [1234]
width = 832
height = 1216
workflow = "sdxl_hires_detailer"
ref = "art/refs/uniform.png"   # IP-Adapter の参照画像（任意）
note = "何を採用したか、なぜか"
```

`artgen gen --preset <人物>/stance` は seed ごとに 1 ジョブ流す。0 以外の `--seed` を渡すと seeds の代わりにそれを使う。

## 形式

- 撮影指示（下絵）: [docs/shots.md](docs/shots.md)
- ポーズ: [docs/poses.md](docs/poses.md)
- 設定画の型紙: [docs/sheets.md](docs/sheets.md)

## 費用

Modal は秒単位の課金。既定値は安く済む設定にしてある。T4 を使い、制限時間は短く、使っていないコンテナは 30 秒で止まる。重みは Volume `artgen-models` に置き、ダウンロードは 1 回だけ。月の上限は Modal のワークスペースの設定で掛けておく。

## 開発

```bash
mise run setup   # uv sync
mise run test    # 単体テスト
uv run artgen …  # チェックアウトから動かす
```

予定は [TODO.md](TODO.md)、このリポジトリで作業するエージェント向けの決まりは [AGENTS.md](AGENTS.md)。
