# 実機SLAM・地図保存・再読込（段階3）

車体出力を起動しない計測用構成。現時点の位置は **LiDAR中心** であり、車体中央ではない。

## 起動

Ubuntuで `~/gouda_ws/install/setup.bash` を読み込んだ後：

```sh
# センサー受信。GUIを再起動するときも、このプロセスは止めない。
ros2 launch gouda_gui sensors_only.launch.py

# 別の端末でGUI・SLAMを起動
ros2 launch gouda_gui observation.launch.py sensors:=false
```

ROS domain 99・localhostに隔離。模擬実行はdomain 98。両モードはHTTPポート8765を共有するため、同時に起動しない。Macの接続入口は `http://127.0.0.1:8766`（`mac_gui_proxy.py`が必要）。

- LiDAR → KISS-ICP → `odom_lidar → hesai_lidar`
- 同じ点群 → センサー高さ±0.15 mの水平スライス → `/scan`
- SLAM Toolbox → `/map` と `map → odom_lidar`
- GUIは点群時刻に対応するTFを待って表示。車体TFは発行しない。
- IMUは受信表示のみ。向き・相対位置・時刻同期が未校正なので融合しない。
- planner、follower、ESP32 bridgeは起動しない。GUIの走行要求は拒否する。
- GUIの停止ボタンは車体に未接続であることを表示して無効化する。

## GUI操作

1. 地図作成タブの「新しい地図を作成」でSLAMを起動する。
2. 作成中の地図を同じ画面で確認する。
3. 「計測を終了」後、地図名を入力し保存する。
4. 保存済み地図を開くと自己位置推定モードへ切り替わる。
5. 走行計画タブの「初期位置」で **LiDAR中心** の位置と向きを指定する。まだ推定位置がない状態でも入力可能。
6. ゴール候補は指定できるが、実機の経路計算と走行開始は無効。

保存先は `~/gouda_ws/maps_sensor_slam/<UUID>/`。map.pgm/map.yaml/grid.json/metadata.jsonに加え、slam.posegraphとslam.dataを保存する。SLAMデータの保存成功後に一覧へ公開する。再生データの地図と実機地図を区別する。保存名をファイルパスとして使用しない。

## 暫定条件と未確認事項

`gouda_sensors/config/mount_provisional.yaml` にユーザー提供条件を記録した。高さは地面から1.60 m、想定範囲1.55〜1.65 m。背もたれを鉛直に固定し、背もたれパイプに3030フレームを固定する。IMUはLiDARの真下。

この高さは計画値であり、まだ取付前。現在のSLAMは取付高さを使う車体座標変換を行わない。左右方向・単位の確認、前後オフセットの実測、LiDAR/IMU各軸方向、両者間隔が必要。水平スライスにはLiDARが概ね水平という前提があり、走行可能領域や低い障害物の判定には使わない。

今回の短時間接続試験を、移動時の地図精度、ループ閉じ込み成功、移動後の再定位精度、車体位置精度の検証と同一視しない。固定後、位置関係・軸方向を確定し、手動移動で収録して別途検証する。

LiDARにはPC受信時刻を使用。Ubuntuの時計修正だけではLiDAR/IMUのハードウェア時刻同期は成立しない。firetime補正ファイル未取得のためKISS-ICPのdeskewは無効。

## 再現性・通信

USB-LANは`enx6c6e0754b24a`、IPは192.168.1.100/24。専用NetworkManager接続`gouda-hesai-usb-stage3`を追加し、既存の仮想LANプロファイルは変更していない。LiDARは192.168.1.201、UDP2368、PTC9347。

64,000点×26 byteの点群は既定のFast DDS共有メモリ512 KiBを超える。観測用起動構成だけに32 MiB設定を適用し、約1.7 Hzだった下流受信が約10 Hzへ改善した。OS全体の通信設定は変更していない。

IMUライブラリの`struct termios`未初期化を限定修正。適用は `scripts/gouda_apply_imu_patch.sh`、差分は `patches/imu-initialize-termios.patch`。原本を`~/gouda_ws/bags/gouda_20260923/stage3/`へ保存。仮想シリアルで32回の開閉、通信速度とrawモード、終了時の設定復元を検証する。これは実機再接続の成功とは別に記録する。

参考： [SLAM Toolboxの保存・自己位置推定](https://raw.githubusercontent.com/SteveMacenski/slam_toolbox/jazzy/README.md)、[Fast DDS共有メモリ設定](https://fast-dds.docs.eprosima.com/en/stable/fastdds/transport/shared_memory/shared_memory.html)。

## IMU再起動に関する既知の問題

IMUは電源入れ直し後に受信できるが、受信ドライバの停止・再起動で本体が応答しなくなる現象が再現した。termios初期化修正だけでは解消していない。USBのソフトリセットも復旧しなかった。原因は未特定であり、ファームウェアの変更・書込みはしていない。センサー受信とGUI/SLAMを別プロセスに分離し、GUI再起動時はセンサー受信を継続する。IMU本体を停止した場合の復旧は現時点で電源入れ直しが必要。
