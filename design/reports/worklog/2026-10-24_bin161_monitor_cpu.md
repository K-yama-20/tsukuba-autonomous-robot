# 第161便 作業記録：gouda_monitor の CPU 100 % の原因（調査だけ）

- 日付：2026-10-24
- 読んだコミット：1d7ee4663687a69ba101121964757405ff16cc00（作業ツリーに未コミットの変更あり）
- 人の指示（原文）：「gouda_monitorのCPU 100 %の原因を調べてください。」
- 変更：コード・設定・正本は変えていない。VM の Gouda は止めていない
- 証拠：`design/research/vehicle_pc/2026-10-24_monitor_cpu/`（results.txt、monitor_load_probe.py）

## 1. やったこと

- monitor_node・monitor_server・monitor_core を読んだ
- VM で、主の thread の CPU を /proc から測った（10 s で 83 %）
- perf・gdb・strace・py-spy は使えなかった（perf_event_paranoid 4、ptrace_scope 1、sudo なし）
- 代わりに、monitor と同じ購読（同じ topic・QoS・raw）だけをする別のプロセス（probe、何も publish しない）を 20 s ずつ動かし、executor の種類で CPU を比べた。probe は `~/claude_scratch` に置き、Gouda の DDS の設定で動かした
- SSE（`/api/events`）を curl で 10 s 受けて、送られる回数と量を数えた（10 s だけ、2 つめの接続を足した）

## 2. 原因（確認した事実と推測）

### 2.1 ESP32 の STATUS の 20 Hz が、そのまま画面の全体の更新 24 回/s になっている（事実）

- PRM-49（status_period_ms）は 50 ms（DEC-169 で 500 → 50 ms）。/esp32/status は 20 Hz で届く（probe で 20.0 msgs/s）
- `monitor_core.on_esp32` は受信のたびに `connection_revision` を上げる（`monitor_core.py:193`）。`monitor_node._on_esp32` は毎回 `server.notify` を呼ぶ
- SSE は revision が変わるたびに、画面の全体の snapshot を送る。snapshot を作るたびに、`maps/index.json` と routes の index をファイルから読み、JSON にする（`monitor_node._state`）
- 測った値：10 s で `event: state` 240 回（24 回/s）、1 回約 63 KB、約 1.5 MB/s
- 推測：この JSON の作成とファイルの読みが HTTP の thread で 24 回/s 走り、Python の GIL を executor と取り合う。ブラウザ（Isolated Web Co 27〜100 %）は、63 KB の JSON の解析と画面の描き直しを 24 回/s している

### 2.2 rclpy の MultiThreadedExecutor が、1 通ごとに重い（事実：probe での比較）

- monitor は `MultiThreadedExecutor(num_threads=4)`（`monitor_node.py:569`。HTTP の thread がサービスの結果を待つ間に future を進めるため）
- 同じ購読で比べた CPU（20 s）：

| 購読 | SingleThreadedExecutor | MultiThreadedExecutor(4) |
|---|---|---|
| IMU だけ（100 Hz） | 5 % | 65 % |
| monitor と同じもの（IMU 100・ESP32 20・LiDAR の frame 10・mode 5 Hz ほか） | 16 % | 69 % |

- IMU（100 Hz）は「届いているか・時刻」を表示するためだけに購読している
- 推測：monitor の 83 % のうち、7 割ほどはこの executor の手間、残りは 2.1 の snapshot と JSON（分けて測る手段がなく、内訳は未確定）
- 同じ MultiThreadedExecutor は mode_manager（3 thread）、global_localization（3）、map_creator（2）でも使っている。今の CPU は mode_manager 8 %ほど（03:4x の top）。global_localization の走行中の負荷は測っていない

## 3. 走行への影響（推測）

- VM の 6 コアのうち、monitor とブラウザで 1.5〜2 コアを使っている。第157便・第160便の、GLIM の遅れ（map→odom が古くなって Nav2 が止まる）と controller の 10 Hz（設定 20 Hz）の一因と考える。monitor を軽くしたときに走行中の遅れが減るかは未確認

## 4. 直す案（承認待ち。まだ DEC にしていない）

- M1（実装）：monitor の executor を SingleThreadedExecutor にする。HTTP の thread が待つサービスの future は、主の thread の spin で進むので、今の理由（future を進める）は単一の thread でも満たせる見込み（確かめが要る）。probe では 69 % → 16 %
- M2（設計・実装）：SSE の送る回数を抑える。案：(a) ESP32 の STATUS で表示が変わらないときは revision を上げない、(b) 送る間隔の上限を決める（新しい PRM。値は人が決める）、(c) 地図・routes の一覧は変わったときだけ送る
- M3（調査）：走行中に global_localization・mode_manager の CPU を測る（読むだけ）
- PRM-49（50 ms）そのものは変えない案を推奨（DEC-169 の人の指示の値。表示の側で間引けばよい）

## 5. 実行した検査・試験

- 試験・設計検査：未実行（コードの変更なし）
- 計測のコマンドと結果：`results.txt` のとおり（VM、03:3x〜03:4x）

## 6. 残るリスク

- 内訳（2.1 と 2.2）は分けて測れていない。M1 だけで足りるかは、直した後に測るまで分からない
- probe を動かした 80 s ほどと curl の 10 s は、VM の負荷を少し足した（走行はしていなかった）

## 7. 次に進められる作業／止まっている作業

- 進められる：M3（読むだけ）
- 止まっている：M1・M2 の実装（人の承認待ち）
