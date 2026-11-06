# MID-360 接続試験の rosbag 解析（読むだけ）

計画 `design/proposals/mid360_connection_test_plan_2026-11-06.md`（3・4 章）と台帳 `../ledger.yaml` の
T04・T05-4・T07・T08-3 の数値を、記録した rosbag から出すスクリプト。rosbag を読むだけで、ROS のノードの起動・
topic の発行・車体への指令はしない。実装の許可は DEC-474・DEC-475（`design/revisions/REV-259.yaml`）。
作ったときに読んだリポジトリのコミットは 9c449b5。

- 基準の値はスクリプトの中で決めない。期待値と許容の幅は引数で渡す。渡されなければ「未判定（基準 tbd）」として
  数値だけを出す（台帳の criteria は提案のまま。Q5 で人が決める）
- 結果は 合格 / 不合格 / 未判定（台帳の記入の決まりと同じ）。「記録のみ」の項目は、引数で基準を渡さない限り未判定
- 出力の JSON・CSV はリポジトリの外に置く（CLAUDE.md 1.10。ログの生データを入れない）。出力には bag のファイル名
  だけを書き、ディレクトリのパスは書かない
- `p4_driver/` は別の流れ（ドライバだけを動かす道具）のもので、ここのスクリプトとは独立

## ファイル

| ファイル | 中身 |
|---|---|
| `bagio.py` | bag の読み取り（rosbag2_py、または純 Python の MCAP・SQLite3）と、PointCloud2・Imu の CDR の復号 |
| `bagstats.py` | topic ごとの時刻・点数・IMU の値の収集、統計、判定、出力の共通部分 |
| `t04_driver_topics.py` | T04-1・T04-2・T04-3・T04-5 と加速度の単位 |
| `t05_4_xt32_offset.py` | T05-4：XT-32 と MID-360 の header.stamp の差、各 topic の受信の遅れ |
| `t07_timeseries.py` | T07-2：点の数と周期の時系列の CSV（温度の topic の有無も表示） |
| `t08_3_tilt.py` | T08-3：地面の当てはめと内蔵 IMU の重力から roll・pitch、その差 |
| `tests/` | 合成した bag（MCAP と SQLite3）で回す pytest。`synth_bag.py` は読み取り側のコードを使わずに bag を書く |

## 使い方

ROS 2 の環境では先に `source /opt/ros/jazzy/setup.bash` をすると rosbag2_py で読む（`--reader auto` の既定）。
`python3 -I` で起動すると PYTHONPATH が効かず rosbag2_py が見つからないので、純 Python に切り替わる
（出力の「注」に出る）。どちらで読んでも、時刻・点数・値は同じになることを確かめてある（下の「試験」）。

共通の引数：`bag`（bag のディレクトリか、1 つの `.mcap`・`.db3`）、`--reader {auto,rosbag2_py,builtin}`、
`--window START END`（最初の受信からの秒。受信の時刻で切る）、`--json-out FILE`、`--json`（要約の代わりに JSON を出す）、
`--sha256`（bag のファイルの sha256。台帳の evidence 用）。

既定の topic：ドライバだけで動かす P4 は `/livox/lidar`（PointCloud2）と `/livox/imu`。製品の構成では
`/sensors/mid360/points`（IFD-59）を `--cloud-topic` で渡す。XT-32 は `/sensors/xt32/points`（IFD-21）。どれも引数で変えられる。

### T04（P4）

```
python3 t04_driver_topics.py <bag> --json-out <リポジトリの外>/t04.json
python3 t04_driver_topics.py <bag> --cloud-hz-expected 10 --cloud-hz-tol-pct 5 --imu-hz-expected 200 --imu-hz-tol-pct 5 \
    --points-expected 20000 --points-tol-pct 10 --latency-drift-max-ms-per-min <人が決める値> --expect-cloud-frame mid360_link
python3 t04_driver_topics.py <bag> --static-window 5 55     # 加速度のノルムを見る静止の区間
```

