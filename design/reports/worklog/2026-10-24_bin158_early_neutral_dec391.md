# 第158便 作業記録：自律走行開始で中立を先に送る（REV-181、DEC-391）

- 日付：2026-10-24
- 読んだコミット：1d7ee4663687a69ba101121964757405ff16cc00（作業ツリーには未コミットの変更あり：REV-180 ほか）
- 読んだもの：`design/reports/status.md`、第157便の作業記録、`autonomy_client.py`・`mode_manager_node.py`・`motion_core.py`・`vehicle_bridge_node.py`、firmware の `control.hpp`、model の TR-05
- 人の指示（原文）：「Aを実行せよ。自律走行開始を押したら、中立信号をまず送る。その間にNav2とが立ち上がったりする」（その直前に「Nav2十かが」の文が中断されて送られ、すぐに送り直された）

## 1. 変更

### 1.1 コード（承認：DEC-391）

- `gouda_core/gouda_core/autonomy_client.py`
  - `activate_vehicle_output(token, record)` を足した。ND-11・ND-12 を configure・activate し、`vehicle_output_active` を記録する
  - `start()` から ND-11・ND-12 の活性化を除いた（Nav2 の STARTUP の後に goal を送るだけ）
  - docstring を新しい順に合わせた
- `gouda_core/gouda_core/mode_manager_node.py`
  - TR-05 の作業の最初に `self.auto.activate_vehicle_output(token, rec)` を呼ぶ。その後に ND-08（GLIM）、ND-07、Nav2、goal
  - docstring を新しい順に合わせた
- 新しい順：自律走行開始 → (記録の自動開始の要求) → **ND-11・ND-12 の活性化** → ND-08 → 初期位置 → ND-07（正常まで）→ Nav2 の設定・STARTUP → goal → 適用中と keepout の確認 → motion_hold を解く
- 中立になる理由：TR-05 で drive_released は false にされ、motion_hold は true（`_publish_motion_hold`）。ND-11 は hold が true の間、中立を出す（`motion_core`）。ND-12 は pc_enable_request つきで最新の値（中立）を周期 PRM-14 で送る。firmware は pc_enable_request つきの中立の COMMAND で PC を有効にする（`control.hpp:183`）
- 数値・設定は足していない・変えていない

### 1.2 試験

- `gouda_core/test/test_tr05_start_order.py`（新規、3 件。rclpy と nav2_msgs がある所だけで動く）
  - TR-05 の順が「記録の要求 → 車体出力 → odometry → 推定・Nav2・goal」で、その間 drive_released が false
  - 車体出力の活性化に失敗したら、その後の手順に進まない
  - `AutonomyClient.start()` が車体出力を活性化しない

### 1.3 正本（REV-181）

- DEC-391（approval、answered）：人の回答を原文で記録。affected TR-05・ND-03・ND-11・ND-12
- TR-05 の transition.actions の先頭に「最初に ND-11・ND-12 を configure・activate する…」を足した。interpretation に追記
- 第157便の証拠 4 ファイルを登録（FILE-AUTONOMY-STOP-FF780D47-*）

## 2. 自律判断と理由

- 活性化の失敗（StepFailed）は今までどおり TR-07（node_failure）で一時停止になる。順が前に移っただけで扱いは同じ
- 副次の効果：今までは Nav2 の起動の後に活性化していたので、活性化の前に開始が失敗すると、Nav2 が動いていないので再開（TR-10）は拒否されていた。今は Nav2 が動いていれば車体出力も必ず活性。振る舞いを広げる変更ではない
- 「ESP32 が PC を有効にした（pc_enabled）ことを motion_hold を解く条件にする」ことはしていない。人の指示の範囲外。必要なら新しい判断事項（承認）にする

