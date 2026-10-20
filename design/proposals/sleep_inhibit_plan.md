# 提案: Gouda の動作中にスリープを抑止する計画（DEC-104。第2版 2026-10-17）

状態: 提案（承認待ち）。
- 人の指示: 「個別に許可を出すので、許可無しで実装してはならない」（DEC-106）。「蓋が閉じた際のスリープの抑止（DEC-104）について検討せよ」（DEC-117）。承認まで実装しない。
- 前提の未回答: DEC-104、蓋の開閉の時刻（x86 機の journal）。

## 1. 目的と、分かっていること・分かっていないこと

目的: 地図作成・自律走行の最中に PC（x86 機、Dell G15 5515、Ubuntu 24.04）がサスペンドしないようにする。蓋を閉じても止まらないようにする。

分かっていること:
- 2026-10-14 の屋外の LiDAR の途切れ 3 回は、有線 LAN（enp2s0、r8169）のリンク断（Link is Down → 2〜3 s 後に Up）。サスペンドはしていない（FILE-X86-LIDAR-DROPOUT）。
- 夕方の途切れ 3 回（4.2・3.2・3.1 s）も、パケットがすべて欠けた形で同じ（FILE-EVENING-MAPS-ROSBAG）。カーネルのログは受け取っていない。
- Ubuntu 24.04（systemd 255）の既定（VM で確認。x86 機も同じ OS のため同じと推定、未確認）:
  - 蓋を閉じるとサスペンド（HandleLidSwitch=suspend。外部電源でも suspend）。
  - GNOME の自動サスペンド: AC では「しない」、電池では「操作がないまま 900 s（15 分）」（VM の設定）。
  - スリープ・蓋の動作の抑止（block）を利用者が取れるのは、画面の前のセッションだけ。SSH からは拒否される（VM で「Access denied」を確認）。

分かっていないこと:
- 蓋の開閉とリンク断の関係（x86 機の systemd-logind の journal に「Lid closed」の時刻が出る。§5 の確かめ方 1）。
- x86 機の電源の設定（GNOME の自動サスペンドの時間、logind の設定）。
- Gouda をどこから起動しているか（画面の端末か、SSH か）。

## 2. 危険の整理

| 場面 | 起きること | 今の Gouda |
|---|---|---|
| 地図作成・自律走行の最中に蓋を閉じる | サスペンド。LiDAR・IMU・ESP32 との通信が止まり、Gouda も止まる | 抑止しない |
| 電池で、キーボード・マウスに触れずに 15 分以上走る（自律走行では普通に起こる） | GNOME の自動サスペンド | 抑止しない |
| 蓋を閉じたときに BIOS・ハードウェアが LAN の省電力を変える | リンク断（推測。未確認） | 抑止では防げない |

自律走行の最中のサスペンドは、手動優先と PC の指令の途絶時の中立（ESP32。基本契約）で車体は中立になる。それでも、自律走行は止まり、記録も止まる（記録の欠落）。

## 3. 方式

### 案 A（推奨）: gouda.sh が動作中だけ抑止を取る

`bash gouda.sh start` が systemd の抑止（block）を取ったまま launch を動かす。

```
systemd-inhibit --what=sleep:idle:handle-lid-switch --who=Gouda --why="地図作成・自律走行中（センサーと LiDAR の LAN を止めない）" --mode=block \
  ros2 launch gouda_core gouda_core.launch.py params_dir:=... data_root:=...
```

- 抑止の寿命は launch と同じ。`gouda.sh stop` や異常終了で外れる（抑止を持つのはプロセスなので、残らない）。
- 効く範囲:
  - sleep の block により、logind はサスペンドの要求を拒む。GNOME の自動サスペンド（電池で 15 分）も logind への要求なので止まる（見込み。§5 の 3 で確かめる）。
  - handle-lid-switch の block により、蓋を閉じても logind はサスペンドしない。
