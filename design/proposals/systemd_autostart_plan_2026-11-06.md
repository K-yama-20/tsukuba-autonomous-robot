# gouda.sh を systemd で動かし、電源投入で自動起動する案（提案、2026-11-06、第205便）

> 2026-11-06 追記：人の方針転換（DEC-435 の回答、REV-224）により、この案は採用しない。代わりに PC の起動時に端末を開くだけにする（DEC-436、承認待ち）。以下は記録として残す。

状態：提案。実装は承認待ち（DEC-435）。コード・設定は変えていない。
前提の回答：DEC-434（電源投入で自動起動）。未回答の前提：DEC-435 の Q2〜Q5、DEC-104（スリープの抑止）。回答で前提が変わったら作り直す。

## 1. 今の起動（確認した事実、コミット 7f0c7ae）

- 起動は `bash gouda.sh start` の一つだけ（ND-01、DEC-090・091）。launch は利用者のシェルの子として、別のプロセスグループで動く。pid ファイル `gouda_data/run/gouda_core.pid`。
- `stop` は SIGINT をグループに送り、時間の上限なしに待つ（SIGTERM・SIGKILL は送らない。DEC-174）。
- 二重起動は pid ファイルと `/proc` の走査で拒む（G-DUP-START）。
- 起動直後のモード（`gouda_core/gouda_core/mode_core.py` の `decide_boot`）：記録なし・前回が手動走行なら手動走行（TR-01）。前回が自律走行・地図作成・一時停止なら一時停止で、自律走行は再び許可しない。再開には人の初期位置の指定が要る（TR-02、DEC-009）。

## 2. 案（推奨）

入口は `bash gouda.sh start / stop / status` のまま。中身を systemd の service にし、電源投入でも同じ service が起動する。起動のきっかけは二つになるが、動く中身（検査・DDS profile・launch）は一つ。

| 項目 | 案 | 理由 |
|---|---|---|
| unit の種類 | system unit `gouda.service`、`User=`・`Group=` は車載 PC の利用者 | ログインなしで電源投入から起動できる。user unit でも linger で可能だが、スリープの抑止（DEC-104）が取りやすいのは system 側（推測、未確認） |
| 入れ方 | `setup.sh` が unit を書いて `systemctl enable`（sudo はこのときだけ） | 一度で入る（setup.sh に集約） |
| ExecStart | gouda.sh の起動部分（前提の検査、DDS profile、`ros2 launch`）を前面で動かす内部の入口 | 検査と profile を通らない起動経路を作らない |
| 起動の順序 | `After=network-online.target`、`Wants=network-online.target` | LiDAR の有線 LAN と DDS の起動前にネットワークを待つ（待つ時間は既定のまま。実測で問題があれば別途） |
| 停止 | `KillSignal=SIGINT`、`KillMode=control-group`、`TimeoutStopSec=infinity`、`SendSIGKILL=no` | DEC-174（上限なし、強制停止なし）と同じ |
| 異常終了 | `Restart=no` | 今と同じ。自動の起こし直しは #46・#47 で別に判断 |
| 二重起動 | `systemctl is-active` で判定。今の `/proc` の走査は試験スタックや手で起動したものの検出に残す | systemd が一つしか起動しない |
| ログ | journal と `gouda_core.launch.log` の両方 | 今の場所を変えない |
| status | `systemctl` の状態と今の表示（data_root、monitor の URL、前回のモード） | 表示を減らさない |
| 環境 | unit の中で `/opt/ros/jazzy/setup.bash` とワークスペースの `install/setup.bash` を読む。`ROS_DOMAIN_ID` 等は今と同じ（環境変数の選択肢は増やさない。DEC-090） | 起動の仕方で ROS の環境が変わらないように |

PC の電源を切る・再起動するとき：systemd は SIGINT を送り、DEC-174 のとおり保存の終わりを待つ。ただし OS の停止の処理全体の待ち時間（`DefaultTimeoutStopSec` ではなく、shutdown の上限）との関係は未確認（Q5）。

## 3. 振る舞いの違い

