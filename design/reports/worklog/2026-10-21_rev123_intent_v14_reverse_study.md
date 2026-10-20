# 作業記録 2026-10-21 第91便: intent.md 第14版、PRM-01〜03、後退の上限の検討（REV-123、DEC-195〜198）

## 読んだもの

- コミット `34bc9e0` ＋ 第90便の作業ツリー（REV-122 を適用、未 commit）。
- `design/intent.md`（人の編集の後）と写し `design/baselines/intent_history/intent_v13_c4d1a69aee5f.md` の差分。REV-114・116（intent の版の記録の手本）。
- `gouda_core/gouda_core/nav2_config.py`、`motion_core.py`、`gouda_core/launch/gouda_nav2.launch.py`、firmware の mapVoltage、上流の雛形（nav2_params.yaml、navigate_through_poses_w_replanning_and_recovery.xml）、第90便に scratchpad で組んだ nav2_params.yaml。

## 人の発言（原文）

- 「後退の速度上限が前進速度上限よりも遅いのは、車椅子側の内部制御のせいである。また、100%倒したときに後退速度上限に当たってしまうと考えよ。つまり、倒し量-速度のグラフの傾きが小さくなったと考えよ。」「intent.mdは更新した」
- 選択式の質問への回答：
  - 全高 120 mm について → 「1200mmの誤りであった。intent.mdは修正した」
  - Nav2 の後退の上限について → 「それぞれの実装のメリデメを詳細に検討せよ。特に、回転と後退が組み合わさった機動をする際の境界条件について考えよ」
  - 人は乗らないについて → 「intent.mdに、人が乗らない旨を書き足した。」

## 経緯

- 最初の差分では、100 行の全高が 120 mm（SHA-256 6af20a12…）だった。同じ行の後輪径 330 mm と矛盾するので、人に確かめた。人が 1200 mm に直し、108 行を書き足した（SHA-256 9bf08d3e…、108 行）。記録したのは直した後の版だけ。

## 変更

- 写し `design/baselines/intent_history/intent_v14_9bf08d3ebe24.md`（intent.md を一字も変えずに写した）。
- REV-123:
  - AR-014（100 行の置換＋108 行の追記、allow_non_append）、RQ-I087（100 行。RQ-I074 を置き換え）、RQ-I088（108 行）、C-029 を記録した。
  - DEC-196（第14版の確認、原文）、DEC-197（後退の関係の人の説明、原文）を recorded で、DEC-198（Nav2 の後退の上限）を pending で登録した。DEC-195 を answered にした。
  - PRM-01 0.80 m、PRM-02 0.60 m、PRM-03 1.2 m にした（出典を SRC-I100-V14 に付け替え）。PRM-69・PRM-36 に解釈を追記した。PRM-66・68 の要求に RQ-I088 を対応付けた。
- 報告 `design/reports/reverse_limit_study_2026-10-21.md`（案 A・B・C の利点と欠点、回転と後退の組み合わせの境界の条件、計算の例、推奨）。
- 第90便の作業記録に訂正を追記した（後退の指令と実際の速度の注は言い過ぎ）。

## 自律判断した変更（理由）

- PRM-01〜03 の出典を、第14版の 100 行（SRC-I100-V14）に付け替えた。最初の試し適用で、DR-11 が「PRM-03 の値 1.2 が出典原文に見当たらない」を出した。調べると、3 つとも古い版の 99 行目（SRC-I099）を指していた。0.8・0.6 が通ったのは、古い文の中に同じ数字が偶然あったため。
- RQ-I088（人は乗らない）を PRM-66・68（速度・加速度）に対応付けた。人の D10 の発言「全体的に安全思想に偏りすぎ。また、電動車椅子に人は絶対に乗らないし…」が、これらの値の根拠になっているため。
- 検討の報告では、EMC-270 の倒し量と速度の関係を、軸ごとに直線と仮定して計算した（報告に明記）。

## 検査・試験（コミット 34bc9e0 ＋ 作業ツリー）

- `apply_revision.py REV-123 --dry-run --check`：1 回目は新しい違反 1（DR-11、PRM-03 の出典。上の理由）。出典を直した 2 回目は、新しい違反 0・新しい未判定 0。そのあと本適用し、再生成した。
- `design/.venv/bin/python design/tools/run_checks.py`（REV-123 の後）：終了コード 1。設計検査は合格 12・違反 0・未判定 5（DR-11 30、DR-15 30）。入力の照合は一致 72・intent の新版 1・不一致 3（drawio、.DS_Store 2 つ。以前から）。検査器の試験は 83 件中 1 件不合格（以前から）。
- Mac `cd gouda_core && python3 -m pytest -q test`：220 passed、8 skipped、1 failed（test_nav2_config の test_vehicle_files_alone_do_not_build。第90便と同じ原因で、修正は許可待ち）。
- 報告の計算は、scratchpad の Python で行った（motion_controller の正規化と ESP32 の円の処理を写したもの）。実機・VM：未実行。

## 残るリスク

- 後退しながら回るときの EMC-270 の振る舞い（後退で旋回も遅くなるか、回る向きが反転するか、前後 0 で跳ねないか）は未確認。後退を速くする前に確かめる必要がある（報告 §4.4、VL-03 にする案）。
- Nav2 の上限は軸ごとで、倒し量の円（楕円の範囲）を知らない。回転と組み合わせると、指令より遅くなる。

## 更新した生成物

- design/generated/ の各ビュー、design/generated/params/*（ハッシュの行）、design/migration_review.md、design/intent_index.yaml、design/reports/model_diff_rev-123.md と検査の結果のファイル。

## 次に進められる作業・止まっている作業

- 人の回答待ち：DEC-198（案 A・B・C）、test_nav2_config の修正の許可、VL-03 を足すか、DEC-189・190。
- commit・push は人の指示を待つ（第90・91便は未 commit）。
