# P4：Gouda を起動せずに livox_ros_driver2 だけを動かす道具（流れ E）

- 状態：**実装済み・ソフト上で確認済み（この Mac の単体テスト、ROS なし）・実車未検証**。ROS の上での起動（`ros2 run`・`ros2 bag record`）は一度も実行していない
- 許可：DEC-474・DEC-475（`design/revisions/REV-259.yaml`）の E
- 計画：`design/proposals/mid360_connection_test_plan_2026-11-06.md` の P4（85〜95 行、提案）。結果は台帳 `../../ledger.yaml` の T04-1〜T04-6 に書く
- 上流：livox_ros_driver2 2144554（`third_party/drivers.repos` の固定）。リポジトリの写しは `design/research/upstream_sensors/livox_ros_driver2_2144554/`。写しにない file（`comm.h`・`lddc.h`・`pub_handler.cpp`・`lds_lidar.cpp` など）は、同じ commit をリポジトリの外に clone して読んだ。下の行番号はその commit のもの

## 1. ファイル

| ファイル | 役割 |
|---|---|
| `make_config.py` | mid360.json（IFD-61）と、ドライバの雛形（`share/livox_ros_driver2/config/MID360_config.json`）から、P4 のドライバの設定を書く |
| `run_driver.py` | ドライバだけを `ros2 run` で起動する（`--dry-run` でコマンドの表示だけ） |
| `record_bag.py` | T04-6：点群と IMU を rosbag に記録する（`--dry-run` でコマンドの表示だけ） |
| `p4_common.py` | 共通部分（製品の `gouda_core.mid360_config` の import、topic 名、`-p` の値の書き方） |
| `test_p4_driver.py` | 単体テスト（ROS なし） |

コードの前提：

- 製品の `gouda_core/gouda_core/mid360_config.py`（REV-242）を、このフォルダと同じ checkout から import する（写していない）。設定の作り方（`read_local`・`find_template`・`write_driver_config`）、起動の parameter（`driver_parameters`）、パッケージ・実行ファイル・node の名前は、すべて製品の関数と定数から取る
- **2026-11-07 の時点で、`mid360_config.py` は HEAD 9c449b5 に入っておらず、作業ツリーにだけある（未追跡）**。Dell で使うには、REV-242 のコードとこのフォルダが入った commit が Dell の checkout に要る（commit・push・Dell の更新は人）。無ければ、道具は `mid360_config.py not found` で止まる
- Python 3 の標準ライブラリだけ。ROS は Dell で実際に起動するときだけ要る

## 2. 上流のドライバの parameter（2144554 で確かめたこと）

ROS 2 の node は `src/livox_ros_driver2.cpp:131-146` で次を宣言して読む。

| parameter | 型 | コードの既定 | `msg_MID360_launch.py` | P4 | 意味（出典） |
|---|---|---|---|---|---|
| `xfer_format` | int | 0 | 1 | **0** | 0＝PointCloud2、1＝Livox の CustomMsg、2＝PCL の型（ROS 2 では未対応：エラーを出して何も出さない、`lddc.cpp:234-243`）。値は `lddc.h:42-47` |
| `multi_topic` | int | 0 | 0 | 渡さない（0） | 0＝全 LiDAR で `livox/lidar`・`livox/imu`。1＝LiDAR ごとに `livox/lidar_<アドレス>`（`lddc.cpp:642-690`） |
| `data_src` | int | 0 | 0 | 渡さない（0） | 0＝LiDAR から直接。ほかは `Invalid data src` を出してデータなし（`livox_ros_driver2.cpp:162-182`） |
| `publish_freq` | double | 10.0 | 10.0 | 渡さない（10.0） | 点群の 1 枚の区切りの周期。0.5〜100 に丸める（`livox_ros_driver2.cpp:148-154`）。double で宣言しているので、渡すなら `10.0` の形 |
| `output_data_type` | int | 0 | 0 | 渡さない（0） | 0＝ROS に publish。1＝bag への書き込み（ROS 1 だけ。ROS 2 では何も出ない、`lddc.cpp:343-350`） |
| `frame_id` | string | `frame_default` | `livox_frame` | **`mid360_link`** | 点群の header.frame_id だけ（`lddc.cpp:263`）。IMU は `livox_frame` に固定（`lddc.cpp:481`） |
| `user_config_path` | string | `path_default` | share の `config/MID360_config.json` | **make_config.py の出力** | ドライバ（`parse_livox_lidar_cfg.cpp:31`）と SDK（`lds_lidar.cpp:142`）が開く JSON |
| `cmdline_input_bd_code` | string | `000000000000001` | `livox0000000001` | 渡さない | 読むが使っていない（`livox_ros_driver2.cpp:169-170`） |
| `lvx_file_path` | string | `/home/livox/livox_test.lvx` | 同じ | 渡さない | 宣言だけで、ROS 2 では読まない |