- 電源を入れると、人の操作なしにセンサーのドライバ・vehicle_bridge・monitor が動く。ESP32 が繋がっていれば vehicle_bridge が接続する。
- 起動直後のモードは今と同じ（手動走行、または一時停止で自律走行は許可しない。§1）。gouda.sh は走行を要求しない（M-001 K2）。
- SSH が切れても Gouda は止まらない（今は SSH のシェルから起動した場合の挙動は確かめていない）。
- 再起動の後に前回のモードの記録が残っていれば、一時停止で起動する（TR-02）。これは今の `gouda.sh start` と同じ。
- IMU は、ドライバを止めて起こし直すと応答しなくなる（記録済みの不具合、USB の抜き差しで回復）。電源投入での起動は止める操作を含まないので影響は今と同じ（推測）。
- `gouda.sh stop` をしない限り、電源を入れるたびに起動する。止めたままにしたいとき（整備など）の手段が要る（Q4）。

影響を受けるID：ND-01、DEC-090、DEC-091、DEC-174、DEC-104、G-DUP-START、TR-01、TR-02、DEC-009。

## 4. 未回答の項目（DEC-435）

- Q1（実装の許可）：§2 の案で実装してよいか。
- Q2（目的）：自動起動で解決したいこと（人の操作を減らす、SSH が切れても止まらない、など）。目的によって、待つ条件（ネットワーク・センサー）や表示を変える。
- Q3（スリープの抑止 DEC-104）：一緒に入れるか。system service から `systemd-inhibit` を取れるかは VM で確かめる。
- Q4（自動起動を止める手段）：推奨は `gouda.sh` に新しい操作を足さず、`sudo systemctl disable gouda` を README に書く。代替：`gouda.sh stop` で次の電源投入の起動も止める（起動の振る舞いが gouda.sh の操作に依存する）。
- Q5（PC の停止との関係）：電源を切るとき、GLIM・rosbag の保存を終わるまで待つ（OS の停止が遅れる）か、上限を置くか。DEC-174 は gouda.sh stop の話で、OS の停止については決めていない。

## 5. 先行事例

- 探した場所と検索語：Web 検索「robot_upstart ROS 2 jazzy systemd launch」（2026-11-06）。
- robot_upstart（https://docs.ros.org/en/jazzy/p/robot_upstart/doc/index.html）：launch ファイルから systemd のジョブを作る。Jazzy の文書あり、1.0.4（2024-09-09）で ROS 2 の試験が通るようになった（changelog）。Clearpath が Jazzy の実機で使っている（https://docs.clearpathrobotics.com/docs/ros/config/overview）。ライセンス、`.launch.py` での使い方、apt での提供の有無は未確認。
  - 採否（案）：不採用。生成されるジョブは gouda.sh の前提の検査と DDS profile の生成を通らず、起動経路が二つになる。unit は 20 行ほどで書ける。unit の書き方（停止の信号、環境の読み込み）は robot_upstart の生成物を参考にする。
- systemd の標準の機能（`KillSignal`、`TimeoutStopSec=infinity`、`SendSIGKILL`、`network-online.target`）：採用。
- つくばチャレンジの他チームの事例：未調査。

## 6. 試験（実装の後、すべて未実行）

| 場所 | 確かめること |
|---|---|
| VM（試験用の別のワークスペース） | unit の起動・停止、SIGINT での停止、保存中の待ち（上限なし）、`gouda.sh status`、二重起動の拒否 |
| VM | 再起動の後に自動で起動し、前回の記録に応じて手動走行・一時停止になる |
| VM | system service から `systemd-inhibit` が取れるか（Q3） |
| x86 の車載 PC（人の協力。実車の PC での起動・停止は人の指示が要る） | 電源投入での起動、センサーが後から繋がったときの待ち、ESP32 の接続、電源を切るときの保存 |

## 7. 変える所（実装の許可の後）

`gouda.sh`、新しい unit のひな形、`setup.sh`、README の起動の節、正本 ND-01（変更セット）、gouda_core/test の起動の試験。
