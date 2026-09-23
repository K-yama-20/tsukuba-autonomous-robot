# KISS-ICP標準RViz2のGUI統合（2026-09-23）

地図作成タブと実機の3D表示は、KISS-ICP付属 `kiss_icp.rviz` を読み込むRViz2の画面を転送する。JavaScriptで点群を描き直さない。標準設定ファイルは変更しない。走行計画は従来の2D地図・map座標の初期位置／ゴール入力を維持する。

## 起動

Ubuntuで、センサー受信と画面・SLAMを別プロセスとして起動する。すでに動いているものを重複起動しない。

```sh
source /opt/ros/jazzy/setup.bash
source ~/gouda_ws/install/setup.bash
export ROS_DOMAIN_ID=99
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export FASTDDS_DEFAULT_PROFILES_FILE=$HOME/gouda_ws/install/gouda_gui/share/gouda_gui/config/fastdds_observation.xml
export FASTRTPS_DEFAULT_PROFILES_FILE=$FASTDDS_DEFAULT_PROFILES_FILE
# 各コマンドは別ターミナル。センサーはGUI再起動時に止めない。
ros2 launch gouda_gui sensors_only.launch.py
ros2 launch gouda_gui observation.launch.py sensors:=false
ros2 run gouda_gui native_view
```

Ubuntu追加パッケージ: `xvfb x11vnc novnc openbox wmctrl python3-aiohttp`。Mesa software renderingを使用し、`LP_NUM_THREADS=1` で描画のCPU占有を抑える。位置合わせのボクセル幅・deskew・センサーTF・IMU融合は変更しない。

Macでは `outputs/gouda_development` を基準に、専用環境で次を実行する。

```sh
native_view/runtime/venv/bin/python mac_gui_proxy.py
```

入口は `http://127.0.0.1:8766`。設定・専用鍵・固定したホスト公開鍵は `native_view/runtime/` 内（Git対象外）。`setup_connection.py` はネットワーク退避と初回セットアップ用。既存鍵を再生成せず、既存のSSH設定を置換しない。

## 描画と通信

- Ubuntuの専用X画面 `:97`、1280×720、24bit色。通常のデスクトップを転送しない。
- RViz2 → x11vnc（localhost:5907）→ aiohttp WebSocket（localhost:6080）→ SSH → Macの中継 → noVNC。
- MacのSSH転送先は固定のGUI 8765と表示6080。Macの入口およびトンネルはloopbackのみ。外部Originと未許可パスを拒否する。
- noVNC 1.3の`_sendEncodings`を限定してHextile/RRE/Raw/CopyRectのみを使用する。JPEGを含むTightを提示しない。バージョン更新時は実際のネゴシエーションを再確認する。
- `/api/viewer` は表示プロセスと点群受信時刻を返す。`/native/ws` はRFB転送。`/native/vendor/` はUbuntuパッケージのnoVNCを配信する。
- ブラウザは画面を領域に合わせて拡縮するが、点群座標・描画色・RViz設定を変更しない。独自の軌跡、凡例、格子、位置マーカーは標準画面に重ねない。
- RViz標準ツールバーの初期位置／ゴール送信先は専用の未使用トピックへ変更する。既存2D計画画面からの操作だけを受け付け、odom_lidarとmapの位置指定を混同しない。
- GUI再読込はRVizやセンサーを再起動しない。SSH断は約2秒間隔で再接続。RViz/入力停止は画面外の状態欄へ明示する。

## ネットワークと退避

仮想LAN `enp0s5` はParallels共有ネットワーク、NetworkManagerプロファイル `gouda-native-shared`（DHCP）。USB-LAN `enx6c6e0754b24a` は従来どおり `192.168.1.100/24`、プロファイル `gouda-hesai-usb-stage3`。旧仮想LANプロファイル `gouda-hesai` は削除せず、自動接続だけを無効化した。

元設定はUbuntu `~/gouda_ws/bags/gouda_20260923/native_view/network-backup` と `network-before.txt`、Mac `native_view/evidence/parallels-before.txt` に保持する。元の重複IP構成へ自動で戻さない。

## 検証・制限

- 2D画面を隠した状態で地図が更新されると倍率が0になる不具合を修正。非表示時は全体表示の計算を延期する。`native_view/test_hidden_map.cjs` が回帰試験。
- `native_view/check_transport.py` が実際のHTTP/WS転送・Origin制限・実機start/plan拒否を確認する。
- ローカル点群はKISS-ICPの局所地図であり、保存済みの走行用全体地図ではない。「2D SLAM地図を保存」は従来の地図画像とposegraphを保存する。
- センサーの電源断後に再接続しても入力が復帰しない場合、標準画面は最後の描画と「更新停止」を表示する。画面再接続だけではLiDAR本体の通信停止を解消しない。