出すもの（点群と IMU のそれぞれ）
- T04-1：bag の topic と型、frame_id の一覧（`--expect-cloud-frame`・`--expect-imu-frame` を渡すと一致を判定）
- T04-2：周期（受信の時刻から：(件数 − 1) ÷ (最後 − 最初)、stamp から）。判定は受信の時刻からの周期
- 受信の間隔と header.stamp の間隔：平均・標準偏差（標本、ddof=1）・最小・最大・p1・p5・p50・p95・p99 [ms]
- stamp の逆行（受信の順で前より小さい）・連続の重複・全体の重複の件数、欠けの疑い（受信の間隔が中央値の
  `--gap-factor` 倍（既定 1.5）を超える数。表示だけで判定には使わない）
- T04-3：1 枚の点数（統計）、field の並び（名前・型・offset）、point_step、並びが途中で変わったか。判定は平均。
  `--points-expected` を渡すと、幅の外の枚数も出す
- 点ごとの時刻の field（`--point-time-field`、既定 `timestamp`）：最初の点 − stamp と 1 枚の中の時間の幅。単位は値の
  大きさから推定し、推定と明記する
- T04-5：受信の時刻 − header.stamp の統計と、その傾き（最小二乗、ms/分）。判定は傾きの絶対値
- MCAP を `--reader builtin` で読むと、送信の時刻（rosbag2 の send_timestamp）で「送信 − stamp」（ドライバの中の遅れ）と
  「受信 − 送信」（DDS の遅れ）に分けて出す。SQLite3 と rosbag2_py では送信の時刻が得られない
- 加速度：静止の区間のノルムの統計と、1 と 9.80665 のどちらに近いか（対数の比。判定ではなく表示）、角速度のノルム

### T05-4（P5）

```
python3 t05_4_xt32_offset.py <bag> --pairs-csv <外>/pairs.csv --json-out <外>/t05_4.json
python3 t05_4_xt32_offset.py <bag> --mid-topic /sensors/mid360/points --max-pair-gap-ms 30
```

- MID-360 の各フレームに、header.stamp が最も近い XT-32 のフレームを組にする。差の絶対値が `--max-pair-gap-ms`
  （既定：XT-32 の stamp の間隔の中央値の半分。データから決め、出力に書く）を超える組は捨てる
- 差 = stamp(MID-360) − stamp(XT-32) の統計。位相が回って周期だけ跳ぶ所をつないだ差と、その傾き（ms/分）、跳びの回数
- 各 topic の受信の遅れ（受信 − stamp）と、組ごとの遅れの差
- 読み方：2 台は別々に走査しているので、stamp の差の大きさは走査の位相を含み、それ自体は誤差ではない。DEC-442・
  PRM-55=1 ではどちらの stamp も PC の受信の時刻（下の「時刻の扱い」）。揺れ（標準偏差）と傾きが時刻の付け方の材料
- 台帳の基準は「記録のみ」。`--offset-std-max-ms`・`--latency-std-max-ms` を渡したときだけ判定する

### T07（P7）

```
python3 t07_timeseries.py <bag> --csv-out <外>/t07_frames.csv --bins-csv-out <外>/t07_bins.csv --bin-s 60
python3 t07_timeseries.py <bag> --csv-out <外>/t07_frames.csv --ref-hz <P4 の周期> --ref-points <P4 の点数> --tol-pct 5
```

- 1 行 1 枚の CSV：`frame, recv_rel_s, stamp_rel_s, recv_interval_ms, stamp_interval_ms, latency_ms, points`
  （時刻は区間の最初の受信からの秒。絶対時刻は書かない）
- `--bin-s` 秒（既定 60。解析の設定で、基準ではない）ごとの周期と点数の平均・最小・最大。最後の短い区間は
  `full: false` で、区間が 1 つしかないときを除いて判定に使わない
- 判定（T07-2「P4 から ±5% 以内」）：`--ref-hz`・`--ref-points` と `--tol-pct` を渡したときだけ。
  基準から最も離れた区間の値で判定する
- **温度：livox_ros_driver2（commit 2144554）には温度を出す topic がない。** T07-1 の温度は人が測る。
  確かめ方：リポジトリの写し `design/research/upstream_sensors/livox_ros_driver2_2144554/lddc.cpp`
  （sha256 37dcc252…、GitHub の同じ commit の `src/lddc.cpp` と一致）で、publisher を作るのは `CreatePublisher`
  （526〜554 行。PointCloud2・CustomMsg・PCL・Imu の 4 種。PCL は `#if 0` で無効）と ROS 1 の advertise だけ。同じ commit の `src/` の全ファイルを
  GitHub から読み、`create_publisher`・`advertise<` がほかにないことも確かめた（写しはリポジトリの外、2026-11-07）。
  なお、機器そのものは通信プロトコル（`livox_eth_protocol_mid360.md` v1.4.12、0x0102 の情報のプッシュ）の
  `core_temp`（0x8007、単位 0.01 °C）を持つが、ドライバはそれを topic にしない
