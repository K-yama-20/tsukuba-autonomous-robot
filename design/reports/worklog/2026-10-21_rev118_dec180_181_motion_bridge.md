# 作業記録 2026-10-21 第86便: 後退の正規化、不感帯の補償と /config のタブ、事前地図作成での vehicle_bridge の configure（REV-118、DEC-180・181）

## 読んだもの

- コミット `0c898dabbd5ab58cfa55c2b6e29419e60d100a77`（作業ツリー: 第85便の報告と、人のファイル）。
- `design/model.yaml` の DEC-169・171・172、ND-02・03・11・12、IFD-26・40・51、TR-03、TS-07、PRM-78。作業記録 第72便（rev105）、第74便（rev106）、第79便（rev111）、第80便（rev112_113）、第82便（rev116_117）。REV-112・117。
- コード: `motion_core.py`、`motion_controller_node.py`、`vehicle_bridge_node.py`、`autonomy_client.py`、`mode_manager_node.py`、`monitor_core.py`、`monitor_node.py`、`monitor_server.py`、`web/`、`esp32_protocol.py`、`recorder_node.py`、`test/stack.sh`・`ubuntu_stage5-5.sh`。

## 人の指示と回答（原文。台帳 DEC-180・181）

- 「DEC-169, DEC-172を許可する。」
- 「DEC-171について追加の要望がある。最低倒し量としきい値はmonitorで設定できるようにしてほしい。/configの中に新しいタブを作って、そこで設定できるようにせよ。」
- 選択式の質問への回答: 設定の項目「最低倒し量3つ＋しきい値3つ」、未設定のとき「補償しない（今の動き） (Recommended)」、反映の時期「保存したらすぐ」、地図作成の後の vehicle_bridge「接続したまま (Recommended)」。

## 変更

### 正本（REV-118）

- DEC-180（DEC-169・172 の実装の許可、地図作成の後は接続したまま）、DEC-181（補償の設定を /config の新しいタブで、6 項目、未設定は補償しない、保存したらすぐ反映）を answered で記録した。
- IFD-52 config/motion_compensation（ND-02 → ND-11・ND-04、gouda_interfaces/msg/MotionCompensation、transient_local）を追加。TS-40（後退の正規化と補償）を追加。
- 次の要素を変えた: ND-11（責務、IFD-52 の購読）、ND-02（IFD-52 の発行）、ND-12（配置の理由）、ND-03（解釈の追記）、TR-03（actions に vehicle_bridge の configure）、PRM-78（解釈）。
- `apply_revision.py REV-118 --dry-run --check`: 新しい違反 0・新しい未判定 0。そのあと本適用。続けて render_views・generate_params・render_migration_review を実行した。generated/params は先頭のハッシュの行だけが変わった。

### コード（人の許可: DEC-180・181）

- `motion_core.py`: 後退（linear.x＜0）は PRM-78 で割る。Compensation（向きごとの最低倒し量 m としきい値 t）と compensate() を追加した。倒し量の大きさ r が t 未満なら 0、t 以上なら 符号×(m＋(1−m)×r)。m と t のどちらかが未設定の向きは補償しない。中立の条件は補償より先に判定する。範囲外（[0, 1) の外）の設定は使わず、前の設定を残す。MotionOutput に、補償の前の値（normalized_forward・normalized_turn）を加えた。
- `motion_controller_node.py`: max_reverse_speed_mps（PRM-78）を宣言して必須にした。IFD-52 はどの lifecycle の状態でも購読し、次の出力から使う。受け取るたびに DecisionEvent（compensation_settings、または compensation_refused）を出す。configure のときには最新の設定を渡す。
- `gouda_interfaces/msg/MotionCompensation.msg` を新設し、CMakeLists に追加した。
- `monitor_core.py`: SensorConfig に項目の表（fields）を渡せるようにした。種別 fraction（0 以上 1 未満）を追加し、MOTION_COMPENSATION_FIELDS を定義した。センサの /config の動きは変えていない。
- `monitor_node.py`: 設定を `<data_root>/config/motion_compensation.json` に置いた（センサの sensor_config.json とは別）。API は GET・POST `/api/motion_compensation`。起動時と保存時に IFD-52 を発行し、settings の DecisionEvent に補償の版と値を加えた。
- `web/`: /config の中にタブを 2 つ設けた（「センサ取付・座標方向」「自律走行の出力」）。新しいタブには、6 つの入力、式の説明、補償する向きの表示、保存ボタンがある。
- `autonomy_client.py`: configure_bridge() を追加した。vehicle_bridge が unconfigured のときだけ configure し、activate はしない。失敗は vehicle_bridge_configure_failed として記録し、地図作成は止めない。トークンなしの呼び出し（token None）では、一時停止・終了でも打ち切らない。
- `mode_manager_node.py`: TR-03 の遷移の後に configure_bridge を非同期で呼ぶ。TR-04 では何もしない（接続したまま）。

## 自律判断した変更（理由）

- 補償の値は generated/params の PRM にしなかった。人が monitor で入れる運用値で、センサの取付値の /config と同じ扱いにした（人の要望どおり）。範囲（[0, 1)）は倒し量の定義から決めたもので、値の仮定ではない。
- 保存先をセンサの /config と別のファイルにした。地図ごとに写すセンサの /config（GNSS の較正に使う）の中身とハッシュを変えないため。
- 旋回は、左右とも同じ値（turn_min・turn_threshold）を使う。人の回答の「3 つ」を前進・後退・旋回と読んだ。
- 範囲外の設定が IFD-52 で届いたときは、使わずに前の設定を残す（記録はする）。monitor は保存のときに拒否するので、通常は届かない。

