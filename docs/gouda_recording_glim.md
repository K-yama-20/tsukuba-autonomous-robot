# 記録とSLAM設定

この手順はセンサー観測、rosbag保存、GLIM/SLAM設定の操作案内です。記録が完了しても、センサー時刻、IMU/LiDARの取付姿勢、校正、地図や自己位置の精度が確認されたことにはなりません。

## 起動と生データの記録

Ubuntuのワークスペースにあるリポジトリで、Mission Controlとセンサー観測を起動します。初回にGLIMを使う場合は、CPU向けの固定版を含むセットアップを選びます。

```bash
cd ~/gouda_ws/src/tsukuba-autonomous-robot
bash scripts/setup.sh --with-glim
bash scripts/gouda.sh view
bash scripts/gouda.sh observe
```

ブラウザで `http://127.0.0.1:8766` を開き、「記録・SLAM」タブを選びます。生LiDAR `/lidar_points`、生IMU `/imu/data_raw`、`/tf`、`/tf_static` は必須です。必要に応じてKISS odometry `/kiss/odometry`、GLIM odometry `/glim_ros/lidar_odom`、再生時計 `/clock` を追加します。

保存形式はMCAPを推奨します。SQLite3も選べます。最大時間、分割ファイルサイズ、停止時に残す空き容量を設定し、「記録設定を保存」、「記録開始」の順に操作します。MCAP機能がない場合は不足パッケージを示して開始を拒否します。最大時間と空き容量は画面を閉じても監視されます。

記録先は `~/gouda_ws/bags/recordings/<セッション>/recording/` です。`metadata.yaml`、MCAPまたはSQLiteの分割ファイル、QoS設定、`recorder.log`、設定と結果を記した `session.json` を保存します。設定ファイルは `~/gouda_ws/bags/gouda/recording.json` に残ります。

「記録を終了」を押すと画面に「finalizing」と表示され、rosbagのファイル確定をバックグラウンドで行います。終了後にLiDARとIMUの双方でメッセージ数が1以上あり、metadataと保存ファイルが確認された場合だけ「completed」になります。センサーを起動しただけ、記録プロセスが起動しただけでは、記録成功になりません。

この記録は入力データの保存です。取付TF、センサー時刻、LiDAR点の時刻列、IMU単位や補正を推定・校正する処理ではありません。実測や校正に使う場合は、`session.json`と元データを保全してください。

## GLIMを使う場合

GLIMはCPU版1.2.2を使います。CUDAはこの導入対象ではありません。GLIM設定は `~/gouda_ws/bags/gouda/mapping.json` に保存され、次のMission Control起動時に適用されます。設定を保存した後はMission Controlを終了して起動し直してください。GLIMの開始は、実測した取付変換、点時刻のフィールド/意味/単位/型、IMU単位、LiDAR/IMU両方の時計オフセットが未入力または `UNKNOWN` の間はブロックされます。

GUIで入力する項目には、IMU原点のLiDAR座標での位置、IMUからLiDARへの姿勢クォータニオン（正規化した `x,y,z,w`）、点時刻のフィールド名とデータ型、点時刻の意味・単位、加速度・角速度の単位、LiDAR/IMUそれぞれの時計オフセットがあります。実測値が揃っていない項目は `UNKNOWN` のままにしてください。取付位置・姿勢を測定していない状態では、GLIMの結果を校正済みとして扱わず、実機SLAMの受入れは保留です。

GUIでは点時刻フィールドとして `t`、`time`、`time_stamp`、`timestamp` を指定できます。現在のHesaiドライバのPointCloud2では `timestamp` フィールドが `FLOAT64` と確認されています。ただし、この型だけでは点時刻の意味、単位、基準時刻は確定しません。実際のセンサー/ドライバ版でフィールドと時刻仕様を確認してください。ADIドライバは `GetAccSI`/`GetGyroSI` でSI単位を出しますが、軸向き、IMUからLiDARへの実測変換、センサー間の時計オフセットは別途確認が必要です。単位や時刻仕様を確定できない項目は `UNKNOWN` のままにします。

GLIMは観測セッションの間にodometry/mapプロセスを1つ動かし、2D地図作成とは独立して連続観測します。3Dセッションの成果物は `~/gouda_ws/maps_glim/session_<id>/` に保存されます。すべての観測を終えて `bash scripts/gouda.sh stop` でMission Controlを正常終了してください。GLIMは終了要求後最大90秒待って `graph.txt`、`graph.bin`、`values.bin` の保存を確認します。プロセスを強制終了すると、セッションの保存が完了しないことがあります。

2D走行用地図は「地図作成」タブから別に作ります。「新しい地図を作成」でSLAM Toolboxの2D地図作成を開始し、観測を終了して地図名を付けて保存します。GLIMの3Dセッションを保存しても2D地図は作られず、2D地図を保存してもGLIMの3D成果物は代替されません。

## 隔離したrosbag再生

再生中に実機センサーのpublisherを同時に起動しないでください。別のROS参加者との混線を避けるため、再生側はDomain 99とlocalhost discoveryを使います。Mission Controlや再生先ノードも同じ環境変数で起動してください。

```bash
cd ~/gouda_ws/src/tsukuba-autonomous-robot
bash scripts/gouda.sh stop
source /opt/ros/jazzy/setup.bash
source ~/gouda_ws/install/setup.bash
export ROS_DOMAIN_ID=99
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 bag play "$HOME/gouda_ws/bags/recordings/gouda_YYYYMMDDTHHMMSSZ/recording" --clock 100
```

再生データを処理する場合は、処理ノードもDomain 99/localhostで起動し、実機LiDAR/IMUを起動しないでください。`gouda_YYYYMMDDTHHMMSSZ` は一覧にある実際のセッション名に置き換えます。`/clock` を記録したbagでは再生時計を使い、処理側の `use_sim_time` を有効にします。保存先や設定を上書きしない専用workspaceを使う場合は、起動前に `GOUDA_WORKSPACE` を設定してください。

## 確認範囲

CIではGUI操作、記録設定、開始・終了、空の入力で成功を誤報しないことを確認します。実機データ取得を伴う確認とは別です。セットアップ、プロセス起動、MCAP生成、metadataの確認だけでは、GLIMの実機精度や正しい取付TF・時刻同期を保証しません。
