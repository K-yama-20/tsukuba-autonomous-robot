# DR-15 の許容の一覧の案（2026-10-21、第88便、DEC-188・DEC-189）

状態: 提案。DR-15 の許容の一覧（`design/tools/hardcode_allowlist.json`。今は空）に書く項目の案。一覧への追加は承認事項（DEC-175）なので、DEC-189 の回答の前には一覧へ書かない。

人の回答（分岐セッションからの転記、DEC-188）：「B6: A案を採用」（案 A＝時間の値の 8 項目を許容し、DR-15 の未判定 30 件を分類して一覧の案を作る）。

対象: コミット 8f50ef5 に REV-120 を適用した作業ツリー。`design/tools/hardcode_scan.py` の scan が出した 30 件で、`design/reports/design_check.txt` の DR-15 の行（未判定 30）と同じ。各行のコードは、走査器と同じ方法（コメントと文字列を除く）で取り直した。

注（第90便、REV-122 の後）：新しく承認した値と同じ数が増え、4・5・17〜19 番の 0.5 は PRM-62・PRM-72 とも、6 番の 0.1 は PRM-33・PRM-34 とも同じ数になった。行と数は同じで、偶然の一致の分類も変わらない。一覧の項目の照合（file・literal・line_contains）も変わらない。DR-15 の件数は 30 のまま。

## 分類の結果

| 分類 | 件数 |
|---|---|
| 時間の値（B6 の 8 項目。DEC-188 で許容の方針） | 9 |
| 偶然の一致 | 18 |
| PRM の写し（許容しない。DEC-190） | 1 |
| 8 項目にない値（DEC-189 で承認を求める） | 1 |
| 走査器の誤検出（DEC-189 で走査器の修正を提案） | 1 |

PRM の写しは 1 件（28 番、gouda.sh:119 の sleep 1＝PRM-77）。許容しない。扱いは DEC-190 で質問している。

## 30 件