## 3. 実行した検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 変更セットの試し | `design/.venv/bin/python design/tools/apply_revision.py REV-181 --dry-run --check` | 作業ツリー（1d7ee46＋未コミット） | 新しい違反 0、新しい未判定 0 |
| 適用・再生成 | `apply_revision.py REV-181`、`render_views.py`、`generate_params.py`、`render_migration_review.py` | 同上 | いずれも終了コード 0 |
| 設計検査 | `design/.venv/bin/python design/tools/run_checks.py` | 同上 | 終了コード 1。design_check：「違反0件・未判定5件」（前と同じ）。input_integrity・intent_identity・migration_validator・migration_tests の FAIL は intent.md の未記録の編集による既存のもの（AR-017） |
| 単体試験（Mac） | `/opt/anaconda3/bin/python3 -m unittest discover -s gouda_core/test` | 同上 | 296 件 OK（skip 14。新しい 3 件は ROS がないので skip） |
| 単体試験（VM） | 作業ツリーを `~/gouda_unit_tree_bin158` に写し、jazzy と `~/gouda_ws/install` を source、ROS_DOMAIN_ID 93 で `python3 -m unittest discover -s gouda_core/test` | 同上 | 296 件 OK（新しい 3 件を含む。`-v` でも 3 件 ok を確認） |
| 結合試験（ubuntu_stage5-6.sh） | — | — | 未実行 |
| 新しい試験が古いコードで不合格になることの確認 | — | — | 未実行 |
| 実車（ESP32 の pc_enabled が開始直後に出ること） | — | — | 未実行（VM の Gouda には反映していない） |

## 4. 原因の分類（1.6）

- 設計（開始の手順の順序）。正本（TR-05）を直し、コードを直した

## 5. 残るリスク

- VM の動いている Gouda には未反映（反映には gouda.sh の再起動が要る。IMU の再接続が要る）。実車で pc_enabled が自律走行開始の直後に出ることは未確認
- 中立の COMMAND が届いても、ESP32 が有効にしない場合（例：pc_enable_request が落ちる、通信の途絶）に、motion_hold が解かれて Nav2 が走り出し、第157便と同じ進みの失敗が起きうる。確かめてから解く案は未承認
- 第157便の止まった直接の原因（map→odom の古さによる TF エラー、CPU 不足の推測）はこの便では直していない

## 6. 更新した生成物

- `design/model.yaml`（TR-05、DEC-391、FILE-*）と、それを元に再生成した views・migration review（apply_revision と render の出力）。params の値は変わっていない

## 7. 次に進められる作業／止まっている作業

- 進められる：VM の Gouda への反映（人の許可と、manual であることの確認の後）、結合試験 ubuntu_stage5-6.sh
- 止まっている：第157便の B〜E（人の判断待ち）

## 8. 追記：VM の Gouda への反映（人の指示「VMのGoudaに反映せよ（manualを確認してから再起動）」）

- 確認：`gouda.sh status` は not running（VM は 02:56 ごろ再起動されていた。uptime 11 min）。直前モード記録は manual（`previous_mode_record.json`）。止める操作は不要だった
- 上書きの前に、VM の 2 ファイルが Mac の HEAD（1d7ee46）と同じ（sha256 先頭 8f41febd7c53・683b244a8857）ことを確かめた。VM だけの変更は上書きしていない
- 写したもの：`autonomy_client.py`、`mode_manager_node.py`、`test/test_tr05_start_order.py`（~/gouda_ws/src/tsukuba-autonomous-robot へ scp）。gouda_core は symlink install（build/gouda_core/gouda_core → src）なので build はしていない。build 側から新しい関数名が見えることを grep で確かめた
- `bash gouda.sh start`（03:06、pgid 5423）。20 s 後：running（26 processes）、launch log に Traceback 0・ERROR 0、/mode/state は mode 1（manual）・idle
- 起動時のセンサの状態：IMU は present・driver 起動。**XT-32 は absent**（192.168.1.100 を持つ interface がない：USB-LAN が VM についていない可能性）、**GNSS・NTRIP は absent**。再起動の後の接続は人の作業
- 未実行：自律走行開始での確認（ESP32 の pc_enabled が開始直後、Nav2 の起動より前に出ること）。センサがつながってから人が開始したときに記録で確かめる
