# Gouda PWAをiPhoneからオフライン利用する

Ubuntu上のGouda GUIを、同じローカルネットワークに接続したiPhoneのSafariで開く手順です。専用のCA証明書、HTTPSサーバー証明書、ランダムな認証トークンを作ります。証明書のiPhoneへのインストール、ホットスポット設定、ユーザーサービスの登録は、各手順を実行した場合だけ行われます。

## 1. Ubuntuで証明書とトークンを作る

まず、iPhoneから実際に解決できるDNS名を選びます。スクリプトは指定された名前を証明書に記録しますが、Ubuntuのホスト名やmDNS/Avahiの設定は変更しません。たとえば `gouda.local` を使う場合、iPhoneからその名前がUbuntuのアドレスへ解決できることを確認してください。名前解決を確認できない場合は、Safariで使うIPアドレスをSANに追加します。

次の値は説明用です。実際に使う名前とアドレスに置き換えてください。

```bash
cd /home/aya/gouda_ws/src/tsukuba-autonomous-robot
python3 scripts/setup_phone_access.py --hostname gouda.local --ip-address 10.42.0.1
```

`--hostname` は必須です。iPhoneでIPアドレスを使うなら、URLに入力するものと同じIPを `--ip-address` で指定します。複数のアドレスはこのオプションを繰り返して指定できます。接続先アドレスが変わると、その新しいアドレスは証明書に一致しません。

出力先は通常 `$GOUDA_WORKSPACE/bags/gouda/phone-access/` です。`GOUDA_WORKSPACE` が未設定なら `~/gouda_ws/bags/gouda/phone-access/` を使います。公開証明書 `ca.crt` だけをiPhoneへ渡してください。`ca.key`、`tls.key`、`token` は秘密情報です。ディレクトリはモード0700、秘密鍵・トークン・設定ファイルは0600で作られます。コマンドの出力にはトークンを表示しません。

同じ名前とIPで再実行すると既存の一式を検査して再利用します。異なるIDや手作業で置かれたファイルがある場合は上書きせず停止します。iPhoneテザリングなどでUbuntuのIPが後から変わった場合は、先にゲートウェイを停止し、新しいIPだけを明示して既存CAを維持してサーバー証明書のSANを拡張できます。CAとトークンは維持されるので、iPhoneでCAを再インストールする必要はありません。

```bash
python3 scripts/setup_phone_access.py --hostname gouda.local --ip-address 172.20.10.4 --extend-existing
```

例のIPは置き換えてください。実際のアドレスは次の読み取り専用確認で調べます。SANを拡張した後はゲートウェイを再起動します。ホスト名の変更やSANの削除にはこの拡張操作を使えません。

現在のネットワーク状態と、Wi-Fi機器がAPモードを申告しているかを読み取り専用で表示するには、次を実行します。

```bash
python3 scripts/setup_phone_access.py --check-network
```

## 2. 公開CA証明書をiPhoneへ移して信頼する

UbuntuからMacへ、既存のローカル転送手段（USB、ファイル共有、SSHなど）で `ca.crt` をコピーし、MacからAirDropでiPhoneへ送ります。Ubuntu自身はAirDropを使いません。AirDropによる近距離転送にインターネット接続は不要です。この手順でiPhoneへ渡すファイルは公開証明書の `ca.crt` だけです。秘密鍵は絶対に転送しません。認証トークンは別途、Ubuntuの自分専用端末で表示して、信頼できるiPhoneへ入力するか、パスワードマネージャーを使って安全に入力してください。

iPhoneで受け取った `ca.crt` をタップし、内容を確認して端末へ追加します。iOSがプロファイルのダウンロードを表示した場合は、**設定 → 一般 → VPNとデバイス管理**からインストールしてください。その後、次を開きます。

**設定 → 一般 → 情報 → 証明書信頼設定**

