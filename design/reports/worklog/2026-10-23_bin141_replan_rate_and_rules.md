# 作業記録 2026-10-23 第141便: 規則の操作の範囲、経路の引き直しの頻度 PRM-103 の実装、障害物の扱いと段差（REV-167、DEC-347〜349）

## 読んだもの

- 作業ツリー `31a6e1d` ＋ 未コミットの変更（第140便まで）。`design/intent.md`（人の 15:08 の編集の版、未記録）。
- `gouda_core/gouda_core/nav2_config.py`・`monitor_core.py`・`monitor_node.py`、`gouda_core/web/app.js`、`gouda_core/test/test_nav2_config.py`・`test_monitor_core.py`、PRM-98・PRM-18・IFD-54 の正本、上流の BT の写し。

## 1. 人の発言・指示（原文）

「異常の時にチームメンバーがボタンを押すなどの操作を加えると、走行失敗になる。再開ボタンを押しても良いのは一時停止線で停止した後や、信号が青になった後のみである。
停止線での再開にpcのボタンを使って良いと考えられる。

costmapの更新頻度は暫定的に1Hzとしたい。また、この値は/configで変更できるようにせよ。

障害物自体は遠くから認識しつつ、近づくにつれて更新していく（更新にはカルマンフィルタなどの数理手法を用いる）のはどうか？それ以外は君の推奨案でいいような気がする。

横断歩道のある面と歩道の面の間には、当然段差がある。日本の歩道は車道より少し高く作られているためだ。横断歩道の面に降りたときと、歩道に乗り上げたとき、機体の角度が大きく変わるが、その瞬間にGLIMやndtが飛んだりクラッシュしたりしないかが心配だ。」

## 2. 行ったこと

- REV-167 を適用（`--dry-run --check` の後）。DEC-345 に人の回答を記録（answered）。DEC-347（経路の引き直しの頻度、answered）、DEC-348（障害物の扱い、recorded）、DEC-349（段差の実測、pending）。PRM-103（replan_rate_hz＝1.0 Hz、暫定）を足し、IFD-54 に replan_rate_hz を足した。番号は reserve_ids.py で予約（REV-167、DEC-347〜349、第141便）。PRM-103 は予約の仕組みの外（model.yaml の最大 PRM-102 の次）。
- **実装（DEC-347 の人の指示「せよ」を、この項目の実装の許可（DEC-106）として扱った）**
  - `nav2_config.py`：REQUIRED に PRM-103、`replan_from_config()`（monitor の値が正の有限の数ならそれ、ほかは PRM-103 と理由）、`build_bt()` で ComputePathThroughPoses を囲む RateController の hz を入れる（見つからなければ例外）、overrides.json と戻り値に replan_rate_hz。
  - `monitor_core.py`：/config「Nav2」タブの項目に replan_rate_hz（新しい種類 'positive'：0 より大きい有限の数）。
  - `monitor_node.py`：Nav2 タブの API に PRM-103・次の起動で使う値・今の起動で使っている値。
  - `web/app.js`：Nav2 タブに入力欄「経路の引き直しの頻度（Hz）」と 3 行の表示（intent.md の新しい行に従い、補足の説明は付けなかった）。
  - 試験：`test_nav2_config.py`（BT の hz、他は変えない、monitor の値の上書きと不正な値）、`test_monitor_core.py`（正の数だけ保存）。
- トラブルシューティング台帳に TRB-004（段差での推定の乱れ）を足した。

## 3. 原因の分類

- 設定（経路の引き直しの頻度が雛形の 0.333 Hz のままで、置かれたコーンへの対応に遅い）。正本の PRM を足し、生成物から作る。

## 4. 検査・試験

- Mac：`/opt/anaconda3/bin/python3 -m unittest discover -s gouda_core/test`（31a6e1d ＋ 作業ツリー）→ 287 件、OK（skip 10）。新しい試験 2 件と test_bt は実行され合格。
- VM：作業ツリーを `~/gouda_unit_tree_bin141` に写して `python3 -m unittest discover -s gouda_core/test`（ROS_DOMAIN_ID 81）→ 287 件、OK（skip 8）。1 回目は写し忘れた証拠のファイル（design/research/vehicle_pc/2026-10-22_mapping_motion）で 1 件エラー、写して再実行（試験基盤の誤り、合否の基準は変えていない）。
- VM：インストール済みの上流の雛形（/opt/ros/jazzy/share/nav2_bt_navigator）から BT を作り、RateController の hz が 1.0 になることを確かめた（missing なし）。
- 設計検査：合格 12・違反 0・未判定 5。DR-15 の未判定は 35 件のまま（新しい直書きなし）。移行の違反 2 件と検査器の試験の不合格 1 件は、intent.md の未記録の編集による（第139便から同じ）。
- 未実行：VM の Gouda への反映（~/gouda_ws）と monitor の画面での確認。確認の時点で VM では Gouda が動いていたので触れていない。反映は人の確認の後。

