# 記録とSLAM設定

この手順はセンサー観測、rosbag保存、GLIM/SLAM設定の操作案内です。記録が完了しても、センサー時刻、IMU/LiDARの取付姿勢、校正、地図や自己位置の精度が確認されたことにはなりません。

## 起動と生データの記録

Ubuntuのワークスペースにあるリポジトリで、Mission Controlとセンサー観測を起動します。初回にGLIMを使う場合は、CPU向けGLIMパッケージを追加します。既存のセンサー設定を再構成しないため `--no-configure` を付けます。

```bash
cd ~/gouda_ws/src/tsukuba-autonomous-robot
bash scripts/setup.sh --with-glim --no-configure
bash scripts/gouda.sh view
bash scripts/gouda.sh observe
```

ブラウザで `http://127.0.0.1:8766` を開き、「記録・SLAM」タブを選びます。生LiDAR `/lidar_points`、生IMU `/imu/data_raw`、`/tf`、`/tf_static` は必須です。必要に応じてKISS odometry `/kiss/odometry`、GLIM odometry `/glim_ros/lidar_odom`、再生時計 `/clock` を追加します。

保存形式はMCAPを推奨します。SQLite3も選べます。最大時間、分割ファイルサイズ、停止時に残す空き容量を設定し、「記録設定を保存」、「記録開始」の順に操作します。MCAP機能がない場合は不足パッケージを示して開始を拒否します。最大時間と空き容量は画面を閉じても監視されます。

記録先のセッションフォルダーは `~/gouda_ws/bags/recordings/<セッション>/` です。rosbagの `metadata.yaml` とMCAPまたはSQLite分割ファイルはその中の `recording/` に保存します。QoS設定 `qos_overrides.yaml`、`recorder.log`、設定と結果を記した `session.json` はセッションフォルダー直下に保存します。設定ファイルは `~/gouda_ws/bags/gouda/recording.json` に残ります。

「記録を終了」を押すと画面に「finalizing」と表示され、rosbagのファイル確定をバックグラウンドで行います。終了後にLiDARとIMUの双方でメッセージ数が1以上あり、metadataと保存ファイルが確認された場合だけ「completed」になります。センサーを起動しただけ、記録プロセスが起動しただけでは、記録成功になりません。

旧設定を読み込んだ場合も、分析に使う次のROSトピックを有効設定とbagへ自動追加します。/cmd_vel は別パッケージが後からpublisherを起動する場合に備えて選択します。bag内に現れなかったトピックは終了後の件数が0になります。

- /cmd_motion、/gouda/motion_permit、/esp32/status
- /gouda/navigation_state、/gouda/pose、/glim_ros/lidar_odom、/cmd_vel

session.json とGUIのtopic countsは、各選択topicの記録件数と、終了metadataで0件だった分析topicを示します。metadata_verified はLiDAR/IMUの双方にメッセージがあり、保存ファイルが非空だったことを表します。control_data_seen と missing_control_topics は分析用topicの存在状況であり、制御成功や車輪の動作を表すものではありません。

現在の /cmd_motion はheaderなしの UInt8 指令で、bag時刻はROS recorderの受信時刻です。指令生成時刻やマイコンでの適用時刻は含まれません。現在の /esp32/status はシリアルstatus frameのJSON (kind, token, seq, motion, flags, fault) で、DAC出力値、測定電圧、車輪の実測速度は含みません。したがって、このbagだけでは指令が物理系に適用されたことを確定できません。実際にbagへ入ったメッセージと取得時刻を確認し、制御応答の評価ではこの限界を考慮してください。

この記録は入力データの保存です。取付TF、センサー時刻、LiDAR点の時刻列、IMU単位や補正を推定・校正する処理ではありません。実測や校正に使う場合は、`session.json`と元データを保全してください。

## GLIMを使う場合

セットアップはUbuntu 24.04/Jazzy向けのCPU版 `ros-jazzy-glim-ros` を導入し、CUDAは対象外です。確認したVMには `1.2.2-0noble` が入っていましたが、セットアップではaptの版を固定していません。GLIM設定は `~/gouda_ws/bags/gouda/mapping.json` に保存され、次のMission Control起動時に適用されます。設定を保存した後はMission Controlを終了して起動し直してください。GLIMの開始は、実測した取付変換、点時刻のフィールド/意味/単位/型、IMU単位、LiDAR/IMU両方の時計オフセットが未入力または `UNKNOWN` の間はブロックされます。