ほかに分かったこと：

- node 名：コードは `livox_driver_node`、上流の launch は `livox_lidar_publisher`、製品（ND-20）は `livox_ros_driver2`
- publisher：`create_publisher(topic, 256)`（`kMinEthPacketQueueSize` 32 の 8 倍、`comm.h:49`・`lddc.cpp:659-660・684-685`）。rclcpp の既定なので reliable・volatile・keep last 256。publisher は最初のデータが来たときに作られる。データが来ないと topic は現れない
- PointCloud2 の field：x・y・z・intensity（float32）、tag・line（uint8）、timestamp（float64）。`point_step` は 26（`#pragma pack(1)` の構造体、`comm.h:148-158`）、height 1、点数は width（`lddc.cpp:262-304`）
- 時刻（同期なし）：header.stamp は、その枚の最初の点の時刻＝PC が packet を受けた時刻（`pub_handler.cpp:265-275` の `high_resolution_clock::now()`）。IMU も同じ。各点の `timestamp` は、相対ではなく絶対の時刻（ns）を float64 にしたもの（`lddc.cpp:328`、`pub_handler.cpp:391`）。今の時刻の大きさでは float64 の刻みは 256 ns（計算）
- 同期なしの枚の区切りは PC の時計で `publish_freq` ごと（`pub_handler.cpp:196-205`）
- 配信は起動の 3 s 後から（点群と IMU の thread が 3 s 待つ、`livox_ros_driver2.cpp:199・209`）
- 版：`src/include/livox_ros_driver2.h` は 1.2.8（計画 4 章の表の 1.2.6 は Release の版）。起動のログの `Livox Ros Driver2 Version:` で確かめる

## 3. 決めたこと（自律判断）と理由

- **frame_id は製品と同じ `mid360_link`**（ドライバの既定にしない）
  - P4 の結果（T04-1 の frame_id、T04-6 の bag）を、製品の ND-20 の設定の確認にそのまま使える。bag を後で製品の経路（mid360_scan など）に流して試すときも frame が合う
  - frame_id は header の文字列だけで、点の座標は変わらない（外部パラメータは 0、変換はしない）。どちらにしても測る値は同じ
  - ドライバの既定はコードと launch で違う（`frame_default` と `livox_frame`）ので、「既定」を一つに決められない
  - rviz2 で見るときは Fixed Frame を `mid360_link` にすれば、TF なしで点群が出る（IMU は `livox_frame`）