- bag に名前に `temp` を含む topic か `sensor_msgs/msg/Temperature` があれば、名前だけを一覧に出す

### T08-3（P8）

```
# P4 の道具（p4_driver/run_driver.py）は点群の frame_id を mid360_link にし、IMU は livox_frame のまま（下の「frame」）
python3 t08_3_tilt.py <bag> --frame mid360_link --imu-in-cloud-rpy-deg 0 0 0 --up-hint-imu --json-out <外>/t08_3.json
python3 t08_3_tilt.py <bag> --frame livox_frame --up-hint <CAD からの上向き x y z> --max-diff-deg 0.5 --per-frame 20
```

- 方法 1（地面）：区間の全フレームの点を合わせ、近すぎる点（`--min-range`）・箱の外（`--roi`）を捨て、
  `--max-points` を超えたら seed 固定で間引く。制約なしの RANSAC で点の多い面から `--max-planes` 枚を順に取り出し、
  各面の inlier に最小二乗（重心まわりの SVD）で当て直す。法線はセンサーの原点の側を正にする。取り出した面のうち、
  法線と上向きの目安（`--up-hint`、`--up-hint-imu`）のなす角が `--max-hint-angle-deg` 以下（＝センサーより下の面）で、
  inlier の割合が `--min-inlier-ratio` 以上の面から、最も点の多い面を地面とする。取り出した面の一覧も出す
- 方法 2（IMU）：`--imu-window` の加速度の平均の向き（静止では重力の逆、上向き）
- 差：roll・pitch の差（地面 − IMU）と、2 つの上向きのなす角。判定は `--max-diff-deg` を渡したときだけで、
  |roll の差| と |pitch の差| の大きい方で見る。なす角が 90° を超えたら、IMU の符号か frame の取り違えを疑う注意を出す
- `--per-frame N`：N 枚を等間隔に選び、1 枚ずつ当てた roll・pitch の揺れも出す
- 地面より上の高さ（原点から面までの距離）も出す（TF の z の材料。T08-3 の判定には使わない）

roll・pitch の定義：上向きの単位ベクトル u を点群の座標で表し、roll = atan2(u_y, u_z)、
pitch = atan2(−u_x, √(u_y² + u_z²))。水平な座標からセンサーへの回転を Rz(yaw)·Ry(pitch)·Rx(roll) と書いたときの値
（ROS の RPY と同じ並び）。yaw は地面でも重力でも決まらない。

読むときの注意
- 方法 1 は床の面に対する傾き、方法 2 は重力に対する傾き。差には床そのものの傾きが入る。台帳の R-L-06 の案
  （その場で車体を 180° 回して 2 回測ると床の傾きが打ち消せる）は試験の手順なので人が決める
- 内蔵 IMU の加速度のゼロ g の初期誤差は ±40 mg（ICM-40609-D データシート DS-000330 Rev 1.2、Table 2、TYP、
  基板実装後。台帳 R-L-01）。Mid-360 に載っているのが -D 版か、Livox が校正しているかは未確認。この誤差の分だけ
  方法 2 はずれうる（台帳 R-L-05 の AI の見積もりで最大約 2.3°）。スクリプトはこの値を基準にも補正にも使わない

#### frame（混同しないための決まり）
- `--frame` は必須。bag の点群の frame_id と違えば止まる。`--imu-frame`（既定 `livox_frame`）も同じ
- 上流のドライバは IMU の frame_id を `livox_frame` に固定する（`lddc.cpp` 481 行）。点群の frame_id は parameter
  （`frame_id`）で変わる。P4 の道具と製品の構成（IFD-59、ND-20）は点群を `mid360_link` にするので、点群と IMU の
  frame_id が違う
- frame_id が違うときは、`--imu-in-cloud-rpy-deg R P Y`（IMU の座標から点群の座標への回転、Rz·Ry·Rx、度）を渡さない
  限り、方法 2 を点群の座標に移さず、差は未判定にする。スクリプトは回転を仮定しない