- 取れない場合（SSH から起動したなど）は、抑止なしで起動を続け、`gouda.sh start` と `status` に「スリープの抑止: なし（理由）」と表示する。起動は止めない（地図作成を妨げないため）。
- 取れたかの確かめ方: `systemd-inhibit --list` に Gouda が出る。`gouda.sh status` にも出す。
- 変える所: `gouda.sh`（start・status）、README §2、正本 ND-01（変更セット）。起動のオプションは増やさない（DEC-090）。
- 二重起動の検出（untracked）は、systemd-inhibit のプロセスも同じ起動として数えるように直す（同じ起動が 2 行に出ないように）。
- 新しい設定値: なし。
- 利点: PC の使い勝手を変えない（Gouda が止まっていれば通常どおり蓋でサスペンドする）。sudo が要らない。
- 欠点: Gouda を画面の前のセッションから起動したときだけ効く。

### 案 B: PC の設定（人が行う。sudo が要る）

- `/etc/systemd/logind.conf.d/` に HandleLidSwitch=ignore・HandleLidSwitchExternalPower=ignore を置く。
- GNOME の電池での自動サスペンドを「しない」にする。
- 利点: 起動の仕方によらず効く。
- 欠点:
  - Gouda が止まっていても蓋でサスペンドしなくなる。鞄の中で動き続け、電池の消耗と発熱が起こりうる。
  - setup.sh で行うなら、PC 全体の設定の変更になる。

### 案 C: 有線 LAN の省電力の無効化

r8169 の PCIe の省電力（ASPM）が、リンク断の原因である場合に限る。原因の確認（§5 の 1・4）が先で、計画は別に出す。

### 運用（併用）

蓋を開けたまま走らせる。Gouda は画面の端末から起動する。monitor の SENSORS 表で点群の途切れを見る。

## 4. 推奨

- 案 A を実装する（承認の後）。
- 運用として、Gouda は x86 機の画面の端末から起動する（SSH からでは抑止を取れない）。
- 案 B は、§5 の確かめ方 3 で案 A が自動サスペンドを止められなかった場合の代わりとして残す。
- リンク断と蓋の関係は、x86 機の journal で確かめてから案 C を判断する。

## 5. 確かめ方（実装の前に人に依頼するもの・実装の後の試験）

1. 実装の前（人。x86 機）: 2026-10-14 の途切れの時刻と蓋の開閉の対応。
   - `journalctl -b -1 -u systemd-logind | grep -iE "lid|suspend"` など、その日の起動の範囲で。
   - `journalctl -k | grep -iE "enp2s0|r8169"`。
   - Wi-Fi・IP の行は、リポジトリに入れる前に除く。
2. 実装の前（人。x86 機）: 今の設定。
   - `gsettings get org.gnome.settings-daemon.plugins.power sleep-inactive-battery-timeout`
   - `gsettings get org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type`
   - `systemd-analyze cat-config systemd/logind.conf | grep -i lid`
3. 実装の後（人の協力。x86 機、電池）:

| 試験 | 確かめること |
|---|---|
| 抑止を取れない場合（SSH から起動） | 起動が続く。start・status に「抑止: なし」と出る |
| 抑止を取れる場合（画面の端末から起動） | `systemd-inhibit --list` に Gouda が出る。stop で消える |
| 蓋を閉じる | journal に「Lid closed」が出て、サスペンドしない。LiDAR の点群が途切れない（SENSORS 表、enp2s0 のリンク） |
| 電池でアイドル | 自動サスペンドの時間（例: 15 分）を過ぎてもサスペンドしない |
| Gouda を止めた後に蓋を閉じる | 通常どおりサスペンドする（PC の使い勝手が変わっていない） |

4. 蓋を閉じたときにリンクが切れるなら、抑止では防げない。案 C に進む（別の承認事項）。

## 6. 承認していただきたいこと

1. 案 A（gouda.sh が動作中だけ抑止を取る）を実装してよいか。
2. 抑止を取れないとき（SSH から起動）に、起動を止めず表示だけにすることでよいか。
3. §5 の 1・2 の確認（x86 機の journal と電源の設定）をお願いしたい。
