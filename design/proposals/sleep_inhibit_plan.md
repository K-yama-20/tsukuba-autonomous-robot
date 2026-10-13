# 提案: Gouda の動作中にスリープを抑止する計画（DEC-104）

状態: 提案（承認待ち）。人の指示「個別に許可を出すので、許可無しで実装してはならない」（DEC-106）により、承認まで実装しない。前提の未回答の項目: DEC-104、蓋の開閉の時刻（journal）。

## 1. 目的と、分かっていること

- 目的: 地図作成・自律走行の最中に、PC がスリープ（サスペンド）しないようにする。蓋を閉じても止まらないようにする。
- 2026-10-14 の屋外の途切れは、有線 LAN（enp2s0）のリンク断。サスペンドはしていない（FILE-X86-LIDAR-DROPOUT）。下の既定と抑止の可否は FILE-GROUND-PLAN-CHECK の (3)。蓋の開閉との一致は未確認（journal の「Lid closed」の時刻と比べる必要がある）。
- Ubuntu 24.04（systemd 255）の既定（VM で確認。x86 機も同じ OS のため同じと推定、未確認）:
  - 蓋を閉じるとサスペンド（HandleLidSwitch=suspend、外部電源でも suspend）。
  - GNOME の自動サスペンドは、AC では「しない」、電池では「操作がないまま 900 s（15 分）でする」（VM の設定）。屋外は電池で動くため、地図作成の途中でもサスペンドしうる。
  - 利用者がスリープ・蓋の動作の抑止（block）を取れるのは、画面の前のセッション（active・inactive）だけ。SSH からは拒否される（VM で「Access denied」を確認）。
- 抑止で防げるもの: OS が行うサスペンド（蓋・アイドル・電源ボタン以外）。
- 防げないもの: 蓋の開閉で BIOS・ハードウェアが行う処理。リンク断の原因がこちらなら、抑止では止まらない。

## 2. 方式（案 A。推奨）

`bash gouda.sh start` が、systemd の抑止を取ったまま launch を動かす。

```
systemd-inhibit --what=sleep:idle:handle-lid-switch --who=Gouda --why="地図作成・自律走行中（センサーと LiDAR の LAN を止めない）" --mode=block \
  ros2 launch gouda_core gouda_core.launch.py params_dir:=... data_root:=...
```

- 抑止は launch と同じ寿命。`gouda.sh stop` で launch が終われば外れる。Gouda が異常終了しても外れる（抑止を持つのはプロセスなので、残らない）。
- 抑止を取れない場合（SSH から起動したなど）は、抑止なしで起動を続け、`gouda.sh start` と `status` に「スリープの抑止: なし（理由）」と表示する。起動は止めない（地図作成を妨げないため）。
- 取れたかどうかの確かめ方: `systemd-inhibit --list` に Gouda が出る。`gouda.sh status` にも出す。
- 変える所:
  - `gouda.sh`（start・status）。起動のオプションは増やさない（DEC-090）。
  - 二重起動の検出（untracked）を、systemd-inhibit のプロセスも同じプロセスグループとして数えるように直す（同じ起動が 2 行に出ないように）。
  - README §2、`design/model.yaml` の ND-01（変更セット）。
- 新しい設定値: なし。

## 3. 試験

| 試験 | 場所 | 確かめること |
|---|---|---|
| 抑止を取れない場合 | VM（SSH） | 起動が続く。start・status に「抑止: なし」と出る |
| 抑止を取れる場合 | x86 機の画面の端末（人の協力） | `systemd-inhibit --list` に Gouda が出る。stop で消える |
| 蓋を閉じる | x86 機（人の協力） | journal に「Lid closed」が出て、サスペンドしない |
| 蓋とリンク断 | x86 機（人の協力） | 蓋を閉じたときの enp2s0 の Link is Down の有無 |
| アイドル | x86 機、電池（人の協力） | 自動サスペンドの時間を過ぎてもサスペンドしない |

蓋を閉じてもリンクが切れるなら、抑止では防げない。その場合は §4 の案に進む（別の承認事項）。

## 4. ほかの案（併用・代替）

- **案 B: PC の設定**（setup.sh が確認して表示。変えるのは人。sudo が要る）
  - `/etc/systemd/logind.conf.d/` に HandleLidSwitch=ignore・HandleLidSwitchExternalPower=ignore を置く。
  - GNOME の電池での自動サスペンドを「しない」にする。
  - Gouda が動いていない時も効く（PC の使い勝手が変わる）。
- **案 C: 有線 LAN の省電力の無効化**: r8169 の PCIe 省電力（ASPM）がリンク断の原因である場合に限る。原因の確認が先で、計画は別に出す。
- **運用**: 蓋を開けたまま走らせる。monitor の SENSORS 表で点群の途切れを見る。

## 5. 承認していただきたいこと

1. 案 A（gouda.sh が動作中だけ抑止を取る）を実装してよいか。
2. 抑止を取れないときに、起動を止めず表示だけにすることでよいか。