**ルート証明書の完全な信頼を有効にする**に表示された「Gouda Phone Access Local CA」を有効にします。手動で追加したルート証明書は、追加しただけではSSL/TLSで信頼されないため、この操作が必要です。Appleの手順: [証明書をAppleデバイスに配布する](https://support.apple.com/en-au/guide/deployment/depcdc9a6a3f/web)、[手動でインストールした証明書を信頼する](https://support.apple.com/en-ie/102390)。

## 3. UbuntuとiPhoneを同じネットワークに接続する

次のいずれかを使います。

- 両方を、端末同士のローカル通信を許可するWi-Fiへ接続する。
- AP対応のWi-FiアダプターをUbuntuに接続し、Ubuntuをホットスポットにする。作成前に `--check-network` を実行し、使うWi-Fi機器に `WIFI-PROPERTIES.AP: yes` が表示されることを確認する。
- iPhoneのインターネット共有へUbuntuをWi-FiまたはUSBで接続する。インターネット接続は不要だが、Ubuntuが現在受け取っているアドレスを調べ、そのIPが証明書のSANに含まれていることを確認する。

現行の開発VMにはEthernetしかなく、Wi-FiのAPモードとiPhone接続は未検証です。

AP対応を確認したUbuntuで、既存ネットワークと重ならないサブネットを選んだ場合のみ、次のコマンドを使えます。例ではWi-Fi専用の接続プロファイルを作り、ホストを `10.42.0.1` にします。Wi-Fi機器名とサブネットは実機に合わせてください。

```bash
WIFI_IF=wlp2s0  # --check-networkで確認したWi-Fi機器名に置き換える
nmcli connection add type wifi ifname "$WIFI_IF" con-name gouda-phone-ap autoconnect no ssid Gouda-Phone wifi.mode ap wifi.band bg wifi-sec.key-mgmt wpa-psk ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv6.method disabled
nmcli --ask connection up gouda-phone-ap
```

2つ目のコマンドでホットスポットのセキュリティキーを入力します。iPhoneを「Gouda-Phone」へ接続します。NetworkManagerの `nmcli` 構文は[公式リファレンス](https://networkmanager.pages.freedesktop.org/NetworkManager/NetworkManager/nmcli.html)を参照してください。

LiDAR用の有線接続と `192.168.1.100` は変更しません。ホットスポットを止める場合は `nmcli connection down gouda-phone-ap` を実行します。フィールドPCの起動時にもWi-Fiを自動公開すると確認できた場合に限り、次を実行してこのプロファイルだけの自動接続を有効にできます。

```bash
nmcli connection modify gouda-phone-ap connection.autoconnect yes
```

これは説明用コマンドであり、セットアップスクリプトは実行しません。

## 4. GUIパッケージをビルドしてユーザーサービスを登録する

この版で追加された `phone_gateway` エントリーポイントを使うため、更新後にGUIパッケージを一度ビルドしてください。この版の `scripts/setup.sh` を最後まで実行済みなら、そのビルドは完了しています。古い版でセットアップ済みの場合は、次を実行します。Ubuntu 24.04上でROS 2 Jazzyと必要な依存パッケージが用意されていることが前提です。

```bash
source /opt/ros/jazzy/setup.bash
cd "${GOUDA_WORKSPACE:-$HOME/gouda_ws}"
colcon build --symlink-install --packages-up-to gouda_gui
```

証明書・トークンを作り、Goudaワークスペースがビルド済みであることを確認してから、リポジトリでユーザーサービスを明示的に登録します。

```bash
cd /home/aya/gouda_ws/src/tsukuba-autonomous-robot
bash scripts/install_phone_gateway_service.sh
```

このスクリプトはユーザーのsystemdサービスを作成し、有効化して起動します。ログイン前のPC起動時にもサービスを開始したい場合だけ、追加でlingerを有効にします。

```bash
sudo loginctl enable-linger "$(id -un)"
```

## 5. iPhoneから開く

iPhoneのSafariで、証明書SANと一致するアドレスを開きます。

- `https://10.42.0.1:8443`
- `https://gouda.local:8443`

これらは例です。ホスト名が解決できない場合はIPアドレスを使ってください。PWAが求めたら、Ubuntuで自分のユーザーとして開いた端末からトークンを表示し、内容をiPhoneへ入力します。`GOUDA_WORKSPACE` が未設定の場合のコマンドです。

```bash
cat "$HOME/gouda_ws/bags/gouda/phone-access/token"
```

`GOUDA_WORKSPACE` を設定している場合は、その値に合わせてパスを置き換えてください。これは自分専用の端末だけで実行し、トークンをチャット、ログ、共有画面へ貼り付けないでください。必要なら信頼できるパスワードマネージャーに保管してください。Safariの共有メニューから **ホーム画面に追加** を選ぶと、ホーム画面にアイコンを作れます。

証明書名エラーが出た場合、Safariに入力した名前/IPがサーバー証明書SANに含まれているか確認します。ホストが見つからない場合は、先にiPhoneから名前解決できるか、同じローカルネットワークにいるかを確認してください。証明書の設定だけでは名前解決や通信経路は作られません。

この構成は、認証付きHTTPSによるローカルGUIアクセスを提供します。全てのWi-Fiのピア間通信や実機ネットワークを保証するものではありません。ホットスポット作成、証明書のiPhoneへの追加、ユーザーサービスの登録は、ここに記載した操作を実行した場合のみ変更されます。
