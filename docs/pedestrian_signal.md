# 歩行者信号アプリ

Ubuntu 24.04 の amd64 / arm64 で動く、Qt デスクトップ上の歩行者信号認識アプリです。既存の `scripts/setup.sh` が apt の OpenCV・PyQt5・NumPy を導入し、ROS 2 ワークスペースと一緒に `gouda_signal` をビルドします。ONNX Runtime CPU 版はワークスペース内の `.venvs/pedestrian_signal` に固定バージョンで導入し、モデルもワークスペース内へ取得します。システム全体への pip インストールは行いません。

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

起動直後は検出を始めません。画面の「開始」操作で対象範囲を選び、利用者が範囲を確認して確定すると検出を始めます。学習済みの検出モデルが確定した範囲内で歩行者用信号機の枠を検出し、分類モデルが赤・緑・不明を判定します。画面全体から対象を自動探索する機能ではなく、対象を追い続ける自動追跡でもありません。推論は CPU 上の ONNX Runtime で実行します。

## モデルの導入とライセンス

通常の `bash scripts/setup.sh` は、固定した Hugging Face のコミットから ONNX モデルを2つ取得します。ダウンロード量は合計約44.7 MBです。`--skip-system` を付けてもモデル取得とワークスペース内ランタイムの準備は行います。既定の保存先は `$GOUDA_WORKSPACE/models/pedestrian_signal/` で、`GOUDA_SIGNAL_MODEL_DIR` で変更できます。再セットアップ時は既存ファイルのサイズと SHA-256 を確認し、違うファイルがあれば置換せず停止します。

使用モデルは Autoware Foundation が公開する Apache-2.0 の YOLOX-s 歩行者信号検出器と MobileNetV2 分類器です。モデルの出所・固定リビジョン・ハッシュは [第三者モデル通知](../third_party/pedestrian_signal_models.md) に記録しています。モデルカード: [検出器](https://huggingface.co/AutowareFoundation/traffic_light_fine_detector), [分類器](https://huggingface.co/AutowareFoundation/traffic_light_classifier)。これらは既存の学習済みモデルで、このプロジェクトで学習したものではありません。上流の評価値や日本の信号機画像に関する記述は、このカメラ・距離・照明・設置条件での精度を示しません。

## ROS 2 出力

ROS 2 有効時は、既定の `/perception/pedestrian_signal` に `std_msgs/msg/String` を送ります。文字列の内容は JSON で、`state`、`reason`、`target_id`、`confidence`、`frame_seq`、`session_id`、`seq`、`source`、`processing_age_ms` を含みます。`source` は `autoware_pedestrian_onnx_v1` です。`processing_age_ms` はアプリ側の処理経過時間で、カメラの露光時刻や撮影時刻を保証するタイムスタンプではありません。

アプリは起動時、判定が古くなった時、停止時に `UNKNOWN` を送ります。受信側でも受信後の経過時間を監視し、例えばメッセージが 0.5 秒届かなければ保持中の状態を期限切れにしてください。`session_id` と `seq` を使って、古いセッションや順序が戻ったメッセージも拒否します。プロセスの異常終了やネットワーク断では最後の `UNKNOWN` が届く保証がないため、受信側の期限切れ処理は常に必要です。

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
