# 第242便 作業記録：MID-360 の取り付けを monitor の /config で設定する（REV-266、DEC-485・486）

- 日付：2026-11-07
- 読んだコミット：9c449b5（作業ツリーに他のセッションの未コミットの変更が多数。REV-242 のコードも未コミット。作業中に model.yaml を他のセッションが更新している）
- 読んだもの：CLAUDE.md（1.1〜1.13）、intent.md の 106・107・110・112 行、status.md の先頭、第217便の作業記録、REV-242・REV-259・REV-260（読むだけ。触っていない）、
  `gouda_core/gouda_core/` の sensor_config.py・sensor_extrinsics.py・static_tf_node.py・monitor_core.py（SensorConfig）・mid360_config.py・nav2_config.py（MID-360 の部分）・
  monitor_node.py（/config の保存）、`gouda_core/launch/gouda_nav2.launch.py`、`gouda_core/web/` の /config の画面（index.html・app.js）、
  `design/docs/mid360_driver_interfaces.md`（REV-260 の根拠。触っていない）、`design/proposals/mid360_mount_measurement_2026-11-07.md`、
  P4 の道具 `design/research/vehicle_pc/2026-11-06_mid360_connection/tools/p4_driver/`（読むだけ）、apply_revision.py、model.yaml の IFD-20・26・61、ND-02・10・13・20、DEC-457
- 原本：Livox Mid-360 User Manual v1.2（2024.04）の PDF 15〜17 ページを直接読んだ（リポジトリの外の公式資料、sha256 3f202c84…。INDEX.md の値と一致）。
  上流 livox_ros_driver2 2144554 の lddc.cpp（リポジトリの写し、登録済みの hash と一致）の 263・480〜495 行を読んだ。
  通信プロトコル（livox_wiki_en の livox_eth_protocol_mid360.md）の 156〜165 行を読んだ。上流の src/comm/pub_handler.cpp は WebFetch（要約の道具）で読んだので、行番号は未確認
- このセッションは監督役のセッションの指示で実装した。Gouda の起動・停止、車載 PC への接続はしていない。コミットはしていない

## 人の指示（原文、DEC-485）

「IMU の frameは公式資料を探して値を見つけよ。また、本体取り付けの位置はgouda_monitorの/configで設定できるようにせよ。」

監督役の解釈：MID-360 の取り付けの位置・姿勢を /config で設定できるようにする実装への yes（DEC-106）。この記録の AI は人の発言を直接は見ていない。

## 変更

| ファイル | 内容 |
|---|---|
| `gouda_core/gouda_core/monitor_core.py` | CONFIG_FIELDS の末尾に mid360_mount_x_m・_y_m・_z_m・_roll_rad・_pitch_rad・_yaw_rad（number）と mid360_axis_mapping（axes）。既定は UNKNOWN。左手系の軸の保存の警告を MID-360 用の文にした（「mid360_link を出さず経路も起動しない」） |
| `gouda_core/gouda_core/mid360_config.py` | 足した関数：mount_from_config（/config の値から base_link → mid360_link、そろわなければ None と理由）、read_config_mount（sensor_config.json を SensorConfig で読む）、read_addresses（mid360.json のアドレスだけ。残った取り付けの鍵を一覧）、legacy_mount_note（残った鍵の注記。/config と同じか違うか）、static_tf（ND-13 用）、launch_inputs（launch 用）。read_local・mount_from_file は変えていない（既存の試験と P4 の道具が使う。REV-242 の形を読むだけ） |
| `gouda_core/gouda_core/static_tf_node.py` | mid360_link を mid360.json でなく /config の 7 項目から出す（mid360_config.static_tf）。記録の details 'mid360' に注記 |
| `gouda_core/launch/gouda_nav2.launch.py` | `_mid360_ready` を launch_inputs に替えた（アドレスは mid360.json、取り付けは /config）。戻り値に注記を足し、MID-360 の log に付ける |
| `gouda_core/web/app.js` | /config の「センサ取付・座標方向」で、保存していない入力をタブの遷移で保つ（サーバの値と違う欄だけ。保存に成功したらサーバの値。拒まれた保存では入力を保つ。「未保存の入力 n」を表示）。Nav2 タブの mid360_enabled の説明 |
| `gouda_core/web/index.html` | /config に MID-360 の説明の 1 行 |
| `gouda_core/test/test_mid360_mount_config.py`（新） | 17 件（下） |
| `design/revisions/REV-266.yaml` | DEC-485（answered）、DEC-486（pending）、IFD-61・IFD-26・IFD-20・ND-13・ND-10・ND-02・ND-20 の変更。1 行目の予約の印は残した |

既存の試験は変えていない。nav2_config.py は変えていない（62 行の docstring「the vehicle PC's addresses and mounting」は古い言い方のまま。範囲の外）。

## 決めたこと（自律判断）とその理由

