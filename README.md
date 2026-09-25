# 剛田 Mission Control — Ubuntu 24.04 / ROS 2 Jazzy

地図作成、保存、初期位置・ゴール設定をWeb GUIで扱い、KISS-ICP標準RViz2はUbuntuデスクトップの別ウィンドウで表示します。画面転送は行いません。
対象は **Ubuntu 24.04を直接起動するx86-64 PC**。開発用ARM64 Ubuntuにも対応します。

## 初回セットアップ

インターネット接続とsudo権限が必要です。ソースからビルドするため初回は時間がかかります。

```bash
sudo apt update && sudo apt install -y git
mkdir -p ~/gouda_ws/src
cd ~/gouda_ws/src
git clone --branch main --single-branch https://github.com/K-yama-20/tsukuba-autonomous-robot.git
cd tsukuba-autonomous-robot
bash scripts/setup.sh
```

非公開リポジトリの場合は、アクセス権のあるGitHubアカウントで認証してください。
GitHubの「Download ZIP」でも利用できます。対象ブランチを展開し、そのフォルダで `bash scripts/setup.sh` を実行してください。ソースは `~/gouda_ws/src/tsukuba-autonomous-robot/` に実フォルダとして配置します。以後はこのフォルダを使います。既存の異なるチェックアウトがある場合は上書きせず停止します。

依存ソフト、固定版の外部ドライバとサブモジュール、ドライバ修正、ビルドをセットアップが実施します。最後にLiDAR専用LANとIMUのUSB接続を選びます。機器がない場合はEnterで省略できます。
既存の地図・設定は削除しません。既に別のソースがある場合は置換せず停止します。

## 起動

Ubuntuにデスクトップログインした端末で、`~/gouda_ws/src/tsukuba-autonomous-robot/` に移動して実行します。RVizは自動で別ウィンドウに開きます。Web GUIはブラウザで **http://127.0.0.1:8766** を開きます。SSHだけの端末では表示先がないため、RVizは起動できません。

```bash
bash scripts/gouda.sh view       # GUI・処理・別ウィンドウのRVizを起動（センサー受信は追加しない）
bash scripts/gouda.sh stop       # 終了時
bash scripts/gouda.sh observe    # LiDAR・IMUを使った観測
bash scripts/gouda.sh viewer     # RVizだけを起動し直す
bash scripts/gouda.sh doctor     # 設定・プロセス・表示状態の診断
bash scripts/gouda.sh configure  # 機器設定をやり直す
```

記録とGLIM/SLAMの設定、保存先、再生方法は[記録とSLAM設定](docs/gouda_recording_glim.md)を参照してください。

## 歩行者信号認識

同じセットアップでインストールしたQtアプリは、Ubuntuデスクトップ上で起動します。詳細は[歩行者信号アプリ](docs/pedestrian_signal.md)を参照してください。

```bash
bash scripts/gouda.sh signal
```

起動コマンドはバックグラウンドで動作を維持します。再実行で生存中のセンサーを再起動しません。`view` から `observe` に切り替える場合もGUIとRVizを維持してセンサー受信を追加します。ブラウザの再読み込みやタブ切替もセンサー受信には影響しません。`stop` はこの起動処理が所有するプロセスだけを止めます。別の起動方法で同じAPIポートを使用している場合は、勝手に停止・流用せずエラーにします。

## 保存地図で経路を確認する

「走行計画」で保存地図を読み込み、「計画開始位置」と「ゴール」をそれぞれ指定して設定ボタンで確定し、「経路を計算」を押します。入力途中の座標は計算に使いません。押せない場合は、ボタンの下に不足している条件を表示します。

観測モードの経路計算には、ESP32、現在位置の受信、センサー接続は必要ありません。保存した2D地図だけを使い、計算時だけ専用のNav2プランナーを起動します。計算終了時には停止します。地図・開始位置・ゴールを変更すると前の経路を無効にします。障害物・未観測領域・地図外に位置を設定した場合や経路が見つからない場合は理由を表示します。

「計画開始位置」は経路計算だけに使う位置です。「自己位置の初期設定」は保存したSLAMデータでLiDARの自己位置推定を始める別の操作です。地図を読み込むだけでは自己位置推定を開始しません。

表示する経路は地図上のプレビューです。車体寸法や取付座標を校正した通過可否の確認は含まず、走行開始も無効のままです。

## 実機の接続

