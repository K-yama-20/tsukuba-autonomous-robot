# 作業記録 2026-10-19 第42便: gnss_localization_submodule の責務と非責務の検討（提案）

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（作業ツリーの drawio は人が編集中で未 commit）
- drawio のセル LHcLvlGkRA-CqYbzRrZq-2（gnss_localization_submodule）・805Qo-s3WLsUmU50dQsv-3（MRTKLIB）・線 LHcLvlGkRA-CqYbzRrZq-3
- Google スプレッドシート Gouda_architecture_detail「モジュール定義」（CSV で書き出し。gnss の行は名前と実装場所 PC だけ）
- ND-19・ND-07・IFD-47〜50・G-GNSS-NO-HEADING・DEC-124/130/131/133/135/137/139、提案 gnss_initial_pose_design.md・ntrip_gga_proposal.md
- VM の ~/MRTKLIB（v0.7.11、dd325d6）の README と mrtk --help（読むだけ）

## 人の指示

「gnss_localization_submoduleの責務と非責務等を考えよ」（drawio とスプレッドシートの URL を添えて）

## 成果物（提案。正本は変えていない）

- `design/proposals/gnss_localization_submodule_responsibility.md`（責務・非責務・異常時・シートの行の案・drawio の線の案・承認事項 Q-A〜Q-F）

## 自律判断

- なし（正本・生成物・drawio・スプレッドシートは変えていない）

## 承認待ち（提案の中の Q-A〜Q-F。判断台帳への登録は人の方針を聞いてから）

## 検査・試験

- 未実行（正本を変えていないため）

## 残るリスク

- drawio に出る線がなく、位置づけ（Global_localization の下位）は推測。
- mosaic-go G5 P6 のデュアルアンテナの対応は原本未照合（G-GNSS-NO-HEADING）。

## 次

- 人の回答（Q-A〜Q-F）。回答で前提が変わったら提案を作り直す。
