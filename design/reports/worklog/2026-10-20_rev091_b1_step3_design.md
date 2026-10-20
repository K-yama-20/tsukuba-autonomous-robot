# 作業記録 2026-10-20 第58便: 案 B1 の段 3 の設計の案（REV-091）

## 読んだもの

- コミット `3341602` ＋ 未コミットの REV-073〜090（REV-080 などは別のセッション）。status.md（第57便、別のセッション）、`gouda_core/gouda_core/sensor_supervisor_node.py`（Driver、起動の時の記録、_evaluate、_start、_stop）、VM の MRTKLIB の `decodetcppath`（src/stream/mrtk_stream.c）と `apps/str2str/str2str.c`（読むだけ）。

## 1. 人の指示（原文）

- 「段 3（中継の起動）の設計を示せ。実装はまだしない。」

## 2. 確かめたこと

- supervisor の起動の時の記録（settings「sensor supervisor configured」）は全ドライバの command をそのまま書く。中継を同じ形で足すと、引数の認証が記録・/rosout・rosbag に出る。
- ドライバの標準出力・標準エラーは ros2 launch のログに入る。str2str の状態の msg（caster:port/マウントポイント）もそのままではログに入る。
- MRTKLIB の URL の分け方: 最後の `@`、最初の `:`、`/` の後のマウントポイントとその後の `:`、str2str は最後の `#` を書式の区切りに使う。MRTKLIB は user・password を URL のデコードをする（apt の rtklib は未確認）。str2str の既定: timeout 10000 ms、再接続 10000 ms、表示 5000 ms。

## 3. 行ったこと

- 提案 §9: 中継の置き方、秘密の扱い（記録用と起動用の command を分ける、全 command の伏せ字、標準エラーから状態だけ）、終了と作り直し（案 A: 作り直さない）、gnss_config の検証の追加、試験、承認事項。
- REV-091: DEC-156（pending）。番号は reserve_ids.py で予約（REV-091、DEC-156、第58便）。第57便は別のセッションが同じ道具で予約していた。REV-091 の先頭の注釈の行は「第57便」と書いたまま適用した（適用済みのファイルは直さない。正しくは第58便）。
- 実装はしていない。

## 4. 検査

- `apply_revision.py REV-091`、`run_checks.py`（3341602 ＋ 作業ツリー）: 設計検査 違反 0・未判定 4。移行の検査の違反は人の drawio と .DS_Store だけ。単体の試験: 未実行（コードの変更なし）。

## 5. 次

- DEC-156 の回答待ち。その後に段 3 の実装の許可を求める。commit はしていない。

## 追記（第59便、REV-092）

- 人の回答（原文、DEC-156）: 「DEC-156 を承認する。」
- REV-092 で DEC-156 を answered。中継の終了の扱いは案 A（同じ同一性では作り直さない）。番号は reserve_ids.py で予約（REV-092、第59便）。
- 検査: `apply_revision.py REV-092`、`run_checks.py`: 設計検査 違反 0・未判定 4。移行の検査の違反は人の drawio と .DS_Store だけ。
- 次: 段 3 の実装の許可待ち。commit はしていない。
