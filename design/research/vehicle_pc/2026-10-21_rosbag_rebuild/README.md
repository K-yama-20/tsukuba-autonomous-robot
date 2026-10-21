# 外付けの rosbag からの地図の作り直し（2026-10-21、第104便、DEC-212）

- 道具：`gouda_core/test/ubuntu_rebuild_from_rosbag.sh`（試験・分析用。製品の手順の TR-03 → GLIM → TR-04 → 原図の登録 → 変換を、試験スタックと同じ隔離で行う。GLIM の保存の待ちの試験用の値 PRM-37 だけを外す）。
- 入力（読むだけ）：VM の `/media/psf/Crucial_4TB/Gouda/gouda_data/records/<run>/rosbag/bag`（点群と IMU だけを 0.5 倍速で再生）、`gouda_data/config/sensor_config.json`（config_revision 2）。
- 出力：VM の `~/gouda_rebuild_2026-10-21/<run>/`（data_root）。`~/gouda_ws` には触っていない。

| rosbag | 長さ | 結果 |
|---|---|---|
| 20261014_173522 | 474 s（7.4 GB） | 再生 960 s。原図 20261019_123731_dc7b4c8a（119 submaps、/config の写しつき）。変換 rev 1（変換器 0.5）：帯の地図を作れた。B は試験用の値 1.0 m（PRM-97 は DEC-225 待ち）で帯は 2 区間。`rebuild_173522.log` |
| 20261014_175847 | 707 s（11 GB） | 再生 1422 s。GLIM が起動から 1263 s でメモリ不足のため止められた（カーネルの OOM killer、glim_rosnode の anon-rss 約 5.7 GB、VM のメモリ 8 GB：`oom_175847.txt`）。Gouda は glim_exited（TR-14 の検出）を記録し、保存のデータがないので原図を登録しなかった（RQ-I009）。VM の `~/gouda_ws` の Gouda は止められていない。`rebuild_175847.log` |

- 分析（`design/research/vehicle_pc/2026-10-21_swept_corridor/corridor_analysis.py`、地図データベースには登録しない）：173522 の作り直した原図を A＝1.0 m・B＝5 m（人の決定。B は DEC-225 の前なので分析で与えた）で変換。帯は 1 区間・空き 57931 格子。今の分類の地図では帯の中の 51000 格子が占有。`summary_173522_A1.0_B5.json`、`corridor_overlay_173522_A1.0_B5.png`（灰の濃さ：点の数、青：帯）。