1. 置き場所を /config に一本化し、mid360.json はアドレスだけを読む。二か所にあると画面の値と使う値が食い違いうるため。アドレスを /config に入れないのは、/config の値が DecisionEvent の settings（log/decision。rosbag の -a に入る）と地図ごとの /config の写しに入るため
2. 形は XT-32 と同じ（/config の項目、R = R_rpy × A、REP-103）。ただし中立の値で埋めない（DEC-457。DEC-122 の規則は XT-32・IMU・GNSS だけ）。7 項目がそろうまで TF を出さず、経路を起動しない
3. 両方に値があるとき：/config を使う。mid360.json の取り付けの鍵は読まず、ND-13 の記録と launch の log に「読まない」「/config と同じ変換／違う変換」を出す。/config がそろっていなければ「/config に入れる」と出す
4. 移行：自動では写さない（人の値を AI が別の場所に動かさない）。REV-242 の形の mid360.json だけでは、この変更の後は MID-360 の経路が起動しない（XT-32 だけ）。車載 PC に mid360.json があるかは確かめていない（第217便の記録では作成は未実行）
5. タブの遷移（intent.md:106）：保存した値はもとからサーバのファイルに残る。今回、保存していない入力もタブの遷移で残るようにした（XT-32 などの欄にも効く）。再読込では消える
6. read_local・mount_from_file は残した（既存の試験と P4 の道具 make_config.py が使う）。用途は「残った鍵の注記」に変わった
7. 内蔵 IMU の frame の事実は ND-20 の interpretation に追記した（REV-260 が ND-20 の responsibilities を丸ごと置き換えるので、ぶつからないよう追記の形にした）

## 内蔵 IMU の frame（公式資料・上流のソースで確かめた事実）

| 事実 | 出典 |
|---|---|
| IMU の加速度・角速度の軸の向きは点群の座標と同じ | User Manual v1.2 PDF 17 ページ（印刷 15）「IMU Data」 |
| IMU のチップの位置は点群の座標で x 11.0 mm、y 23.29 mm、z −44.12 mm | 同上 |
| 電源を入れると IMU を 200 Hz で送り始める（PC から有効・無効にできる） | 同上 |
| ドライバは IMU の header.frame_id を文字列 livox_frame に固定する（点群は parameter frame_id ＝ mid360_link） | lddc.cpp 481 行（点群は 263 行） |
| ドライバは加速度・角速度を単位を変えずに写す。プロトコルの単位は角速度 rad/s、加速度 g | lddc.cpp 490〜495 行、livox_eth_protocol_mid360.md 160〜165 行、上流 pub_handler.cpp（WebFetch。行番号未確認） |
| 手元の機体との一致 | 未確認 |

## 承認事項・実測待ち

- DEC-485（answered）：上の指示の原文
- DEC-486（pending、承認）：ND-13 が mid360_link → livox_frame を出すか。推奨は B「出す（mid360_link を出すときだけ、移動は公式の値、回転なし）」。代替 A 出さない、C 移動 0、D 付け替えの node・fork
  - 気づき：REV-260（未適用）の DEC-478 が同じ問いで推奨は A。この便の推奨が B なのは、人の指示が IMU の frame の値を求めたため。どちらかに答えがあれば両方を閉じる
- DEC-457（pending、実測）：変えていない。入れる場所は mid360.json から /config に変わった（DEC-485 の note に書いた。DEC-457 は書き換えていない）
- DEC-455・456：変化なし

## 実行した検査・試験

対象：9c449b5＋作業ツリー（他のセッションの未コミットの変更を含む）。Mac。

