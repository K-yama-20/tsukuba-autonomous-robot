# 第104便: 帯の地図を走行用に、Nav2 の設定（DEC-211・213〜218）、外付けの rosbag からの地図の作り直し（REV-134、DEC-225）

## 読んだもの

- コミット：`3b4fb53`（design/nav2-tab-2026-10-21、PR #14 は未 merge）の上の作業ツリー（REV-133 は未 commit で適用済み）。
- `nav2_config.py`、上流の雛形（`research/upstream_jazzy/nav2_bringup/params/nav2_params.yaml` の inflation_layer・obstacle_layer）、`map_convert.py`、`monitor_node.py`（地図タブ、waypoint の保存、Nav2 タブ）、`web/app.js`・`index.html`、`check_design.py` の DR-13、model.yaml の Q-12・PRM-11・IFD-30。
- 外付けのドライブ（VM の /media/psf/Crucial_4TB/Gouda、読むだけ）：`gouda_data/records/20261014_173522`・`20261014_175847` の rosbag、`gouda_data/config/sensor_config.json`。

## 人の発言（原文）

「転記は私の回答で間違いない。PRM-72・96・97 の値の変更、DEC-211・213〜218 の実装、外付けの rosbag からの地図の作り直し（VM、読むだけ）に着手して。」

DEC-211〜218 の note に記録した（REV-134）。

## 記録と設計（REV-134）

- PRM-72＝1.0 m（DEC-218）、PRM-96＝1.0 m（DEC-213）を承認値に。PRM-98（inflate_around_unknown＝false、DEC-217）を追加。
- ND-05：帯の地図を走行用の map.yaml に、今の分類の地図は表示用の map_ground_band・ground_band.png、重ね図 corridor_overlay.png、帯が作れない原図は変換を失敗に（DEC-211・212）。ND-10：combination_method 2、inflate_around_unknown（DEC-214・216〜218）。ND-02：waypoint の警告、地図タブの表示、Nav2 タブの真偽の項目。IFD-54 に inflate_around_unknown。試験 TS-46。
- DEC-225（pending）：PRM-97（B）＝5 m は、検査ルール DR-13（「旧値の5 mを流用していない」、依頼4）が単位 m の 5.0 を意味にかかわらず違反とするため、値を入れていない。DR-13 は旧 waypoint の半径（Q-12・PRM-11・IFD-30、DEC-016）を指していた。検査ルールの緩和は承認事項。単位や書き方を変えて通すことはしない。

## 自律判断した変更とその理由

- inflate_around_unknown の既定は新しい PRM-98 にし、Nav2 タブの値で上書きする（DEC-207 (a)・DEC-209 と同じ形）。ほかの設定（allow_unknown・combination_method・膨らませの半径）をタブに置くかは DEC-219 のまま。
- combination_method 2 は設計の選択（DEC-122 と同じ扱い）として nav2_config の定数にし、DEC-216 を書いた。global の obstacle_layer だけ（local は voxel_layer で、合成の意味が違う）。
- 帯の外の waypoint の警告は、保存の応答と manifest の warnings に、区間の重なりの警告と同じ形で入れた。
- 重ね図は帯の地図の格子の上に、点の数の濃淡（高さは使わない：分岐先の指摘）と帯の青で描く。
- rosbag の作り直しは、試験スタックと同じ隔離（試験用の data_root と ROS_DOMAIN_ID 79、センサーのドライバなし）で、PRM-37 の試験用の値（GLIM の保存の待ち 90 s）だけを外した（実車では PRM-37 は未確定で上限なし。保存が切られると原図が残らないため）。

## 修正（原因の分類：1.6）

- 試験の基盤：5-6 の試験の fixture が帯の幅を試験用の値のファイルだけから読んでいた（PRM-96 が承認値になり KeyError）。生成物と試験用の値を重ねて読むように直した。
- 試験の基盤：5-6 の試験で、模擬の ND-07 を起こした直後の開始が「ND-07 is not running」で拒否された（node の発見が遅れた）。見つかるまで待つようにした。合否の基準は変えていない。
- 試験：帯の外の waypoint の試験が、格子の外の点しか使っておらず、規則を壊した写し（不明を空きとみなす）で不合格にならなかった。格子の中の不明の点を足した。

## 実行した検査・試験

