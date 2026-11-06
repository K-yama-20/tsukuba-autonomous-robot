# 作業記録 2026-11-07 第250便: MID-360 なしで起動・走行できるかの確認（試験のみ）

## 読んだもの

- コミット `9c449b5`（ブランチ design/mppi-sim-2026-11-03）＋作業ツリー（他のセッションの未コミットの変更を含む。2026-11-07 04:24 頃の状態をワークステーションに写した）。
- `CLAUDE.md`（1.1、1.3〜1.6、1.10〜1.12）、`design/reports/status.md` の冒頭。
- コード：`gouda_core/gouda_core/mid360_config.py`（全体）、`gouda_core/launch/gouda_nav2.launch.py`（全体）、`nav2_config.py` の `add_mid360`・`write`、`monitor_node.py` の Nav2 タブの snapshot、`static_tf_node.py` の MID-360 の部分、`sensor_supervisor_node.py` の `_observe`・`_build_*`、`gouda.sh` の start・stop、`gouda_core/test/drive_sim.sh`。
- 試験したファイルの sha256（先頭 16 桁）：`mid360_config.py` b74c89cef5178c5c、`gouda_nav2.launch.py` 9ede7d2141e89073、`nav2_config.py` 39088fb30cf2ee0a、`mode_manager_node.py` 7fb7f81394fdcc00、`static_tf_node.py` fea7756605070186、`design/generated/params/gouda_nav2.yaml` 105f4445c40d22a1（PRM-142 `mid360_enabled: true`）、`gouda.sh` 9259d715f00cb8b6。
- 車載 PC には触れていない。gouda.sh はどこでも起動していない。

## 1. 人の言葉（原文）

- 「MID-360の取り付けは5:30-6:00頃になる予定です。それまでmid-360なしでも一連の実機テストを進められますか？色々なセッションで並行して作業を進めていますから、それも統合しつつ、mid-360が無いからクラッシュするということにならないようにしたいね。」

## 2. 方法

- シミュレーション用のワークステーションに自分の workspace を作り（`~/gouda_ws_stop/src` の写しに、Mac の今の `gouda_core/`・`gouda_interfaces/`・`design/generated/params/`・`gouda.sh` を重ねた）、`colcon build --packages-select gouda_interfaces gouda_core` で作った（成功）。
- ドライバ：ワークステーションには setup.sh の節を試した別のセッションの livox_ros_driver2（colcon で作ったもの）と Livox-SDK2 があった。読むだけで使い、そのディレクトリは変えていない。setup.sh が作る `<workspace>_livox` と同じ版かは確かめていない（推測では同じ固定の commit）。
- 状態ごとの設定：`drive_sim.sh` の `SIM_FIXTURE` に自分の小さな fixture（ワークステーションの結果のディレクトリに置いた。共有の試験ファイルは変えていない）を渡し、いつもの fixture の後に `config/mid360.json` と `config/sensor_config.json` を置いた。アドレスは文書用の試験の範囲（応答する機器はない）。取り付けの値は試験用の仮の値（車両の値ではない）。
- 走行：`drive_sim.sh free`（ROS_DOMAIN_ID 197）。始める前に、他のセッションを含む模擬の数を数え、5 未満のときだけ始めた（見た数：C 4、A 2、D1 4、B 4）。一度に 1 本。
- 判定の関数：`gouda_nav2.launch.py` の `_mid360_ready` を状態ごとの設定で直接呼んだ（ドライバを読み込んだときと、読み込まないとき）。
- ドライバ単独：試験の範囲のアドレスの設定で `livox_ros_driver2_node` を 20 秒動かした。
- PRM-142 を /config の 「Nav2」 タブの保存（`nav2_recovery.json` の `mid360_enabled`）で false にしたときの `nav2_config.write` の結果を確かめた。

## 3. 結果（状態ごと）

| 状態 | launch に Traceback（MID-360 によるもの） | 自律走行開始 | `free` でゴール | launch のログの理由 | 確かめ方 | 判定 |
|---|---|---|---|---|---|---|
| A ドライバなし、mid360.json なし（今の車載 PC） | なし | 可（`TR-05: manual -> autonomy`） | 着いた（`pause:goal_reached`、60.9 s、接触 0） | `MID-360 layer NOT used (XT-32 only): <cfg>/mid360.json does not exist ...; the MID-360 mounting is not complete (...)` | 走行 | 合格 |
| B ドライバあり、mid360.json なし・取り付けなし | なし | 可 | 着いた（`pause:goal_reached`、69.2 s、接触 0） | A と同じ理由（`mid360.json does not exist ...`） | 走行・判定の関数 | 合格 |
| C ドライバあり、アドレスと取り付けあり、機器なし | なし | 可 | 着いた（`pause:goal_reached`、60.9 s、接触 0） | `MID-360 layer used: PRM-142 true (...), the vehicle PC's settings and the driver found` | 走行 | 合格（ただし第 5. の 1・2） |
| D1 mid360.json が壊れた JSON、取り付けあり | なし | 可 | 着いた（`pause:goal_reached`、60.9 s、接触 0） | `MID-360 layer NOT used (XT-32 only): <cfg>/mid360.json could not be read (JSONDecodeError)` | 走行 | 合格 |
| D2 アドレス 1 つ、取り付けが 1 項目欠け | 例外なし | 未実行（走行） | 未実行 | `lidar_ip is missing or not an IPv4 address; the MID-360 mounting is not complete (... mid360_mount_z_m)` | 判定の関数 | 合格（判定の関数の範囲） |
| D3〜D5 配列・不正なアドレス・空のファイル・壊れた sensor_config.json | 例外なし | 未実行（走行） | 未実行 | `could not be read (ValueError)`、`host_ip is missing or not an IPv4 address; ...`、`could not be read (JSONDecodeError); ...` | 判定の関数 | 合格（判定の関数の範囲） |

