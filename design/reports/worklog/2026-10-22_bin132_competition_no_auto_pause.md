# 作業記録 2026-10-22 第132便: 本番で自動で一時停止しない方針の承認事項（REV-160）

## 読んだもの

- コミット `31a6e1d`＋作業ツリー（第127〜131便の未コミットの変更あり）。
- `design/reports/status.md`（第131便）、`reports/handover_2026-10-21_2.md` §2〜5、`design/intent.md` 第14版（SHA-256 9bf08d3e…）、判断台帳（DEC-056・200・201・216・222・224・227・229・286・287）。
- コード：`gouda_core/gouda_core/mode_manager_node.py`（455-535 行）・`vehicle_core.py`、`firmware/gouda_esp32_v4/include/gouda_v4/control.hpp`（170-190 行）。
- 洗い出しには読むだけのサブエージェントを使った（mode_core・motion_core・autonomy_core・nav2_config・sensor_supervisor・生成した params）。そのうち次の 3 点は、自分でソースを読んで確かめた。
  - 推定不能で即一時停止すること
  - motion_hold の解放の条件
  - ESP32 の再許可の条件
- Nav2 の上流の既定値（RPP の衝突検出など）は、リポジトリでは確かめていない（推測を含む）。

## 1. 人の発言（原文、DEC-304 に記録）

1. 「つくばチャレンジでは、一時停止モードに入ったり、同じ場所で3分以上滞留（1mくらいの前進が出来ない場合）してしまうと、走行失敗と判定されてしまう。…（略、全文は DEC-304）…現在の状況および、君の方針をまとめよ。」
2. 「方針の項目を承認事項として判断台帳に登録し、intent.md の修正案も作って。実装はまだしない。」

## 2. 行ったこと

- 番号は reserve_ids.py で予約した（REV-160、DEC-304〜314、第132便）。
- 提案 `design/proposals/competition_no_auto_pause_2026-10-22.md` を書いた（洗い出しと方針）。
- intent.md の編集依頼 `design/proposals/intent_edit_request_competition_2026-10-22.md` を書いた（§1〜3 必須、§4・5 任意）。
- REV-160 を適用した。
  - DEC-304 は人の発言の記録（recorded）。
  - DEC-305〜313 は承認事項（pending）、DEC-314 は実測（pending）。
  - entities・modifications はない。
- 自律判断：なし（記録と提案だけ）。
- コード・設定・intent.md は変えていない。

## 3. 衝突（CLAUDE.md 1.1：チャットの指示と確定済みの判断の矛盾）

人の発言は、次の確定済みのものと衝突する。黙って適用せず、DEC-305 に登録した。

- DEC-200（answered）：推定不能・Nav2 の失敗で一時停止する。
- intent.md 第14版：15 行（RQ-I012）、93 行（RQ-I064）、38 行（RQ-I027）。

## 4. 作業中に観測した人の編集（記録はまだ）

- 22:19、intent.md が SHA-256 `07668b549ea1b5473aa5671704706e94736cc398051a0d1f2ca5b7496f120332` に変わった。
- HEAD との差は 15 行だけ。「（走行失敗の判定を避け、完走を確実なものとする為、一時停止モードに入らずとも良い。）」が足された。
- 人が編集を終えたかを確かめていないので、authority_revision（AR-015）にはまだ記録していない。
- このため、移行の検査に違反が 2 件出る（下の §5）。
- 編集依頼の §2 に、この編集との関係を書き足した。

## 5. 検査

コマンド：`apply_revision.py REV-160 --dry-run --check` → `apply_revision.py REV-160` → `run_checks.py`。対象は 31a6e1d＋作業ツリー。

- dry-run：新しい違反 0、新しい未判定 0。
- run_checks の終了コードは 1。
  - 設計検査：合格 12・違反 0・未判定 5（DR-04 5、DR-05 2、DR-10 3、DR-11 30、DR-15 35）。要約行は「違反0件・未判定5件」。
  - 入力の完全性：違反 3。既存の drawio と .DS_Store 2 つ。
  - 移行の検査（migration_validator）：違反 2。どちらも、上の §4 の intent.md の人の編集をまだ記録していないため。
    - intent revision chain reaches current file
    - intent reproduced from archived copy plus recorded lines AR-014
  - 検査器の試験：83 件中 1 件不合格（test_real_model、同じ原因）。
- gouda_core の単体試験：未実行（コードの変更なし）。

## 6. 原因の分類

不具合の修正はしていない。

## 7. 残るリスク

- 失格の条件は人の発言による。大会の規則の原文は読んでいない（原本未照合）。
- 方針を採ると、異常のときに車体が止まらない。止める手段は、随行者のゲームパッドと人の一時停止ボタンになる。推定がずれたまま走りうる。

## 8. 更新した生成物

- `design/model.yaml`（REV-160 の決定 11 件）。
- 検査の報告（`run_checks.py` による）。model_diff は作っていない（決定の追加だけのため）。
- status.md。

## 9. 次

- 人の判断：DEC-305（方針と intent.md の修正案）、DEC-306〜313、実測 DEC-314。
- 人の確認：intent.md の編集を終えたか。終えていれば AR-015 として記録する。
- 承認を待たずに進められること：DEC-287 の直しの承認（既存の pending）。
- 止まっていること：DEC-306〜311 の実装（DEC-305 待ち）。
- commit はしていない。
