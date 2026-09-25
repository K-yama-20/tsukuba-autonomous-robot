# LiDAR・IMUの時刻対応（2026-09-26）

## 今回の構成

ユーザー確認：同期用の追加配線はない。USBとXT32付属ケーブルのみ。

- XT32：PCをPTP配信元にしてEthernet経由でPC時刻へ合わせる。ドライバーは `use_timestamp_type: 0`（機器時刻）を使う。
- IMU_16607 USB：Data Readyによる取得時点のマイコン内部マイクロ秒時刻を、PC受信時刻との対応から推定変換する。ハードウェア同期ではない。
- GLIM：検査済みの `/gouda/synced/imu` と `/gouda/synced/points` を購読する。元の計測時刻・点群データを保持し、設定済みの残留オフセットはGLIM内で一度だけ適用する。

## 資料で確認したこと

ユーザー提供 `TR-IMU基板共通_USB,UART通信仕様書.pdf` p.12 §5.4.12：timestampはIMUデータ取得時点のMCU起動後経過時間、単位us。取得はDR信号に同期。p.2：同じ値が複数回送信される場合がありimu_counterで新規計測を判別する。

同仕様書はDR間隔が不均一な場合があるためtimestampをログ用途とし演算利用を推奨していない。今回の対応は時刻の由来を保持するソフトウェア推定であり、センサーの厳密な等間隔サンプリングや絶対同期を保証しない。固定USB遅延は回帰残差から特定できない。実測による残留オフセット・有効性の確認は残る。

`IMU_16607_ハードウェアマニュアル.pdf` p.8：内部ADIS_SYNCはMCU PB0へ接続。p.9：外部CN1のPB2/PB10は補助信号との記載のみ。別製品Platform2のCN3/PB10のGNSS PPS記載を、そのままIMU_16607の端子仕様として扱わない。追加配線や電気条件は未確定のため設定・接続しない。

公式資料：
- [TechnoRoad ROS2 driver](https://github.com/technoroad/ADI_IMU_TR_Driver_ROS2)
- [Hesai PTP同期手順](https://hesaitechnology.github.io/dev/docs/how_to_guides/ptp_sync_application/)
- [linuxptp設定](https://www.linuxptp.org/documentation/ptp4l/)

## 導入・機器を動かさない設定確認

リポジトリルートで実行。通常のセットアップが時刻対応ドライバーパッチを適用し、元ファイルを保存する。ESP32の書き込み・走行指令はない。

```sh
bash scripts/setup.sh --with-glim --no-configure
python3 scripts/time_sync_host.py inspect
```

`inspect` はホスト設定、選択されたLiDAR時刻源、NICの対応機能、PTP実行ファイルの有無を読み取る。LiDAR本体の同期ロックは自動取得していないため、結果を同期済みと解釈しない。

XT32のWeb画面で Clock Source=PTP、Profile=1588v2、Transport=UDP/IP、Domain=0を設定・確認する。IMU側の同期端子設定は変更しない。

LiDAR専用Ethernetインターフェースを指定して別ターミナルで実行：

```sh
sudo python3 scripts/time_sync_host.py ptp --interface <LiDAR用インターフェース>
```

これは明示実行時のみPTPを配信する。PCを配信元に限定し、LiDAR側からPCの時計を変更する構成にはしない。Ctrl+Cで停止。ソフトウェア時刻刻印を用いるのでNICのハードウェア同期精度を主張しない。XT32のHome画面でTracking/Lockedおよびoffsetを確認する。PTPの時刻系とROSのUTC/Unix時刻が一致することも確認する（数十秒の差を手入力で隠さない）。

観測プログラムを停止してから、機器設定の確認記録を付けてホスト設定を移行：

```sh
python3 scripts/time_sync_host.py prepare --evidence '追加同期配線なし。XT32 PTP/1588v2/UDP/IP/domain0、PC配信元、機器画面の状態と確認日時をここに記入'
```

元のhost.json、LiDAR設定、既存mapping.jsonは `bags/gouda/time-sync-*/` に保存。新しいLiDAR設定を別ファイルに作成し、参照先を変更する。未測定の取付姿勢・位置やオフセットをゼロで埋めない。元に戻す場合は保存したhost.jsonとmapping.jsonを元の位置に戻す（現在の設定も先に保存する）。

GUI「記録・SLAM」の時刻方式は「PC時刻への推定対応」を選ぶ。端子・機器設定の確認記録を入力する。IMU取付寸法・向きなど従来の未確定項目は引き続きGLIM開始条件となる。「外部共通時計」は現USBドライバーでは非対応として開始を拒否する。

## 検査・記録

- IMUの変換モデルが未確定ならGLIM用データを流さない。
- 計測番号の重複、時刻の逆行、PC時計の急変、点群時刻のNaN・単位不整合・異なる時刻系を検出する。
- 各IMU計測の時刻と対応する時計状態を照合する。別トピックの到着順は短時間バッファして吸収する。
- 点群と直近IMUの時刻差／受信の古さを検査。PC時計のジャンプ検知後は地図作成を再起動する。
- `host_mapped` はソフトウェア変換モデルが検査を通った状態。PTPロック実測やハードウェア同期成立の意味ではない。
- `/imu/time_reference`、`/imu/clock_status`、`/gouda/time_sync/state` を既存の生データ・指令値・推定値と一緒に記録する。
- Gazeboでは共有 `/clock` を使う専用方式を使用し、実機側の設定に流用しない。

PTP実機ロック、USB固定遅延、残留オフセット、GLIMでの地図精度は実機未検証。前回Gazeboで残ったGLIM推定の問題を、この変更だけで解決済みとはしない。


## 実施済みのソフト検証

Python 143件、C++制御・時計モデル、模擬USBでの実IMUドライバー、ROS時刻ゲートの通信、ブラウザー設定保存・再表示、GLIM実プロセスの入力なし起動・終了が合格。詳細は `docs/time_sync_validation.json`。実機同期成立や地図精度の検証とは別。