| 検査 | コマンド | 結果 |
|---|---|---|
| 単体試験（変更前） | `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test` | 456 件 OK（skip 35） |
| 単体試験（変更後） | 同上 | 473 件 OK（skip 35） |
| MID-360 の試験 | `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test -p "test_mid360*.py"` | 23 件 OK（新 17、既存 6） |
| P4 の道具の試験（読むだけ。pycache を書かない） | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=gouda_core python3 -m unittest discover -s design/research/vehicle_pc/2026-11-06_mid360_connection/tools/p4_driver -p "test_*.py"` | 19 件 OK（mid360_config の変更で壊れていない） |
| JS の構文 | `node --check gouda_core/web/app.js` | OK |
| 構文 | `python3 -m py_compile` static_tf_node.py・gouda_nav2.launch.py・mid360_config.py | OK |
| 画面（一回限り。ROS なし） | scratchpad の小さな server（本物の web/ と一時フォルダの SensorConfig）を Browser pane で開いた | mid360_* の 7 欄が出る。2 欄に入力 → Nav2 タブ → 戻る、地図タブ → 戻る：入力が残り「未保存の入力 2」。不正な値で保存 → NG、入力は残る。直して保存 → revision 1、サーバの値で表示、タブを移っても残る。console の error は scratch の server にない /api/map_settings の 404 と、わざと拒ませた保存の 400 だけ |
| 変更セットの試し | `design/.venv/bin/python design/tools/apply_revision.py REV-266 --dry-run --check`（2 回） | 0 new violations、0 new undetermined（model not written） |
| IPv4 の文字列 | 新しい試験の中の検査と `grep -nE` で REV-266・試験・mid360_config.py・index.html | なし |
| run_checks.py、本適用、generate_params、ROS 上での launch・static TF の起動、車載 PC、実機の MID-360、実車 | — | 未実行 |

新しい試験（test_mid360_mount_config.py、17 件）：7 項目が /config の項目で既定なし／保存が再読込と他の項目の保存の後も残る／REV-266 より前の sensor_config.json を読める／不正な軸は保存で拒む／左手系は MID-360 用の警告で保存／そろえば変換、1 つでも UNKNOWN・NaN・bool・左手系・不正な軸なら None と理由（中立の値なし）／sensor_extrinsics.static_transforms は変わらない／mid360.json のアドレスだけ・欠け・REV-242 の形／read_addresses からドライバ設定／ND-13 用の注記（読まない・同じ・違う・一部の鍵）／launch の入力（/config のファイルなし・一部・そろう・mid360.json なし・config_dir なし・REV-242 の形だけでは起動しない）／gouda_nav2.launch.py の `_mid360_ready`（launch の module を差し替えて実行。ドライバなし・取り付けなし・そろう）／変更したファイルに IPv4 なし。

## 設計検査の状態（1.4）

- dry-run の範囲：違反の増加 0、未判定の増加 0。全体の run_checks.py は実行していない（未判定）
- 移行が正確：この便では扱っていない
- 実車投入可能：人の判断待ち。材料：単体試験と画面の一回限りの確認だけ。ROS 上・車載 PC・実車は未実行。取り付けは未実測（DEC-457）

## 原因の分類（1.6）

- この変更の原因：仕様（人の指示 DEC-485 による要求の変更）→ 設計（取り付けの IF を IFD-61 から IFD-26 へ）と実装。REV-242 で mid360.json に置いた理由（monitor が保存のときに知らないキーを落とす）は、項目を CONFIG_FIELDS に足すことで解消した
- 作業中の自分の誤り
  - 実装：mount_from_config の理由の文に sensor_pose の「base_link axes used instead」が残り、MID-360 では誤り（何も使わない）。試験の前に直した
  - 試験の手順：`python3 -m unittest <ファイルのパス>` が module 名の解決で失敗。discover と -p に替えた（合否の基準は変えていない）

## 残るリスク・考慮漏れ

- 移行：車載 PC に REV-242 の形の mid360.json（取り付けの値入り）があると、この変更を入れた後は /config に入れるまで MID-360 の経路が起動しない（XT-32 だけ。log と記録に理由）。車載 PC のファイルの有無は未確認
- 反映は一式で：monitor_core.py・mid360_config.py・static_tf_node.py・gouda_nav2.launch.py・web/app.js・web/index.html。一部だけ入れると TF と経路の条件が食い違う。車載 PC には第217便の REV-242 の版が入っている
- 値を消したとき：/tf_static から mid360_link は消えるが、動いている node の tf2 の buffer には前の静的 TF が残る（再起動まで）。経路も gouda.sh の再起動まで動く。今までの静的 TF と同じ性質
- launch は gouda.sh start のときだけ読む。起動の後に 7 項目を入れると TF はすぐ出るが、MID-360 の層は次の起動から（画面に書いた）
- 値の妥当性の検査（度と rad の取り違え、pitch の範囲など）はない。足すのは新しい制約なので承認事項。誤った値は地面を障害物にする・障害物を見落とすおそれ
- 保存していない入力は再読込・別の端末では残らない。別の端末で同じ欄が保存されても、入力中の値が表示される（「未保存の入力 n」で分かる）。ブラウザの自動の試験はない（一回限りの確認だけ）
- 古い記述：`design/proposals/mid360_mount_measurement_2026-11-07.md`（提案）は「mid360.json に取り付けを入れる」のまま。REV-260（未適用）の DEC-478 は IMU の frame で推奨が逆。nav2_config.py 62 行の docstring。どれもこの便の範囲の外で変えていない
- /livox/imu の加速度は g のまま（DEC-477）。TF を出しても、そのまま使える IMU にはならない

## 生成物の変更箇所

- なし（REV-266 は dry-run だけ。model.yaml・generated は書いていない）

## 次の作業

- 進められる：REV-266 の本適用（親のセッションの判断）、車載 PC への反映（人の指示の後）、人が /config に MID-360 の 7 項目を入れる（DEC-457 の実測の後）、ROS 上で static TF と launch の log を確かめる
- 止まっている：DEC-486 の回答（mid360_link → livox_frame）、DEC-455〜457
