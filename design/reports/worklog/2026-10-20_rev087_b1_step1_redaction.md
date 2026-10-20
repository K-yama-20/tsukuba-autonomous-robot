# 作業記録 2026-10-20 第53便: 案 B1 の段 1、記録の伏せ字（REV-087）

## 読んだもの

- コミット `3341602` ＋ 未コミットの REV-073〜086。status.md（第52便）、提案 `proposals/ntrip_gga_proposal.md` §5・§7、`gouda_core/gouda_core/device_watch.py`、`sensor_supervisor_node.py`（_start）。

## 1. 人の許可（原文、DEC-153）

- 「段 1（記録の伏せ字）の実装を許可する。」

## 2. 変更（実装）

- `gouda_core/gouda_core/device_watch.py`: `redact_command`（ntrip・ntrips・ntripc の URL は全体を、ほかの URL は `user:password@` を `<redacted>` に。大文字小文字を問わない）、`command_lines`（/proc/<pid>/cmdline を読み、伏せ字にしてから 200 文字に切る。読めなければ '?'）。
- `gouda_core/gouda_core/sensor_supervisor_node.py`: `_start` の device_in_use の記録の command line を `dw.command_lines(users)` に置き換えた。記録の形（pid → 文字列）とほかの振る舞いは同じ。
- 自律判断: ntrip の URL は caster・ポート・マウントポイントも伏せた（提案 §5.1 の秘密の範囲）。伏せ字の後に切る（切り方で秘密の一部が残らないように）。

## 3. 試験

- `gouda_core/test/test_redact_command.py`（新規、5 件。値はすべて架空）: ntrip の URL 全体、他の ntrip の形と大文字、他の URL の userinfo、普通の command は変えない、切る位置をずらしても秘密が出ない。
- Mac: `python3 -m pytest -q test`（gouda_core）184 件合格・1 件 skip。
- VM: 一時の写し（~/gouda_unit_tree、試験の後に削除。動いている Gouda と ~/gouda_ws には触れていない）で同じく 184 件合格・1 件 skip。
- `apply_revision.py REV-087`、`run_checks.py`（3341602 ＋ 作業ツリー）: 設計検査 違反 0・未判定 4（DR-15 合格）。移行の検査の違反は人の drawio と .DS_Store だけ。

## 4. 残るリスク

- 伏せ字は supervisor の device_in_use の記録だけに入れた。ほかに他のプロセスの command line を記録する場所はない（gouda_core を grep で確認）。
- VM の Gouda には入っていない（commit と VM の更新は人の判断）。

## 5. 次

- 段 2（gnss_rtk.yaml の書式と serial_1 の値の出どころ。PRM の追加は承認事項）の許可待ち。commit はしていない。
