# 第204便 作業記録：MID-360 の接続試験・動作確認の計画と記録台帳

- 日付：2026-11-06
- 読んだコミット：7f0c7ae（作業ツリーに別のチャットの未コミットの変更あり）
- 人の指示（原文）：「mid-360の接続テスト及び動作確認を行う。計画と、実験結果記録台帳を準備せよ」「mid-360の公式トリセツ等の公式資料、及びqitta等の技術資料等も収集して、有益な情報を厚めよ。トリセツはmid-360用のフォルダに、qitta等から集めた情報は台帳のしかるべきセクションに参考情報として要約して記載せよ。原文のリンクも残すこと。」

## 作ったもの

| ファイル | 内容 |
|---|---|
| `design/proposals/mid360_connection_test_plan_2026-11-06.md` | 計画（提案）。段階 P0〜P8、手順、合否基準（案）、仕様の値と出典、判断の Q1〜Q6 |
| `design/research/vehicle_pc/2026-11-06_mid360_connection/ledger.yaml` | 台帳。試験 31 項目（すべて 未判定・未実行）、実施の記録、参考情報 61 件（公式 10、技術記事・issue・fork など） |
| リポジトリの外 `TsukubaChallenge/Sensors/MID-360/official/` | 公式資料（User Manual EN・CHS v1.2、Quick Start Guide v1.8、FW Release Notes、Viewer 2 の Manual・Release Note、STEP 2 つ、GitHub の README・config・LICENSE・プロトコル文書）。`INDEX.md` に URL・版・sha256 |

## 自律判断と理由

- 公式資料はリポジトリの外に置いた。著作物で、公開リポジトリに入れる許諾を確かめていないため
- 「mid-360用のフォルダ」は、センサーの資料を置いている `TsukubaChallenge/Sensors/` の下に `MID-360/` を新しく作った（既存の `MID-360_stay/` はステーの CAD 用のため）
- 台帳に MID-360 のアドレスの具体的な値を書かなかった（1.10）
- 計画の置き場所を proposals（基準が未承認のため、1.7）、台帳を research/vehicle_pc（証拠の置き場所の慣例）にした
- 収集の 2 つの報告で、同期なしの時刻の付け方が食い違った。ドライバのソース（pub_handler.cpp 265〜274 行）を AI が読み、「PC の受信の時刻」が正しいと確かめた。放熱の上限は User Manual の原文で 75 °C を確かめた（販売店の要約の 80 °C は採らない）

## 見落としとして指摘すること

- **サブネットの重なり**：車載 PC の XT-32 の USB-LAN は、MID-360 の工場出荷時と同じサブネット（`docs/gui_native_rviz.md` 45 行）。そのまま 2 つ目の口を足すと受信が不安定になりうる（推測、扱った記事は見つからず）。Q2
- **光の向き合い**：User Manual p10 は、他の LiDAR の光が真正面に向き合うと回復不能な損傷のおそれと書く。XT-32 と MID-360 の配置を取り付けの前に人が確認
- **PoE の禁止**：PoE のスイッチをつなぐと回復不能な損傷（UM p13）
- **外部パラメータの二重**：ドライバの JSON の extrinsic は本体に書き込まれる。TF と両方に入れると二重に回る
- **型式**：Mid-360S・L だと config の形式が違う
- **IMU の frame_id が固定**：公式ドライバでは livox_frame から変えられない。mid360_link にするには TF でつなぐか fork（#77 の設計に影響）

## 実行した検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 台帳の YAML の読み込み | `design/.venv/bin/python -c "YAML().load(...)"`（ruamel） | 作業ツリー（7f0c7ae＋変更） | 読めた。31 項目・参考 61 件 |
| 公式資料の文字列の照合（一部） | `pdftotext -layout` と grep | User Manual EN v1.2 | 9〜27 V、18 W・8 s、PoE、100BASE-TX、200,000 点/s、ICM40609、他の LiDAR、逆さ 0.5 m、75 °C を確認 |
| 設計検査 | `design/.venv/bin/python design/tools/run_checks.py` | 作業ツリー（7f0c7ae＋変更） | 違反0件・未判定5件（既存の移行の不一致の FAIL はそのまま） |
| MID-360 の接続試験 | — | — | 未実行（機材・Q1〜Q4 待ち） |

## 原因の分類（1.6）

- 修正なし（計画と記録の作成）

## 残るリスク

- 技術記事・fork の内容は収集の担当の報告で、AI は ★ 以外を原本で照合していない
- 合否基準は案。人の承認なしに判定に使えない
- サブネットの問題の対策は推測

## 承認・判断待ち

- 計画 5 章の Q1〜Q6（未登録。回答の後に判断台帳へ）

## 次に進められる作業と止まっている作業