| # | 場所 | 数 | 分類 | 理由 |
|---|---|---|---|---|
| 1 | `gouda_core/gouda_core/glim_runner.py:146` | 0.2 | 時間の値（B6 の 8 項目。DEC-188 で許容の方針） | GLIM の終了を待つ間の確認の間隔（2-6）。待ちの上限ではない（上限は PRM-37）。PRM-16 と同じ数は偶然 |
| 2 | `gouda_core/gouda_core/gnss_calibration.py:140` | 50 | 偶然の一致 | GNSS の較正（オフラインの道具）の最適化の反復回数の既定値。PRM-10 と同じ数は偶然 |
| 3 | `gouda_core/gouda_core/gnss_calibration.py:180` | 2 | 偶然の一致 | 格子の端を含めるための刻みの半分（割る 2）。変数名の delay に走査が反応した。時間の値ではない |
| 4 | `gouda_core/gouda_core/map_convert.py:143` | 0.5 | 偶然の一致 | 格子のセルの中心（0.5 セル）。PRM-42 と同じ数は偶然 |
| 5 | `gouda_core/gouda_core/map_convert.py:303` | 0.5 | 偶然の一致 | 割合の半分のしきい値（変換の内部の分類）。PRM-42 と同じ数は偶然 |
| 6 | `gouda_core/gouda_core/map_creator_node.py:79` | 0.1 | 偶然の一致 | 変換の進捗の割合（10 %）。PRM-14 と同じ数は偶然 |
| 7 | `gouda_core/gouda_core/mode_manager_node.py:57` | 50 | 偶然の一致 | DecisionEvent（IFD-28）の QoS の depth 50（DEC-072 の設計の値）。PRM-10 と同じ数は偶然 |
| 8 | `gouda_core/gouda_core/mode_manager_node.py:239` | 50 | 偶然の一致 | GNSS の記録の購読の QoS の depth。PRM-10 と同じ数は偶然 |
| 9 | `gouda_core/gouda_core/monitor_core.py:109` | 50 | 偶然の一致 | monitor のセンサーの受信の表示に使う履歴の数（表示だけ）。PRM-10 と同じ数は偶然 |
| 10 | `gouda_core/gouda_core/monitor_core.py:235` | 50 | 偶然の一致 | monitor の操作の履歴の表示の件数（表示だけ）。PRM-10 と同じ数は偶然 |
| 11 | `gouda_core/gouda_core/monitor_node.py:53` | 50 | 偶然の一致 | IFD-28 の QoS の depth 50（DEC-072）。PRM-10 と同じ数は偶然 |
| 12 | `gouda_core/gouda_core/monitor_server.py:63` | 5 | 時間の値（B6 の 8 項目。DEC-188 で許容の方針） | monitor の HTTP サーバの終了を待つ上限（2-7）。指令の経路・安全の期限に関わらない |
| 13 | `gouda_core/gouda_core/motion_controller_node.py:36` | 50 | 偶然の一致 | IFD-28 の QoS の depth 50（DEC-072）。PRM-10 と同じ数は偶然 |
| 14 | `gouda_core/gouda_core/recorder_node.py:34` | 50 | 偶然の一致 | IFD-28 の QoS の depth 50（DEC-072）。PRM-10 と同じ数は偶然 |
| 15 | `gouda_core/gouda_core/sensor_supervisor_node.py:47` | 50 | 偶然の一致 | IFD-28 の QoS の depth 50（DEC-072）。PRM-10 と同じ数は偶然 |
| 16 | `gouda_core/gouda_core/septentrio_query.py:86` | 0.01 | 時間の値（B6 の 8 項目。DEC-188 で許容の方針） | 受信機への問い合わせの道具（septentrio_query）の読み取りの間隔（2-8）。Gouda の走行では使わない |
| 17 | `gouda_core/gouda_core/speed_mask.py:66` | 0.5 | 偶然の一致 | 格子のセルの中心（0.5 セル）。PRM-42 と同じ数は偶然 |
| 18 | `gouda_core/gouda_core/speed_mask.py:67` | 0.5 | 偶然の一致 | 格子のセルの中心（0.5 セル）。PRM-42 と同じ数は偶然 |
| 19 | `gouda_core/gouda_core/speed_mask.py:76` | 0.5 | 偶然の一致 | 刻みへの丸めの判定（半分の刻み）。PRM-42 と同じ数は偶然 |
| 20 | `gouda_core/gouda_core/static_tf_node.py:33` | 50 | 偶然の一致 | IFD-28 の QoS の depth 50（DEC-072）。PRM-10 と同じ数は偶然 |
| 21 | `gouda_core/gouda_core/vehicle_bridge_node.py:43` | 50 | 偶然の一致 | IFD-28 の QoS の depth 50（DEC-072）。PRM-10 と同じ数は偶然 |
| 22 | `gouda_core/gouda_core/vehicle_bridge_node.py:97` | 0.05 | 時間の値（B6 の 8 項目。DEC-188 で許容の方針） | シリアルの読み取りの待ち（2-2）。読み取りのスレッドが停止の要求に気づく間隔で、指令の送信（PRM-14）・中立化（PRM-09・PRM-13）に関わらない。PRM-41 と同じ数は偶然 |
| 23 | `gouda_core/gouda_core/vehicle_bridge_node.py:167` | 1 | 時間の値（B6 の 8 項目。DEC-188 で許容の方針） | シリアルの読み取りのスレッドの終了を待つ上限（2-4）。ポートを閉じるときだけ |
| 24 | `firmware/gouda_esp32_v4/src/main.cpp:20` | 5 | 時間の値（B6 の 8 項目。DEC-188 で許容の方針） | firmware の Core::tick を呼ぶ間隔（2-11）。時間切れの値はすべて設定（PRM-13・21 など）から来る。下の注を参照 |
| 25 | `firmware/gouda_esp32_v4/src/main.cpp:98` | 1 | 時間の値（B6 の 8 項目。DEC-188 で許容の方針） | firmware の loop の 1 ms の休み（2-12） |
| 26 | `gouda.sh:101` | 1 | 時間の値（B6 の 8 項目。DEC-188 で許容の方針） | gouda.sh start が monitor の URL を待つ回数 20 と間隔 1 s（2-9）。起動の表示だけで、走行に関わらない |
| 27 | `gouda.sh:101` | 20 | 時間の値（B6 の 8 項目。DEC-188 で許容の方針） | 同上（20 回） |
| 28 | `gouda.sh:119` | 1 | PRM の写し（許容しない。DEC-190） | PRM-77（gouda.sh stop の進捗の表示の間隔 1 s）の値を手で書き写したもの |
| 29 | `setup.sh:53` | 3 | 8 項目にない値（DEC-189 で承認を求める） | setup.sh が配布物を落とすときの再試行の回数（インストールの道具）。Gouda の起動・走行には関わらない |
| 30 | `setup.sh:148` | 50 | 走査器の誤検出（DEC-189 で走査器の修正を提案） | setup.sh の "$(python3 -c '...PRM-50...')" の中の文字列。シェルの文字列の取り除き方（ダブルクォートの中のシングルクォート）の誤りで、文字列の中の PRM-50 の 50 を拾った |