- LiDAR専用の有線LANを選びます。PC側 `192.168.1.100/24`、XT32側 `192.168.1.201`、UDP 2368、PTC 9347を使用します。インターネットの既定経路があるLANは変更しません。
- NetworkManagerに専用接続を追加します。既存プロファイルは残し、変更前の情報を設定フォルダの `network-backups/` に保存します。戻す場合は記録された以前の接続を `sudo nmcli connection up uuid <UUID>` で有効にします。
- 補正CSVはXT32本体から読み取り専用コマンドで取得します。取得できない場合は、その機器から取得済みのCSVを指定するか、後で設定します。補正値を推測したサンプルには置き換えません。
- IMUは `/dev/serial/by-id/` の一覧から選択します。USB権限の追加が必要だった場合は、一度ログアウト・ログインしてください。
- 未接続・設定不足なら `observe` は原因を表示します。LiDARに別の宛先IPが設定されている場合、本体側の設定は自動変更しません。

## 保存先・表示

x86とParallelsの双方で、ワークスペース内にソース・ビルド・地図・機器設定をまとめます。

```text
~/gouda_ws/
├── src/
│   ├── tsukuba-autonomous-robot/
│   ├── ADI_IMU_TR_Driver_ROS2/
│   ├── HesaiLidar_ROS_2.0/
│   ├── kiss-icp/
│   └── urg_node2/
├── build/
├── install/
├── log/
├── bags/
│   ├── gouda/                  # host.json・機器設定・実行状態・ログ
│   └── recordings/             # GUIで記録したrosbag
├── maps/
├── maps_sensor_slam/
└── maps_glim/                  # GLIM 3D観測セッション
```

`GOUDA_WORKSPACE` でワークスペースを変更できます。既存のParallelsの記録フォルダと補正データは保持します。新規設定の保存先は日付やユーザー名に依存しません。個人の設定、地図、点群、ログをGitへ追加しないでください。

RVizはKISS-ICP付属の表示設定をそのまま使用します。Ubuntuの通常の描画環境を使い、ソフトウェア描画を強制しません。本番起動ではXvfb・Openbox・x11vnc・noVNCを起動せず、画像圧縮・画面転送も行いません。RViz自体の点群描画とSLAMの計算負荷は残ります。標準の局所点群と保存済みの走行用2D地図は別用途です。

MacからGUIを使用する場合、既存の認証付きSSHでAPIを中継できます。RVizはUbuntu側のデスクトップに表示され、Macへの画面転送はありません。

```bash
python3 gouda_gui/gouda_gui/gateway.py --ssh-runtime /path/to/existing/native_view/runtime
```

指定フォルダには既存の `connection.json`、`id_ed25519`、検証済みの `known_hosts` が必要です。秘密鍵や接続設定は共有しません。

## すでに旧版をビルドしたx86 PCの更新

環境の削除やUbuntu・ROSの入れ直しは不要です。先に旧版が管理するプロセスを停止してから更新します。現在使っているリポジトリのフォルダで次を実行してください。

```bash
bash scripts/gouda.sh stop
git pull --ff-only
bash scripts/setup.sh --no-configure
cd ~/gouda_ws/src/tsukuba-autonomous-robot
bash scripts/gouda.sh observe
```

旧版の `~/.config/gouda/` と `~/.local/share/gouda/` は移行元として保持します。設定・地図の衝突がある場合は上書きしません。必要なビルドの退避と再構築はセットアップが行います。旧ソースフォルダを自分で削除する必要はありません。機器設定が未完了の場合は `bash scripts/gouda.sh configure` を実行してください。

センサー停止を伴う更新後にIMUが応答しなくなった場合は、既知の再接続問題の可能性があります。GUI再接続やRVizだけの再起動ではセンサー受信を再起動しません。

## 検証と現在の制限

```bash
bash scripts/test.sh
```

GitHub Actionsではx86-64／ARM64のクリーン環境でセットアップ、再実行、テスト、実機データ待ちの空のGUI、別ウィンドウのRViz起動、タブ切替・再接続を確認します。CIだけで使う仮想デスクトップは、本番起動には含めません。入力のないCIでは地図保存や位置推定の実機検証は行いません。CIログの成功は実機センサーや実走行の成功を示しません。

- `observe` は観測専用です。車両制御ブリッジや走行出力は起動しません。デモ起動、架空の地図・座標の生成機能は配布しません。
- IMUドライバの再起動後に応答が停止する問題は未解決です。受信プロセスと表示を分離していますが、再発時にはIMUの電源入れ直しが必要な場合があります。
- センサー取付座標・軸方向は未校正です。IMU融合とdeskewは有効にしていません。地図精度の実測保証はありません。
- 過去の調査記録は `docs/` にあります。現在の導入・保存先はこのREADMEを優先してください。

外部ソースは各プロジェクトのライセンスに従います。第三者ソースは `third_party/external.repos` の固定コミットから取得し、`patches/` の変更を適用します。
