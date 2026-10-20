# 作業記録 2026-10-20 第61便: 自律走行に要る node と詳細設計書の記載の照合（調査のみ）

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（作業ツリーは未 commit の変更あり。他のセッションの変更を含む）。
- `design/reports/status.md`（第59便まで）、`design/model.yaml` の ros_node（ND-01〜19）と module（M-001〜039）。
- 詳細設計書: リポジトリの写し `design/docs/Gouda_architecture_detail.xlsx`（2026-10-08）と、Google スプレッドシート（ID 1YsDMMmeVlaqwRGtAY7-fJNq4Pycb_bJa-KiKO9JsEwE）の「モジュール定義」を内蔵ブラウザから gviz の CSV で読んだ（読み取りだけ。編集はしていない）。
- 実装: `gouda.sh`、`gouda_core/launch/gouda_core.launch.py`・`gouda_nav2.launch.py`・`gouda_sensors.launch.py`、`gouda_core/gouda_core/mode_manager_node.py`（TR-05 の ND-07 の確認、ND-08 の GLIM 起動）、`autonomy_client.py`。

## 人の質問

「自律走行の際に必要なnodeは何か？詳細設計書に漏れなく記載はあるか？」

## 結果（事実）

自律走行（MODE-AUTO・MODE-PAUSE）で動く・動くべき node（正本の ND と実装の launch から）:

| 区分 | node | 正本 | 実装 |
|---|---|---|---|
| 進行 | gouda_mode_manager | ND-03 | あり |
| HMI | gouda_monitor | ND-02 | あり |
| 記録 | gouda_recorder | ND-04 | あり |
| TF | gouda_static_tf | ND-13 | あり |
| 自己位置（大域） | gouda_global_localization | ND-07 | **なし**（TR-05 で開始を拒否。DEC-115） |
| 自己位置（局所） | glim_rosnode（odometry だけ）＋ gouda_local_odometry | ND-08 | あり |
| Nav2 | map_server、filter_mask_server、costmap_filter_info_server、controller_server、smoother_server、planner_server、behavior_server、bt_navigator、velocity_smoother、lifecycle_manager_navigation | ND-10（障害物は ND-09 として costmap の設定） | あり（実車値未確定なら起動しない） |
| 車両出力 | gouda_motion_controller、vehicle_bridge | ND-11、ND-12 | あり（lifecycle） |
| センサー | gouda_sensor_supervisor → hesai_ros_driver、adi_imu_driver、septentrio_gnss_driver | ND-18、ND-14、ND-15、ND-19 | あり |
| ROS 外 | ESP32 firmware、str2str（NTRIP 中継のプロセス） | ND-17、DEC-151 | firmware あり／中継は段 3 |
| 任意 | rviz2 | ND-16 | gouda.sh は起動しない |
| 自律走行では不要 | gouda_map_creator | ND-05（MODE-MAP・MANUAL） | 常時起動 |

詳細設計書（スプレッドシート）との食い違い:

1. 「モジュール定義」に node の分割・配置の記載はない（module 単位）。node の一覧は正本 model.yaml の ND にだけある。
2. 「使用モード定義」の自律走行の行が、不採用の safety_supervisor・Safety_gate（DEC-004、M-013・M-014）を必要なものに挙げている。シートは更新されていない。
3. 自律走行に要る次の node・module がシートにない: gouda_sensor_supervisor（ND-18）、gouda_static_tf（ND-13。シートは robot_state_publisher のまま）、GNSS のドライバ（ND-19。41 行目に gnss_localization_submodule の草案があるだけ）、gouda_recorder（シートは gouda_logger）。
4. ID の衝突: シートの 12 行目（gouda_section_executor）は ID が空で、移行で正本が M-039 を付けた。人がシートの 41 行目に M-039 を gnss_localization_submodule として付けた（第57便）。同じ M-039 が二つの意味を持つ。
5. 正本の側の不足: ND-10 の記述に smoother_server、filter_mask_server（mask 用の map_server）、lifecycle_manager_navigation の名前がない（責務の文には一部あり）。M-021 urg_node2・M-033 Hokuyo は シートで自律走行・実装中だが、正本に ND も扱いの解釈（interpretation）もない。
6. 正本と実装の食い違い: ND-08 は正本で lifecycle_node・process_group gouda_localization、実装は lifecycle でない Node を gouda_core の launch で起動。

## 自律判断した変更

- なし（正本・生成物・コードは変えていない）。

## 承認事項・実測待ち

- 新規の登録はしていない。上の 2〜6 の扱い（シートの更新、M-039 の ID の付け直し、ND-10 の記述の補足、Hokuyo の扱い、ND-08 の正本と実装のどちらに合わせるか）は承認事項の候補。人に提示した。

## 検査・試験

- 未実行（何も変えていない）。

## 残るリスク

- ND-07 がない限り、実車で自律走行は開始できない（TR-05 で拒否される。安全側）。
- M-039 の衝突は、シートから正本へ取り込むときに取り違えの原因になる。

## 次に進められる作業・止まっている作業

- 進められる: 食い違い 2〜6 を判断台帳に登録する（人の了承の後）。
- 止まっている: ND-07 の実装（DEC-115 保留）。

## 追記: ND-11・ND-12 の実装の状況（人の質問「gouda_motion_controller、vehicle_bridgeはもう既に実装が完了しているのか？」）

