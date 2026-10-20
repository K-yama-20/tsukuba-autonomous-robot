# 上流ソースの保存（センサドライバと GLIM の時刻の扱いの照合用。2026-10-13 取得）

読み取り専用の証拠。ビルド・実行はしていない。DEC-083（点群の時刻を PC 受信時刻にする）の帰結の照合に使った（作業記録 2026-10-13 第20便）。

| ディレクトリ | 取得元 | 版 |
|---|---|---|
| hesai_ros2_e7e112f/ | https://github.com/HesaiTechnology/HesaiLidar_ROS_2.0 | commit e7e112f0809f0eed5e3c81c55a1a0376474db234（master、2026-04-27。docs/gouda_development_20260923.md の導入済み版と同じ） |
| hesai_sdk_9d5dc4f/ | https://github.com/HesaiTechnology/HesaiLidar_SDK_2.0（上の submodule） | commit 9d5dc4fc4ade5be5f6a6ca00e71dd4050b054168 |
| glim_v1.2.2/ | https://github.com/koide3/glim | tag v1.2.2（実車PC の ros-jazzy-glim 1.2.2-0noble と同じ版番号。DEC-062） |
| glim_ros2_v1.2.2/ | https://github.com/koide3/glim_ros2 | tag v1.2.2 |
| adi_imu_742b7ba/ | https://github.com/technoroad/ADI_IMU_TR_Driver_ROS2 | commit 742b7babec7e7a20937d4e8be0df77a771a1294a（2026-07-29） |
| septentrio_gnss_driver_1.4.8/ | ROS 2 の apt（packages.ros.org）の ros-jazzy-septentrio-gnss-driver 1.4.8-2noble.20260916.090359（arm64）を VM で apt-get download して展開した share/septentrio_gnss_driver/config/gnss.yaml（2026-10-17。BSD-3-Clause）。gouda_core.gnss_config の雛形と単体試験に使う |

照合した事実（ファイルと行）:
- Hesai SDK `udp6_1_parser.h`（XT の UDP 6.1）: use_timestamp_type が 0 以外のとき、各 packet の sensor_timestamp に受信時刻 recv_timestamp を入れる（259〜263 行）。点の `timestamp` は packet の sensor_timestamp（177 行。firetime 補正は timeSecond/timeNanosecond だけに入る、158〜161 行）。frame_start_timestamp は最初の packet の値（264 行）。
- Hesai SDK `lidar.h` 776 行: recv_timestamp = GetMicroTimeU64()。`plat_utils.cc` 127〜143 行: Linux では gettimeofday（壁時計）。
- Hesai ROS 2 `source_driver_ros2.hpp`: 点の `timestamp` は FLOAT64（279・300 行）、header.stamp は frame_start_timestamp（311〜314 行）。
- GLIM `ros_cloud_converter.hpp` 87〜90 行: 点時刻の field 名 t / time / time_stamp / timestamp を読む。`time_keeper.cpp`: 既定（config_sensors.json の autoconf_perpoint_times=true、autoconf_prefer_frame_time=false）で、点時刻の最大が 1.0 を超えると絶対時刻とみなして相対化し、frame の時刻を最初の点の時刻で上書きする。点群と IMU の時刻差が 1 s を超えると警告する。
- ADI IMU ドライバ `adis_rcv_bin_node.hpp`: header.stamp = this->now()（272 行）、既定 publish_tf=true（161 行）、topic imu/data_raw（57 行）、parameter device・frame_id・parent_id・rate・publish_tf。
