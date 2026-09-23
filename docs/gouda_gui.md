# Gouda Mission Control

一つのウィンドウに左サイドタブを配置したブラウザGUI。
参考は `emc270-mission-control.html`（2026-09-02）。元HTMLは変更していない。
制御と状態の本体はUbuntu、ブラウザは表示・操作を担当する。

## 起動

Ubuntuの既存workspaceで：

```bash
source /opt/ros/jazzy/setup.bash
source ~/gouda_ws/install/setup.bash
ros2 launch gouda_gui simulation.launch.py
```

Ubuntuのブラウザで `http://127.0.0.1:8765` を開く。
シミュレーションはROS domain 98、localhost discovery、既存のnative ESP32 coreとPTYを使用する。
実機USBシリアルは開かない。既存の自動開始を使う試験はdomain 97のまま。
既に起動中なら同じlaunchを重複実行しない。

Macからも接続する開発用中継はMac側 `outputs/gouda_development/mac_gui_proxy.py`。
Parallels Guest Toolsを通じて上記localhostだけに接続する。
Macでこれを起動して `http://127.0.0.1:8766` を開く。
ネットワークアダプタを変更せず利用できる。VMが停止・GUIが未起動の場合は接続エラーを表示する。
この中継は開発用途であり、実車の停止応答時間を保証する通信経路ではない。

## 操作

1. **地図作成**：新しい地図を作成 → 作成中の地図を確認 → 計測終了 → 名前を付けて保存。
2. **走行計画**：保存地図を選択して読込。ゴール選択後、地図クリックで位置、ドラッグで向きを指定。
   数値入力でも指定できる。初期位置は指定後に設定ボタンで適用する。
3. 経路を計算。経路表示中は車両が動かない。地図・初期位置・ゴール変更でプレビューを無効にする。
4. **走行監視**へ切り替えて明示的に走行開始。指定したゴール位置へ到達後、指定した向きへ旋回する。
5. 停止は全タブ共通。要求送信と、速度・角速度が小さく制御が解除された「停止確認済み」を分ける。
6. **点検設定**で点群、IMU、自己位置、ナビゲーション、ESP32の更新状態を確認する。

タブ切替は処理を開始・終了しない。地図の拡大・移動、入力中の位置も切替で保持する。
再読込時にはUbuntu側の状態を取得する。元HTMLの架空電池残量・DAC値・正常表示は継承していない。
記録時刻はUbuntuの時計、画面の最終受信時刻はブラウザ側の時計。時計同期未確認時は一致を前提にしない。

## 実装境界

- 地図生成は、**模擬点群を既存map座標へ変換して投影する占有格子作成**。
  20×20 m、0.1 m/cell、模擬の高さフィルタ0.15〜1.8 m。
  未観測セルを保持し、観測障害物を同一セッションのレイで消さない。
- **SLAM、ループ閉じ、実機地図定位の完成を意味しない。** 地図生成と実機走行の操作はsimulationモード限定。
  実機の取付TF、地面・障害物判定、車体寸法、DAC校正は従来の残件。
- `mode:=live` / `mode:=replay` の単体GUI起動は外部 `/map`、有効なmap座標の点群・poseを表示可能。
  実機SLAMの開始・地図読込・実車走行は未接続。実機モードをsimulationへ見せ替えない。
- 初期位置変更は模擬車両が制御解除・停止している時だけ受理し、X/Yとも±3 m以内。
  実機の初期位置送信は `/initialpose` の受信先がある場合に限る。位置推定の確定とは区別する。
- 単一ゴール対応。経由点編集、走行計画のファイル保存、点検画面からの校正操作、bag再生操作は後続。
- 3D表示は受信したXYZ点群の固定斜め視点表示。RVizを置き換える高機能3D操作画面ではない。
- ブラウザ切断は「表示更新停止」。自律走行中にブラウザを閉じるだけでは走行を中止しない。
  ROS入力・TF異常や制御上流喪失では既存の車両停止系が動作する。

## 地図保存

Ubuntu `~/gouda_ws/maps/<UUID>/` に以下を一括保存する。

- `grid.json`：セル、解像度、原点、座標系
- `metadata.json`：表示名、作成時刻、simulation/live区分、取得フレーム数、生成方法
- `map.pgm` / `map.yaml`：Nav2互換の2D地図

表示名はディレクトリ名に使わない。保存途中の地図は一覧に出さず、同名でも上書きしない。
シミュレーション地図を実機地図として読み込まない。

## ROS接続

| 用途 | 接続 |
|---|---|
| 地図 | `/map` OccupancyGrid |
| 模擬環境の初期地図 | `/gouda/world_map` OccupancyGrid |
| 点群 | `/lidar_points` PointCloud2、取得時刻のTFでmapへ変換 |
| 自己位置 | `/gouda/pose` Odometry |
| 経路計算要求 | `/goal_pose` PoseStamped → Nav2 ComputePathToPose |
| プレビュー | `/gouda/preview_path` Path |
| 明示開始 | `/gouda/start` Trigger |
| 中止・制御解除 | `/gouda/cancel` Trigger / `/gouda/arm` SetBool(false) |
| 模擬初期位置 | `/gouda/sim/set_pose` PoseStamped |
| 実機初期位置 | `/initialpose` PoseWithCovarianceStamped |

GUI用launchはfollowerの `auto_start:=False` を必ず指定する。
プレビューの寿命は60秒、開始地点から0.2 m超移動した場合は再計算。
開始要求はプレビューID、入力鮮度、停止状態、ESP32の準備応答を確認する。
終端の向きの許容誤差はsimulationの `yaw_tolerance=0.15 rad`（約8.6度）。
5状態の固定旋回速度と停止時の回転量を考慮した値であり、実機精度の保証ではない。
模擬Serial bridgeは実プロセスを直接管理し、終了・再起動で旧サービスを残さない。
従来の自動開始試験との互換性のため、follower単体のauto_start既定値はTrueのまま。

HTTPは標準ライブラリを利用し、ローカル配信・外部CDNなし。
POSTは起動ごとの操作トークンと同一Originを要求する。任意のシェル実行APIは提供しない。

## 検証

- `gouda_gui/test/test_core.py`：地図生成、未知セル保持、保存・読込、PGM上下方向、入力検証、HTTP操作制限。
- `gouda_navigation/test/test_goal_heading.py`：終端姿勢への旋回と取消。
- `gouda_gui/test/acceptance_http.py`：起動済みsimulation GUIに対して実行。実機モードを拒否。
- Mac `outputs/gouda_development/gui_browser_test.cjs`：ブラウザから地図作成・保存・経路確認・走行・停止、幅1440/1024/768/390、JavaScriptエラー。
- 証跡はMac `outputs/gouda_development/evidence/gui-*`。
