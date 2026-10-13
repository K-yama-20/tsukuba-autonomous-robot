# Joystick270 Firmware

今仙技術研究所 EMC-270 電動車椅子の純正ジョイスティック信号を、
ESP32-DevKitC-VE（ESP32-WROVER-E 8 MB）、MCP4922、AE-ADS1015、
TQ2-5Vリレーを使って計測・エミュレーションするプロジェクトです。

このリポジトリには次を含みます。

- PlatformIO / Arduino framework のESP32ファームウェア
- 左右輪速度を送る別ESP32向けUART模擬送信機
- ROS 2 Jazzy用C++ USBドライバと独自メッセージ
- 中央無動作範囲の自動探索、NVS二重保存、全サンプルログ
- 通信、較正、フェイルセーフ、実車試験の文書

正式仕様は [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md)、試験手順は
[`docs/TEST_PROCEDURE.md`](docs/TEST_PROCEDURE.md)、別ESP32との速度通信は
[`docs/ENCODER_UART.md`](docs/ENCODER_UART.md) を参照してください。

## ファームウェアのビルド

```bash
~/.platformio/penv/bin/pio run -e joystick270
~/.platformio/penv/bin/pio test -e native
python3 -m unittest tools/test_tools.py
```

初回書込み時は、校正ログ領域も作成します。

```bash
~/.platformio/penv/bin/pio run -e joystick270 -t upload
~/.platformio/penv/bin/pio run -e joystick270 -t uploadfs
```

## ROS 2 Jazzy

```bash
cd ros2_ws
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src --rosdistro jazzy -y
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
```

設定と起動方法は [`docs/ROS2_SETUP.md`](docs/ROS2_SETUP.md) にあります。

## 重要

本プロジェクトのローカルビルド成功は、EMC-270実車での安全性や電気的適合を
証明しません。端点値、中央較正、ADC監視負荷、リレー接点、通信断停止を実車で
段階的に確認するまで、人を乗せた状態では使用しないでください。
