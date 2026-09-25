# Gouda 開発記録 — 2026-09-23

## 作業対象と保全

- Ubuntu 24.04.5 ARM64 / ROS 2 Jazzy、ユーザー aya。
- `/home/aya/gouda_ws/src/tsukuba-autonomous-robot`。
- `feature/aya-navsystem`、開始HEAD `4dce4f040390f7e12dfed0ef68e85f4414341762`。
- 既存の `.gitignore` 差分、未追跡の description/interfaces/scripts、空のNav2/KISS設定を保全。
- 既存IMU driverとlaunchは変更せず使用。Git switch/pull/rebase/reset/pushは未実行。
- 変更前のGit状態・既存ファイルSHA-256は `~/gouda_ws/bags/gouda_20260923/initial_*`。
- Ubuntuへの追加ファイルは `managed_files.json` で追跡し、既存ファイルの上書きを拒否。

## 実機センサで確認した結果

Parallelsのnet0が共有モードのまま、Ubuntuには192.168.1.100/24が設定されていた。
初回はUDP受信0。Macの有線en17（AX88179B）へnet0をブリッジ変更後に受信した。
Ubuntuの固定IPは維持した。元へ戻す設定は `prlctl set 'Ubuntu Linux' --device-set net0 --type shared`。
ただし元の固定IPと共有モードの組み合わせではLiDARへ届かない。

| 項目 | 今回の観測 |
|---|---|
| UDP | 192.168.1.201:10000 → 192.168.1.100:2368、1080 byte |
| PTC | TCP 9347へ接続成功、角度補正取得成功 |
| SDK識別 | 6_1 XTM1 parser、32 channel。現物ラベル/製造番号/firmwareは未確認 |
| 点群 | `/lidar_points`、PointCloud2、`hesai_lidar` |
| fields | x/y/z/intensity FLOAT32、ring UINT16、timestamp FLOAT64、point_step=26 |
| 初回記録 | 14.7秒、148点群＋148生packet frame |
| 通常フレーム | 64,000点。初期partial frameは別扱い |
| センサ時刻 | 現在から約226,108,112秒ずれ、下流の鮮度判定には使用不可 |
| 受信時刻設定 | `use_timestamp_type=1`、143観測、約9.66 Hz、観測最大header age約104 ms |
| IMU同時観測 | ADIS16607-2、1426観測、約97.8 Hz。設定100 Hz/内部1000 Hzを維持 |
| 補正 | `xt32_device_correction.csv` を本体から取得し保存 |
| 残件 | firetime読込みエラー、実時刻同期、取付TF・向き・死角の確認 |

初回のPython点検処理は点ごとのループが遅く、観測側3.47 Hzだった。bag自体は148フレームを記録。
二回目はNumPyで検査し、観測9.66 Hz。これをパケット欠落率ゼロの証明にはしない。
センサの設定時計、回転数、IP等を書き換えるコマンドは送っていない。
firetimeは未入手。ログのエラーを消すための仮ファイルは作っていない。

導入版Hesaiには、生packet記録時に個別stampを保存せず、再生時もSDKへ受信時刻を渡さない問題があった。
そのためreceive-timeで再解析すると点群時刻0になり、監視は正しく拒否した。
`patches/hesai-replay-timestamps.patch` で記録・再生の時刻受け渡しとpacket長検証を追加。
driverの版は据え置き。旧bagはframe header時刻へフォールバックするため、点別時刻の校正を主張しない。
このdriverソース1ファイルのみをsibling checkoutで変更し、本体repoへ再現patchを保存した。
修正後の専用launch試験では実機68フレーム、生packet再生69フレームを取得し、双方で健全性判定成立。
不正packet長の拒否ログと、その後の正常な点群再生も確認した。

データ保存先: `~/gouda_ws/bags/gouda_20260923/`。
`live_points_packets` はセンサ時計版、`receive_time_points_packets_imu` はPC受信時刻版。
後者にもセンサ間の同時性や正確なデスキューを保証する校正はない。

実bag再生→KISS-ICPで84メッセージのオドメトリを確認した。
出力は `odom_lidar → hesai_lidar`。取付TF未確定のためbase_linkへ変換していない。
firetime/時刻未検証のためdeskew=false。再生終了後、監視がSTALEへ移ることを確認。
地図上の自己位置推定完成・精度検証・走行距離の実測を意味しない。

## 追加したソフトウェア

- `gouda_sensors`: 設定検証、Hesai hardware/PCAP/packet-replay起動境界、点群frame/fields/時刻/有限値/入力停止監視。
- `gouda_navigation`: Nav2 ComputePathToPose、global costmap、離散追従、目標世代管理、取消、入力/TF鮮度と進捗監視。
- `gouda_vehicle`: 20 Hz serial bridge、200 ms上流/許可/status期限、明示的arm、シミュレーションPTY限定。
- `firmware/gouda_esp32`: 共通C++通信core、250 ms watchdog、token/sequence、DAC出力、未校正arm拒否。
- `gouda_sim`: 共通coreのnative emulator、実PTY、1秒起動/1秒線形減速、ICRモデル、模擬観測、停止までの占有領域検査。

