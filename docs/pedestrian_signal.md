# 歩行者信号アプリ

Ubuntu 24.04 の amd64 / arm64 で動く、Qt デスクトップ上の歩行者信号色認識アプリです。既存の `scripts/setup.sh` が apt の OpenCV・PyQt5・NumPy を導入し、ROS 2 ワークスペースと一緒に `gouda_signal` をビルドします。別のインストーラーや pip によるグローバル導入は使いません。

## 起動

リポジトリのディレクトリで実行します。

```bash
bash scripts/gouda.sh signal
```

既定ではカメラ番号 `0` を使います。カメラ番号、デバイスパス、または動画ファイルを指定できます。ROS 2 の既定トピックは `/perception/pedestrian_signal` です。

```bash
bash scripts/gouda.sh signal --camera /dev/video0
bash scripts/gouda.sh signal --camera /path/to/video.mp4
bash scripts/gouda.sh signal --no-ros
bash scripts/gouda.sh signal --ros-topic /perception/pedestrian_signal
```

起動直後は検出を始めません。画面の Start 操作で ROI の選択に進み、選択範囲を確認して確定すると検出を始めます。ROI は利用者が手動で選びます。認識器は固定の HSV 閾値を使う色分類器で、学習済み AI モデルではなく、自動追跡もしません。

## ROS 2 出力

ROS 2 有効時は、既定の `/perception/pedestrian_signal` に `std_msgs/msg/String` を送ります。文字列の内容は JSON で、`state`、`reason`、`target_id`、`confidence`、`frame_seq`、`session_id`、`seq`、`source`、`processing_age_ms` を含みます。`source` は `ubuntu_roi_color_v1` です。`processing_age_ms` はアプリ側の処理経過時間で、カメラの露光時刻や撮影時刻を保証するタイムスタンプではありません。

別の端末で出力を確認する場合は、アプリと同じ ROS 2 ドメインでトピックを購読します。既定の設定は次のとおりです。

```bash
ROS_DOMAIN_ID=99 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST ros2 topic echo /perception/pedestrian_signal
```

## 動作範囲

画面は Ubuntu のネイティブ Qt ウィンドウに表示します。ブラウザ画面、画面転送、仮想ディスプレイは使いません。このアプリは歩行者信号の認識結果を ROS 2 の知覚トピックに出す機能に限られます。既存の観測・自律走行プロセスを起動・停止せず、車両の速度や操舵などの動作指令も送信しません。

このアプリが扱えるカメラ、照明、距離、設置位置、信号機ごとの色条件は機材と環境に依存します。実カメラを使った認識精度や現場での動作は別途確認が必要です。カメラ映像がない場合の結果を実機認識の保証とみなさないでください。

## セットアップ時の既存環境

通常の初回導入は `bash scripts/setup.sh` を実行します。既存の機器設定を再選択したくない場合は、リポジトリのディレクトリから次のように実行できます。

```bash
bash scripts/setup.sh --no-configure
```

`--no-configure` は機器選択の対話設定を省略します。セットアップが既存の地図・設定を置換または削除することはありません。既存の異なるチェックアウトや競合する設定があれば、処理を止めて状態を保持します。
