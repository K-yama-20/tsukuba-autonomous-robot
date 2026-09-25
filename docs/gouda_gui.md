# Mission Controlの起動

現在の導入・起動手順は [README](../README.md) を参照してください。

- `bash scripts/setup.sh`：初回セットアップ。
- `bash scripts/gouda.sh view`：実機データを待つGUIと標準RVizを起動。
- `bash scripts/gouda.sh observe`：設定済みのLiDAR・IMU受信を追加。
- `bash scripts/gouda.sh doctor`：接続と更新状態を診断。
- `bash scripts/gouda.sh stop`：管理対象だけ停止。

入口は `http://127.0.0.1:8766`。デモの地図や座標は生成しません。
初期位置・ゴール設定は走行用2D地図で行い、標準RViz内の局所点群とは区別します。
観測モードでは車両への走行出力を起動しません。


## iPhoneからのMission Control

`phone_gateway` はiPhone向けのHTTPS入口です。通常のMission Controlと同じ地図、記録、SLAM、自動運転の画面を小さい画面に並べ、地図は2本指で拡大縮小できます。位置と向きは従来どおり数値でも入力できます。ホーム画面へ追加すると全画面表示になります。制御画面をオフライン保存したり、オフライン中の操作を後で送る機能はありません。操作は接続中に一度だけ送信されます。

ローカルの `http://127.0.0.1:8766` は従来どおり初期設定です。遠隔アクセスは、証明書・アクセスキー・LAN Host許可を明示した場合だけ別ポートで有効になります。例えば、設定スクリプトが発行した証明書とキーを使い、PCとiPhoneが同じプライベートネットワーク上にいる状態で次のように起動します。

```sh
ros2 run gouda_gui phone_gateway --remote-only --remote-bind 0.0.0.0 --remote-port 8443 \
  --tls-cert /path/to/tls.crt --tls-key /path/to/tls.key \
  --remote-token-file /path/to/token --allowed-host 192.168.1.20
```

`--allowed-host` は繰り返し指定できます。テザリングやPCのアクセスポイントでIPが変わる場合は、証明書SANと許可Hostをその接続先に合わせて作り直します。`--allow-private-hosts` はプライベートIP Hostを許可する明示的な代替設定です。どちらの方法でもHTTPSとアクセスキーが必要です。アクセスキーはブラウザーのタブセッション内だけに保持します。状態と操作要求はアクセスキーに加え、Mission Control自身の操作セッションでも確認されます。

PC常駐の遠隔入口を使う場合は `scripts/setup_phone_access.py` の手順を参照してください。そこで作ったCA証明書をiPhoneに信頼させてからHTTPS URLを開き、共有アクセスキーを入力します。ゲートウェイはGUIバックエンドが停止している間も起動要求を受けられます。画面から観測の開始、明示選択したプロファイルでの再起動、停止、保存設定の適用を要求できます。要求には処理IDが返り、完了状態はPC側の状態取得で確認します。

地図、記録、SLAM設定、走行計画、明示起動済みの自動運転はブラウザーから利用できます。地図作成に必要なセンサー配線や機器へのアクセス、Ubuntuの初回起動、電源操作と物理非常停止は現地作業です。RVizの3D点群はPCの画面に表示します。iPhoneには画面転送を行いません。自動運転の開始条件、手動優先、停止確認は既存の制御側の判定が引き続き必要です。