- コード（`motion_controller_node.py`・`motion_core.py`・`vehicle_bridge_node.py`・`vehicle_core.py`・`esp32_protocol.py`）は工程 5-5 の範囲で実装済み。作業ツリーに未 commit の変更はない。
- 実車の設定（trial なし）では configure が FAILURE になる: ND-11 は PRM-39〜42 が tbd、ND-12 は PRM-09・14・61 が tbd（`generated/params/*.yaml`）。firmware の PRM-43〜49 も tbd（DEC-077・079 の回答待ち）。
- 試験は stub・ホスト試験・VM の範囲だけ。ESP32 実機・車体では未実行（status.md の三つの状態のとおり）。
- 変更・検査の実行はなし。

## 追記 2: DEC-077・DEC-079 の判断材料の提示（人の指示「dec-077,079を判断したいので、情報を提示せよ」）

読んだもの: model.yaml の DEC-077・079・022・030・037・048・050、PRM-43〜49、`docs/esp32_protocol_v4.md` §1・§5・§7、新 firmware `firmware/gouda_esp32_v4/include/gouda_v4/{control,config}.hpp`・`src/main.cpp`、旧 `firmware/gouda_dualsense_usb/include/control.hpp`・`firmware/gouda_esp32/include/{legacy_control,legacy_settings,calibration}.hpp`、`docs/gouda_protocol_v3.md`、`design/research/joystick270_firmware/extract.md`、`../Electric/Joystick270/Joystick270_BOM.csv`・`../Electric/Joystick270_Firmware/docs/SPECIFICATION.md`・`../Electric/Joystick270_BoardTest/README.md`、`generated/measurement_plan.md`。

確認した事実:
- 旧の値（2500／230／4700／4700 mV、8 %、200 ms）は `firmware/gouda_esp32/include/calibration.hpp:6` に「Requested 2500 mV from the user's DualSense implementation; NOT a voltage measurement.」とある。電圧の測定値ではない。
- 基板の DAC は MCP4922-E/P、VREF は 1k/1k の分圧（BOM R3・R4）、ゲイン 2（参照 firmware の仕様）。フルスケールは +5 V の線の電圧に比例する。参照 firmware はフルスケールの初期候補を 4990 mV とし、方向別の端点は「安全な仮既定値はなく、未登録なら ARM を拒否」。
- フルスケールの設定と実際が違うときの出力（計算。dacCode と同じ式、実際の出力はコード×実フルスケール／4096）: 設定 4700・実際 4990 なら中立 2500 mV の要求が約 2653 mV、最大 4700 が約 4989 mV。設定 4990・実際 4700 なら中立が約 2355 mV。
- 新 firmware は設定が無効（DAC 値なし）の間 DAC へ書き込まない（main.cpp:71）。そのとき MCP4922 が何 V を出すかは未確認。
- 手動の優先: 元資料（モジュール定義の M-025・M-027 の行）は「P押下中のgamepad操作優先」「P解放でPC指令へ復帰」。v3・v4 はスティックが deadzone の外にある間を手動とする（P ボタンを使わない）。この差は判断台帳に登録されていない。

推測（確認していない）:
- DEC-077 の備考の「人は旧 firmware を実機で動作確認済みと申告: DEC-037」は、DEC-037 の回答「先ほど提示したfirmwareは実機で動作確認済み」が DEC-030 で人が示した参照 firmware（Joystick270-Firmware、フルスケール 4990）を指す可能性があり、旧 firmware（gouda_dualsense_usb、4700）の実機確認の根拠にならないおそれがある。

変更・検査: なし。上の食い違い（DEC-077 の根拠の読み、P ボタンと deadzone）の登録は人の了承待ち。

## 追記 3: test_vehicle_core.py の 12 件の失敗の原因の分類（別セッション「Global localization/Navigation ノード検討」からの連絡）

- 再現: commit 3341602 ＋作業ツリー（REV-097 適用後）、`cd gouda_core && python3 -m pytest -q test/test_vehicle_core.py` → 12 failed、10 passed。全件 `design/generated/params/firmware_config.trial.yaml` の FileNotFoundError。
- 原因の分類（1.6）:
  1. 試験（試験基盤）: `load_yaml_flat`（test_vehicle_core.py:25-32）が trial ファイルの存在を前提にしている。PRM-43〜49 がすべて承認され（REV-095・096）、generate_params.py は tbd の trial 値がないとき trial ファイルを作らない（generate_params.py:61-73）。
  2. 設計: 作業ツリーを変えずに一時コピー（scratchpad）で「trial ファイルがなければ空」として実行すると 9 failed、13 passed。生成された承認値（PRM-45=4800 mV、PRM-46=4700 mV）が firmware の設定の有効条件（dac_max_mv ≤ dac_full_scale_mv。firmware `config.hpp:16`、`esp32_sim.config_valid`）を満たさず、config_valid=0。DEC-160（pending）で既知の矛盾。TS-17〜19 等は有効な設定を前提にするので不合格になる。本物の信号であり、期待値の変更や trial 値の追加で隠さない（1.5・1.6）。
- 修正はしていない（コードの変更は人の許可が要る: DEC-106）。(1) は合否の基準を変えない基盤の修正の候補。(2) は DEC-160（と DEC-161 の実測）の回答で解消する。
- 連絡元のセッションに上の分類を返信した。
