# Gouda — つくばチャレンジ自律走行ロボット（Ubuntu 24.04 / ROS 2 Jazzy）

Gouda の車載 PC で動かすソフトウェアと、その設計の正本です。

- 地図作成（GLIM）と、原図から各種の地図（Nav2 用の 2D 地図、3D 点群地図、確認用の傾き・段差・高さの図）への変換
- ブラウザの操作画面（gouda_monitor）：運行、発進準備、地図、waypoint、記録、設定のタブ
- センサー（XT-32、ADIS16607-2）のドライバの起動と、USB の抜き差しの検知
- 記録（log と rosbag）、モードの管理、車体への出力（ESP32 firmware v4。実車には未投入）

現状と、人の判断を待っている事項は [design/reports/status.md](design/reports/status.md) にあります。実車での走行（自律走行）は、まだ人が「投入してよい」と判断していません。

## コマンドの一覧

| いつ | コマンド（リポジトリのフォルダで実行） |
|---|---|
| 初回（何も入っていない PC） | `bash setup.sh`（[§1](#1-pc-のセットアップ初回)） |
| 起動・停止・状態 | `bash gouda.sh start` ／ `bash gouda.sh stop` ／ `bash gouda.sh status` |
| 2 回目以降（更新） | `bash gouda.sh stop` → `bash update.sh` → `bash gouda.sh start`（[§3.1](#31-通常の更新)） |
| `update.sh` がない古い版が入っている PC | 1 回だけ [§3.2](#32-古い版からの更新1-回だけ)。次回から 2 回目以降と同じ |

起動の方法は `gouda.sh` だけです。環境変数や起動オプションはありません（DEC-090・DEC-091）。

## 1. PC のセットアップ（初回）

対象は Ubuntu 24.04（amd64 または arm64）です。インターネット接続と sudo 権限が要ります。ワークスペースは `~/gouda_ws` とし、リポジトリはその `src/` の下に置きます（この配置は必須）。

```bash
sudo apt update && sudo apt install -y git
mkdir -p ~/gouda_ws/src && cd ~/gouda_ws/src
git clone https://github.com/K-yama-20/tsukuba-autonomous-robot.git
cd tsukuba-autonomous-robot
bash setup.sh
```

`setup.sh` は次を行います。足りないものがあるときだけ sudo のパスワードを聞きます。何度実行しても、すでにあるものはそのままです。

1. ROS 2 Jazzy（desktop）、ビルドの道具、Python のモジュール、GLIM 1.2.2（GLIM の PPA。設計はこの版で確認した：DEC-062）
   - すでに別の版の GLIM が入っている場合は止まります。版を変えるのは設計の判断です。
2. センサーのドライバ（`~/gouda_ws/src/HesaiLidar_ROS_2.0`、`~/gouda_ws/src/ADI_IMU_TR_Driver_ROS2`）
   - [third_party/drivers.repos](third_party/drivers.repos) に書いた commit を使い、改変しません（DEC-075）。
   - ドライバにローカルの変更があると止まります。旧実装の `scripts/setup.sh` はドライバに patch を当てていました（[§3.2](#32-古い版からの更新1-回だけ) を参照）。
3. rosdep（gouda_core、gouda_interfaces、2 つのドライバの依存）
4. シリアルポートを使うための dialout グループ（IMU、ESP32）。追加したときは、一度ログアウトしてログインし直します。
5. ビルド：`colcon build --symlink-install`（gouda_interfaces、gouda_core、2 つのドライバ）
6. LiDAR 用の LAN と時刻同期の確認
   - PC 側のアドレス（PRM-51：192.168.1.100）を持つ LAN がなければ、有線 LAN の一覧から選んで NetworkManager の接続を追加できます（Enter で省略）。
   - デフォルトルートのある LAN にこのアドレスを付ける古い接続があると、警告と削除のコマンドを表示します。
   - 時刻同期（NTP）が切れていると、有効にするコマンドを表示します。

LiDAR 用の接続を後から手で追加する場合（`<IF>` は USB-LAN などのインタフェース名。`ip link` で確認）：

```bash
sudo nmcli connection add type ethernet con-name gouda-lidar-<IF> ifname <IF> ipv4.method manual ipv4.addresses 192.168.1.100/24 ipv4.never-default yes ipv6.method disabled
```

## 2. 起動・停止

```bash
cd ~/gouda_ws/src/tsukuba-autonomous-robot
bash gouda.sh start     # 全部を起動（起動直後は手動走行。記録は開始しない）
bash gouda.sh status    # 起動状態・データの置き場・ログ・monitor の URL
bash gouda.sh stop      # この起動が所有するプロセスだけを止める
```

- monitor（操作画面）は `gouda.sh start` が表示する URL（http://127.0.0.1:8080/、PRM-26）を、この PC のブラウザで開きます。
- センサーのドライバは gouda_sensor_supervisor が起動します。デバイスがなければ接続を待ち、USB が繋ぎ直されたときだけドライバを作り直します（[design/docs/sensor_supervision.md](design/docs/sensor_supervision.md)）。
- **IMU の既知の問題**：`gouda.sh` を止めて起動し直すと、IMU が応答しないことがあります。運行タブの SENSORS 表で IMU が届いていなければ、IMU の USB を抜き差ししてください。
- 設定値はすべて `design/generated/params`（正本 `design/model.yaml` から生成）から読みます。未確定の値は空のままで、推測で埋めません。

## 3. 更新（2 回目以降）

すでに Gouda が入っている PC を最新の main にします。リポジトリのフォルダに `update.sh` があるかで手順が分かれます。

```bash
ls ~/gouda_ws/src/tsukuba-autonomous-robot/update.sh
```

| `update.sh` | 手順 |
|---|---|
| ある | [§3.1](#31-通常の更新) |
| ない（古い版） | [§3.2](#32-古い版からの更新1-回だけ) を 1 回だけ。次回からは §3.1 |

### 3.1 通常の更新

```bash
cd ~/gouda_ws/src/tsukuba-autonomous-robot
bash gouda.sh stop
bash update.sh
bash gouda.sh start      # IMU が届かなければ IMU の USB を抜き差し
```

`update.sh` は次を行います。

1. Gouda が起動中のとき、またはこのリポジトリの管理下のファイルにローカルの変更があるときは、何も変えずに止まります。
2. origin の main を取得し、main に切り替えて fast-forward します（merge や rebase はしません）。
3. `setup.sh` を実行します。新しい版に必要なパッケージを入れ、ドライバの commit が変わっていれば合わせ、ビルドします。

### 3.2 古い版からの更新（1 回だけ）

`update.sh` がない版（`gouda.sh` または旧実装の `scripts/gouda.sh` で起動していた版）が入っている PC で行います。

旧実装の版（`scripts/gouda.sh` がある版）では、先に次を行います。

```bash
# 旧 scripts/setup.sh がドライバに当てた patch を退避する（消さずに残る。これがあると setup.sh が止まる）
git -C ~/gouda_ws/src/HesaiLidar_ROS_2.0 stash --include-untracked
git -C ~/gouda_ws/src/ADI_IMU_TR_Driver_ROS2 stash --include-untracked
# 旧実装のスマホ用サービスを入れていた場合は止める（ログイン時に自動で起動するため）
systemctl --user disable --now gouda-phone-gateway.service
```

そのあと、どの古い版でも次を行います。

```bash
cd ~/gouda_ws/src/tsukuba-autonomous-robot
bash gouda.sh stop                 # 旧実装の版では: bash scripts/gouda.sh stop
git fetch origin
git switch -C main origin/main     # 手元の main を origin の main に合わせる
bash setup.sh
bash gouda.sh start
```

## 4. 実機の接続

| 機器 | 接続 | 設定（正本の値） |
|---|---|---|
| LiDAR（Hesai XT-32） | 専用の有線 LAN（USB-LAN） | XT-32 192.168.1.201（PRM-50）、PC 192.168.1.100/24（PRM-51）、UDP 2368（PRM-52）、PTC 9347（PRM-53）、600 rpm＝10 Hz（PRM-60。起動時にドライバが設定） |
| IMU（ADIS16607-2） | USB | `/dev/serial/by-id/usb-STMicroelectronics_STM32_Virtual_ComPort_007137944B34-if00`（PRM-54）。ttyACM 番号は使いません。100 Hz（PRM-56） |
| ESP32（車体） | USB シリアル | firmware v4。デバイス名（PRM-61）と DAC 電圧（DEC-077）は未確定で、書き込みは未実施 |

- 点群の時刻は PC の受信時刻です（XT-32 の内部時刻は年単位でずれているため。DEC-083）。
- GLIM のためのセンサーの取付位置は、monitor の設定タブで人が入力します（RQ-I081）。

**開発用の VM（Mac の Parallels）で動かす場合**

- USB-LAN と IMU を VM に接続します（Parallels のデバイスメニュー）。
- 動かしている間は Mac をスリープさせないでください。スリープすると VM が止まり、USB-LAN が外れ、VM の時計がずれます。

## 5. 地図の作成と変換

1. 運行タブの SENSORS 表で、点群と IMU が届いていることを確かめます。届いていなくても開始はできますが、警告が出ます。
2. 「地図作成開始」で GLIM が起動し、記録も自動で始まります。車体を動かして、「地図作成終了」で終えます。
3. 原図（GLIM の dump）が地図データベースに登録され、変換が自動で走ります。
4. 「地図」タブで原図を選び、変換設定を入れて再変換できます。変換のたびに新しい rev ができ、原図は変わりません。rev ごとに、2D 地図・高さ・傾き・段差の図を切り替えて見られます。

- 高さは、点群から推定した地面から測ります（DEC-093）。傾きと段差の図は確認用で、走行には使いません（DEC-097）。
- 変換設定の暫定の既定値は承認待ちです（DEC-098）。それまでは、地図作成を終えたときの自動変換は失敗します（原図は残ります）。地図タブで値を入れれば変換できます。
- 変換の方式、設定の意味、移動しての地図作成の実機試験の手順は [design/docs/map_conversion.md](design/docs/map_conversion.md) にあります。原図の解析は次のとおりです。

```bash
python3 -m gouda_core.map_inspect ~/gouda_ws/gouda_data/maps/<origin_id>/source --cell <m> --radii <m> <m> --band <m>
```

## 6. フォルダの構成

```text
~/gouda_ws/
├── src/
│   ├── tsukuba-autonomous-robot/     このリポジトリ（main）
│   ├── HesaiLidar_ROS_2.0/           XT-32 のドライバ（third_party/drivers.repos の commit）
│   └── ADI_IMU_TR_Driver_ROS2/       IMU のドライバ（同）
├── build/  install/  log/            colcon
└── gouda_data/                       データ（PRM-25）
    ├── maps/                         地図データベース（原図と変換後地図。内容ハッシュで識別）
    ├── mapping/                      地図作成中の GLIM の作業領域
    ├── routes/                       waypoint と速度マスク
    ├── records/                      記録（セッションごとに log/ と rosbag/）
    ├── config/                       monitor の設定タブの値（センサーの取付位置など）
    ├── state/                        直前のモードの記録
    └── run/                          起動中の情報（monitor の URL、launch のログ、センサーの状態）
```

リポジトリの中：

| 場所 | 内容 |
|---|---|
| `gouda.sh`、`setup.sh`、`update.sh` | 起動、セットアップ、更新 |
| `gouda_core/` | ノード（mode_manager、recorder、map_creator、monitor、sensor_supervisor、motion_controller、vehicle_bridge）、操作画面（`web/`）、試験（`test/`） |
| `gouda_interfaces/` | 独自のメッセージ・サービス・アクション |
| `firmware/gouda_esp32_v4/` | ESP32 の firmware v4 |
| `third_party/drivers.repos` | センサーのドライバの commit |
| `design/` | 設計の正本と記録（[§8](#8-設計の文書と検査)） |
| `docs/` | 設計の元資料（`docs/architecture/` の Excel・drawio）と、旧実装の調査記録 |

## 7. 旧実装のファイル

`scripts/`、`gouda_gui/`、`gouda_sensors/`、`gouda_navigation/`、`gouda_vehicle/`、`gouda_bringup/`、`gouda_sim/`、`third_party/external.repos`、`patches/` は旧実装（Mission Control）のものです。`gouda.sh`・`setup.sh`・`update.sh` はこれらを使いません。旧 `scripts/gouda.sh` などの起動スクリプトは削除済みです（DEC-068）。旧実装が入っている PC の更新は [§3.2](#32-古い版からの更新1-回だけ) です。

## 8. 設計の文書と検査

| 場所 | 内容 |
|---|---|
| [design/reports/status.md](design/reports/status.md) | 現状の要約。承認待ち・実測待ち・次の作業 |
| `design/intent.md` | 設計意図（人が所有。AI は編集しない） |
| `design/model.yaml` | 正本（YAML）。変更は `design/revisions/REV-xxx.yaml` を `design/tools/apply_revision.py` で適用 |
| `design/docs/` | 正本（Markdown） |
| `design/generated/` | 生成物（設定ファイル `params/`、一覧）。手で編集しない |
| `design/reports/worklog/` | 作業記録 |
| `design/research/` | 調査と実機の記録（証拠） |

検査（Mac でも Ubuntu でも可）：

```bash
python3 -m venv design/.venv && design/.venv/bin/pip install -r design/tools/requirements.lock.txt   # 初回
design/.venv/bin/python design/tools/run_checks.py
```

## 9. 試験

```bash
cd ~/gouda_ws/src/tsukuba-autonomous-robot/gouda_core
source /opt/ros/jazzy/setup.bash && source ~/gouda_ws/install/setup.bash
python3 -m unittest discover -s test -p 'test_*.py'          # 単体試験
bash test/stack.sh start /tmp/gouda_test                       # 試験用の起動（別の ROS ドメインとデータの置き場。センサーのドライバは起動しない。ソフト試験の仮値を使う）
bash test/stack.sh stop /tmp/gouda_test
python3 test/demo_monitor_server.py 8765                       # ROS なしで操作画面の見た目を確認（DEMO と明示された合成の値）
```

ソフト試験の仮値（`*.trial.yaml`）は試験用の起動だけが使い、`gouda.sh` は使いません。

## 10. 現在の制限

- 実車での試験は未実施です。実車に投入してよいかは人の判断待ちです。
- 変換設定の暫定値は承認待ち（DEC-098）です。地面の見え方と点の密度は、移動しての地図作成で測ります（DEC-099・DEC-100、TS-34）。
- `gouda.sh` を起動し直すと、IMU が応答しないことがあります（USB の抜き差しで直ります）。
- 点群の配送で欠落があります（ドライバは 10 Hz、monitor が受け取るのは約 2 Hz、GLIM が処理したのは約 8 Hz。G-DDS）。
- ESP32 firmware v4 は実機に書き込んでいません（DEC-077）。

外部のソースは、それぞれのプロジェクトのライセンスに従います。