- 回転の材料：User Manual v1.2 の IMU Data の節（PDF 17 ページ）に、IMU の加速度・角速度の向きは点群の座標と同じ、
  IMU の位置は点群の座標で x 11.0・y 23.29・z −44.12 mm とある（AI が pdftotext で原文を読んだ）。ドライバは
  点群の座標を変換しない（外部パラメータは 0、ドライバ側の変換は無効：台帳 R-OF-08）ので、`mid360_link` の点群は
  ドライバの点群の座標そのまま。この 2 つから `0 0 0` を渡すかどうかは、使う人が判断する
- 加速度の符号（静止で上向きに +1 g が出るか）は Livox の資料で確かめていない（未確認）。逆なら上の注意が出る

#### 解析の設定の既定値と理由（基準ではない。値は出力の params に残る）

| 引数 | 既定 | 理由 |
|---|---|---|
| `--min-range` | 0.1 m | User Manual の Specifications（PDF 22 ページ）の近距離の死角 0.1 m。点がないときは (0,0,0) で来る（PDF 15 ページ）ので、これも捨てる |
| `--ransac-threshold-m` | 0.05 m | 同じ表の距離の偶然誤差（1σ）≤ 2 cm（10 m）、≤ 3 cm（0.2 m）。10 m で 2.5σ。床の凹凸が大きい所では変える |
| `--ransac-iters` | 1000 | 3 点の RANSAC で、地面の割合が 0.2 でも正しい 3 点を一度も引かない確率が (1 − 0.2³)^1000 ≈ 3×10⁻⁴ |
| `--max-planes` | 3 | 地面・壁・その他。屋内で壁が多いときは増やすか `--roi` を使う |
| `--min-inlier-ratio` | 0.1 | 地面と壁を取り除いた後の、点のまばらな所を斜めに切る面を地面に選ばないため |
| `--max-hint-angle-deg` | 30° | 目安と地面の法線のずれの許容。壁（約 90°）・天井（約 180°）とは分けられる |
| `--up-hint` | 0 0 1 | 水平の取り付けの場合。傾けた取り付けでは CAD の値か `--up-hint-imu` を使う（既定のままだと地面が選べず「出ない」になる。選べない時に別の面を選ばないことはテストで確かめた） |
| `--max-points`・`--seed` | 200000・0 | 計算の時間と、結果の再現 |

方法を選んだ理由（外れ値に強い方法）
- 地面の点のほかに、壁・物・車体の写り込みが多く入る。最小二乗だけでは外れ値に引かれる。M 推定（Huber など）は
  初期値が要り、外れ値が半分を超えると崩れる。RANSAC は外れ値が半分を超えても、点の多い面を選べる
- 最初は「目安の向きに近い候補だけで RANSAC」にしたが、合成のテストで、地面が目安の範囲の外にあると、地面を斜めに
  切る面（inlier 7 %、残差の RMS が閾値の約 0.6 倍）を地面として返した。そこで、制約なしで本当の面を先に取り出し、
  目安は面を選ぶのにだけ使う形にした（`tests/test_t08_3.py` の `test_default_hint_rejects_steep_ground`）
- 重い依存（Open3D・PCL）は足さず、numpy だけで書いた（下の「先行事例」）

## 時刻の扱い（解析の前提。出典つき）

rosbag2（ros2/rosbag2 の jazzy ブランチ commit 12b5e8b を 2026-11-07 に GitHub から読んだ。写しはリポジトリの外）
- 既定の保存形式は mcap（`rosbag2_storage/src/rosbag2_storage/default_storage_id.cpp` が `"mcap"` を返す）。
  ワークステーションの rosbag2 0.26.11（Jazzy）でも `ros2 bag record --help` が「defaults to 'mcap'」と出した
- 受信の時刻：記録した側の `rmw_message_info.received_timestamp`、送信の時刻：送り手の `source_timestamp`
  （`rosbag2_transport/src/rosbag2_transport/recorder.cpp` 792〜805 行のうち 801・802 行、use_sim_time なしの場合。use_sim_time ありでは
  受信の時刻が `node->now()`）