- 進められる：解析スクリプト（rosbag から周期・点数・時刻の差、地面の当てはめ）の作成（試験の道具。着手は人の確認の後、DEC-106）
- 止まっている：P1 以降（Q1〜Q4）、P8（ステーの取り付け）

## 追記：Q1 の回答（REV-220、DEC-431）

- 人の回答（原文）：「dellのx86機でテストを行います」→ DEC-431 に記録（apply_revision の dry-run で新しい違反 0、適用後に render_views・generate_params を実行）
- AI が読むだけで Dell を確かめた（ssh、ip・nmcli・/proc/cpuinfo・ls。設定は変えていない）
  - 有線の口は内蔵の 1 つ。LiDAR 用の固定アドレスの接続の設定が 2 つ（どちらも自動接続あり、MID-360 の工場出荷時と同じサブネット）
  - AVX2 あり。Livox Viewer 2 が当日すでに置かれている（アドレスのない口で落ちる問題の LD_PRELOAD の回避つき、置いた人は記録にない）。Livox-SDK2 は未導入。パスワードなしの sudo はない。Gouda は動いていなかった。Dell の上で別の Claude のセッションが動いていた
- 計画を直した：2 章に Dell の状態と影響、P2 の注意、Q1 を回答済みに、Q2 の推奨を「PoE なしのスイッチで同じ口にまとめる」に変えた（口が 1 つのため）、Q4 に sudo は人と書いた
- 台帳：meta.decisions に DEC-431、sessions.S01.host を Dell に
- 実装（自分の誤り）の修正：台帳の YAML で ` #` を含む値を引用符で囲む処理が、行末のコメント 6 か所まで値に取り込んでいた。コメントに戻した（原因の分類：実装。AI の一時スクリプトの誤り）

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 変更セットの試し | `apply_revision.py REV-220 --dry-run --check` | 作業ツリー（7f0c7ae＋変更） | 新しい違反 0・未判定 0 |
| 設計検査 | `run_checks.py` | 適用後の作業ツリー | 違反0件・未判定5件。FAIL は既存の移行の不一致（SystemArchitecture.drawio、.DS_Store 2 つ）のみ |
| 台帳の読み込み | ruamel | 同上 | 31 項目、すべて未判定 |

## 追記：Q2 の回答（REV-221、DEC-432）

- 人の回答（原文）：「Non-PoE switch」→ DEC-432 に記録
- 計画：2 章の P5、Q2 を回答済みに、T03-4（アドレスの変更は重なる場合だけ）、P5 の手順（スイッチに PoE がないことを確かめてからつなぐ）、準備するもの（LAN ケーブル 3 本、PoE なしのスイッチ）
- 台帳：open_questions から Q2 を外し、decisions に DEC-432。P5 の reason を「PoE なしのスイッチの用意」に
- 残る判断：Q3（電源）、Q4（ドライバの入れ方）、Q5（合否基準）、Q6（発熱の条件）。車体への搭載のつなぎ方（#77 の A-7）は未決

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 変更セットの試し | `apply_revision.py REV-221 --dry-run --check` | 作業ツリー（7f0c7ae＋変更） | 新しい違反 0・未判定 0 |
| 設計検査 | `run_checks.py` | 適用後の作業ツリー | 違反0件・未判定5件。FAIL は既存の移行の不一致のみ |

## 追記：Q3 の回答と最初の試験の報告（REV-222、DEC-433）

- 人の発言（原文）：「12Vでいく。x86で、livoxviewer2にて、点群の受信は確認完了した」→ DEC-433 に記録
- 台帳
  - S01：2026-11-06 21:27〜21:38（Dell の Livox Viewer 2 のログの開始と終了）、実施は人、12 V（電源の種類と電流の制限は未確認）、ファームウェアの版は未記録
  - T03-1（点群の表示）：合格。根拠は人の報告のみ（写真・保存した点群はなし、AI は画面を見ていない）。基準は提案のまま（Q5）。視野の端の見え方は報告になし
  - 合格 1・不合格 0・未判定 30
- AI が読むだけで確かめた（21:40 ごろ）：有線の口はリンクなし。Viewer 2 のログには機体の情報（版・型式）は出ていない
- Viewer 2 で受信できたので、リンク・アドレスは通っていたとみられる（推測）。ただし T02-1〜T02-3 は測っていないので未判定のまま

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 変更セットの試し | `apply_revision.py REV-222 --dry-run --check` | 作業ツリー（7f0c7ae＋変更） | 新しい違反 0・未判定 0 |
| 設計検査 | `run_checks.py` | 適用後の作業ツリー | 違反0件・未判定5件。FAIL は既存の移行の不一致のみ |
| Dell の状態の読み取り | ssh で /sys/class/net、nmcli、Viewer 2 のログ | Dell | リンクなし、ログに機体の情報なし |

