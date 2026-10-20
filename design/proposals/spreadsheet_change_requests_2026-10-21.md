# 詳細設計書（スプレッドシート）の変更案（2026-10-21、第87便、DEC-183）

状態: 提案。人の回答 DEC-183（転記、原文「A2: 推奨案で問題ない。」）で、方針が決まった。方針は、正本 `design/model.yaml` を正とし、シートの変更案を作ること。シートは人のファイルで、編集は人が行う。AI はシートを編集していない。

読んだもの: Google スプレッドシート Gouda_architecture_detail（ID 1YsDMMmeVlaqwRGtAY7-fJNq4Pycb_bJa-KiKO9JsEwE）。2026-10-21 に内蔵ブラウザで開き、シート「モジュール定義」「使用モード定義」を gviz の CSV で読み取った（読み取りだけ）。リポジトリのローカルの xlsx（`docs/architecture/` は 2026-10-14 の保存、`design/docs/` は 2026-10-08）は最新ではない（人の指摘）。41 行目は、ローカルの写しにはない。

行の番号: gviz の CSV の順で数えた。CSV は空の行を飛ばす（「使用モード定義」では、ローカルの写しの 8 行目「非モード: 停止中」が CSV では 7 番目になる）。「モジュール定義」では空の行がなく、ローカルの写しの 1〜40 行目と並びが一致した。そのため、行の番号は「モジュール定義」は行番号として、「使用モード定義」は使用モードの名前で示す。

## 1. 「使用モード定義」の自律走行の行（DEC-183 の (1)）

| 列 | 今の記載（原文） | 変更案 | 根拠 |
|---|---|---|---|
| 主に起動・利用するもの | mission_manager、global_localization、local_odometry、Nav2、XT-32障害物点群処理、motion_controller、safety_supervisor、Safety_gate、vehicle_bridge、必要センサ/TF | 「safety_supervisor、Safety_gate」を削る。正本の node に合わせ、次の並びにする案：mode_manager（ND-03）、global_localization（ND-07）、local_odometry（ND-08）、Nav2（ND-10、障害物は costmap の設定 ND-09）、motion_controller（ND-11）、vehicle_bridge（ND-12）、static_tf（ND-13）、sensor_supervisor とセンサのドライバ（ND-18・14・15・19）、recorder（ND-04）、monitor（ND-02） | DEC-004：safety_supervisor・Safety_gate（M-013・M-014）は不採用。最終指令の遮断は、Nav2 の取り消し、motion_hold（IFD-40）、cmd_vel の途絶時の中立で行う |
| 車両操作 | PCの自律指令を連続送信。P押下中のgamepad操作をESP32が優先し、P解放でPC指令へ戻る。 | 変更案は出さない（下の注） | 注：今の firmware（v4）は、スティックが deadzone の外にある間を手動とし、P ボタンを使わない（第61便の追記 2）。この差は判断台帳に未登録。直すかどうかは人の判断 |

同じシートの「原則起動しないもの」の列（事前地図作成・手動操縦・地図整備の行）にも「Safety_gate」が出てくる。起動しないものの一覧なので、害はない。消すかどうかは人の判断。

## 2. 「モジュール定義」にない node（DEC-183 の (2)）

| 正本 | 今のシート | 変更案 |
|---|---|---|
| ND-18 gouda_sensor_supervisor（センサードライバの起動と、デバイスを差し直したときの作り直し） | 該当する行がない（「sensor_supervisor」の語なし） | 行を追加する。機能ドメイン sensors、コンポーネント種別 supervisor、使用モード 全モード |
| ND-13 gouda_static_tf（静的 TF の唯一の発行者。/config の取付値から作る） | 40 行目 M-038 robot_state_publisher（進捗 未実装、使用モード 事前地図作成, 自律走行） | 40 行目のモジュール名を gouda_static_tf に改めるか、備考に「実装は gouda_static_tf（ND-13）」と書く。使用モードは正本では事前地図作成・自律走行・一時停止 |
| ND-19 septentrio_gnss_driver（mosaic-go G5 P6） | 41 行目 M-039 gnss_localization_submodule（受信機の測位とドライバ、NTRIP の中継を含む草案） | 3 節の番号の付け直しとあわせて扱う。ドライバの行を分けるかは人の判断 |
| ND-04 gouda_recorder（ログと rosbag の独立した記録） | 18 行目 M-016 gouda_logger、19 行目 M-017 log_database | 18 行目のモジュール名を gouda_recorder に改めるか、備考に「実装は gouda_recorder（ND-04）」と書く |

## 3. M-039 の二つの意味（DEC-183 の (3)）

- 12 行目：Module_ID が空欄、モジュール名 gouda_section_executor（navigation、自律走行）。移行のときに、正本がこの行に M-039 を付けた（正本の M-039＝gouda_section_executor）。
- 41 行目：人が付けた M-039、モジュール名 gnss_localization_submodule（localization、進捗 未実装、使用モード 全モード、定義Status 草案）。
- 変更案：41 行目の GNSS の行を **M-040** に改める。12 行目の Module_ID の欄に M-039 を書く。正本の番号（M-039＝gouda_section_executor）は変えない。M-040 を正本に取り込むのは、シートが改められた後に、別の変更セットで行う。

## 4. 正本の側で直したもの（DEC-183 の (4)）

- ND-10 の責務に、起動する server の名前を補った（REV-119）。補った名前は、map_server、filter_mask_server、costmap_filter_info_server、controller_server、smoother_server、planner_server、behavior_server、bt_navigator、velocity_smoother、lifecycle_manager_navigation。シートの 13 行目 M-011 Navigation は変えなくてよい（module 単位の記載のため）。

## 5. Hokuyo（DEC-183 の (5)）

- 23 行目 M-021 urg_node2（使用モード 自律走行）、35 行目 M-033 Hokuyo LiDAR（進捗 実装中、使用モード 自律走行）。正本には ND も扱いの解釈もない。
- 今年使うかは、DEC-184（pending）で人に質問している。回答があるまで、シートは変えない。
