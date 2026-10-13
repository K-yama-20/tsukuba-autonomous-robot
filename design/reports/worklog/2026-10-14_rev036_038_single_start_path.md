# 作業記録 2026-10-13〜14 第23便: 起動経路を一つにする、センサー値の確定（REV-036〜038）

## 読んだもの

- ローカル HEAD `c9d471e`（REV-035 まで）、`reports/status.md`、`reports/worklog/2026-10-13_rev034_035_sensor_supervision.md`、gouda.sh、`gouda_core/launch/*.py`、試験 script、README、判断台帳（起動に関する指示の検索）、intent.md 第8版。
- 上流 HesaiLidar_SDK_2.0（9d5dc4f）の lidar.h（speed の扱い、374〜378 行）と hesai_lidar_sdk.hpp・lidar_types.h（default_frame_frequency の扱い）。

## 1. 人の指摘と回答（原文で台帳へ）

- DEC-090（指摘）: センサーを使う／使わない起動モードがあるのは何故か、起動経路はなるべく一つに、起動オプションで迷いが生じないように。
  - 事実: GOUDA_SENSORS は AI が REV-031 で自分の判断で入れた。gouda.sh の環境変数は 8 つあった。台帳と intent.md に同じ文の指示は見つからなかった（チャットで受けていたなら記録漏れ）。23:33 のセッションは仮値なしで起動され、センサーのドライバが起動していなかった（迷いの実害）。
- DEC-091（回答）: 変更案と推奨値を了承。IMU 100 Hz、LiDAR 10 Hz（600 rpm）を確定。LiDAR は 1200 rpm 可、IMU は約 1000 Hz 可、いずれ 1200 rpm の可能性を併記。DEC-084・085・089 も本回答で回答済み。

## 2. 変更（自律判断と理由）

- gouda.sh: start／stop／status だけ。環境変数なし。ワークスペース（gouda.sh の 2 つ上）、データの置き場（PRM-25）、設定（design/generated/params）、ROS 2 Jazzy は固定。起動中に launch が終わったら失敗と表示（前便から）。
- launch: 引数は params_dir・data_root と、試験 script 専用の trial。センサーは常に supervisor の下で起動（デバイスが無ければ待つ）。monitor のポート（PRM-26）と ESP32 のシリアル（PRM-61）は生成ファイルから読む。
- 正本: PRM-25（<workspace>/gouda_data）、PRM-26（8080、宣言先を gouda_monitor の ROS parameter に）、PRM-53（9347）、PRM-56（100 Hz）、PRM-57・58（1.0 s）、PRM-59（5.0 s）を承認値に。PRM-60（LiDAR 600 rpm、新規）、PRM-61（ESP32 の by-id、新規、未確定）。
- LiDAR の回転数: ドライバの設定 speed に PRM-60 を入れ、起動時に SDK が PTC で LiDAR に設定する（上流 SDK lidar.h 374〜378 行）。default_frame_frequency も rpm/60 にそろえる（多フレーム結合と不一致警告にだけ使われる）。これまで「ドライバは LiDAR の設定を変えない」としていたが、DEC-091 の「設定しろ」によりドライバが回転数を設定する。
- 試験: `gouda_core/test/stack.sh` を新設（ROS ドメイン 77、専用のデータの置き場、センサーのドライバ設定を除いた設定の写し、OS が選ぶ monitor のポート、仮値を読む）。試験 script は gouda.sh の環境変数を使わない。単体試験の期待値は生成された index（正本の値）から読むように変更（値が確定したため。手で写した値を使わない）。
- supervisor の修正（原因の分類: 実装）:
  - 起動時に無いデバイスを記録していなかった。最初の評価で「無い（現れたら起動）」を記録するように変更。
  - ドライバを起動しなかったセッションが、前に開いた IMU の列挙を「なし」で上書きしていた。そのため、再接続なしの再オープンを警告できなかった。開いた列挙をセッションをまたいで保持するように変更。
- 試験基盤の修正: stage 5-5 試験で、新しい ROS ドメインではノードの発見に時間がかかり、固定の 3 秒待ちでは vehicle_bridge の configure が「Node not found」になった。発見を待つように変更（合否の基準は変えない）。

## 3. 実行した検査・試験

| 検査・試験 | 対象 | 結果 |
|---|---|---|
| 全検査 | REV-038 適用後 | 終了コード 0。違反 0・未判定 4 |
| gouda_core 単体（Mac） | 81c7822 | 116 件 OK（1 件 skip、VM で実行） |
| stage 5-5 試験（stack.sh、1 回目） | e06608b | vehicle_bridge が未起動（試験手順の待ち不足）。hold 期限切れから中立まで 0.632 s で判定（0.6 s）を超過 |
| stage 5-5 試験（待ちを修正、2 回） | 9649784 | 合格。hold 期限切れから中立まで 0.429 s・0.517 s、cmd_vel 停止から中立まで 0.746 s・0.734 s、模擬 ESP32 の PC 指令期限切れ、STALE 表示、motion_hold 保持 |
| bash gouda.sh start（環境変数なし） | 81c7822 | monitor が 8080 で開く。IMU は名前から見つけてドライバを起動（応答なし。再オープンの警告を記録）。LiDAR は USB-LAN が VM から外れていて「無い」と記録 |

0.632 s の超過は 1 回だけで、修正後の 2 回では再現しなかった。判定の基準は変えていない。環境の問題とは断定せず、未解決として扱う。そのときの条件は記録に残した（VM の負荷平均は 1 回目の時点では未記録、2 回目の時点で 0.46）。
記録: `research/vehicle_pc/2026-10-14_single_start_path_vm_test.txt`（FILE-VEHICLE-PC-SINGLE-START）。

未実行: IMU と USB-LAN の抜き差しによるドライバの作り直し（人の協力が要る。セッションは起動したまま）。LiDAR の回転数設定の実機での確認（USB-LAN が外れているため）。

## 4. 承認待ち・人の作業

- 人の作業: USB-LAN を VM に接続し直す。IMU の USB を抜き差しする（supervisor が検知して各ドライバを起動・作り直すはず）。
- 承認待ち（前から）: DEC-077・078・079（新 firmware）、DEC-050（実機照合）。PRM-61（ESP32 の by-id）は新 firmware の書き込み時に決める。地図の変換の設定 PRM-33〜36・38 は未確定のため、実車（仮値なし）では原図は保存されるが 2D への変換は失敗する（変換は後で再実行できる）。

## 5. 残るリスク

- 点群の配送の欠落（G-DDS）は未調査。
- gouda.sh を止めて起動し直すと IMU が応答しないことがある（抜き差しで直る。supervisor が警告する）。
- 地図の変換の設定値が未確定（PRM-33〜36・38）。

## 6. 次に進められる作業

- 抜き差しによる作り直しの実機確認（TS-32）、LiDAR の回転数設定の確認、G-DDS の測定、変換の設定値の決定（人）。