- どの状態でも、MID-360 によって launch が止まったり、ノードが落ちたりはしなかった。
- 状態 C の詳細：
  - ドライバは `bind failed` / `Failed to init livox lidar sdk.` / `Init lds lidar fail!` を出したが、終了しないで動き続けた（単独で 20 秒、走行中もずっと）。`/sensors/mid360/points` には発行者がいない（単独の試験で `Unknown topic`）。
  - 両方の costmap に `mid360_layer` が入った（`Initialized plugin "mid360_layer"`）。`mid360_scan` は `Got a subscriber to laserscan` を出した。点群が来なくても costmap は止まらず、ゴールに着いた。
  - 層の設定は `expected_update_rate` と `observation_persistence` を書いていない（`nav2_params.yaml` で確認）。上流の既定は 0 で、0 のとき ObservationBuffer の isCurrent は常に真になる、と理解している（上流のソースの記憶。ワークステーションには `observation_buffer.hpp` の宣言だけがあり、実装は読めていない。走行がゴールに着いたことは、この理解と矛盾しない）。
  - static TF：`mid360_link published from /config`。
  - モード管理・センサ監視：MID-360 を参照するコードはない（`sensor_supervisor_node.py`・`mode_manager_node.py` に mid360・livox の文字列なし）。自律走行開始は拒まれなかった。
- launch の中の Node に `respawn`・`on_exit`・`OnProcessExit` の設定はない（`gouda_core/launch/*.py` を検索）。ROS 2 launch の既定では、1 つのノードが終わっても launch は止まらない。ドライバが自分で終わる場面は起きなかったので、終わったときの動きは走行では確かめていない（未判定。読んだ範囲では止まらない）。
- 判定の関数で例外は一度も出なかった（`read_local` が `OSError`・`ValueError` を受け、`SensorConfig.load` が壊れた JSON を受ける）。

## 4. 状態 B の走行

- `ros2 pkg prefix livox_ros_driver2` がドライバを返す状態で走らせた（始める前の模擬の数 4）。層は入らず（`nav2_params.yaml` に `mid360_layer` なし）、ゴールに着いた。Traceback は #86 と停止のときの `KeyboardInterrupt` だけ。

## 5. 見つけたこと（危ないものを先に）

1. **モニタでは、MID-360 の層が実際に使われているかが分からない**（コードを読んで確認、走行の `overrides.json` でも確認）。`run/nav2/overrides.json` には `mid360_enabled`（PRM-142 の値 true）しか入らず、使ったかどうか（`mid360.used`・理由）は入らない。モニタの Nav2 タブは overrides.json の値を「使用中」として出すので、XT-32 だけのときも `true` と出る。判別できるのは launch のログの `[gouda_nav2] MID-360 layer used: ...` / `NOT used (XT-32 only): ...` の一行だけ。issue #95。
2. **機器が応答しないとき、ドライバが SIGINT・SIGTERM で止まらない**（状態 C の走行で確認）。停止のとき SIGINT の 5 秒後に SIGTERM、さらに 10 秒後に SIGKILL を受けて終わった。gouda.sh stop は止まるが約 15 秒延びる。機器がつながっているときは未確認。issue #96。
3. センサ監視の thread の `AttributeError: 'Driver' object has no attribute 'host_ip'` が、A・B・C・D1 のすべての走行で出た。MID-360 とは関係なく、既に issue #86 にある。模擬で GNSS の中継の機器が無いときに起きるもの（読んだ範囲。車載 PC で起きるかは未確認）。
4. 停止のときの `KeyboardInterrupt` の Traceback（gouda_mode_manager・gouda_monitor）は試験の後始末で出たもの。MID-360 とは関係ない。
5. gouda.sh start は `<workspace>_livox/install/local_setup.bash` が無いとき `MID-360 driver not built (<path> missing): XT-32 only` と出して続ける（読んで確認。gouda.sh は実行していない）。

