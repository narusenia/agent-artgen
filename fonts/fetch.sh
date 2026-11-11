#!/bin/sh
# 設定画の文字用フォント（Noto Sans JP 2.004 / Noto Serif JP 2.003、SIL OFL 1.1）を取得する。
# 版はタグで固定。取得元: https://github.com/notofonts/noto-cjk
set -eu
cd "$(dirname "$0")"
base=https://raw.githubusercontent.com/notofonts/noto-cjk
for w in Regular Bold; do
  [ -f NotoSansJP-$w.otf ] || curl -fsSL -o NotoSansJP-$w.otf "$base/Sans2.004/Sans/SubsetOTF/JP/NotoSansJP-$w.otf"
  [ -f NotoSerifJP-$w.otf ] || curl -fsSL -o NotoSerifJP-$w.otf "$base/Serif2.003/Serif/SubsetOTF/JP/NotoSerifJP-$w.otf"
done
[ -f OFL.txt ] || curl -fsSL -o OFL.txt "$base/Sans2.004/LICENSE"
shasum -a 256 -c SHA256SUMS