- **起動は `ros2 run ... --ros-args -r __node:=... -p ...`**（上流の launch を使わない）
  - `msg_MID360_launch.py` には launch の引数がない。xfer_format 1 と share の雛形の JSON が launch の中に書いてあり、変えるには install 先の file を書き換えることになる（JSON を変えたら build.sh をやり直す、RD #116）
  - 自分の launch file を足すより、`ros2 run` の方が「ドライバだけ」を直接表し、渡した parameter がコマンドの 1 行に全部見える
  - node 名は製品と同じ `livox_ros_driver2`。parameter は製品の `driver_parameters` と同じ 3 つ（xfer_format・frame_id・user_config_path）だけを渡し、ほかはドライバの既定のまま（製品と同じ）。topic は remap しない（`/livox/lidar`・`/livox/imu`）
  - 文字列の parameter は、YAML として読まれても文字列のままになる形にする（`/a #b/x.json` のような path は引用符で囲む）
- **mid360.json は、アドレス（host_ip・lidar_ip）だけで P4 を進める**。製品の `read_local` の問題のうち、取り付けの値の不足は P4 を止めず、note として表示する（ドライバの設定は取り付けの値を使わない。取り付けは P8 の後に測る、DEC-457）。file がない・読めない・アドレスが不正なときは止まる
- **mid360.json は `--mid360-json <folder>/mid360.json` で受ける**。製品の `read_local` が「folder の中の `mid360.json`」を読む作りなので、file 名は `mid360.json` に限る
- **rosbag は、決めた秒数の後に SIGINT を 1 回だけ送り、閉じ終わるまで時間の制限なしで待つ**（`gouda.sh stop` が rosbag の保存を待つのと同じ、DEC-174）
  - `timeout` を使わない理由：`timeout` は子と process group の両方に signal を送るので、SIGINT が 2 回届きうる。Jazzy の `ros2 bag record` は SIGINT を KeyboardInterrupt で受けて片付けるので、2 回目で片付けが途切れるおそれがある（推測）。SIGTERM の扱いは rosbag2 0.26.9 から（0.26.0〜0.26.8 にはない。上流の tag を読んで確かめた）
  - topic は位置引数で渡す。`--topics` は 0.26.4 からで、Dell の rosbag2 の版は確かめていない。0.26.4 以降は deprecation の警告が出るが、記録は同じ
  - storage は rosbag2 の既定（Jazzy では mcap）。製品の recorder（`gouda_core/recorder_node.py`）も既定のまま
  - `--disable-keyboard-controls` を付ける（記録が端末を読まない）
- **DDS の設定は道具に入れない**。どちらで測るかは人が選ぶ（4 章の手順 2、6 章の 2）

## 4. 人が Dell で行う手順

`<workspace>` は Gouda の作業場所（例 `~/gouda_ws`）、`<repo>` は `<workspace>/src/` の下の checkout。出力はリポジトリの外（例 `~/mid360_p4`）に置く。

0. 前提
   - 計画の P2（リンク・アドレス）が済んでいる。MID-360 は Dell の内蔵の有線の口に直結し、XT-32 のケーブルは抜く（計画 2 章）。どの接続の設定を有効にするかは人が決める
   - A2（`bash setup.sh`）が済み、`<workspace>_livox/install` にドライバがある
   - Livox Viewer 2 は閉じる（6 章の 5）
1. Gouda が動いていないことを確かめる
   ```
   bash <repo>/gouda.sh status
   ```
   - `not running` なら 2 へ
   - `running` なら、Gouda を止めずに `/mode/state` を読む（`ros2 topic echo --once /mode/state`。`gouda.sh status` は前の `previous_mode_record.json` も出す）。その値を添えて、P4 をどうするか（Gouda を止めるか、別の時にするか）を人が決める（計画 51 行）。AI が手順を代わりに進めている場合、AI は止めずに人に聞く
2. 端末の準備（ドライバ・確認・記録に使う端末のすべてで同じにする）
   ```
   source /opt/ros/jazzy/setup.bash               # ~/.bashrc で読まれていれば不要
   source <workspace>_livox/install/setup.bash
   ros2 pkg prefix livox_ros_driver2              # <workspace>_livox/install/livox_ros_driver2 が出る
   ```
   DDS の設定を選ぶ（6 章の 2）。どちらで測ったかを台帳の session の notes に書く
   - a：既定のまま（何もしない）
   - b：製品と同じ。`export FASTRTPS_DEFAULT_PROFILES_FILE=<workspace>/gouda_data/run/fastdds_profile.xml`（前の `gouda.sh start` で書かれたもの）。無ければ `python3 -m gouda_core.dds_profile <repo>/design/generated/params ~/mid360_p4/fastdds_profile.xml` で作り、そのパスを使う