## 6. 人向けの表

### XT-32 だけか、MID-360 も使っているかを走行の前に見分ける

- launch のログ（gouda.sh start の log）の `[gouda_nav2] MID-360 layer ...` の一行。`used:` なら層あり、`NOT used (XT-32 only): <理由>` なら XT-32 だけ。
- ドライバの workspace が無いときは、gouda.sh start の端末に `MID-360 driver not built (...): XT-32 only` も出る。
- static TF の記録（`static_tf_published`）の `mid360_link published from /config` / `mid360_link not published: ...` は TF の有無であって、層の有無ではない（D1 では TF は出たが層は入らなかった）。
- モニタの Nav2 タブの `mid360_enabled` の「使用中」は PRM-142 の値であって、層の有無ではない（#95）。

### 後で MID-360 の層を入れるときに、そろっていること

1. `bash setup.sh` が最後まで通り、`<workspace>_livox/install/local_setup.bash` と `livox_ros_driver2` の `config/MID360_config.json` がある。
2. `<data_root>/config/mid360.json` に `host_ip`（PC 側）と `lidar_ip`（MID-360）の 2 つの IPv4 アドレス。JSON のオブジェクトであること。
3. モニタの /config 「センサ取付・座標方向」に `mid360_mount_x_m`・`_y_m`・`_z_m`・`_roll_rad`・`_pitch_rad`・`_yaw_rad`・`mid360_axis_mapping` の 7 項目（右手系）。
4. PRM-142 が true（生成物の既定は true。/config の 「Nav2」 タブで false が保存されていないこと）。
5. 判定は gouda.sh start の時だけ。設定を変えたら gouda.sh stop → start がいる（TF は保存ですぐ出し直す）。
6. 起動の後、launch のログに `MID-360 layer used:` があることを確かめる。

### 機器を付けた後も XT-32 だけにする

- /config の 「Nav2」 タブで `mid360_enabled` を false にして保存し、gouda.sh を start し直す。ログは `MID-360 layer NOT used (XT-32 only): PRM-142 mid360_enabled is False (monitor /config Nav2 tab ...)`（`nav2_config.write` を直接呼んで確認。走行では未実行）。
- または `mid360.json` を置かない（名前を変える）。

## 7. 検査・試験

| 試験 | 場所 | 対象 | 結果 |
|---|---|---|---|
| `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test -p "test_mid360*"` | Mac | 作業ツリー（9c449b5＋未コミット） | 23 件 OK |
| 同上 | ワークステーション | 同じ写し | 23 件 OK |
| `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test` | Mac | 同上 | 489 件 OK（skip 35） |
| 全体の単体試験 | ワークステーション | — | 未実行 |
| `drive_sim.sh free`（状態 A・B・C・D1） | ワークステーション | 同上 | 4 本ともゴール（上の表） |
| `_mid360_ready` の直接の呼び出し（A・C・D1〜D5、ドライバの有無） | ワークステーション | 同上 | 例外なし、理由は上の表 |
| ドライバ単独 20 秒（試験の範囲のアドレス） | ワークステーション | 同上 | 生きていた、`Init lds lidar fail!` |
| PRM-142 false の保存での `nav2_config.write` | ワークステーション | 同上 | `used: False`、costmap の plugins に `mid360_layer` なし |
| 設計検査 | — | — | 未実行（正本・生成物は変えていない） |

## 8. 実行していないもの・判定していないもの

- 車載 PC での確認（setup.sh・gouda.sh start）：未実行。
- 実機の MID-360 をつないだときの動き、機器の電源を入れたり切ったりしたとき：未実行（DEC-456 は未回答）。
- ドライバが自分で終わったときの launch の動き：未判定（起きなかった）。
- D2〜D5 の走行：未実行（判定の関数だけ）。
- 上流の ObstacleLayer・ObservationBuffer の実装（1.3.13）を読むこと：未実行（記憶による）。
- 原本の照合：対象外（コードと試験だけ）。

## 9. 原因の分類（1.6）

- 修正はしていない。#95 は設計（判定の結果を記録・表示する契約の不足）、#96 は物理特性・上流のドライバ（実測と上流の調査が要る）。

## 10. 残るリスク

- 車載 PC の `<workspace>_livox` と、ここで使ったドライバが同じものかは確かめていない。
- 実機では host_ip が PC の NIC にあるので `bind failed` にならず、機器を待つ動きになるはず（推測）。その場合の停止の時間・ログの量は未確認。
- モニタで層の有無が見えないので、取り付けの後に入ったつもりで入っていない（逆も）ことに気づくのが遅れうる（#95）。

## 11. 次

- 人：#95・#96 を見て、要るものに approved を付ける。
- 車載 PC で setup.sh の後に gouda.sh start をして、launch のログの `MID-360 layer ...` の一行を確かめる（人の指示があれば）。