## 試験の期待値の変更（1.6 の「試験」）

- `test_motion_core.py` の test_normalisation_saturates_and_never_adds_a_limit の 2 つ目の入力を変えた。後退（−PRM-39×0.25 → −0.25）を前進（＋PRM-39×0.25 → 0.25）にした。後退の正規化が DEC-172（人の承認）で変わったため。後退は新しい試験 test_reverse_is_normalized_by_prm78 で確かめる。合否の基準そのもの（飽和すること、速度を抑えないこと）は変えていない。

## 検査・試験（作業ツリー、コミット 0c898da＋この変更。未 commit）

- Mac `cd gouda_core && python3 -m pytest -q test`: 220 passed、8 skipped（前回 208）。
- VM（新しい作業用ワークスペース `~/gouda_rev118_ws` に写して colcon build --symlink-install --packages-select gouda_interfaces gouda_core）。`python3 -m pytest -q test`: 228 passed、不合格 0。
- VM の結合 1（ROS_DOMAIN_ID=79、`gouda_core/test/stack.sh` の分離された構成、模擬の ESP32 を pty で接続、スクリプトは scratchpad の it_rev118.sh）:
  - 地図作成の開始の前は vehicle_bridge が unconfigured だった。開始の後は inactive になり、mode_manager の vehicle_bridge_configured、HELLO・SET_CONFIG（accepted）、/esp32/status（manual_x_q10000 など）が出た。地図作成中、模擬の ESP32 が受けた COMMAND は 0 件。
  - 地図作成の終了の後も inactive だった。2 回目の開始では vehicle_bridge_configure_skipped が出た。事前地図作成のセッションの切断回数の記録（link_count_started・ended）も出た。
  - 補償: GET は 6 項目とも UNKNOWN。POST（4 項目）は revision 1 で保存され、config/motion_compensation に値と NaN が出た。motion_controller の compensation_settings（revision 1: forward）を確認した。範囲外（turn_min 1.5）は保存を拒否した。
- VM の結合 2（ROS_DOMAIN_ID=79、承認値の gouda_motion_controller.yaml、probe_rev118.py）: 8 項目すべて PASS。項目は、補償なし、PRM-78 での後退（−1.0、−0.5）、設定の直後からの補償（0.6、−0.625）、しきい値未満の中立、後退の補償、しきい値が未設定の向きは補償しないこと、範囲外の設定を使わないこと。
- 画面: scratchpad の DEMO サーバ（ROS なし、本物の SensorConfig）を内蔵ブラウザで開き、次を確かめた。タブの切り替え、入力と保存（revision 1、補償する向き: 前進）、タブを切り替えても値が残ること。入力欄がラベルの下に回り込んでいたので、同じ行に並ぶように直した（VM の試験はこの修正の前の app.js で行った。見た目だけの差）。
- `design/.venv/bin/python design/tools/run_checks.py`: 終了コード 1。設計検査は合格 12・違反 0・未判定 5（DR-15 は 30 件のままで、増えていない）。終了コード 1 の原因は、移行の照合の違反（人の drawio と .DS_Store。以前から）。
- 実機（ESP32・車体）: 未実行。

## 残るリスク

- **VL-01（未検証）**: PC がシリアルポートを開くと ESP32 がリセットされる場合、地図作成の開始のときにリセットが起きる。そのとき人はゲームパッドで手動走行していることがあり、手動の出力が一瞬途切れる可能性がある。今のコードは DTR・RTS を設定しない。卓上の VL-01 で確かめるまでは、地図作成の開始は止まった状態で押すことを勧める（運用の注意。決定ではない）。
- 補償は、保存したら走行中でもすぐ効く（人の選択）。走行中に保存すると、次の指令から倒し量が段差状に変わる。
- しきい値未満は中立にする（DEC-171 案 A）。RQ-I020 の例外で、ND-11 の責務に明記した。
- 補償の値は人が入れる運用値で、判断台帳の承認の対象ではない。記録は DecisionEvent（monitor の settings、motion_controller の compensation_settings）と、`motion_compensation.json` の版で残る。
- PC 側の補償・中立化は、車体の停止を保証しない（CLAUDE.md 1.5）。手動の優先と PC 指令の途絶時の中立化は、firmware が受け持つ。
- VM の `~/gouda_ws` と x86 機には反映していない。テスト用に `~/gouda_rev118_ws` を作った（VM の上の作業用で、人の作業領域ではない）。

## 更新した生成物

- design/generated/params/*（ハッシュの行だけ）、design/generated/ の review_r3・lower_design_r2・gate3_package、design/migration_review.md、design/intent_index.yaml、design/reports/model_diff_rev-118.md と検査の結果のファイル。

## 次に進められる作業・止まっている作業

- 人の作業: 卓上の VL-01・TS-17〜19。最低倒し量・しきい値の実測（前進・後退・旋回）と /config への入力。VM・x86 機への反映。commit・push の指示。
- 止まっている: 実車での確認。ND-07、Nav2 の値（第85便の報告）。