- MCAP：logTime＝受信、publishTime＝送信（`rosbag2_storage_mcap/src/mcap_storage.cpp` 873〜874 行）。
  SQLite3：`messages.timestamp`＝受信のみ（`sqlite_storage.cpp` 464〜469・542 行）
- rosbag2_py の `read_next()` は受信の時刻だけを返す（`rosbag2_py/src/rosbag2_py/_reader.cpp` 54〜55 行）
- 車載 PC に入っている rosbag2 の版での確認はしていない

livox_ros_driver2（commit 2144554。`src/comm/pub_handler.cpp` と `src/comm/comm.h` は GitHub から読み、リポジトリに写しはない）
- 同期なし（DEC-442）：パケットの時刻は受け取った瞬間の PC の時計（`pub_handler.cpp` の `GetEthPacketTimestamp`、
  265〜275 行）。点ごとの時刻 = パケットの時刻 + i × 点の間隔（391 行ほか）。フレームの header.stamp = そのフレームの
  最初の点の時刻（`GetLidarBaseTime` 281〜286 行、`lddc.cpp` 310〜316 行）
- PointCloud2 の `timestamp` field は、その点の時刻の ns を float64 にしたもの（`lddc.cpp` 328 行、`comm.h` の
  `LivoxPointXyzrtlt`：pack(1)、point_step 26、timestamp は offset 18 の double）。float64 の絶対 ns は約 256 ns の刻み
- 同期なしのときの発行は、PC の時計の一定の周期（`publish_freq`、既定 10 Hz）ごと（`pub_handler.cpp` 196〜207 行）
- IMU の header.stamp も受け取った瞬間の PC の時計（`pub_handler.cpp` 117 行）
- ここから、点群の「受信 − stamp」にはフレームを集める時間（約 1 周期）が入ると読める（コードを読んだうえでの推測。
  T04-5 で実測する）

加速度の単位
- 通信プロトコル（`livox_eth_protocol_mid360.md` v1.4.12、Data Type 0 の IMU Data の表）：gyro は rad/s、acc は g
- ドライバはそのまま `linear_acceleration` に入れる（`lddc.cpp` 490〜495 行。換算なし）。よって `/livox/imu` の加速度は
  g（ROS の決まりの m/s² ではない）。台帳 R-L-03・R-M-03 と同じ。実データで確かめるのが T04 の `unit_guess`
- 公式資料の場所：リポジトリの外の `TsukubaChallenge/Sensors/MID-360/official/INDEX.md`
  （プロトコルの sha256 728a33c8…、User Manual EN v1.2 の sha256 3f202c84…）

## bag の読み取り

- `--reader auto`（既定）：rosbag2_py があればそれ、なければ純 Python。`rosbag2_py`・`builtin` で固定できる
- 純 Python で読めるもの：MCAP（chunk なし・あり、chunk の圧縮なし・zstd・lz4、chunk の CRC を確かめる、
  Footer の前で切れたファイルは読めたところまで読んで印を付ける）、SQLite3（`.db3`、読み取り専用で開く）、
  bag のディレクトリ（`metadata.yaml` の `relative_file_paths`、なければ `*.mcap`・`*.db3`）と分割されたファイル
- 読めないもの：ファイル単位の圧縮（`.mcap.zstd` など）、rosbag2 のメッセージ単位の圧縮（中身が CDR でないので
  止まる）、XCDR2。どれも Jazzy の `ros2 bag record` の既定では使われない
- メッセージの本体の復号は、どちらの読み方でも `bagio.py` の CDR の復号（XCDR1、little・big endian）を使う

## 依存

新しい依存は足していない（setup.sh は変えていない）。
- 必須：Python 3.10 以上、numpy
- 任意：PyYAML（`metadata.yaml` を読む。なければファイル名で探す）、rosbag2_py（ROS 2）、zstandard・lz4
  （MCAP の chunk が圧縮されているときだけ）、pytest（テスト）
- 確かめた環境：この Mac（Python 3.13.9、numpy 2.3.5、zstandard・lz4 あり、rosbag2_py なし）、ワークステーション
  （Ubuntu 24.04・ROS 2 Jazzy、Python 3.12.3、numpy 1.26.4、pytest 7.4.4、rosbag2 0.26.11、lz4 あり・zstandard なし）。
  車載 PC では実行していない