## 追記：内蔵 IMU とドライバの調査（K-yama-20/tsukuba-autonomous-robot#80）

- 人の指示（原文）：「まず内蔵imuの公式情報と、みんながよく使ってる鉄板のドライバをリサーチせよ」「記録する」「重力方向から角度を求められないのかな？取り付け時の角度はあまり精度が良くないです。」
- ICM-40609-D のデータシート（DS-000330 Rev 1.2）は人がブラウザで取得し、リポジトリの外の `Sensors/MID-360/official/icm40609/` に配置。AI が sha256 と主な値を INDEX.md に記録
- 台帳の references に L_internal_imu（6 件）・M_driver_choice（3 件）を追記（合計 70 件）
- issue #80 に案を登録：6 面法でゼロ g の誤差を測り、重力の向きから roll・pitch を求める。歪みの補正は P4 の rosbag で確かめてから判断。実装はしない
- 鉄板のドライバは公式（commit 固定）、2 番手は TU Darmstadt の fork（収集の担当の調査）
- 自分の誤り：台帳への追記のコマンドに、標準入力を待つ `cat` が混じり 120 s で止まった。書き込み前に止まっていたので、台帳は壊れていない。書き直して実行した（原因の分類：実装。AI の一時コマンドの誤り）

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 台帳の読み込み | ruamel | 作業ツリー | 読めた。参考 70 件 |
| データシートの値の読み取り | pdftotext | DS-000330 Rev 1.2 | Table 1・2（p10〜11）を確認 |

## 追記（2026-11-07）：ドライバと時刻同期の決定（REV-232、DEC-442）

- 人の発言（原文）：「一旦推奨案で行こう。メインチャットに指示せよ」。分岐したチャットでの発言を、そのセッションが原文を引用して伝えた（この記録の AI は直接見ていない）
- 内容：Q4 は公式の livox_ros_driver2 を commit 固定で setup.sh・drivers.repos に足す方針（2 番手は TU Darmstadt の fork）。Livox-SDK2 は 24.04 のビルドの修正の後の master の commit に固定。時刻はまず同期なし（XT-32 と同じ PC の受信の時刻）、足りなければ PTP
- 実装の許可ではない。setup.sh・drivers.repos の変更は、別に利用者の明示の yes を取る（DEC-106）
- 計画：P4 にドライバと時刻の方針、P5 に T05-4、Q4 を回答済みに
- 台帳：T05-4（XT-32 と MID-360 の時刻の差）を追加、open_questions は Q5・Q6、P4 の reason を「ドライバの導入の yes 待ち」に。32 項目：合格 1・不合格 0・未判定 31

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 変更セットの試し | `apply_revision.py REV-232 --dry-run --check` | 作業ツリー（7f0c7ae＋変更） | 新しい違反 0・未判定 0 |
| 設計検査 | `run_checks.py` | 適用後の作業ツリー | 違反0件・未判定5件。FAIL は既存の移行の不一致のみ |
| 台帳の読み込み | ruamel | 同上 | 32 項目 |

## 追記（2026-11-07）：MID-360 のドライバを setup.sh に足した（REV-233、DEC-443）

- 人の回答（原文）：「着手してよい」→ DEC-443（承認）に記録。範囲はドライバの取得・ビルド・導入まで（Gouda への組み込み、/config・TF・costmap は含まない、AI の解釈）
- 変更（コード・設定）
  - `third_party/drivers.repos`：Livox-SDK2 `c0796f0`（2026-09-21 の master。24.04 のビルドの修正 68ae1e1 を含む）、livox_ros_driver2 `2144554`（同日の master。Jazzy 対応 1.2.6 の後、1.2.8）
  - `setup.sh`
    - 2：Livox の 2 つは別の作業場所 `<workspace>_livox`（Dell では ~/gouda_ws_livox）に取得（SDK は sdk/、ドライバは src/）。変更なしの確認は他のドライバと同じ
    - 3：rosdep はドライバの package_ROS2.xml の写しを一時フォルダで読む（チェックアウトを変えないため）
    - 5：Gouda のビルドの後、commit が変わったときだけ、SDK を cmake でビルドして sudo で /usr/local に入れ、ldconfig。ドライバは upstream の `build.sh jazzy`。build.sh はエラーで止まらないので、ライブラリができたかで判定して止める
    - `sdk/COLCON_IGNORE` を置く（下の試しのビルドで見つけた問題への対処）
    - 最後に `source ~/gouda_ws_livox/install/setup.bash` を表示
  - `README.md`：setup.sh の説明とフォルダの構成
- 自律判断と理由
  - SDK とドライバは同じ日の master にそろえた（ドライバの master は同じ日の SDK の機能に合わせて更新されている、commit の説明から）
  - 作業場所の名前を `<workspace>_livox` にした（作業場所ごとに分かれ、既存の ~/gouda_ws_sim などと同じ並び）
  - ~/.bashrc の既存の印の間には足さない（既存の印は変えない作り）。Gouda からは MID-360 のドライバはまだ起動しない