Nav2の経路計画を利用し、追従はGouda離散制御へ一本化。NavigateToPose/BT/controller/recovery全体の統合ではない。
simulationは位置真値をフィードバックに用いる制御・通信試験であり、推定器の精度試験ではない。
半径0.55 m、余裕0.15 m、速度0.3 m/s、旋回0.35 rad/s等はsimulation専用仮定。
synthetic map/TFを実機へ転用しない。実機用footprint/安全判定は未校正。

## DualSense版の再利用

ユーザーが指定した `outputs/Joystick270_DualSense` を再利用元とした。
元のmain/control/settings/platformio/READMEをSHA-256付きでreference_dualsenseへ保存。
SPI18/23/5、1MHz mode0、MCP4922 A=X/B=Y、制御word、2500mV停止要求、GPIO32 LOWを継承。
新ファームウェアは自律走行用USB Serial版。既存Bluetooth操作版は変更・書込みしていない。
Bluetoothと自律指令の同時仲裁は未実装。元の動作保証を新Serial版へ拡張していない。
PlatformIO ESP32向けbuild成功。フラッシュ未実施、実端子電圧/車体応答は未検証。

## 実行した試験

- Ubuntu ARM64で追加4パッケージのcolcon build成功。
- Pythonテスト42件成功（入力契約、設定、経路制御、wire異常、遅延/速度/ICRモデル）。
- 共通C++ core: CRC既知値、parser、校正拒否、sequence再送、250 ms境界、millis wrap、切替neutral。
- native wire試験: 破損CRC、重複packetによるwatchdog延命拒否、旧token arm拒否。
- ROS隔離ドメイン97: Nav2→追従器→bridge→PTY→共通core→遅延モデル。
- 直進1.5m: 終端誤差約0.034m。障害物disable約0.144s、上流停止disable約0.240s。
- 旋回を含む(1.5,0.8)m: 終端誤差約0.052m。起動待ち中の取消後に動作が復活しない。
- 障害物出現後のdisable、1秒モデルによる減速、障害物消失後に自動再armしない。
- 実bag再生、KISSセンサ座標系オドメトリ、入力停止監視。

上記は一回の仮定条件における観測値。最大停止時間や実車安全性能の保証ではない。
追加の同時負荷実行では上流停止disable約0.330s、直進誤差約0.045m。
Hesai受信試験をビルド/閉ループと同時実行した1回は8秒34フレームで事前条件（40超）を下回った。
条件を緩めず単独再試験で73フレームを確認した。VM性能を実車用周期保証として扱わない。
Hokuyoの実機依存テストは対象外、成功扱いしない。AMD64実行は未実施。

## 残る項目と段階判定

| 段階 | 現在の到達点 | 次に必要なもの |
|---|---|---|
| 0 現状監査 | 完了 | 再開時にGit差分再確認 |
| 1 Hesai | 実UDP/PTC/点群/IMU同時記録・再生を確認 | 現物ID、firetime、時刻同期、取付TF、向きの実確認 |
| 2 自律走行 | Nav2計画＋離散追従を模擬環境で確認 | 実機base odom、地図生成/地図定位、実点群障害物フィルタ校正 |
| 3 PC/ESP32 | 共通core/bridge/emulator、ESP32 build確認 | DAC較正LUT、版/readback、実Serial profile、書込み/電圧試験 |
| 4 simulation | 直進/旋回/取消/異常停止の閉ループ確認 | 狭路/経路更新ストレス/CPU負荷/時計異常E2E、実測同定と許容閾値 |
| 5 配布 | 依存版・実行手順を記録中 | 上記完了後にARM64/AMD64再現確認、最終パッケージ化 |

software-onlyの全完了条件にはまだ達していない。実機の自律走行はNO-GO。
未確定の取付寸法・DAC値・速度・安全余裕を推測で設定しない。
再開時は残項目をこの順序で進め、完成済みIMUの再設定から始めない。

## 根拠

- 導入済みHesai `e7e112f0809f0eed5e3c81c55a1a0376474db234`、SDK `9d5dc4fc4ade5be5f6a6ca00e71dd4050b054168`。
- [Hesai公式driver](https://github.com/HesaiTechnology/HesaiLidar_ROS_2.0)。設定APIは導入済みソースと照合。
- KISS-ICP `1ffa7d7512f10bfc8b1185095011fa31184019e3`。
- IMU driver `742b7babec7e7a20937d4e8be0df77a771a1294a`、library `324cb47c0160d7b249ad2d0ed75c3fbd72ce6382`。
- Nav2 Jazzy 1.3.13。ComputePathToPoseの契約はUbuntu内の導入済みaction定義を確認。
