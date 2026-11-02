# 第182便 作業記録：PRM-135 を /config で変えられるように、影響を台帳に登録（REV-193、DEC-406、TRB-013）

- 日付：2026-11-02
- 読んだコミット：f61a71b（作業ツリーに別のチャットの未コミットの変更あり）
- 人の回答（原文、DEC-406）：「0.5秒でよいが、/configで変えられるようにせよ。また、これによる影響を台帳に記録せよ。トラブルシューティング台帳みたいなのがあったよね」

## 変更

- nav2_config.TUNABLES に map_odom_future_offset_s（PRM-135）。読むのは ND-07（configure のとき）で、Nav2 は使わない
- localization_core.with_map_odom_offset、global_localization_node、web/app.js の表示名、単体試験
- 正本 REV-193。台帳 design/troubleshooting/ledger.yaml に TRB-013

## 自律判断

- PRM-89 以上の保存値は使わず PRM の値に戻す（走れなくしないため、古い TF を残さないため）
- 別のタブを作らず既存の「Nav2」タブに足した

## 検査

- 単体試験（Mac）、設計検査は作業ツリーで実行。結果は status.md の第182便のとおり
- monitor の画面での表示の確認・VM・実車：未実行

## 分類・リスク

- 分類：設定。残るリスクは TRB-013。コミットはまだ
