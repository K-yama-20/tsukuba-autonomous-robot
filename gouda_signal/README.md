# Gouda 歩行者信号 色判定プロトタイプ

Ubuntu 24.04 / ROS 2 Jazzy向けのネイティブQt5デスクトップアプリです。カメラ映像のユーザー指定ROI内で赤・緑の画素を調べ、状態をGUIと`std_msgs/msg/String`で表示します。

## 起動

依存パッケージはリポジトリの`bash scripts/setup.sh`で導入します。ROS 2環境を読み込んだ後、次のいずれかで起動します。

```bash
ros2 run gouda_signal pedestrian_signal
bash scripts/gouda.sh signal
```

アプリはカメラを自動で開始しません。入力欄にV4L2番号（既定値`0`）、`/dev/videoN`、動画ファイルまたはOpenCVが対応するURIを指定し、Startを押します。映像が表示されたら点灯部をドラッグし、ROIを確定します。カメラを開始するたび、または入力を編集するたびにROIの確定が必要です。入力の変更は実行中カメラを停止し、映像・ROI・判定を直ちに消去します。

```bash
ros2 run gouda_signal pedestrian_signal -- --camera /dev/video0
ros2 run gouda_signal pedestrian_signal -- --camera ./intersection.mp4 --no-ros
ros2 run gouda_signal pedestrian_signal -- --no-ros
```

`--no-ros`は単体GUIの起動用です。ROSを使う場合の既定トピックは`/perception/pedestrian_signal`で、`--ros-topic /other/topic`で変更できます。ランチャーはROSの`ROS_DOMAIN_ID=99`を設定します。

## 判定

これは信号器を自動検出・追跡するAIではなく、確定したROI内の色だけを見るプロトタイプです。分類条件はiOS版コアと同じ固定HSVしきい値です。画素の明度は0.28以上、彩度は0.42以上、赤の色相は0–22度または338–360度、緑は72–175度で、ROI面積の0.8%以上の画素を必要とします。赤と緑がともにしきい値を満たす場合はUNKNOWNです。

緑は1.2秒連続して見えた後にGREENになります。フレーム間隔が0.45秒を超えれば連続時間をリセットします。3.2秒以内に緑の消灯が2回起きると点滅としてUNKNOWNにし、緑が2秒安定してから回復します。赤はREDを出し、しきい値を満たす色がない場合はUNKNOWNです。confidenceは色の画素量と優勢度から計算するヒューリスティック値で、確率ではありません。

最新フレームだけを扱い、処理間の古いフレームを蓄積しません。動画ファイルはファイルに報告されたFPS（1–120の範囲外または無効なら30 FPS）に合わせて読みます。映像プレビューは縦横比を保ち、最大1280×960ピクセルに縮小します。ROIの座標はプレビューの余白を除いたカメラ画像に対応します。OpenCVの読み込み完了時刻を単調時計で記録します。カメラの露光時刻やネットワーク内の遅延を測った値ではありません。

開始直後、ROI未確定、カメラ停止、動画終端、読み込みエラー、500 msを超える映像停止、アプリ終了ではUNKNOWNを発行します。新しいGREEN/RED判定はフレームごとに発行し、古いGREEN/REDを周期送信で延命しません。UNKNOWNは状態と理由を定期送信します。

ROSのStringデータはUTF-8のコンパクトなJSONです。主な項目は`version`、`session_id`、`seq`、`state`、`reason`、`target_id`、`confidence`、`source`、`frame_seq`、`processing_age_ms`です。`source`は`ubuntu_roi_color_v1`です。`processing_age_ms`はOpenCVの読み込み完了から発行時までの時間で、カメラ撮影や露光からの年齢を意味しません。初回の映像前は`frame_seq`と`processing_age_ms`を`null`にします。

このアプリのGREEN/RED/UNKNOWNは観測状態だけを表します。横断可否の判断や車両の移動制御には接続しないでください。映像の録画やデモカメラは含みません。
