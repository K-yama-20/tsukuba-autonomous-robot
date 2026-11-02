# 第180便 作業記録：map→odom を少し先の時刻で出す（REV-191、DEC-403、PRM-135）

- 日付：2026-11-02
- 読んだコミット：f61a71b（作業ツリーに別のチャットの未コミットの変更あり。MPPI ほか。触れていない）
- 人の回答（原文、DEC-403）：「OSS方式で実装」

## 1. 変更

- `localization_core.py`：設定 map_odom_future_offset_s、`future_stamp`。PRM-89 以上の値は起動で断る
- `global_localization_node.py`：map→odom の stamp を odometry の時刻＋PRM-135 に。値の計算（DEC-285）は同じ
- `test_localization_core.py`：stamp の計算と値の範囲の試験
- 正本：DEC-403、PRM-135、ND-07、IFD-18

## 2. 自律判断と理由

- 値 0.5 s は AI の暫定（slam_toolbox の既定）。人は値を指定していない。下限は遅れ 0.13〜0.17 s＋周期 0.1 s（計算）
- odometry の時刻に足す形にした（AMCL と同じ）。GLIM が止まれば TF も古くなる

## 3. 検査・試験

- 単体試験（Mac）`/opt/anaconda3/bin/python3 -m unittest discover -s gouda_core/test`：327 件 OK（skip 15）。対象は作業ツリー（他のチャットの変更を含む）
- 設計検査 `design/.venv/bin/python design/tools/run_checks.py`：違反 0・未判定 5。intent 由来の 4 つの FAIL はそのまま
- tf2 の確かめ（VM、ROS_DOMAIN_ID 97、~/gouda_unit_tree_bin180/tfprobe.py、Gouda には触れず）：10 Hz で出す TF を、今の時刻で 0.1 s 待って引く。時刻 −0.15 s：成功 0・失敗 20、待ち中央値 0.104 s。時刻 +0.35 s：成功 20・失敗 0、待ち中央値 0.0008 s
- 変更セットの試し：新しい違反 0・新しい未判定 5（DR-15。既存の 0.5 の文字が PRM-135 と同じ数になったもの）
- 実の Gouda・Nav2 での確認・実車：未実行

## 4. 原因の分類（1.6）

- 設計（第172便）

## 5. 残るリスク

- 効果（エラーが消える、0.1 s の詰まりが消える、DEC-222 の override が効く）は実機で未確認
- map→odom の補正が TF に現れるのが約 0.35 s 遅れる（計算）
- 推定が止まっても TF は最大 0.5 s 有効。監視は PRM-89

## 6. 次

- 止まっている：実機の確認（VM か x86 の PC）。コミット・push はまだ
