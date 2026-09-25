# Gouda 歩行者信号認識プロトタイプ

Ubuntu 24.04 / ROS 2 Jazzy向けのネイティブQt5アプリです。手動で確定した検索範囲の中からAutoware由来のONNX歩行者信号検出器が対象を見つけ、信号状態分類器が赤・緑・不明を判定します。カメラ映像をGUIに表示し、結果を`std_msgs/msg/String`のJSONとして発行します。

## 起動

依存関係とモデル実行環境を`bash scripts/setup.sh`で導入した後、次のコマンドで起動します。ランチャーがROS 2とワークスペースの環境を読み込みます。

```bash
bash scripts/gouda.sh signal
```

カメラは自動で開始しません。V4L2番号（既定値`0`）、`/dev/videoN`、動画ファイルまたはOpenCV対応URIを入力して「開始」を押します。映像が表示されたら歩行者信号器全体を囲み、「ROIを確定」を押してください。ROIはモデルの検索範囲です。カメラを開始するたび、また入力を編集したときは再度ROIを確定してください。入力を編集するとカメラ、映像、ROI、前の判定を直ちにリセットします。

追加引数はランチャーの後ろに指定します。

```bash
bash scripts/gouda.sh signal --camera /dev/video0
bash scripts/gouda.sh signal --camera ./intersection.mp4 --no-ros
bash scripts/gouda.sh signal --model-dir /path/to/models --confidence 0.8
bash scripts/gouda.sh signal --classifier hsv --no-ros
```

既定では学習済みモデルを使います。ONNXファイルは`GOUDA_SIGNAL_MODEL_DIR`または`$GOUDA_WORKSPACE/models/pedestrian_signal`から読み込みます。`--confidence`は分類器の最低スコアで、既定値は0.8です。検出器のスコアしきい値はモデルマニフェストの0.3を使います。必要なファイルや実行環境がない場合はUNKNOWNを表示して理由を示し、HSVへ自動で切り替わることはありません。HSV色判定は明示的なデバッグ用`--classifier hsv`でのみ使います。

`--no-ros`はROSを使わずにGUIを開く指定です。ROSの既定トピックは`/perception/pedestrian_signal`で、`--ros-topic /other/topic`で変更できます。ランチャーは`ROS_DOMAIN_ID=99`を既定値として設定します。

## 判定と鮮度

検出器は確定ROIの中から歩行者信号器を見つけ、分類器が赤・緑・不明を返します。分類にはCPU向けONNX Runtimeを使い、GUIとは別の終了可能なプロセス内で推論します。処理要求・結果は各1件に制限し、遅れてきたフレームやROI変更前の結果は破棄します。検出位置が前の対象から大きく移動した場合は判定時間をリセットします。これは物体追跡を行う機能ではありません。複数または未検出など単一の信号器を選べない場合はUNKNOWNです。

緑は1.2秒連続して確認した後にGREENになります。推論フレーム間隔が0.45秒を超えれば連続時間をリセットします。3.2秒以内に緑が2回消えると点滅としてUNKNOWNにし、2秒安定してから回復します。赤はREDです。confidenceはモデルの出力スコアで、校正済みの確率を意味しません。

最新フレームだけを処理し、古いフレームをためません。動画ファイルは報告FPS（1–120の範囲外または無効なら30 FPS）に合わせて進み、終端で停止します。プレビューは縦横比を保ち、最大1280×960ピクセルに縮小します。ROI座標はレターボックスの余白を除いたカメラ画像に対応します。OpenCVのフレーム読み込み完了時刻を単調時計で記録します。カメラ露光時刻やネットワーク内の遅延を測定した値ではありません。

起動、ROI未確定、モデル不在、カメラ停止、動画終端、読み込みエラー、0.5秒を超えるカメラまたは推論停止、終了はUNKNOWNです。GREEN/REDは新しい推論結果に対して発行し、古い状態を周期送信で延命しません。UNKNOWNは0.5秒ごとに発行します。

ROSのStringデータはUTF-8のコンパクトなJSONです。主な項目は`version`、`session_id`、`seq`、`state`、`reason`、`target_id`、`confidence`、`source`、`frame_seq`、`processing_age_ms`です。学習済みモードの`source`は`autoware_pedestrian_onnx_v1`、デバッグ用HSVモードでは`ubuntu_roi_color_v1`です。`frame_seq`と`processing_age_ms`は推論に入力したフレームを指します。`processing_age_ms`はOpenCVの読み込み完了から発行までの時間で、露光開始からの年齢ではありません。まだ推論フレームがない場合は両項目を`null`にします。

GREEN/RED/UNKNOWNは画像からの観測状態です。横断可否の判断や車両の移動制御には接続しないでください。映像録画やデモ映像は含みません。