## 試験

```
cd design/research/vehicle_pc/2026-11-06_mid360_connection/tools
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests
```

合成の条件（`tests/synth_bag.py` の `make_scenario`。期待値はこの条件と、生成した配列から決める）
- MID-360：10 Hz・100 枚、stamp の揺れ 0.5 ms（正規分布）、受信 − stamp は 105 ms から 30 ms/分で増える＋0.3 ms の揺れ、
  送信は受信の約 1 ms 前、点数 1500〜1560（7 枚周期）、Livox の field の並び（point_step 26）、点の時刻は絶対 ns
- 地面：センサーは高さ 0.60 m、roll 2.0°・pitch −35.0°。点の 70 % が地面（1 cm の揺れ）、15 % が壁、15 % が空中のごみ
- IMU：200 Hz、上向きは roll 2.2°・pitch −35.1°（地面との差 −0.2°・+0.1°）、加速度は g（1 件のテストは m/s²、
  1 件は符号を反転）、ノイズ 0.002
- XT-32：10 Hz、MID-360 より stamp が 23 ms 遅い、受信 − stamp は 30〜32 ms
- ほかに：stamp の逆行と重複、分割ファイル、zstd・lz4 の chunk、CRC の不一致、途中で切れた MCAP、big endian の CDR、
  frame_id の食い違い、IMU の座標の回転、天井のある場面、外れ値 60 % の場面

## 先行事例（CLAUDE.md 1.11）

探した場所：リポジトリの中（`mcap_min`・`RANSAC`・`rosbag` で検索）、PyPI（JSON API、2026-11-07）、
ROS 2 Jazzy の rosbag2 のソース、台帳の references（R-I-01 など）。

| 候補 | 採否 | 理由 |
|---|---|---|
| リポジトリの `design/research/vehicle_pc/2026-10-14_evening_scripts/mcap_min.py`・`extract_bag.py` | 設計を流用 | 外部の依存なしの MCAP の読み取りと CDR の復号、XT-32 の地面の RANSAC。publishTime・SQLite3・CRC・切れたファイル・big endian・frame の検査を足して書き直した（元のファイルは変えていない） |
| rosbag2_py（ROS 2 Jazzy の rosbag2、Apache-2.0） | 採用（あれば使う） | Jazzy の公式。車載 PC とワークステーションには入る。ただし送信の時刻を返さない。Mac にはない |
| rosbags（Ternaris、PyPI 0.11.9、Apache-2.0、Python 3.10 以上） | 不採用 | 純 Python で MCAP・SQLite3 の両方を読める。この Mac にも車載 PC にも入っておらず、setup.sh の外の導入になる。保守の状況・実機での使用例は未調査。入れる場合は純 Python の読み取りの置き換えの候補 |
| mcap（Foxglove、PyPI 1.6.0、MIT）と mcap-ros2-support（0.6.0、ライセンスは PyPI に記載なし） | 不採用 | MCAP だけで SQLite3 を読めない。入っていない |
| `ros2 topic hz`・`ros2 bag info` | 補助 | 周期と件数は出るが、stamp の揺れ・逆行・受信の遅れ・点数の時系列は出ない |
| Open3D `segment_plane`（PyPI 0.20.0、MIT） | 不採用 | RANSAC の面の当てはめ。依存が重く（車載 PC に入っていない）、ここでの用途は numpy で足りる |
| PCL の SACSegmentation、Autoware の extrinsic_ground_plane_calibrator（台帳 R-I-01） | 不採用 | C++・Autoware の依存。同じ RANSAC の系統。Autoware の中身と Jazzy での動作は未確認 |

## 確かめられなかったこと

- 実機の MID-360 の bag では一度も動かしていない（P4 は未実行）。点の時刻の field の単位、加速度の単位と符号、
  frame_id、受信の遅れは、実機の bag で T04 を回して確かめる
- 車載 PC に入っている rosbag2・numpy の版、zstandard の有無
- 加速度の符号の向き（静止で上向きに +1 g か）の Livox の資料での裏付け
- Mid-360 の IMU が ICM-40609-D か、Livox の校正の有無（台帳 R-L-01 と同じ）
- T04-4（帯域・CPU）は対象の外（rosbag からは出せない。`ros2 topic bw`・`top` で測る）
