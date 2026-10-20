# 作業記録 2026-10-21 第73便: DR-15 の未判定 11 件と、設定にない時間の値の調査（調査のみ）

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（作業ツリーは未 commit の変更あり）。`design/tools/check_design.py`（DR-15）、`design/tools/hardcode_scan_roots.json`、`design/rules/README.md`、DR-15 の 11 件の各ファイル、gouda_core・firmware・gouda.sh の時間に関わる数値（grep で 54 行）。

## 人の指示

「…全部一つづつ徹底的に調べよ」

## 結果

- 報告 `design/reports/dr15_literal_audit_2026-10-21.md`。
- 11 件のどれも PRM の値の写しではない。7 件は偶然の一致・誤検出（セルの中心 0.5、版の文字列 0.2、docstring の「CLAUDE.md 1.5」など）。vehicle_bridge のシリアルの write_timeout 0.2 s・timeout 0.05 s・失敗後の待ち 0.5 s と GLIM の終了の確認の間隔 0.2 s は、設定に宣言されていない時間の値。
- 検査器が見ない値: recorder の rosbag の停止の待ち 30 s、gouda.sh の停止の 30 s・10 s（PRM-37 の「上限なし」と食い違う可能性）、firmware の 5 ms など。
- vehicle_bridge が USB の抜けで 0.5 s ごとに DecisionEvent を出し続ける（推測。未試験）。

## 変更

- なし（コード・正本・生成物は変えていない）。

## 検査・試験

- 未実行（何も変えていない）。

## 次に進められる作業・止まっている作業

- 人の判断待ち: 報告 §4 の 3 点。
