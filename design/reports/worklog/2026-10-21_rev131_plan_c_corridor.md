# 第101便: 案 C（通った帯の 2D 地図）の実装（変換・単体試験・分析用の再変換・VM の試験）（REV-131、DEC-210）

## 読んだもの

- コミット：`4b44f75`（design/records-2026-10-21。PR #12 は 763929a で main に merge 済み）の上の作業ツリー（REV-126〜130 は未 commit で適用済み）。
- 提案 `proposals/swept_corridor_map_2026-10-21.md`、`map_convert.py`、`map_creator_node.py`、`map_database.py`（register_source の /config の写し）、`sensor_extrinsics.py`、`monitor_core.py`（SensorConfig）、`test/stage56_fixture.py`、`ubuntu_stage5-6.sh`。
- VM（読み取り）：原図 2 つの source/、`~/gouda_ws/gouda_data/config/sensor_config.json`。

## 人の発言（原文）

「転記は私の回答で間違いない。案 C の実装（変換・単体試験・分析用の再変換・VM の試験まで）に着手して。DEC-211〜215 は後で答える。」

DEC-210 の note に記録した（REV-131）。

## 記録と設計（REV-131）

- ND-05 の責務に、帯の 2D 地図（map_swept_corridor.yaml・.pgm、swept_corridor.json）を追加の成果物として足した。新しい設定値 PRM-96（帯の半分の幅）・PRM-97（つながない距離）は未確定（値は DEC-213、試行の値 0.5 m・1.0 m）。試験 TS-44。

## 自律判断した変更とその理由（DEC-211〜215 が未回答の間の範囲）

- 走行に使う map.yaml は替えない（DEC-211）。帯の地図は別のファイル。
- /config の写しがない原図では帯を作らない（DEC-212 の代わりの案の側。理由を manifest の stats に残す）。分析用の再変換だけは、使った /config を記録して作った。
- Nav2 の allow_unknown（DEC-214）と waypoint の保存（DEC-215）は変えていない。地図タブの A・B の入力欄（提案 §4）も今回は作っていない。
- 帯の外の不明な格子は 205、空きは 254（map_server の慣例）。占有は作らない。格子の中心の計算で 0.5 の文字を使わない（DR-15）。

## 実装

- `map_convert.py`：read_trajectory、base_path（T_map_base = T_map_imu・inv(T_base_imu)、水平の位置だけ）、split_at_gaps、corridor_grid、swept_corridor。convert は mount（/config の写し）を受け取り、帯を作れたら成果物に加える。変換器の版 0.4。
- `map_creator_node.py`：PRM-96・97 を宣言、原図の横の sensor_config.json があれば mount として渡す。
- 試験：`test_mapping_core.py` に 4 件（帯は通り道から幅以内だけ・占有なし、跳びをつながない、IMU の取付のずれ、軌跡・取付・設定がなければ作らず 2D 地図は作る）。`stage56_fixture.py` に corridor の選択（合成の歩いた跡から帯の地図）、`ubuntu_stage5-6.sh` に MAP_KIND。
- 分析：`research/vehicle_pc/2026-10-21_swept_corridor/`（corridor_analysis.py、README.md、overlay_*.png、summary_*.json、trajectory_steps.txt）。

## 実行した検査・試験

- `apply_revision.py REV-131 --dry-run --check`：新しい違反 0、新しい未判定 2（DR-11、PRM-96・97 の値）。
- Mac `python3 -m pytest -q gouda_core/test`：243 合格、8 skip、不合格 0。
- 規則を壊した写し（跳びをつなぐ、取付の符号を逆、幅を 2 倍、不明を占有に）：どれも test_mapping_core が不合格になった。
- VM 単体（ROS を source）：251 合格、不合格 0。
- VM 分析用の再変換（原図 20261014_044153・20261014_054556、VM の今の /config rev 18、試行の値）：帯の空き 9098・4587 格子。つながなかった所 10・4。今の分類の地図の占有のうち帯の中 570・955 格子（README）。
- VM `MAP_KIND=corridor WS=~/gouda_rev128_ws bash gouda_core/test/ubuntu_stage5-6.sh`（ROS_DOMAIN_ID 77）：帯の地図（半分の幅 0.5 m、空き 775 格子）で T2 が最後の waypoint に着いた（TR-08、最後の姿勢 (4.001, 2.759)）。T3〜T6 は前回と同じ結果。Nav2 の ERROR 5 行（Failed to make progress 1、取消のときの halt 4）。allow_unknown は上流の既定（true）のままなので、帯の外へ経路を引かないことはこの試験では確かめていない（DEC-214 の後）。
- 設計検査 `run_checks.py`：要約行 `{"合格": 12, "違反": 0, "未判定": 5} 違反0件・未判定5件`、DR-11 49、DR-15 31。終了コード 1 の原因は入力の照合の 3 件（前と同じ）。
- 提案 §5 の未確認（obstacle_layer の clearing が static の不明を空きに上書きするか）：未確認のまま。

## 分かったこと（DEC-213 の材料）

- VM の原図の軌跡は約 5 Hz（間隔の中央値 0.2 s、最大 1.2〜1.9 s）。提案の「約 10 Hz」と違う。1 m を超えた隣り合う点の多くは、時間があいただけ（速さ 0.64〜2.63 m/s）で、LiDAR の途切れの跳びではないと見られる（推測）。試行の値 1.0 m では、ふつうの走行の所も帯が切れる。B を距離だけで決めるか、時間あたりの距離（速さ）で決めるかは、人に示す（判定の方法の変更は承認事項）。
- 今の分類の地図は、車体が通った帯の中に占有の格子を持つ（570・955）。

## 修正

- なし。

## 残るリスク

- 分析の取付は今の /config で、地図作成のときと同じかは確かめていない。
- 帯の外へ迂回できない・帯が切れる所で経路が引けない（DEC-213・214 の値と設定しだい）。

## 次の作業

- 人の判断：DEC-211〜215、DEC-208、DEC-209。
- 止まっている：帯の地図を走行に使うこと（DEC-211）、allow_unknown（DEC-214）、地図タブの A・B、waypoint の保存の確認（DEC-215）。
- commit：未実行（第94〜101便の分）。PR #12 は merge 済みなので、新しいブランチを main から作る必要がある。
