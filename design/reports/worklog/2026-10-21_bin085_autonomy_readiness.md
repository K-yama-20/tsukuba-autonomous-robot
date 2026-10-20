# 作業記録 2026-10-21 第85便: 自律走行に向けた不足と完了の一覧、vehicle_bridge・motion_controller の状況（調査のみ）

## 読んだもの

- コミット `0c898dabbd5ab58cfa55c2b6e29419e60d100a77`（ブランチ design/field-mapping-2026-10-14。作業ツリーの変更は人のファイル design/docs/SystemArchitecture.drawio、docs/architecture/ の 2 つ、*.bkp だけ）。
- `reports/handover_2026-10-21.md`、`reports/status.md`、`reports/handover_2026-10-17.md` §5、`reports/worklog/2026-10-20_bin061_autonomy_node_inventory.md`、`docs/implementation_stages.md`。
- `design/model.yaml`: ros_node ND-01〜19、pending の判断（18 件）、DEC-115・169・171・172、試験 TS-01・02・05〜07・13〜21。
- `design/generated/params/`: gouda_motion_controller・vehicle_bridge・tbd のあるファイル（bt_params、gouda_monitor、gouda_mode_manager、controller_server、gouda_map_creator、gouda_nav2）、gouda_static_tf。
- コード: `gouda_core/gouda_core/motion_core.py`・`motion_controller_node.py`・`vehicle_core.py`・`vehicle_bridge_node.py`（全文）、`mode_manager_node.py`・`nav2_config.py`・`autonomy_core.py`・`monitor_node.py`・`web/app.js`・`launch/*.py`（必要な箇所）。

## 人の指示（原文）

「自律走行するために、まだ足りないもの・もう実装が完了しているもの等を表にまとめよ。また、vehicle_bridgeは完成しているかが知りたい。gouda_motion_controllerの状況も詳しく知りたい。」

## 結果

報告 `reports/autonomy_readiness_2026-10-21.md`。要点:
- ソフトウェアの骨組み（モード、Nav2 の起動と goal、速度上限、車体出力）はできている。実車での自律走行を止めているのは次の 3 つ: ND-07 未実装（DEC-115 保留）、Nav2 の実車の値（PRM-11・17・18・66〜73）未確定、Nav2 で使える 2D 地図がない（DEC-098・107）。
- vehicle_bridge: 工程 5-5 の範囲のソフトウェアとしては完成している。設定値はすべて承認済み。ESP32 実機・車体では未試験。事前地図作成での configure（DEC-169）は許可待ち。
- motion_controller: 基本の機能は実装済みで、ソフト試験に合格している。設定値はすべて承認済み。不感帯の補償（DEC-171）と後退の正規化（DEC-172、PRM-78 は宣言も使用もしていない）は許可待ち。実機未試験。

## 自律判断した変更

- なし（正本・生成物・コードは変えていない）。新しいファイルは報告とこの作業記録だけ。

## 承認事項・実測待ち

- 新規の登録はしていない。報告 §4 の順序（Nav2 の値、ND-07 の方式、地図の設定値、卓上試験、反映）は、既存の承認・実測の項目を並べたもの。
- 報告 §4 の 1 の「ND-07 なしの試験の構成」は TR-05 の契約（ND-07 必須）の外になるので、進めるなら承認事項として登録する。

## 検査・試験

- 未実行（何も変えていない）。報告の試験の結果は、既存の作業記録・status.md からの引用。

## 残るリスク

- 後退の実速度（約 0.2 m/s）と、低速で動き出さない可能性は、計算と推測。実測していない。
- status.md の後半（三つの状態、承認待ちの一覧）には、古い記述が残っている（例: 「DEC-160 の回答まで firmware は DAC に書かない」）。今回は直していない。

## 更新した生成物

- なし。

## 次に進められる作業・止まっている作業

- 進められる: 人の指示があれば、報告 §4 のどれかの検討（計画・分析）。
- 止まっている: ND-07 の実装（DEC-115）、Nav2 の実車での起動（PRM 未確定）、motion_controller の改良と vehicle_bridge の configure（実装の許可、DEC-106）。
