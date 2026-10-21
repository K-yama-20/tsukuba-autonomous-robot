# 第100便: DEC-107 への人の回答（転記）と案 C の実装の指示の記録（REV-130、DEC-210〜215）

## 読んだもの

- コミット：`4b44f75`（design/records-2026-10-21）の上の作業ツリー（REV-126〜129 は未 commit で適用済み）。PR #12 は 763929a で main に merge 済み（gh で確認）。
- 分岐セッション「Side chat」（local_11a193cd…）からのセッション間のメッセージ。提案 `proposals/swept_corridor_map_2026-10-21.md`（分岐セッションで作成。全文を読んだ）。model.yaml の DEC-107。

## 人の発言（原文、転記）

1.「DEC-107 は、まず案 C（地面推定なしで通った帯だけを空きにする 2D 地図）を試し、案 A は DEC-105 の後に再検討する。案 C の設計を提案として出して。」
2.「メインのチャットに実装を指示せよ」

出所：分岐セッションからのセッション間のメッセージ。人がこのメインのチャットに貼ったものではない。台帳には転記として記録した。実装の許可（DEC-106）としては、このチャットで人に確かめてから使う。

## 記録したこと（REV-130）

- DEC-107（answered）：案 A（地面の推定の修正）は今は採らず DEC-105 の後に再検討、まず案 C を試す。
- DEC-210（answered、転記）：案 C の設計（提案 §3〜§7）で実装を始める（提案 §9 の 1）。
- DEC-211〜215（pending）：提案 §9 の 2〜6（走行用の 2D 地図を帯の地図に替える、/config の写しのない古い原図の扱い、設定 A・B の値、NavFn の allow_unknown を false に、帯の外の waypoint の保存）。
- 正本の構成とコードは変えていない。

## 自律判断した変更とその理由

- なし（記録だけ）。

## 実行した検査

- `design/.venv/bin/python design/tools/apply_revision.py REV-130 --dry-run --check`：新しい違反 0、新しい未判定 0。
- 本適用の後、`render_views.py`・`generate_params.py`・`render_migration_review.py`、`run_checks.py`（終了コード 1）：要約行 `{"合格": 12, "違反": 0, "未判定": 5} 違反0件・未判定5件`。入力の照合の不一致は前と同じ 3 件。
- 単体試験：未実行（コードは変えていない）。

## 残るリスク

- 案 C は map_convert.py・map_creator_node.py・test_mapping_core.py を触る。ND-07 の段 2（20 m 格子）と同じファイル（第99便は未 commit）。
- 提案 §5 の未確認：obstacle_layer の clearing が static_layer の「不明」を「空き」に上書きするか（AI の推測）。

## 次の作業

- 人の確認：転記がご本人の回答か、案 C の実装に着手してよいか。DEC-211〜215 の回答。
- commit：未実行（第94〜99便の分も含めて）。
