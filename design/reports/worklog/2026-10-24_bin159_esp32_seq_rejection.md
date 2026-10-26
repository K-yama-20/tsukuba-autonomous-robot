# 第159便 作業記録：再び車両が動かなかった原因（ESP32 が PC の指令をすべて棄却）と、DAC の勾配の確認（読むだけ）

- 日付：2026-10-24
- 読んだコミット：1d7ee4663687a69ba101121964757405ff16cc00（作業ツリーに未コミットの変更あり：REV-180・181 ほか）
- 人の発言（原文）：「また失敗した。何故車両が動かないのかな。まさか電圧を急に2500→4000のように急激に挙げたりはしてないよね？勾配をつけろと言ったはずだが。」
- 変更：コード・設定・正本は変えていない。VM の Gouda・ESP32 には触れていない

## 1. 対象

- VM の記録 `records/20261024_031034`（03:10 の自律走行、03:13 の地図作成、03:17 の自律走行）と `records/20261024_031914`（03:19 の自律走行）
- 証拠：`design/research/vehicle_pc/2026-10-24_esp32_seq_rejection/decision_timeline_031034_031914.txt`（DecisionEvent と mode/state の変化。NTRIP の情報がないことを grep で確かめた）
- ESP32 の今の STATUS（03:2x に `ros2 topic echo --once /esp32/status`）：source=none、reason=pc_stale、boot_token=0x9a1148b7、last_pc_seq=1643、uptime_ms=2850271

## 2. 原因（確認した事実）

1. ESP32 は、PC からの COMMAND を **すべて棄却** していた。`pc_frame_rejected`（arg 5）が 1210 回（03:10 に 259、03:11 に 272、03:17 に 35、03:19 に 460、03:20 に 184）。`pc_enabled` は 1 回も出ていない
2. arg 5 は「seq が前より新しくない」（`firmware/gouda_esp32_v4/include/gouda_v4/control.hpp:179`）。firmware は、同じ起動（boot_token）の間、最後に受け付けた seq（last_pc_seq）を覚えていて、それより大きい seq だけを受け付ける（`protocol.hpp:49`、`design/docs/esp32_protocol_v4.md` の「送信側ごとに厳密増加」）
3. bridge（ND-12）は、プロセスの起動ごとに seq を 1 から数え直す（`gouda_core/gouda_core/vehicle_core.py:70・90`）。HELLO の後に、ESP32 の last_pc_seq から続けることはしていない
4. ESP32 は 02:35 ごろから再起動していない（esp_ms 2134362 at 03:10:34、uptime 2850 s at 03:2x）。VM は 02:56 ごろに再起動され、Gouda は 03:06 に起動し直された（第158便の反映）。前の Gouda が送った最後の seq は 1643 で、新しい Gouda の seq はまだそれを超えていない（送ったのは自律走行が有効な間だけ。棄却 1210 回と HELLO・SET_CONFIG の数とつじつまが合う）
5. そのため、ESP32 は PC の出力を一度も使わず（source=none）、DAC は中立のまま。Nav2 と motion controller は drive を出していた（03:10:53、03:19:37 の output_drive）が、車体には届いていない

- DEC-391（中立を先に送る）の順序は記録どおり動いていた（03:17:19 に vehicle_output_active が odometry_started より先、直後に x 0・y 0・flags 1 の COMMAND）。ただ、その中立も棄却されていた
- 分類（1.6）：**実装**（bridge が、ESP32 の起動が同じまま PC 側だけが再起動した場合の seq の続け方を持っていない）。プロトコルの文書にもこの場合の決めがないので、**設計** の不足でもある
- 今回これが表に出た理由（推測）：これまでは Gouda の再起動のときに ESP32 も USB の差し直しなどで再起動していた（boot_token が変わると seq の記憶も消える）。今回は VM だけが再起動した

## 3. 電圧を急に上げていないか（人の質問）

- この 4 回の走行では、ESP32 が PC の指令を受け付けていないので、**PC からの電圧の変化は 1 度も出ていない**（DAC は中立 2500 mV のまま）。03:13〜03:14 の manual_override はゲームパッドの操作
- 今の作りの勾配（確認した事実）：
  - PC 側は Nav2 の velocity_smoother（OPEN_LOOP、20 Hz）が速度の変化を制限する。前進の加速度の上限 PRM-68＝1.2 m/s²、旋回の角加速度の上限 PRM-73＝2.0 rad/s²（DEC-192）
  - motion controller は cmd_vel を比例で正規化する（最高速 PRM-39＝1.25 m/s、PRM-40＝0.97 rad/s）。ESP32 は正規化した値を中立 2500 mV・半径 2220 mV（PRM-43〜46）で DAC に書く。ESP32 にも motion controller にも勾配の処理はない
  - 換算（計算）：前進は 1.2÷1.25×2220 ≒ 2130 mV/s。速度上限 0.5 m/s の区間なら 2500 → 約 3390 mV まで約 0.42 s。旋回は 2.0÷0.97×2220 ≒ 4580 mV/s（0 から最大まで約 0.49 s）
  - 勾配がない所：止める側（motion_hold・cmd_vel の途絶・自律走行の終了）は中立へ即座に戻す（安全側の作り）。/config の最小出力の補償（compensation）を使うと、0 からいきなり最小値に跳ぶ（今回は compensation_revision 0 で未使用）
- 「勾配をつけろ」という指示は、判断台帳（model.yaml の decisions）・intent.md・作業記録・firmware を「勾配」「ランプ」などで探したが見つからなかった（別のチャットで出て、記録されていない可能性）。DAC の電圧の変化の速さそのものを決めた値（mV/s など）は今はない

## 4. 承認・確認の候補（まだ DEC にしていない）

- F（実装、2）：bridge が HELLO_REPLY の後に STATUS（GET_STATUS）の last_pc_seq を読み、その次の値から seq を数える。推奨（PC 側だけで直る、firmware の書き込みが要らない）。代替：firmware で HELLO を受けたら seq の記憶を消す（書き込みが要る）、ESP32 を毎回 USB で再起動する（運用で補う）
- G（設計）：ESP32 が PC を有効にした（pc_enabled）ことを motion_hold を解く条件にする。今回のように指令が棄却されている間は走り出さず、理由を monitor に出す。`pc_frame_rejected` が続いたら monitor に知らせる
- H（承認・実測）：DAC の電圧の勾配の決め方。今の velocity_smoother の上限（2130 mV/s・4580 mV/s 相当）で足りるか、ESP32 側にも mV/s の上限を置くか。値は実測が要る

## 5. 今すぐの回避（人の作業。AI は行っていない）

- ESP32 を USB の差し直しで再起動すれば、boot_token が変わり seq の記憶も消えるので、次の自律走行では受け付けるはず（推測、未確認）

## 6. 実行した検査・試験

- 試験・設計検査：未実行（記録の読み取りだけ）
- コマンド（VM で読むだけ）：records の events.jsonl の集計（python）、`ros2 topic echo --once /esp32/status`（Gouda の DDS の設定で）、nav2_params.yaml と launch log の grep

## 7. 残るリスク

- F を直すまで、Gouda だけを再起動すると、同じことがまた起きる
- 今の bridge の seq が 1643 を超えた所で、走行の途中から急に受け付けが始まる。そのときも ESP32 は中立の COMMAND が来るまで PC を有効にしないので、急に動き出すことはないと考える（firmware の 183 行。推測を含む）

## 8. 次に進められる作業／止まっている作業

- 止まっている：F・G・H の実装（人の承認待ち、DEC-106）