## 5. 人の問いへの答え（チャットでも答えた）

- 規則：異常のときにチームメンバーが操作すると失敗。再開ボタンは停止線で止まった後か信号が青になった後だけ。→ 自動で待機に入らない設計（DEC-305）は必須。本番で人が止める手段は実質ない。
- 障害物を遠くから認識し、近づくにつれて更新する：止まっている物は、印を消さずに保つことで目的を果たせる（カルマンフィルタは要らない）。動く物（歩行者・ロボット）を追うには、点群を物にまとめてカルマンフィルタで追跡する仕組みが要り、Nav2 1.3.13 にはない。第3版で扱う。
- 段差：DEC-349 の実測と TRB-004。

## 6. 残るリスク

- 経路の引き直しを 1 Hz にすると、経路が頻繁に変わって車体がふらつく可能性がある（推測）。実車で確かめる。
- 「costmapの更新頻度」を経路の引き直しの頻度と解釈した（DEC-347 の note）。違っていれば直す。
- VM の Gouda には未反映。

## 7. 次

- VM の Gouda への反映と monitor の Nav2 タブの確認（人の許可の後）。
- costmap の提案 第3版（MID-360、止まっている物と動く物、距離、DEC-341）。

## 8. 追記：VM の Gouda への反映と monitor の確認（2026-10-23 16:0x）

人の指示（原文）「Deploy to the VM's ~/gouda_ws and check the monitor Nav2 tab, but only after confirming Gouda is in manual mode or stopped; ask me if it is running a trial.」

- モードの確認（止める前に別の手順で 2 回）：monitor の /api/state で MANUAL・idle・run_id なし・受信あり。永続の記録も manual（human_pause_or_end true）。走行の試行中ではないので進めた。
- 写したもの：VM の `~/gouda_ws/src/tsukuba-autonomous-robot` は c2b8d65 ＋ 未コミットの変更。写す前に、VM の 7 ファイル（nav2_config.py・monitor_core.py・monitor_node.py・app.js・試験 2 件・bt_params.yaml）と手元の差が、この便の変更だけであることを diff で確かめた。7 ファイルを scp で上書き。gouda_core は symlink install なので colcon build は不要（build/gouda_core/gouda_core は src へのリンク）。
- `bash gouda.sh stop`（1 秒で停止）→ `bash gouda.sh start`。
- 確認（起動の後）：
  - `gouda_data/run/nav2/navigate_through_poses.xml` の RateController が `hz="1.0"`。`overrides.json` の replan_rate_hz は 1.0（PRM-103、monitor の保存なし）。
  - monitor の /api/nav2_recovery：replan_rate_hz の欄（UNKNOWN）、PRM-103＝1.0、次の起動・今の起動とも 1.0。
  - 内蔵ブラウザで SSH の転送（localhost:18080 → VM の 127.0.0.1:8080）から「設定 /config」→「Nav2」タブを開き、入力欄「経路の引き直しの頻度（Hz）」と 3 行の表示を目で確かめた。
  - 不正な値の拒否：POST `{"replan_rate_hz":"0"}` → `False replan_rate_hz: 0.0 is not a number above zero`、config_revision 0 のまま、nav2_recovery.json は作られなかった。正しい値の保存は試していない（人の設定のファイルを作らないため。単体試験で確認済み）。
  - 起動の後もモードは MANUAL。launch のログに Traceback・ERROR なし。
- センサー：3 つとも未受信。supervisor の記録は「device_absent」（XT-32 の LAN の口、IMU・GNSS の USB が VM にない。/dev/serial/by-id がない）。再起動の前から VM にセンサーがつながっていなかった（monitor の表示も USB 未接続）。再起動による IMU の応答なし（既知）とは別。
- 転送の SSH は閉じた。