（作業ツリーは 3b4fb53 の上の未 commit の変更）
- `apply_revision.py REV-134 --dry-run --check`：最初の版で DR-13 の違反 3（PRM-97 の 5.0 m、PRM-96・97 の説明の「5 m」）→ PRM-97 を外し DEC-225 を登録。直した版で新しい違反 0、新しい未判定 5（DR-15。既存の行の見出しが変わっただけ：PRM-72 が 0.5 でなくなった）。
- `run_checks.py`：要約行 `{"合格": 12, "違反": 0, "未判定": 5} 違反0件・未判定5件`、DR-11 31、DR-15 31。終了コード 1 の原因は入力の照合の 3 件（前と同じ）。
- Mac 単体：248 合格、8 skip、不合格 0。規則を壊した写し 4 つ（帯がなければ分類の地図に戻る、combination_method 1、タブの値を使わない、不明を空きとみなす）で不合格になることを確認（4 つ目は試験を直した後）。
- VM 単体（`~/gouda_rev128_ws`、再 build）：256 合格、不合格 0。
- VM `ubuntu_nav2_recovery.sh`：最初の起動で local・global の inflate_around_unknown は false、inflation_radius 1.0、global の combination_method 2。"yes" は拒否、true を保存して起動し直すと両方 true、launch のログに出所。
- VM `MAP_KIND=corridor ubuntu_stage5-6.sh`（帯の半分の幅 1.0 m の合成の帯の地図）：
  - 1 回目：T2 で一度 TR-07（plan_failure、Nav2 の status 6、error_code 0）。bt_navigator のログ「Timed out while waiting for action server to acknowledge goal request for compute_path_through_poses」の直後に「Goal failed」。再開で最後の waypoint に着いた。T3〜T6 は期待どおり。ログは VM の `/tmp/st56_rev134_run1_stack.log`。
  - 2 回目：T2 の開始が「ND-07 is not running」で拒否（試験の基盤の問題、上の修正）。
  - 3 回目（修正の後）：T2 はそのまま最後の waypoint に着いた（TR-08）。T3〜T6 も期待どおり。goal の受け付けの時間切れは起きなかった。
  - 1 回目の失敗は再現していない。未解決として残す（VM の負荷が高かった：load average 2〜4。bt_navigator の server_timeout は雛形のまま。環境の問題とは断定しない）。
- VM `ubuntu_rebuild_from_rosbag.sh`（ROS_DOMAIN_ID 79、0.5 倍速）：
  - 20261014_173522（474 s）：再生 960 s。原図 20261019_123731_dc7b4c8a（119 submaps、/config の写しつき）、変換 rev 1（変換器 0.5、帯の地図を作れた。B は試験用の値 1.0 m で、帯は 2 区間・つながなかった所 1）。
  - 同じ原図を B＝5 m（人の決定、DEC-225 の前なので分析で与えた）で分析：帯は 1 区間、空き 57931 格子。今の分類の地図では、その帯の中の 51000 格子が占有（床の反射などの影響と見られる。推測）。重ね図 `research/vehicle_pc/2026-10-21_rosbag_rebuild/corridor_overlay_173522_A1.0_B5.png`。
  - 20261014_175847（707 s、11 GB）：再生 1422 s。GLIM が起動から 1263 s で、メモリ不足のためカーネルの OOM killer に止められた（glim_rosnode の anon-rss 約 5.7 GB、VM のメモリ 8 GB。`journalctl -k` で確認：`research/vehicle_pc/2026-10-21_rosbag_rebuild/oom_175847.txt`）。Gouda は glim_exited（TR-14 の検出）を記録し、TR-04 で保存のデータがないので原図を登録しなかった（RQ-I009 のとおり）。VM の `~/gouda_ws` の Gouda は止められていない（プロセスを確認）。同じ条件でのやり直しはしていない（メモリが足りないことは変わらないため）。
- rosbag の再生での ND-07 の評価、実車：未実行。

## 承認待ち・実測待ち

- DEC-225（DR-13 と PRM-97）、DEC-219（Nav2 タブの範囲）、DEC-220〜224（人が描く範囲）。

## 残るリスク

- 1 回目の Nav2 の goal の受け付けの時間切れ（未解決）。
- 長い走行の地図作成は、VM（メモリ 8 GB）では GLIM がメモリ不足で止まる。作り直すには、メモリの多い機械（x86 機は今は手元にない：DEC-205 の人の発言）か、VM のメモリを増やすこと（人の作業）が要る。
- 製品の手順での変換は PRM-97 が未確定のため、実車（trial なし）では帯の地図を作れず変換が失敗する（DEC-225 の後に再変換）。
- 作り直した原図の取付は、ドライブの /config（config_revision 2）。分岐先によれば、地図作成のときに GLIM に渡した T_lidar_imu と一致する。

## 次の作業

- 人の判断：DEC-225、DEC-219〜224。作り直した地図を VM の `~/gouda_ws` に入れるかは人（今は `~/gouda_rebuild_2026-10-21/` にある）。
- commit：未実行。PR #14 は未 merge。
