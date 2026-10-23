# 第113便：VM のセンサーの接続の確認と Parallels の設定の点検

日付：2026-10-21

## 読んだもの

- コミット `a27de9e`（main。PR #16 の merge）。VM の `~/gouda_ws` は a86a7d0（PR #16 の前）で、Gouda は人が起動したもの。

## 人の指示（原文）

- 「VMを最新版にした。センサ接続状況を確かめよ。parallelsの設定も詰めたい。本番走行中はclaude.appも閉じる」

## 確かめたこと（読むだけ。Gouda は止めていない）

- センサー（monitor の /api/state、lsusb、/dev/serial/by-id）

  | 機器 | USB | ドライバ | データ |
  |---|---|---|---|
  | IMU（STM32、ttyACM2） | VM に接続 | 起動 | 受信あり |
  | GNSS（Septentrio、ttyACM0・1） | VM に接続 | 起動 | /sensors/gnss/navsatfix は未受信。屋内で測位していない可能性（推測、未確認） |
  | ESP32（CP2102N、ttyUSB0） | VM に接続 | 手動走行では開かない（vehicle_bridge は地図作成・自律走行で使う） | 未受信（設計どおり） |
  | XT-32（USB-LAN AX88179B 経由） | VM に接続 | 起動していない（192.168.1.100 を持つ口がない） | 未受信 |

  - NTRIP の中継は、gnss_rtk.yaml がないため起動していない（RTK 補正なし）。
- USB-LAN が使えない原因
  - VM の起動（23:40）のとき、カーネルが「string descriptor read error -71」「cdc_ncm: failed GET_NTB_PARAMETERS」「bind() failure」を出した。そのため、ネットワークの口（enx6c6e0754b24a）ができていない。
  - 前の起動（23:35）では cdc_ncm が結び付き、口ができていた。
  - 起動の途中で USB を VM に渡すときの失敗とみられる（推測）。USB-LAN の付け直しで直る見込み（未確認）。
  - `ip route get 192.168.1.201` は enp0s5 経由になっている（今は 192.168.1.0/24 の経路がないため）。
- Parallels（`prlctl list -i`、`prlsrvctl usb list`）
  - CPU 6（Mac は 8）、メモリ 12 GB（Mac は 16 GB）。Pause idle は off。
  - Autostop は suspend、「On window close」も suspend。
  - 時刻の同期は on（60 s ごと、Smart mode off）。
  - カメラ（FaceTime・iPhone）の自動共有が on で、VM に渡っている。
  - USB の自動接続：AX88179B・STM32・Septentrio は guest。CP2102N（ESP32）は ask。
- Mac（`pmset -g`）
  - sleep 1 分（AC・電池とも）。今は「sleep prevented by Claude」で、Claude のアプリが眠りを止めている。
  - standby 1、powernap 1、displaysleep 60。

## 判断の材料（提案。設定は変えていない）

- Claude のアプリを閉じると、Mac は 1 分で眠り、VM と Gouda が止まる見込み。Mac の眠りの抑止は DEC-104（pending、`proposals/sleep_inhibit_plan.md`）。Mac の設定は人が変える。
- Parallels の案
  - 「On window close」を、続けて動かす設定にする（窓を閉じても VM が止まらない）。
  - CP2102N の自動接続を guest にする（付け直しのたびに問い合わせが出て、VM に渡らない間ができる）。
  - カメラの自動共有を off にする。
  - 時刻の同期の扱い（ROS の時刻が跳ぶ。memory にある既知の問題）は、実測の項目として判断待ち。

## 実行した検査・試験

- 上の確認（読むだけ）。設計検査・単体試験は未実行（コードと正本は変えていない）。

## 次の作業

- 人の作業：USB-LAN を付け直す（Parallels の「デバイス」→ USB で切断・接続、または抜き差し）。その後、XT-32 の受信を確かめる。
- 人の判断：Parallels の設定の案、DEC-104（Mac の眠り）。VM の `~/gouda_ws` を a27de9e にする（update.sh）。
