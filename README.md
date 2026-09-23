# 剛田 Mission Control — Ubuntu 24.04 / ROS 2 Jazzy

地図作成、保存、初期位置・ゴール設定と、KISS-ICP標準RViz2画面を同じGUIで扱います。
対象は **Ubuntu 24.04を直接起動するx86-64 PC**。開発用ARM64 Ubuntuにも対応します。

## 初回セットアップ

インターネット接続とsudo権限が必要です。ソースからビルドするため初回は時間がかかります。

```bash
sudo apt update && sudo apt install -y git
git clone --branch feature/aya-navsystem --single-branch https://github.com/K-yama-20/tsukuba-autonomous-robot.git
cd tsukuba-autonomous-robot
bash scripts/setup.sh
```

非公開リポジトリの場合は、アクセス権のあるGitHubアカウントで認証してください。
GitHubの「Download ZIP」でも利用できます。対象ブランチを選んで展開し、そのフォルダで `bash scripts/setup.sh` を実行してください。

依存ソフト、固定版の外部ドライバとサブモジュール、ドライバ修正、ビルドをセットアップが実施します。最後にLiDAR専用LANとIMUのUSB接続を選びます。機器がない場合はEnterで省略できます。
既存の地図・設定は削除しません。既に別のソースがある場合は置換せず停止します。

## 起動

リポジトリのフォルダで実行し、ブラウザで **http://127.0.0.1:8766** を開きます。

```bash
bash scripts/gouda.sh view       # 実機データを待つ画面だけ起動
bash scripts/gouda.sh stop       # 終了時
bash scripts/gouda.sh observe    # LiDAR・IMUを使った観測
bash scripts/gouda.sh doctor     # 設定・プロセス・入力更新状態の診断
bash scripts/gouda.sh configure  # 機器設定をやり直す
```

起動コマンドはバックグラウンドで動作を維持します。再実行で生存中のセンサーを再起動しません。`view` から `observe` に切り替える場合も画面を維持してセンサー受信を追加します。ブラウザの再読み込みやタブ切替もセンサー受信には影響しません。`stop` はこの起動処理が所有するプロセスだけを止めます。別の起動方法で同じポートや専用画面を使用している場合は、勝手に停止・流用せずエラーにします。

## 実機の接続

- LiDAR専用の有線LANを選びます。PC側 `192.168.1.100/24`、XT32側 `192.168.1.201`、UDP 2368、PTC 9347を使用します。インターネットの既定経路があるLANは変更しません。
- NetworkManagerに専用接続を追加します。既存プロファイルは残し、変更前の情報を設定フォルダの `network-backups/` に保存します。戻す場合は記録された以前の接続を `sudo nmcli connection up uuid <UUID>` で有効にします。
- 補正CSVはXT32本体から読み取り専用コマンドで取得します。取得できない場合は、その機器から取得済みのCSVを指定するか、後で設定します。補正値を推測したサンプルには置き換えません。
- IMUは `/dev/serial/by-id/` の一覧から選択します。USB権限の追加が必要だった場合は、一度ログアウト・ログインしてください。
- 未接続・設定不足なら `observe` は原因を表示します。LiDARに別の宛先IPが設定されている場合、本体側の設定は自動変更しません。

## 保存先・表示

| 内容 | 保存先 |
|---|---|
| 機器設定・補正値 | `~/.config/gouda/` |
| 地図・実行状態・ログ | `~/.local/share/gouda/` |
| 外部ソース・ビルド | `~/gouda_ws/` |

`GOUDA_WORKSPACE` で作業領域、`XDG_CONFIG_HOME` と `XDG_DATA_HOME` で保存先を変更できます。設定済みの別作業領域への切替は既存設定を上書きしません。旧環境の地図は移動・削除せず、必要に応じて従来の地図フォルダから移してください。

3D表示はKISS-ICP付属のRViz設定をそのまま使い、専用仮想画面をnoVNCでフルカラー・可逆転送します。マウスで回転・移動・拡大できます。標準の局所点群は保存済みの走行用2D地図とは別です。表示ソフトはUbuntu 24.04のnoVNC 1.3系を対象とし、CIで実際のブラウザ表示を確認します。

Macから既存SSH接続を使う場合は、Macでaiohttpを導入したPythonから次を実行します（通常のUbuntu利用では不要）。鍵や接続設定は共有しません。

```bash
python3 gouda_gui/gouda_gui/gateway.py --ssh-runtime /path/to/existing/native_view/runtime
```

指定フォルダには `connection.json`（`host` / `user`）、`id_ed25519`、検証済みの `known_hosts` が必要です。接続先Ubuntuの8765と6080を転送します。既存のMac用起動方法も引き続き利用できます。

## 検証と現在の制限

```bash
bash scripts/test.sh
```

GitHub Actionsではx86-64／ARM64のクリーン環境でセットアップ、再実行、テスト、実機データ待ちの空の画面、RViz画面のブラウザ操作・再接続を確認します。入力のないCIでは地図保存や位置推定の実機検証は行いません。CIログの成功は実機センサーや実走行の成功を示しません。

- `observe` は観測専用です。車両制御ブリッジや走行出力は起動しません。デモ起動、架空の地図・座標の生成機能は配布しません。
- IMUドライバの再起動後に応答が停止する問題は未解決です。受信プロセスと表示を分離していますが、再発時にはIMUの電源入れ直しが必要な場合があります。
- センサー取付座標・軸方向は未校正です。IMU融合とdeskewは有効にしていません。地図精度の実測保証はありません。
- 過去の調査記録は `docs/` にあります。現在の導入・保存先はこのREADMEを優先してください。

外部ソースは各プロジェクトのライセンスに従います。第三者ソースは `third_party/external.repos` の固定コミットから取得し、`patches/` の変更を適用します。
