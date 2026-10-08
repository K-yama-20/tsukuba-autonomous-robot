# 車体出力段階: 手動優先と指令途絶時の中立化が成立する入力・時間値（DEC-049 の優先 1）

状態: 案（値は DEC-048 で承認済み。新 firmware・新 PC node での成立は未確認）。モデル: ND-11・ND-12・ND-17、IFD-15・16・17・40・43、PRM-08・09・13・14・21、TS-07・TS-13。

## 1. 指令の経路と各段の入力

```
Nav2 controller_server ──cmd_vel (IFD-15)──▶ gouda_motion_controller ──joystick_command (IFD-16)──▶ vehicle_bridge ──serial COMMAND (IFD-17)──▶ ESP32 firmware ──DAC──▶ EMC-270
gouda_mode_manager ──motion_hold (IFD-40)──▶ gouda_motion_controller
Bluetooth gamepad ──BT report──▶ ESP32 firmware（手動優先: RQ-I023）
```

## 2. 途絶の判定と中立化（どの入力を、誰が、いつ）

| # | 入力 | 判定する部品 | 期限 | 期限切れの動作 | 根拠 | 状態 |
|---|---|---|---|---|---|---|
| 1 | cmd_vel（Nav2→motion_controller） | gouda_motion_controller（ND-11） | **700 ms**（PRM-08） | 正規化操作値を中立にして発行を続ける | RQ-I063、intent.md:102、DEC-048 | 承認済み |
| 2 | motion_hold（mode_manager→motion_controller） | gouda_motion_controller | PRM-16（周期発行の期限。tbd） | hold 扱い＝中立 | DEC-004 | 値未確定 |
| 3 | joystick_command（motion_controller→bridge） | vehicle_bridge（ND-12） | PRM-09（tbd。PRM-08 より短く PRM-14 より長い） | 中立の COMMAND を送り続ける。古い指令を再送しない | M-015 P17 の方針 | 値未確定 |
| 4 | 有効な PC 指令フレーム（bridge→ESP32） | ESP32 firmware（ND-17） | **1 s**（PRM-13。最後の有効指令の受信から） | DAC を中立にする。リレー解除はしない（RQ-I077） | RQ-I068、intent.md:102、DEC-048 | 承認済み |
| 5 | Bluetooth ゲームパッド報告 | ESP32 firmware | **250 ms**（PRM-21） | 手動入力を無効にし中立。PC 指令の timeout とは別の既存動作で、firmware 書き直しを理由に撤去しない | RQ-I024、DEC-048 | 承認済み |
| 6 | （周期）bridge の送信 | vehicle_bridge | PRM-14（tbd。1 s に対し十分短い） | — | IF-028 K29 の方針 | 値未確定 |

順序: PC 側の中立化（700 ms）が ESP32 の watchdog（1 s）より先に効く。bridge は cmd_vel の有無に関係なく一定周期で送るため、PC が正常なら ESP32 の watchdog は作動しない。PC 全体が止まったときだけ 4 が効く。

## 3. 手動優先（RQ-I023）が成立する条件

- Bluetooth ゲームパッドの操作が有効（報告が 250 ms 以内）な間、ESP32 は PC 指令より手動を優先して DAC に出す（経路の確認は DEC-042）。
- 手動から PC 指令へ戻る条件（中立安定時間など）は新 firmware の設計（G-FIRMWARE）。既存 firmware の 200 ms（kNeutralResumeMs）は参考値。
- PC 側はこの切替を観測できない（S-05・ST-15 の方針を維持）。

## 4. 試験との対応

| 試験 | 確認すること |
|---|---|
| TS-07 | motion_hold=true／hold 途絶／cmd_vel 途絶 700 ms のいずれでも中立 |
| TS-13 | cmd_vel 停止後 700 ms で中立、bridge は PRM-14 周期で送信継続。ESP32 側の 1 s は PC 正常時に作動しない |
| （新 firmware 単体） | 有効指令の受信から 1 s で DAC 中立。BT 報告途絶 250 ms で手動入力無効。実装段階で TS を追加 |
