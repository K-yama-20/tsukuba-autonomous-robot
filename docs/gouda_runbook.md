> 過去の開発試験記録です。現行の公開版にはデモ起動・模擬地図生成を含めません。導入と起動は [README](../README.md) を参照してください。

# Gouda 開発用実行手順

この手順はUbuntu ARM64/Jazzyの開発環境で確認した範囲。最終配布版ではない。
AMD64での実行・実機自律走行・較正は未完了。既存IMUと既存ユーザー変更は保全する。

## ビルドと試験

Ubuntu内で実行する。
今回のUbuntuにはHesai再生修正を適用済み。新しい同版checkoutでは先に
`bash scripts/gouda_apply_hesai_patch.sh` を実行し、workspace直下で
`colcon build --symlink-install --packages-select hesai_ros_driver --executor sequential` を実行する。
patchは固定commit専用であり、異なる版へ強制適用しない。

```bash
cd ~/gouda_ws/src/tsukuba-autonomous-robot
bash scripts/gouda_build_test.sh
GOUDA_ACCEPTANCE_VARIANT=straight bash scripts/gouda_ros_acceptance.sh
GOUDA_ACCEPTANCE_VARIANT=turn bash scripts/gouda_ros_acceptance.sh
```

対象は今回追加した4パッケージとnative coreのみ。Hokuyo実機依存試験は含めない。
emulatorはESP32と共通C++ core。ROS試験はドメイン97/localhost内で起動し、終了時に起動プロセスを停止する。
結果は `~/gouda_ws/bags/gouda_20260923/acceptance_{straight,turn}/`。
`GOUDA_WORKSPACE` を指定するとworkspaceを変更できる。

## Hesaiの実機受信

今回の観測: Ubuntu enp0s5=192.168.1.100/24、Hesai=192.168.1.201、UDP宛先2368、PTC9347。
Parallels net0はMac en17/AX88179Bにブリッジ。対象装置/接続が変われば値を再確認する。

```bash
source /opt/ros/jazzy/setup.bash
source ~/gouda_ws/install/setup.bash
ros2 launch gouda_sensors hesai.launch.py mode:=hardware \
  config:=$HOME/gouda_ws/bags/gouda_20260923/checked_hardware.yaml
```

`/lidar_points` と `/gouda/lidar_diagnostics` を出す。車両出力は起動しない。
設定ではPC受信時刻を使用する。firetimeが空のためupstreamの読込みエラーログが残る。
測定用profileであり、時刻同期・動体デスキュー・取付校正済みprofileではない。
IMUを同時に使う場合は、既存の `ros2 launch gouda_bringup imu.launch.py` を別ターミナルで実行する。

別の設定ファイルを作る場合:

```bash
ros2 run gouda_sensors configure_hesai \
  --upstream "$HOME/gouda_ws/src/HesaiLidar_ROS_2.0/config/config.yaml" \
  --correction "$HOME/gouda_ws/bags/gouda_20260923/xt32_device_correction.csv" \
  --mode hardware --device-ip 192.168.1.201 --host-ip 192.168.1.100 \
  --udp 2368 --ptc 9347 --output /tmp/gouda_measured_hardware.yaml
```

生成処理はホスト側ファイルのみ。既存出力ファイルがあれば拒否する。
別個体にこの角度補正を流用しない。corrected hardware YAMLは記録ディレクトリの実個体ファイルを参照する。
PCAP入力は `--mode pcap --pcap /absolute/path.pcap`、生packet rosbagは `--mode packet_replay`。

## 記録点群の再生

実機driverが動いていない隔離ドメインで実行する。

```bash
export ROS_DOMAIN_ID=98
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 bag play ~/gouda_ws/bags/gouda_20260923/receive_time_points_packets_imu \
  --clock 100 --topics /lidar_points /imu/data_raw
```

監視にも `--ros-args -p use_sim_time:=true` を指定する。
生packet再解析は `mode:=packet_replay` と `checked_packet_replay.yaml` でHesai launchを起動し、bagの `/lidar_packets` だけ `--clock 100` を付けて再生する。
packet-replay launchはdriver/monitor双方のuse_sim_timeを有効にする。保存packetに元の受信時刻が含まれるため、実時間の鮮度判定と混ぜない。
同時に記録済み `/lidar_points` を出して二重publisherにしない。
PCAPファイルは未取得なので、PCAP parser経路は未検証とする。

## ESP32

```bash
pio run -d firmware/gouda_esp32
```

`espressif32@6.12.0`、esp32dev、Arduino、USB115200、C++17。
今回はMacの既存PlatformIOでbuild確認。UbuntuのPlatformIO導入はまだ実行していない。
upload操作はしていない。元DualSense版を変更していない。
新Serial版は `calibration::validated=false` で走行armを拒否する。
relay bypass構成のためGPIO32 LOWを緊急停止/電気的切離しと誤認しない。
実機bridge、校正LUT、測定記録、neutral確認、再arm試験が揃うまで実車へ進めない。

## 次の実装

実機base/IMU/LiDARの取付TFと車体外形を測定し、実機のオドメトリ→地図定位→障害物処理を接続する。
それまではKISSのsensor-frame出力とsimulationのmock TFを区別する。
続いて実測DAC LUTと版/readbackを整備し、PCのhardware profileを実装・検証する。
最後に残シナリオとAMD64再現確認を行い、配布構成を固定する。
