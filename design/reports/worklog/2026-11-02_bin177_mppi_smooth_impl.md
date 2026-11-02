# 第177便 作業記録：MPPI を既定にし、経路の平滑化を足す（REV-190、DEC-400・401・402）

- 日付：2026-11-02
- 読んだコミット：f61a71b（作業ツリーに別のチャットの未コミットの変更あり）
- 人の回答（原文、DEC-402）：「実装する」（問い：MPPI を既定にする構成で、MPPI と平滑化の実装に着手するか）

## 1. 変更

- `gouda_core/gouda_core/nav2_config.py`：
  - PRM-130 true で FollowPath を上流の雛形の MPPI に。vx_max PRM-131 0.8 m/s、wz_max PRM-132 1.0 rad/s、ax PRM-68、az PRM-73、vx_min 0、CostCritic は footprint、visualize false、prune_distance は雛形の比で 2.72 m。その他は雛形のまま
  - PRM-130 false で今までの RPP（PRM-114〜123 が効く）
  - local costmap：PRM-124 8 m、PRM-133 10 Hz
  - BT：PRM-134 true で ComputePathThroughPoses の後に SmoothPath（simple_smoother）。全体を Sequence で包む（ReactiveSequence の中だと SmoothPath の実行中に計画を出し直すため）。計画は {unsmoothed_path} に出し、FollowPath の {path} は平滑化後だけ
- `gouda_core/launch/gouda_nav2.launch.py`：MPPI のとき nav2_mppi_controller がなければ Nav2 を起動しない
- `setup.sh`：ros-jazzy-nav2-mppi-controller
- `gouda_core/web/app.js`：/config「Nav2」タブの 5 つの項目の表示名
- `gouda_core/test/test_nav2_config.py`：新しい試験 4 件。既定が MPPI・PRM-124 が 8 になったことで、RPP の試験を明示の false にし、PRM-124 の期待値を変えた（承認された仕様の変更による）
- 正本（REV-190）：DEC-402、PRM-130〜134、PRM-124、ND-10

## 2. 自律判断と理由

- 切り替えを新しい種類の入力にせず boolean にした：monitor の仕組みをそのまま使える
- prune_distance は新しい PRM にせず雛形の比で追従させた
- collision_monitor・waypoint の渡し方・keepout は変えていない（DEC-372・366 ほか未回答）

## 3. 実行した検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 変更セットの試し | `apply_revision.py REV-190 --dry-run --check` | 作業ツリー（f61a71b＋変更） | 新しい違反 0・新しい未判定 3（DR-15：既存の 1.0 の文に PRM-132 が足されたもの。既存の箇所） |
| 適用・再生成 | apply_revision・render_views・generate_params・render_migration_review | 同上 | いずれも 0 |
| 単体試験（Mac） | `/opt/anaconda3/bin/python3 -m unittest discover -s gouda_core/test` | 同上 | 309 件 OK（skip 15） |
| 設計検査 | `design/.venv/bin/python design/tools/run_checks.py` | 同上 | 終了コード 1。design_check 違反 0・未判定 5。migration_tests は前と同じ 2 件失敗、migration_validator の違反は前と同じ 2 件（intent 由来） |
| 実車の値（trial なし）で設定の生成 | `nav2_config.write`（python、雛形は design/research） | 同上 | missing なし。FollowPath は MPPI、BT は Sequence ＋ SmoothPath |
| app.js の構文 | `node --check` | 同上 | OK |
| Nav2 の起動（MPPI・SmoothPath が実際に読み込まれるか）、模擬の結合試験、CPU の測定、実車 | — | — | 未実行（Mac に ROS なし、VM に ssh がつながらない） |

## 4. 原因の分類（1.6）

- 設計（controller の選択、DEC-122 の見直し）・設定（値）

## 5. 残るリスク

- 実装済み・単体試験まで確認済み・Nav2 での起動は未確認・実車未検証
- MPPI は CPU を多く使う（batch 2000×56、20 Hz、local 10 Hz）。実車の PC で未測定で、自己位置の遅れにつながる恐れ
- FollowPath の transform_tolerance は雛形の 0.1 s のまま。map→odom の遅れ（第157・160便）で TF エラーになる恐れがあり、未確認
- 回避は局所の判断で、stop の四角などの監視はない。XT-32 は足元が見えない（MID-360 は未統合）
- 車輪のエンコーダがなく、指令と実速度のずれで MPPI の予測が外れる恐れ（推測）
- 迂回で waypoint を 0.7 m より外して通ると、引き返す経路が出る恐れ（TRB-006、PRM-11 は未変更）
- x86 の PC・VM で update.sh（sudo）を実行しないと MPPI の package がなく、Nav2 が起動しない恐れ（入っているかは未確認）
- MPPI を既定にしたので、main に入れるとそのまま実車の既定が変わる。切り戻しは /config で PRM-130 を false

## 6. 次に進められる作業／止まっている作業

- 止まっている：起動・結合試験・CPU の測定（VM か x86 の PC への接続）、collision_monitor（DEC-372）、waypoint（DEC-366・367・380）
- コミット・push はまだ

更新した生成物：再生成（`design/reports/model_diff_rev-190.md`）。gouda_nav2.yaml に PRM-124・130〜133、bt_params.yaml に PRM-134。