3. mid360.json（IFD-61）を用意する：`<workspace>/gouda_data/config/mid360.json`
   - P4 で要るのは `host_ip`（有効にした接続の設定での PC のアドレス）と `lidar_ip`（P2 で確かめた MID-360 のアドレス）だけ。形式は `gouda_core/gouda_core/mid360_config.py` の冒頭
   - 取り付けの値（`mid360_mount_*`・`mid360_axis_mapping`）は P4 では使わない。無ければ make_config.py が note を出す
   - リポジトリには入れない
4. ドライバの設定を作る
   ```
   cd <repo>/design/research/vehicle_pc/2026-11-06_mid360_connection/tools/p4_driver
   mkdir -p ~/mid360_p4
   python3 make_config.py --mid360-json <workspace>/gouda_data/config/mid360.json --out ~/mid360_p4/MID360_config.json
   ```
   表示の `changed from the template:` が 5 つのアドレスの項目だけで、`extrinsic_parameter` がすべて 0 であることを見る。雛形は読み込んだ ROS の環境から探す（`--template` で直接も渡せる）
5. ドライバだけを起動する（端末 1。止めるのは Ctrl-C）
   ```
   python3 run_driver.py --config ~/mid360_p4/MID360_config.json --dry-run    # 組み立てたコマンドを見る
   python3 run_driver.py --config ~/mid360_p4/MID360_config.json
   ```
   - 出るはずのログ（ソースから。未実行）：`Livox Ros Driver2 Version: 1.2.8`、`Data Source is raw lidar.`、`Config file : <path>`、`Init lds lidar success!`、データが来てから `livox/lidar publish use PointCloud2 format`・`livox/imu publish use imu format`
   - ログを file に残すなら（任意）：`python3 run_driver.py ... 2>&1 | tee ~/mid360_p4/driver_<日時>.log`。パイプにすると、std::cout の行の表示が遅れることがある（推測）。リポジトリには入れない（6 章の 7）
6. 別の端末（2 と同じ準備）で T04-1〜T04-5 を確かめる（5 章）
7. T04-6 を記録する
   ```
   python3 record_bag.py --out ~/mid360_p4/t04-6_<日時>
   ros2 bag info ~/mid360_p4/t04-6_<日時>
   ```
8. 終わり：端末 1 で Ctrl-C。bag とログはリポジトリの外に置いたまま、台帳には file 名と sha256 を書く（作った MID360_config.json の sha256 は書かない、6 章の 8）

## 5. 確かめる点（T04-1〜T04-6）

「ソースから」の欄は、上流のソースと仕様から読んだ期待で、実機では未確認。合否の基準は計画の案（人が決める、Q5）。