注（24 番、firmware の 5 ms）：分岐セッションの説明では、8 項目は「どれも指令の経路・安全の期限に関わらない」とした。ただし 5 ms は、firmware が出力を決める処理（Core::tick）を呼ぶ間隔で、出力の経路の上にある。時間切れの判定（PRM-13 の 1.0 s、PRM-21 の 0.25 s）は設定の値を使い、5 ms はその刻み（判定が最大 5 ms 遅れうる）。人の回答（DEC-188）で許容の方針は決まっているが、この性質を承認の材料として書いておく。

## 許容の一覧に書く項目の案（28 件、DEC-189 の承認の後に書く）

1〜27 番と 29 番。line_contains は、走査器が取り出したコードの行に含まれる文字列。

```json
{
 "entries": [
  {
   "file": "gouda_core/gouda_core/glim_runner.py",
   "line_contains": "time.sleep(0.2)",
   "literal": "0.2",
   "reason": "GLIM の終了を待つ間の確認の間隔（2-6）。待ちの上限ではない（上限は PRM-37）。PRM-16 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/gnss_calibration.py",
   "line_contains": "max_iter:int=50",
   "literal": "50",
   "reason": "GNSS の較正（オフラインの道具）の最適化の反復回数の既定値。PRM-10 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/gnss_calibration.py",
   "line_contains": "s.delay_step_s/2",
   "literal": "2",
   "reason": "格子の端を含めるための刻みの半分（割る 2）。変数名の delay に走査が反応した。時間の値ではない",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/map_convert.py",
   "line_contains": "self.cell-0.5",
   "literal": "0.5",
   "reason": "格子のセルの中心（0.5 セル）。PRM-42 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/map_convert.py",
   "line_contains": "(t<=0.5)",
   "literal": "0.5",
   "reason": "割合の半分のしきい値（変換の内部の分類）。PRM-42 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/map_creator_node.py",
   "line_contains": "feedback(,0.1)",
   "literal": "0.1",
   "reason": "変換の進捗の割合（10 %）。PRM-14 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/mode_manager_node.py",
   "line_contains": "DECISION_QOS=QoSProfile(",
   "literal": "50",
   "reason": "DecisionEvent（IFD-28）の QoS の depth 50（DEC-072 の設計の値）。PRM-10 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/mode_manager_node.py",
   "line_contains": "qos=Q(reliability=ReliabilityPolicy.RELIABLE,durability=DurabilityPolicy.VOLATILE",
   "literal": "50",
   "reason": "GNSS の記録の購読の QoS の depth。PRM-10 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/monitor_core.py",
   "line_contains": "history:int=50",
   "literal": "50",
   "reason": "monitor のセンサーの受信の表示に使う履歴の数（表示だけ）。PRM-10 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/monitor_core.py",
   "line_contains": "self.command_log[-50:]",
   "literal": "50",
   "reason": "monitor の操作の履歴の表示の件数（表示だけ）。PRM-10 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/monitor_node.py",
   "line_contains": "DECISION_QOS=QoSProfile(",
   "literal": "50",
   "reason": "IFD-28 の QoS の depth 50（DEC-072）。PRM-10 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/monitor_server.py",
   "line_contains": "self._thread.join(timeout=5)",
   "literal": "5",
   "reason": "monitor の HTTP サーバの終了を待つ上限（2-7）。指令の経路・安全の期限に関わらない",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/motion_controller_node.py",
   "line_contains": "DECISION_QOS=QoSProfile(",
   "literal": "50",
   "reason": "IFD-28 の QoS の depth 50（DEC-072）。PRM-10 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/recorder_node.py",
   "line_contains": "DECISION_QOS=QoSProfile(",
   "literal": "50",
   "reason": "IFD-28 の QoS の depth 50（DEC-072）。PRM-10 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/sensor_supervisor_node.py",
   "line_contains": "DECISION_QOS=QoSProfile(",
   "literal": "50",
   "reason": "IFD-28 の QoS の depth 50（DEC-072）。PRM-10 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/septentrio_query.py",
   "line_contains": "time.sleep(0.01)",
   "literal": "0.01",
   "reason": "受信機への問い合わせの道具（septentrio_query）の読み取りの間隔（2-8）。Gouda の走行では使わない",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/speed_mask.py",
   "line_contains": "(np.arange(W)+0.5)",
   "literal": "0.5",
   "reason": "格子のセルの中心（0.5 セル）。PRM-42 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/speed_mask.py",
   "line_contains": "(np.arange(H)+0.5)",
   "literal": "0.5",
   "reason": "格子のセルの中心（0.5 セル）。PRM-42 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/speed_mask.py",
   "line_contains": "step_mps-q)>0.5",
   "literal": "0.5",
   "reason": "刻みへの丸めの判定（半分の刻み）。PRM-42 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/static_tf_node.py",
   "line_contains": "DECISION_QOS=QoSProfile(",
   "literal": "50",
   "reason": "IFD-28 の QoS の depth 50（DEC-072）。PRM-10 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/vehicle_bridge_node.py",
   "line_contains": "DECISION_QOS=QoSProfile(",
   "literal": "50",
   "reason": "IFD-28 の QoS の depth 50（DEC-072）。PRM-10 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/vehicle_bridge_node.py",
   "line_contains": "timeout=0.05,exclusive=True",
   "literal": "0.05",
   "reason": "シリアルの読み取りの待ち（2-2）。読み取りのスレッドが停止の要求に気づく間隔で、指令の送信（PRM-14）・中立化（PRM-09・PRM-13）に関わらない。PRM-41 と同じ数は偶然",
   "decision": "DEC-189"
  },
  {
   "file": "gouda_core/gouda_core/vehicle_bridge_node.py",
   "line_contains": "self.thread.join(timeout=1)",
   "literal": "1",
   "reason": "シリアルの読み取りのスレッドの終了を待つ上限（2-4）。ポートを閉じるときだけ",
   "decision": "DEC-189"
  },
  {
   "file": "firmware/gouda_esp32_v4/src/main.cpp",
   "line_contains": "kControlPeriodMs = 5",
   "literal": "5",
   "reason": "firmware の Core::tick を呼ぶ間隔（2-11）。時間切れの値はすべて設定（PRM-13・21 など）から来る。下の注を参照",
   "decision": "DEC-189"
  },
  {
   "file": "firmware/gouda_esp32_v4/src/main.cpp",
   "line_contains": "delay(1);",
   "literal": "1",
   "reason": "firmware の loop の 1 ms の休み（2-12）",
   "decision": "DEC-189"
  },
  {
   "file": "gouda.sh",
   "line_contains": "seq 1 20",
   "literal": "1",
   "reason": "gouda.sh start が monitor の URL を待つ回数 20 と間隔 1 s（2-9）。起動の表示だけで、走行に関わらない",
   "decision": "DEC-189"
  },
  {
   "file": "gouda.sh",
   "line_contains": "seq 1 20",
   "literal": "20",
   "reason": "同上（20 回）",
   "decision": "DEC-189"
  },
  {
   "file": "setup.sh",
   "line_contains": "--retry 3",
   "literal": "3",
   "reason": "setup.sh が配布物を落とすときの再試行の回数（インストールの道具）。Gouda の起動・走行には関わらない",
   "decision": "DEC-189"
  }
 ]
}
```

## 走査器の修正の案（30 番）

- `_shell_code_lines` は、ダブルクォートの文字列を先に消す。そのため、`"$(python3 -c '... "PRM-50" ...')"` のようにダブルクォートの中にシングルクォートがあると、文字列の境目を取り違える。その結果、文字列の中の `PRM-50` の 50 が、コードの数として残る。
- 案：シェルの行を左から 1 文字ずつ読み、引用の入れ子（`$(...)` の中の引用）を追って文字列を消す。修正の後は、30 番は出なくなる見込み（試していない）。走査器のコードの変更なので、DEC-189 の承認の後に行う。
