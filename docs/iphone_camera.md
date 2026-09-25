# iPhone映像をROS 2へ入力する

この機能は信号認識を実装する前段として、iPhoneのネットワーク映像をROS 2へ入力する。現時点では画像の表示だけを行い、認識や車体制御には接続しない。

## 接続方式

iPhoneはUbuntuへBluetoothカメラとして直接公開しない。iPhone側でRTSPまたはHTTP/MJPEGを配信し、UbuntuからIP通信で受信する。

接続は次のいずれでもよい。

- iPhoneとUbuntuを同じWi-Fiへ接続する。
- UbuntuをiPhoneのパーソナルホットスポットへ接続する。
- Bluetooth PANでIP疎通させる。帯域が小さく不安定になりやすいため、初回確認にはWi-Fiを推奨する。

iPhoneにRTSPまたはHTTP/MJPEG配信に対応したカメラアプリを用意し、アプリが表示するストリームURLを使用する。アプリは撮影中に前面表示したままにする。

## セットアップ

既存環境を更新する。

```bash
cd ~/gouda_ws/src/tsukuba-autonomous-robot
bash scripts/setup.sh --no-configure
```

## 起動

RTSPの場合：

```bash
export GOUDA_IPHONE_STREAM_URL='rtsp://172.20.10.1:8554/live'
bash scripts/gouda_camera.sh transport:=rtsp latency_ms:=500
```

HTTP/MJPEGの場合：

```bash
export GOUDA_IPHONE_STREAM_URL='http://172.20.10.1:8080/video'
bash scripts/gouda_camera.sh transport:=http_mjpeg latency_ms:=500
```

URLは例であり、iPhoneアプリに表示された実際のURLへ置き換える。認証情報を含むURLはシェル履歴へ直接入力せず、環境変数を設定する。

入力解像度をそのまま使う場合はwidth/heightを省略する。負荷を下げる場合は両方を指定する。

```bash
bash scripts/gouda_camera.sh transport:=rtsp width:=1280 height:=720
```

## 確認

別の端末で次を実行する。

```bash
source /opt/ros/jazzy/setup.bash
source ~/gouda_ws/install/setup.bash
export ROS_DOMAIN_ID=99
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 topic hz /camera/front/image_raw
ros2 run rqt_image_view rqt_image_view /camera/front/image_raw
```

発行トピック：

- `/camera/front/image_raw`: RGB画像
- `/camera/front/camera_info`: カメラ情報。初回は未校正

車載PCとiPhoneの時計は同期していないため、ROSメッセージにはUbuntuでフレームを受信した時刻を付ける。後の信号認識では、この時刻から画像の鮮度を監視する。

## 終了と障害時

起動した端末でCtrl+Cを押して終了する。映像が途切れた場合はドライバが再接続を試みる。iOSがカメラアプリを停止した場合、アプリを前面に戻して配信を再開する。

RTSPで映像が出ない場合は、アプリがH.264/H.265のどちらを送っているかと、Ubuntuに対応するGStreamerデコーダがあるか確認する。HTTP URLが静止画ではなく連続MJPEGエンドポイントであることも確認する。