| ID | コマンド（例） | 見る点 | ソースから |
|---|---|---|---|
| T04-1 | `ros2 topic list -t`<br>`ros2 topic echo --once --field header /livox/lidar`<br>`ros2 topic echo --once --field header /livox/imu`<br>`ros2 topic info -v /livox/lidar`<br>`ros2 param get /livox_ros_driver2 xfer_format`（frame_id・user_config_path も） | topic・型・frame_id・QoS・parameter | `/livox/lidar` は `sensor_msgs/msg/PointCloud2`・`mid360_link`、`/livox/imu` は `sensor_msgs/msg/Imu`・`livox_frame`。reliable・volatile・keep last 256。データが来ないと topic が出ない |
| T04-2 | `ros2 topic hz /livox/lidar`、`ros2 topic hz /livox/imu` を 60 s（Ctrl-C で止める） | 平均・揺れ | 点群は 10 Hz（publish_freq 10.0）。IMU は 1 packet ごとに 1 message（仕様の既定 200 Hz） |
| T04-3 | `ros2 topic echo --once --field fields /livox/lidar`<br>同じく `--field width`・`--field height`・`--field point_step` | field と 1 枚の点数 | 2 章の 7 つの field、point_step 26、height 1、点数＝width。仕様からは 1 枚およそ 20,000 点（200,000 点/s を 10 Hz で割る、計算。点数は枚ごとに違う） |
| T04-4 | `ros2 topic bw /livox/lidar` を 60 s<br>`top -p "$(pgrep -d, -f lib/livox_ros_driver2/livox_ros_driver2_node)"` を 60 s | 帯域、ドライバの CPU | 1 枚およそ 0.52 MB（20,000 点 × 26 B）、10 Hz でおよそ 5.2 MB/s（計算）。`ros2 run` はドライバを子の process として起動する（ros2cli jazzy の `ros2run/api`）。この pattern は子（ドライバ本体）にだけ合う。`pgrep -f` は PID だけを出す（`-a` は付けない） |
| T04-5 | 解析スクリプト（流れ B。ここでは作らない）を T04-6 の bag に使う | header.stamp と受信の時刻の差 | 同期なしでは header.stamp は PC の受信の時刻（2 章）。各点の timestamp は絶対の ns |
| T04-6 | `python3 record_bag.py --out ~/mid360_p4/t04-6_<日時>`、`ros2 bag info <out>` | 記録の長さ、topic ごとの message の数 | 60 s の後に SIGINT を 1 回。bag の Duration は最初と最後の message の間なので、起動にかかった分だけ 60 s より短くなりうる（推測）。大きさはおよそ 5.2 MB/s × 60 s ≈ 310 MB（計算。IMU は小さい） |

## 6. 気になる点（道具には入れていない）

