# 作業記録 2026-10-21 第94便: main への取り込み（PR #11・#10）

## 読んだもの

- コミット `cefa92b`（作業ブランチの最後）、origin/main、PR #6・#10・#11（gh）。

## 人の指示（原文）

「mainへのmergeを行え。既存のPRもうまく処理して」「PR #11 は自分で GitHub の画面から merge する。終わったら知らせるので、PR #10 の扱いと後の確認を続けて。」

## 経緯

- AI が PR #11（design/field-mapping-2026-10-14 → main、17 commit、main からの遅れ 0、衝突なし、走る CI なし）を作った。AI の merge の操作は Claude Code の権限の仕組みに止められたので、人が GitHub の画面から #11 と #10（README の更新手順）を merge した。
- PR #6（feature/pedestrian-signal-ubuntu、2026-09-25）は main より 80 commit 遅れ、README.md・scripts/gouda.sh（新しい実装では削除）・scripts/setup.sh で衝突する（git merge-tree で確認）。旧実装の上の機能で、今の設計では信号の認識は範囲外。扱い（閉じる／残す）は人の判断待ち。触っていない。

## 確認（事実）

- origin/main は `416a6d6`。作業ブランチの最後（`cefa92b`）を含み、作業ブランチとの差は README.md だけ（PR #10 の変更）。コードは同じなので、cefa92b での試験（gouda_core 223 合格、設計検査 違反 0・未判定 5）はそのまま当てはまる。main の上での試験の再実行：未実行。
- 手元の作業ブランチ design/field-mapping-2026-10-14 は main より 4 commit 遅れ（進んでいる commit はない）。

## 自律判断した変更

- なし。この作業コピーの fetch の設定（feat/architecture だけを取る）は変えず、ブランチを名前で指定して取った。

## 残るリスク・人の判断待ち

- PR #6 の扱い。
- 実車 PC・VM の update.sh は、次に実行したとき main（416a6d6）を取り込む。

## 次の作業

- 次のチャットへ引き継ぐ（第95便）。