- 試しのビルド（Dell、~/livox_build_test、sudo なし。SDK は /usr/local の代わりに一時の場所へ。終わってから消した）
  - 1 回目：SDK・ドライバともビルドできた。ただし build.sh の colcon が作業場所の中の SDK のチェックアウトもパッケージとしてビルドし、ドライバはその写しにリンクしていた（/usr/local のものではない）→ `sdk/COLCON_IGNORE` を足した（原因の分類：実装。AI が作った手順の誤り）
  - 2 回目（COLCON_IGNORE あり）：ドライバだけビルド（27.8 s）。ドライバは一時の場所の SDK（/usr/local の代わり）にリンク、チェックアウトは変更なし、`livox_ros_driver2_node` は起動して版 1.2.8 を表示（存在しない設定ファイルを渡したので、すぐ設定の読み込みに失敗。MID-360 はつないでいない）
  - 警告は 94 行（SDK の同梱の spdlog の C++20 の警告など）。失敗はなし
- setup.sh 自体は実行していない（sudo が要る）。Dell で人が `bash setup.sh` を実行する
- 残るリスク
  - 本当の /usr/local への導入と ldconfig は未確認。`libapr1-dev` は Dell にないので、setup.sh の rosdep が入れる（APR はドライバの CMake では「見つかれば使う」）
  - ドライバの設定ファイル（MID360_config.json）は upstream のものを書き換えると「ローカルの変更」で setup.sh が止まる。P4 の試験の設定ファイルの置き場所（リポジトリの外か、/config から作るか）は次に決める
  - VM・ワークステーションでは未確認

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 変更セットの試し | `apply_revision.py REV-233 --dry-run --check` | 作業ツリー（7f0c7ae＋変更） | 新しい違反 0・未判定 0 |
| setup.sh の構文 | `bash -n setup.sh` | 同上 | OK（shellcheck は Mac にない、未実行） |
| drivers.repos の読み込み | `yaml.safe_load` | 同上 | 4 件 |
| 試しのビルド | ssh で Dell に scratch の手順（`livox_build_test.sh`、COLCON_IGNORE ありの 2 回目） | SDK c0796f0・ドライバ 2144554 | ビルド成功、リンク先は一時の場所の SDK、チェックアウトは変更なし、node は起動 |
| `bash setup.sh` | — | — | 未実行（sudo は人） |
| 設計検査 | `run_checks.py` | 適用後の作業ツリー（setup.sh 変更後） | 違反0件・未判定5件。setup.sh の未判定 2 件は既存の行（curl の --retry 3、PRM-50 の文字列）で、行の番号がずれただけ。FAIL は既存の移行の不一致のみ |

## 追記（2026-11-07）：Dell での `bash setup.sh` の結果（読むだけで確認）

- 人の報告（原文）：「Dell で `bash setup.sh` を実行した。」
- AI が ssh で読んだ結果：Dell のリポジトリは branch `dev-tab-vehicle-test`（9caaa65、2026-11-03）で、追跡しているファイルに 48 件のローカルの変更（車両試験の作業。design/generated のほか gouda_core/vehicle_* など）。今回の setup.sh・drivers.repos の変更は Mac の作業ツリーにしかなく、Dell の setup.sh・drivers.repos には livox の記述がない（grep で 0 件）
- そのため、実行されたのは古い setup.sh。~/gouda_ws_livox はなく、/usr/local に Livox-SDK2 もなく、libapr1-dev も入っていない。MID-360 のドライバは未導入
- 原因の分類：試験（手順）。AI が「Dell で setup.sh を実行」と頼んだとき、変更が Dell に届いていないことを書かなかった（AI の説明の不足）
- Dell のチェックアウトは AI は変えない（~/gouda_ws は触らない、別の作業のローカルの変更がある）。届け方は人の判断

## 追記（2026-11-07）：コミットと push

- 人の指示（原文）：「コミットして push」「push してよい」（push の前にメールアドレスを報告：作者・コミッターとも ryoya-1@g.ecc.u-tokyo.ac.jp）
- コミット 9c449b5（setup.sh・third_party/drivers.repos・README.md のみ）。branch design/mppi-sim-2026-11-03 に push（7f0c7ae..9c449b5。別のチャットの 6f57eee を含む）
- 記録（model.yaml、REV-220〜222・232・233、計画・台帳・作業記録・status.md）は他のチャットの未コミットの変更と混ざるので、コミットしていない
- main には入っていない。Dell への反映は、main への PR と Dell のローカルの変更 48 件の片付けの後の `bash update.sh`、または Dell でこの branch を取る（人の判断）