1. **計画 88 行と違う**：計画は「起動は `ros2 launch livox_ros_driver2 <launch>` のみ」。上流の launch が引数を持たないため `ros2 run` にした（3 章）。Gouda を起動しない点は同じ。計画の文言を直すかは人が決める（計画は提案）
2. **DDS の受け渡しで結果が変わりうる**：1 枚はおよそ 520 KB（計算）。Jazzy の Fast DDS（2.14.x）の共有メモリの segment の既定は 512 KiB＝524,288 B（Fast-DDS 2.14.x の `src/cpp/rtps/transport/shared_mem/SharedMemTransport.cpp:57`）。点数が少し多い枚は segment に入らず UDP に回るかもしれない（推測）。製品は大きな segment の profile（PRM-101、`gouda_core/gouda_core/dds_profile.py`）を全 process に渡している。既定のままの T04-2〜T04-4 は、ドライバではなく DDS の受け渡しで悪く出るかもしれない。比べたいときは a・b の両方で測る
3. **IMU の frame_id は `livox_frame` に固定**（`lddc.cpp:481`）。frame_id の parameter は点群だけに効く。製品の launch（`gouda_core/launch/gouda_nav2.launch.py:86-88`）は IMU を remap しないので、製品でも IMU は `/livox/imu`・`livox_frame` のまま出る。`livox_frame` は TF にない。正本の不足として流れ D で扱う予定（REV-259 の要約：内蔵 IMU、livox_frame）
4. **ドライバは接続のたびにセンサー本体に書き込む**：JSON の `pcl_data_type`（1）・`pattern_mode`（0）・`extrinsic_parameter`（0）を送る（`livox_lidar_callback.cpp:60-106`）。前に誰かが本体に取り付けの値を書いていても、P4 で 0 に書き換わる（本体に残るかは未確認、計画 165 行）。前の値を残したいなら、P4 の前に Livox Viewer 2 で読んでおく。製品も同じ動き
5. **Livox Viewer 2 と同時に動かさない**：どちらも PC 側の同じポート（host_net_info の 56101〜56501 など）を使うので、同時だとドライバが受けられない可能性がある（推測。SDK の socket の設定は確かめていない）
6. **host_ip は、そのとき有効な口のアドレスでなければならない**：SDK はそのアドレスに socket を作る（Livox-SDK2 c0796f0 の `sdk_core/device_manager.cpp:306-`）。ROS 2 では SDK の画面への log を止めており（`lds_lidar.cpp:131`）、file にも書かない（Livox-SDK2 `sdk_core/base/logging.cpp:28`）。失敗しても理由は出ず、`Failed to init livox lidar sdk.` や `Init lds lidar fail!` だけになる（推測。どの行が出るかは未実行）。その場合もドライバは終わらず、データなしで動き続ける（`livox_ros_driver2.cpp:175-185`）。T06-4 の材料
7. **ドライバの画面の出力にはアドレスが出る**：例えば `set pcl data type, handle: <アドレスを数にしたもの>`（`livox_lidar_callback.cpp:66`）。ログや画面の写しを issue・台帳に貼らない
8. **作った MID360_config.json にはアドレスが入る**。その sha256 も台帳に書かない（同じサブネットのアドレスを総当たりすれば元に戻せる）。bag には、multi_topic 0 ならアドレスは入らない（推測：topic 名・frame_id・データにアドレスはない）。multi_topic 1 にすると topic 名にアドレスが入る（2 章）
9. **取り付けの値がなくても P4 は進む**が、製品の MID-360 の経路（PRM-142 が true のとき）は、mid360.json の取り付けの値が揃うまで起動しない（`gouda_nav2.launch.py` の `_mid360_ready` が `read_local` の問題を見る）
10. **publish_freq を変える場合は小数で渡す**（`-p publish_freq:=20.0`）。整数で渡すと、宣言の型（double）と違うので起動で失敗するはず（rclcpp の parameter の型の決まり。推測、未実行）。この道具は publish_freq を渡さない（製品と同じ 10.0）
11. **A1（流れ A：build.sh でなく colcon で作る、DEC-475）** の後も、別の作業場所 `<workspace>_livox` は保つ（DEC-475）。この手順は変わらない見込み（推測）
12. **道具に入れていない確認**：Gouda や Livox Viewer 2 が動いているか、出力先がリポジトリの外か、は道具では見ない（指示どおり、手順で人が見る）

## 7. テスト（ROS なし）

```
python3 -I -m unittest discover -s design/research/vehicle_pc/2026-11-06_mid360_connection/tools/p4_driver -p 'test_*.py' -v
```

- make_config.py：リポジトリの写しの雛形と、文書用の範囲（RFC 5737）から実行時に作ったアドレスで、変わるのが 5 つのアドレスの項目だけ、外部パラメータが 0（x・y・z は整数のまま。ドライバは `GetInt` で読む、`parse_livox_lidar_cfg.cpp:137-150`）、製品の `driver_config` と同じ結果、表示にアドレスが出ないこと。アドレスの不足・不正、file がない、file 名が違う、雛形の外部パラメータが 0 でない、ROS がなく `--template` もない、の各場合に止まること
- run_driver.py・record_bag.py：`--dry-run` のコマンドの文字列（製品の名前・parameter と同じ、topic の remap なし、相対 path は絶対 path に、引用符が要る path）
- record_bag.py の止め方：ros2 bag record の代わりの process で、SIGINT が 1 回だけ届き、片付けの終わりまで待つこと。先に終わった process には signal を送らないこと
- このフォルダの file に IPv4 のアドレスがないこと

2026-11-07、Mac（Python 3.13.9、ROS なし）、HEAD 9c449b5＋作業ツリー（`mid360_config.py` は未追跡）で 19 件合格。Dell（Python 3.12、ROS あり）では未実行。