GUIで入力する項目には、IMU原点のLiDAR座標での位置、IMUからLiDARへの姿勢クォータニオン（正規化した `x,y,z,w`）、点時刻のフィールド名とデータ型、点時刻の意味・単位、加速度・角速度の単位、LiDAR/IMUそれぞれの時計オフセットがあります。実測値が揃っていない項目は `UNKNOWN` のままにしてください。取付位置・姿勢を測定していない状態では、GLIMの結果を校正済みとして扱わず、実機SLAMの受入れは保留です。

GUIでは点時刻フィールドとして `t`、`time`、`time_stamp`、`timestamp` を指定できます。現在のHesaiドライバのPointCloud2では `timestamp` フィールドが `FLOAT64` と確認されています。ただし、この型だけでは点時刻の意味、単位、基準時刻は確定しません。実際のセンサー/ドライバ版でフィールドと時刻仕様を確認してください。ADIドライバは `GetAccSI`/`GetGyroSI` でSI単位を出しますが、軸向き、IMUからLiDARへの実測変換、センサー間の時計オフセットは別途確認が必要です。単位や時刻仕様を確定できない項目は `UNKNOWN` のままにします。

GLIMは観測セッションの間にodometry/mapプロセスを1つ動かし、2D地図作成とは独立して連続観測します。3Dセッションの成果物は `~/gouda_ws/maps_glim/session_<id>/` に保存されます。すべての観測を終えて `bash scripts/gouda.sh stop` でMission Controlを正常終了してください。Mission Controlの正常終了処理はGLIMへ終了要求を送り、最大90秒待ちます。現在の確認処理は `graph.txt` と `values.bin` の存在を確認します。プロセスを強制終了すると、セッションの保存が完了しないことがあります。

2D走行用地図は「地図作成」タブから別に作ります。「新しい地図を作成」でSLAM Toolboxの2D地図作成を開始し、観測を終了して地図名を付けて保存します。GLIMの3Dセッションを保存しても2D地図は作られず、2D地図を保存してもGLIMの3D成果物は代替されません。

## 隔離したrosbag再生

再生中に実機センサーpublisherを同時に起動しないでください。再生と処理ノードをDomain 99/localhostに隔離します。まずセンサーを起動せず、再生モードのMission Controlを起動します。

```bash
cd ~/gouda_ws/src/tsukuba-autonomous-robot
bash scripts/gouda.sh stop
source /opt/ros/jazzy/setup.bash
source ~/gouda_ws/install/setup.bash
export ROS_DOMAIN_ID=99
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 launch gouda_gui observation.launch.py replay:=true sensors:=false
```

別の端末でも同じROS環境とDomain 99/localhostを設定してから、bagを再生します。LiDAR/IMU生データだけを流し、記録済みの推定TFやodometryを稼働中の推定器へ重ねないでください。必要な静的変換がある場合だけ、検証した `/tf_static` を追加してください。

```bash
source /opt/ros/jazzy/setup.bash
source ~/gouda_ws/install/setup.bash
export ROS_DOMAIN_ID=99
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 bag play "$HOME/gouda_ws/bags/recordings/<実際のセッション名>/recording" --clock 100 --topics /lidar_points /imu/data_raw
```

GLIM設定が完成している場合、Mission Controlの再生モードで処理します。再生時計を使う処理ノードは `use_sim_time` を有効にします。再生bagをもう一度rosbag記録する場合も、Mission Control再生モードの記録機能を使ってください。記録側は `--use-sim-time` を指定して `/clock` をbagに含めます。`GOUDA_WORKSPACE` を使うときは、Mission Controlを起動する前に専用workspaceを設定し、センサーや既存設定・地図のworkspaceと混ぜないでください。

## 確認範囲

CIではGUI操作、記録設定、開始・終了、空の入力で成功を誤報しないことを確認します。実機データ取得を伴う確認とは別です。セットアップ、プロセス起動、MCAP生成、metadataの確認だけでは、GLIMの実機精度や正しい取付TF・時刻同期を保証しません。
