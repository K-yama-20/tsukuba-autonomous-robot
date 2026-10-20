# 作業記録 2026-10-20 第57便: Google スプレッドシートの gnss_localization_submodule の行の記入

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（作業ツリーは未 commit の変更あり）。status.md（第56便まで）。
- Google スプレッドシート Gouda_architecture_detail（ID 1YsDMMmeVlaqwRGtAY7-fJNq4Pycb_bJa-KiKO9JsEwE）「モジュール定義」を記入の前に CSV で書き出して読んだ。41 行目は gnss_localization_submodule・実装場所 PC だけで、ほかは空（第42便で読んだときと同じ）。

## 人の指示

「spreadsheetを更新せよ」（続けてスプレッドシートの URL）。

## 実行

- このセッションに Google Sheets のコネクタがない（Drive だけ）ため、内蔵ブラウザでスプレッドシートを開き、41 行目の各セルに入力した。ブラウザはログインしていない状態で表示され（右上に「ログイン」）、編集はリンクの権限で匿名として記録されているはず（推測）。
- 入力の後に CSV で書き出し、41 行目が入力どおり（M-039、localization、processor、PC、…、no、no、モジュール差替可、…、草案、備考）であることを確かめた。
- リポジトリの `design/docs/Gouda_architecture_detail.xlsx`（登録済みの写し）は変えていない。

## 記入した内容の考え方（自律判断ではなく、人の指示による記入。内容は草案）

- このチャットでの議論の到達点に合わせた。人の指摘（GNSS は local planning・local localization・走行制御にも有用で、Global_localization に取り込むと依存が複雑）を受け、利用側に依存しない独立の供給元として書いた。初期化の手順は Global_localization 側。
- 調べた事実を反映: 位置・速度・方位は受信機の中で計算（PC で測位し直さない）、NTRIP の中継は RTKLIB の str2str（DEC-139 案 B1、DEC-151 承認）、受信機は DualAnt・MultiAntenna Fixed、アンテナ間隔 0.34 m（DEC-149）。
- 未承認の点は備考に明記: 独立のモジュールとする位置づけ、local_odometry への供給（速度・方位だけ）、Navigation・走行制御での利用。
- 秘密の扱い（DEC-139 の人の規則）に従い、NTRIP の接続先・認証は書いていない（非公開のファイル名だけ）。
- 進捗は選択肢から「未実装」（ドライバの起動・記録は実装済みだが本体は未実装）。使用モードは「全モード」。

## 残ること・食い違い

- 提案 `design/proposals/gnss_localization_submodule_responsibility.md` は第1版（Global_localization の下位、中に MRTKLIB）のまま。シートの行はそれより新しい考え（独立の供給元、MRTKLIB は使わない）で書いた。提案の第2版への書き直しは未実行。
- 正本（model.yaml）にこのモジュールはない。取り込むかは承認事項（未登録）。
- drawio の線（出力先）は人の編集のまま。

## 検査・試験

- 未実行（正本・生成物を変えていない）。
