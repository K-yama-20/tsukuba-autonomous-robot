# 作業記録 2026-10-18 第33便: DEC-126 の実装（地図作成の間の GNSS の記録）、貼られた仕様の照合（REV-063）

## 読んだもの

- コミット `2ce59ea3eb892b4a430f7f38f179b13aab4c37c9` ＋ 第31・32便の未コミットの作業（REV-060〜062）。
- 人が貼った文書（`design/research/gnss_reference_spec_2026-10-18.md` に原文の写し）。
- コード: mode_manager_node.py（TR-03・TR-04）、map_database.py（register_source）、gnss_config.py、提案 `proposals/gnss_initial_pose_design.md` 第1版。
- 上流: septentrio_gnss_driver の README（master。https://raw.githubusercontent.com/septentrio-gnss/septentrio_gnss_driver/master/README.md、別の agent に読ませた要約。ros2 ブランチは 404）。導入する 1.4.8 と同じ版かは原本未照合。

## 1. 人の回答・資料（判断台帳に原文）

- DEC-126: 「DEC-126は許可。」
- DEC-130: 同じメッセージに貼られた「GNSS（デュアルアンテナ・ネットワークRTK）活用 実装仕様まとめ」。扱いの指示はなかったので、参考の資料として照合した（名称・数値はすべて参考値と文書自身に書かれている。数値は採っていない）。アンテナ間隔 0.6 m は文書の中で実測値とされている（記録だけ。設計の値にはまだ使っていない）。

## 2. 実装（DEC-126）

- `gouda_core/gouda_core/gnss_log.py`（新規）: 地図作成の間の GNSS の記録（JSON Lines。topic、PC の受信時刻、メッセージの全項目）。
- `mode_manager_node.py`: GNSS の topic（IFD-47〜50）を購読し、TR-03 で作業フォルダの gnss.jsonl を開き、TR-04 で閉じて原図の登録に渡す。ドライバの型がないときは記録に note を残し navsatfix だけを書く。DecisionEvent gnss_record_started・gnss_record_stopped（GNSS の行がないときは「この地図からは対応を作れない」と書く）。
- `map_database.py`: register_source に gnss を足し、gnss.jsonl を原図の横に置き、SHA-256 と行数を source_manifest.json の gnss に書く。
- `gnss_config.py`: publish.attcoveuler を true に明示（雛形も true。IFD-50）。
- `package.xml`: rosidl_runtime_py。

## 3. 自律判断した変更とその理由

- gnss.jsonl を GLIM の dump（source/）の中ではなく横に置いた。提案 第1版は「原図の内容ハッシュに含める」と書いたが、source の content_hash は GLIM の dump の同一性を表していて、その意味を変えないため。GNSS の記録は manifest に別の SHA-256 で結び付けた（提案を第2版で直した）。
- 方位の共分散（AttCovEuler）を IFD-50 として記録に加えた（貼られた仕様 §7 の方位の標準偏差の判定に要る。ドライバは既定で出している）。
- メッセージを選ばずに全項目を書く（後の対応の計算でどの項目を使うか決まっていないため。受信機の時刻 block_header も残る）。

## 4. 修正

なし。

## 5. 試験（コマンド・対象・結果）

対象: コミット 2ce59ea ＋ 作業ツリー。

- Mac の単体: `cd gouda_core && python3 -m unittest discover -s test -p "test_*.py"` → 168 件 OK・1 件 skip（新規 test_gnss_log.py 2 件）。
- 全検査 `design/.venv/bin/python design/tools/run_checks.py` → 終了コード 1。不合格は人の drawio の SHA だけ。設計整合性 違反 0、未判定 4（DR-04 5、DR-05 2、DR-10 2、DR-11 67）。DR-15 合格。
- ROS 上の試験: 最初は VM（10.211.55.4）が ssh でつながらず未実行。人が VM を起動した後、`gouda_core/test/ubuntu_gnss_mapping_record.sh` で合格（REV-064、FILE-GNSS-MAPPING-RECORD-VM-TEST）。G1: 合成の GNSS 4 種類 × 20 通 → gnss.jsonl 80 行が原図の横に置かれ、manifest の SHA-256（2076c942…）と一致、原図の content_hash は GLIM の dump だけ。G2: GNSS なしの地図作成は空の記録と「対応を作れない」の記録で、地図作成は止まらない。VM の単体試験も全件 OK・1 件 skip。
- 未実行: 受信機（mosaic-go）をつないだ実機での記録（DEC-125 の回答と x86 機への反映の後）。

## 6. 承認事項と実測待ち

- 新規 pending: DEC-131（enu→map の TF）、DEC-132（取付の方位オフセットの校正）、DEC-133（仕様 T3 の形の自動の初期化。DEC-128 の代わり）、DEC-134（走行中の発散の監視と再初期化。詳細は ND-07 の後）。
- 第2版で推奨を変えたもの: DEC-127（4 自由度＋RANSAC、地図作成の時の記録で）、DEC-128（取り下げを推奨）。DEC-129 は変わらず。
- 実測・確認: DEC-125（接続先・RTK の受け方）は回答待ち。方位の定義（生の AttEuler が ENU に変換されるか）は実機の記録で確かめる（提案 §10）。

## 7. 残るリスク

- 方位の定義・RTK の mode の値の意味は原本未照合（README に記載なし）。
- 基線長の検査（仕様 §7）は、ドライバの basevector を有効にして中身を確かめるまで設計に入れられない。

## 8. 生成物の変更

- render_views の再生成（判断台帳・未決の一覧）。generated/params は元の model の SHA の行だけ。

## 9. 次に進められる作業と止まっている作業

- 人の作業: DEC-125・127・129・131〜134 の回答、x86 機への反映。
- commit はしていない。
