# 現状の要約（status.md）

最終更新：2026-10-17（REV-059、第30便）。

**引き継ぎ: `reports/handover_2026-10-17.md`**（次のチャットの最初に貼るプロンプトは §0。次の作業は Global_localization または Navigation のノードの実装の検討と報告。前回の引き継ぎは `handover_2026-10-14.md`）。

**第30便: recorder の rosbag の再開と GLIM の異常終了の検出を修正（実装。人の許可 DEC-117）、スリープの抑止の計画 第2版、intent 第11版**（作業記録 `reports/worklog/2026-10-17_rev058_059_recorder_glim_fix.md`）。
- 人の連絡（DEC-117）: Septentrio mosaic-go G5 P6（デュアルアンテナ、ネットワーク RTK）を搭載。DEC-115 は保留。最新版を x86 に反映し、二重起動の防止は正常。
- recorder（G-REC-ROSBAG-RESTART）: 開始ごとに `rosbag/bag_NN` に書く。子プロセスの予期しない終了を失敗として record/status・session.json・ログに残し、monitor がポップアップで示す。
- GLIM（G-GLIM-EXIT）: 地図作成中の GLIM の予期しない終了を DecisionEvent glim_exited（TR-14 の検出と表示だけ）で記録し、monitor がポップアップで示す。モードは保ち、再起動しない。
- 試験: Mac の単体 134 件 OK・1 件 skip。VM の試験スタックで rosbag の再開・強制終了、GLIM の強制終了・通常終了が合格（FILE-RECORDER-GLIM-FIX-VM-TEST）。x86 機は未確認（反映は人）。
- スリープの抑止（DEC-104）: 計画を第2版にした（電池での自動サスペンド、抑止の効く範囲、x86 機での確かめ方）。推奨は案 A のまま。
- intent 第11版（DEC-118、人の編集）: 体験 9 の初期位置は GNSS で取得し人が確認する。人が指定する前提の設計への影響を G-INIT-POSE-GNSS（未解決）に一覧した。設計は変えていない。
- 全検査は終了コード 1（原因は人が編集中の drawio だけ。設計整合性は違反 0）。commit はしていない。

**第29便: 自己位置推定の方式の検証（案 A と案 A3）**（作業記録 `reports/worklog/2026-10-17_rev056_057_localization_verification.md`、記録 `research/vehicle_pc/2026-10-17_localization_eval/`）。実装なし（DEC-106）。
- 人の回答（DEC-114）: A と A3 を重点的に検証、VM の使用を許可、合格基準は AI の案（95 % 点 0.3 m 以内、発散なし、0.5 m 超で不良）、次の実機試験も同じ場所を 2 回。
- 検証（VM、同じ走行の地図で楽観的）:
  - 走行全体の誤差の 95 % 点: A 0.124 m、A3 0.209 m（どちらも基準内）。
  - 初期姿勢が 5 m・90 度ずれると、A は誤った姿勢を「正常」として出し続けた（524 回中 510 回）。A3 は Monte Carlo の初期姿勢の探索ですぐ戻った。A3 は走行全体で 0.5 m 超を 1 回見逃した。
  - 処理は A3 の方が軽い（33 ms 対 55 ms、メモリ 205 MB 対 1.37 GB）。
- 承認待ち:
  - DEC-115: 第一候補を A3 に変える（最終は次の実機試験のデータで別の走行の地図での評価の後）。あわせて 0.5 m 超の見逃しの対策と、次の実機試験の段取り。
  - DEC-116: VM の試験の環境に Fast DDS の共有メモリの設定（G-DDS の対策）。
- G-DDS の原因を裏付けた: VM の中で約 2 MB の点群が DDS で落ちる。共有メモリの区画を大きくすると等倍でも 200/200 届いた。
- 別の走行の地図での評価は、今のデータに重なる走行がなくできない（173522 と 175857 は別の場所、181044 は rosbag なし）。

**第28便: 自己位置推定の方式の選定（提案）**（作業記録 `reports/worklog/2026-10-17_rev051_localization_selection.md`、提案 `proposals/localization_selection.md`）。
- 人の指示（DEC-109、原文）: map_creator の改良を一旦置き、自己位置推定の方式の選定に進む。DEC-107・DEC-098 は保留（未回答のまま）。
- 地面の推定の要否: 3D 照合方式なら、自己位置推定には要らない。Nav2 の 2D 地図は経路の高さ基準の帯で足りる見込み。2D 方式なら地図全体で要る。
- 推奨: 案 A（3D 照合）。odom は GLIM を odometry だけで、map→odom は lidar_localization_ros2（NDT_OMP）。比較に案 B（Nav2 AMCL）。
- 人の指示（DEC-110）で Cartographer を案 C として検討した。自身の地図でしか自己位置推定できず（地図作成も置き換え）、上流の保守は終了、品質の出力なし、点の時刻の形式が合わない。第一候補にしない（評価に加えるかは人の判断）。
- 人の指示（DEC-111）で LeGO-LOAM と Autoware の ndt_matching を検討した。どちらも ROS 1 だけのため外した。後継の Autoware Core の NDT（ndt_scan_matcher ＋ ekf_localizer）を案 A3 として評価に加えることを推奨（品質の出力が最も豊富。中継の node が二つ要り、依存が重い）。
- 人の回答（DEC-112）: KISS-ICP は以前の評価試験で目標性能を出せなかったため外す。案 A・A3・B のみを検討。rosbag は VM に移さない。提案を第2版に書き直した（3 案に共通の GLIM の odometry の設計、要求との照合の表、VM を使わない評価の計画）。推奨は第一候補 A、A3・B と比べて決める。
- **intent.md 第10版**（人の編集、機械比較で検出。DEC-113、AR-010）: 82 行に「OSSとして公開されており使用実績の豊富なものについては、Nav2に追加しても良い。」が加わった（RQ-I057 → RQ-I083、照合 C-026）。提案の承認事項 2 を、案 A・A3 がこれに当たるかの判断に変えた。
- 承認待ち（提案 §9 の 6 点）: 第一候補 A で A3・B と比べて決める進め方、intent の「Nav2 に機能を持たせ」の読み、実際のパッケージを動かす評価の場所（rosbag は VM に移さない）、合格の基準、同じ経路の 2 回の走行、実装時に要る独自の小さな node の承認の扱い。実装なし（DEC-106）。
- 全検査は終了コード 1。原因は、人が編集中の移行の原資料 `design/docs/SystemArchitecture.drawio` の SHA の不一致だけ（3 件の不合格がすべてこれ。設計整合性は違反 0）。drawio の扱いは人の判断。

**第27便: 夕方の x86 機の原図 3 件・rosbag 2 本の解析**（作業記録 `reports/worklog/2026-10-14_evening_maps_rosbag_analysis.md`、出力 `research/vehicle_pc/2026-10-14_evening_maps_rosbag.txt`）。実装・設定・正本の変更なし（DEC-106）。
- 原図の判定:
  - 173522・175857 は同じ場所の高さが一致（差の中央値 0.04 m）。175857 は出発点から 0.35 m で終了。
  - 地図全体が出発時の向きの左へ 2〜4 度傾く（未判定）。181044 は片道で rosbag なし。
- 地図の傾き（G-MAP-TILT）: rosbag の IMU の重力と LiDAR の地面から、IMU が LiDAR に対して約 2 度、左側が上がっている（走行中の平均からの参考値）。GLIM の T_lidar_imu は回転なし。地図の傾きの向きと合う。オフラインの GLIM での確認は VM 待ち。値の設定は人（RQ-I081）、DEC-105 の実測は残る。
- LiDAR の途切れ（G-LIDAR-DROPOUT）が夕方に 3 回再発（4.2・3.2・3.1 s、パケット全欠損）。リンク断かは x86 機のカーネルのログ待ち。
- recorder の不具合の疑い（実装）: 同じセッションで rosbag を再開すると同じ出力先に書こうとして黙って失敗し、181044 の rosbag が失われた（VM での再現は未実行）。
- 175310 の失敗: GLIM が gtsam の例外で異常終了。間隔 1 ms 未満の LiDAR の frame があり、二重起動に似る（x86 機は二重起動の防止の前の build）。mode_manager は異常終了に気づかなかった（TR-14 は未実装）。
- DEC-107 の根拠の数値（屋外の山 47 %、下の外れた点 0.6 %）は補正前の odometry で求めていた。取り直しが要る。
- 修正方針の候補（承認事項。判断台帳には未登録）: (1) IMU と LiDAR の回転、(2) LAN のリンク断、(3) recorder、(4) GLIM の異常終了の検出・表示、(5) 二重起動の防止を x86 機へ、(6) 地面の推定。
- 人への依頼: x86 機のログ（カーネル・logind・~/.ros/log）、3 件の経路、VM の起動と rosbag の写し。

前便（第26便）までの要約は以下。

**実機の地図作成の試験（廊下、二往復）**（作業記録 `reports/worklog/2026-10-14_rev045_field_mapping_judgement.md`）。
- 1 回目: 不合格。Gouda が 2 つ同時に動いていた（G-DUP-START）。
- 2 回目: 原図（3D）は往復で整合（区間の長さの差 2 m 以内、壁の差 0.15 m 以内）。
  - 廊下の向きに 4.15 度の一様な傾きがある（廊下が水平かを人に確認）。
  - 床より下の反射と推定される点（12 %）で地面の推定が下がり、2D 変換は不合格（G-FLOOR-REFLECTION。地面の推定の修正が次の作業）。
  - ゴミ箱は未判定（位置を人に確認）。
  - GLIM の処理周期 4.37 Hz。rosbag は未記録。
- x86 機の地図作成 2 件（REV-047）。
  - 廊下: 原図は整合。GLIM は 10.00 Hz を欠けなく処理し、出発点から 0.27 m で終了、壁が一致。
  - 廊下の不合格点: 4.40 度の傾きがあり、床の反射で 2D 変換は不合格。
  - 屋外: LiDAR の frame が 3 回、約 3 s 途切れ（G-LIDAR-DROPOUT）、約 9 m ずれた。同じ場所の高さが 1.8 m 違い、原図は不合格。
  - VM での処理周期の低さは VM に固有と見られる（G-DDS）。
- 人の回答（DEC-103）: 廊下は水平（傾きは誤差: G-MAP-TILT）、屋外は出発点に戻った（終点のずれは誤差）、使用環境は屋外、二重起動の防止を許可。
- 二重起動の防止を実装（gouda.sh の拒否、supervisor の device_in_use）。VM で試験合格。センサーありの試験は未実行。
- LiDAR の途切れ: 3 回とも有線 LAN（enp2s0）のリンク断と同じ秒。サスペンドはなし。蓋の開閉は journal で確認待ち。
- 承認待ち: DEC-104（スリープの抑止。計画 `design/proposals/sleep_inhibit_plan.md`）、DEC-107（地面の推定の修正。人の方針 DEC-108 に基づく設計 `design/proposals/ground_estimation_design.md`。承認は 4 点を個別に）。人の指示（DEC-106）により、個別の許可まで実装しない。
- 実測待ち: DEC-105（IMU と LiDAR の間の傾き。水平な床で静止して Record）。
- 人の作業: 蓋の開閉の時刻の確認（journal）、次の試験で Record を押す。

前便（第25便）: **設計のブランチを人が main に merge した**（PR #8）。README を現行の実装に合わせて書き換え、PC のセットアップと更新のスクリプトを用意した（ブランチ `docs/pc-setup-2026-10-14`。main への merge は人）。
- 初回: `bash setup.sh`（何度実行してもよい。足りないときだけ sudo）。更新: `bash gouda.sh stop` → `bash update.sh`（main へ fast-forward してから setup.sh）→ `bash gouda.sh start`。
- ドライバの commit は `third_party/drivers.repos` の 1 か所。ドライバは改変しない（DEC-075）。
- VM の別のワークスペースで setup.sh・update.sh を確認。何も入っていない PC での apt・PPA・接続の追加の部分は未試験。
- 承認待ち: DEC-101（旧実装のファイルの扱い）。作業記録 `reports/worklog/2026-10-14_rev044_readme_setup_update.md`。

前便（第24便）: **gouda_monitor に「地図」タブを新設**（intent.md 第9版 106 行目、DEC-092）。
- 原図を選び、変換設定を入力して再変換できる。変換のたびに新しい rev ができる。
- 人の回答: 高さの基準は地面（DEC-093）、今は GLIM を変えず移動して作った原図で密度を測る（DEC-096 C）、段差・坂の地図は確認用（DEC-097 A、条件付き承認。条件は確認中）。
- 変換を、点群から推定した地面からの高さで判定する方式にした（PRM-62〜64 を新設）。
- 1 つの rev として次を作る（DEC-095）。地図タブで切り替えて見られる。
  - 2D 占有格子（Nav2）
  - 3D 点群地図（PCD）
  - 表示用の傾き・段差・高さの図（走行には使わない）
- 確認: VM の試験スタック（実機の原図の写し）と DEMO。
- 暫定の推奨値は承認待ち（DEC-098）。実車の設定では既定値の欄は空で、値を入れれば再変換できる。
- これまでの原図はすべて静止して作られていた。地面の見え方（DEC-099）と点の密度・GLIM の処理周期（DEC-100）は、移動しての地図作成の実機試験（TS-34、手順 `docs/map_conversion.md` §5、解析 `map_inspect`）で測る。
- 作業記録 `reports/worklog/2026-10-14_rev039_040_map_tab.md`。

前便（第23便）: 起動経路を一つにした（`bash gouda.sh start` だけ、環境変数なし。DEC-090・DEC-091）。IMU 100 Hz、LiDAR 600 rpm を確定（REV-036〜038）。

前便（第22便）: センサーの受信表示と再接続時のドライバ作り直し（REV-034・035）。

前便（第21便）: GLIM の開始を VM で検証し、gouda.sh・mode_manager などの不具合を修正（REV-032・033）。

前便（第20便）: IMU デバイス名と XT-32 の時刻（PC 受信時刻）を確定、センサドライバの起動を実装（REV-031）。

前便（第19便）: XT-32 の IP・宛先・ポートと IMU の名前を宣言（REV-030）。

前便（第18便）: **工程5-5（車体出力）を実装し、Ubuntu の ROS 2 Jazzy 上で stub 試験合格（PC 側と firmware 中核の卓上 stub。ESP32 実機・車体なし）**。作業記録 `reports/worklog/2026-10-10_rev027_stage5-5.md`。次は DEC-076 の順序どおり、5-3 のセンサー有り試験 → 5-5 の実車試験（いずれも人のハード接続・判断が必要。着手前にセンサー・車体・ESP32 の接続状況を人に確認する）。実車向け firmware の書き込みは DEC-077（DAC 電圧の初期値）の回答待ち。

工程5-5 の内容: IFD-40 の独自型 `gouda_interfaces/msg/MotionHold` を確定、PC–ESP32 プロトコル v4 を設計（`docs/esp32_protocol_v4.md`、G-FIRMWARE）、ND-11 `gouda_motion_controller`・ND-12 `vehicle_bridge`（lifecycle node）、ND-17 新 firmware `firmware/gouda_esp32_v4`（PlatformIO、Bluepad32、MCP4922、NVS 設定）、mode_manager の `control/motion_hold` 発行、monitor の `/esp32/status` 表示。設定は generated/params から読み、未確定値は trial ファイル（stub 専用）。完了条件 (a) 手動優先 (b) 入力途絶時の中立化 (c) 一時停止中の中立出力 は、firmware 中核のホスト試験と PC 側の stub 試験で確認（実機・実車では未確認）。

前便まで: 工程5-1〜5-4 はソフト試験合格（5-3・5-4 はセンサーなし・合成データの範囲）。ゲート3は条件付き承認（DEC-064・065）。intent.md は第7版（`f69dd98b…`）。GLIM 1.2.2-0noble（DEC-062）。試験環境は Parallels の Ubuntu 24.04（`ssh -o BatchMode=yes aya@10.211.55.4`、`~/gouda_ws`。DEC-067）。firmware のビルド環境は Mac の PlatformIO（`~/.platformio/penv/bin/pio`）。

## 三つの状態（CLAUDE.md 1.4）＋報告用の三区分（DEC-057）

- 移行が正確：作業ツリーでは**違反 1 件**（2026-10-17、REV-059 適用後）。人が編集中の移行の原資料 `design/docs/SystemArchitecture.drawio` の SHA-256 が baseline と違う（`reports/input_integrity.json`）。それ以外の原資料・抽出結果・baseline は一致。REV-050 の時点（コミット 6950a1a）では合格。drawio の扱い（新版として記録するか、変更を戻すか）は人の判断。
- 設計検査に合格：**未判定**。設計整合性 17 ルール 違反 0・未判定 4（DR-04 5 件、DR-05 2 件: RQ-I027・RQ-I072 は問題／衝突のみで対応、DR-10 2 件: 版照合、DR-11: 未確定値 59）。検査違反 0 件は未判定の解消でも実車適合の証明でもない。
- ソフト試験合格：**工程5-1〜5-5 が合格**（5-5: TS-07・TS-13・TS-19 PC 側・TS-12・TS-30 を Ubuntu で、TS-17・18・19・29 を firmware 中核のホスト試験と Python 模擬で。FILE-VEHICLE-PC-STAGE55）。5-3・5-4 はセンサーなし、5-5 は ESP32 実機・ゲームパッド・車体なしの範囲。TS-01〜06・08〜11・14〜16・20〜22 は未実行。
- 実車検証済み／実車投入可能：**人の判断待ち**。実車試験は未実施。承認済みの実車値は PRM-07・08・13・21 の 4 件のみ。DAC 電圧（PRM-43〜46）は未確定で、実車向け firmware ビルドには入っていない（DEC-077）。DEC-050 の実機照合は未実施。

## 検査結果の件数（`design/.venv/bin/python design/tools/run_checks.py`、REV-059 適用後の作業ツリーで終了コード 1。原因は人が編集中の drawio だけ。下の表は REV-050 の時点の値で、違う所を注記した）

| 検査 | 合格 | 違反 | 未判定 |
|---|---|---|---|
| 入力の完全性（原資料・抽出・baseline・intent の SHA-256） | 75 件一致 | 1（design/docs/SystemArchitecture.drawio。人が編集中） | 0 |
| 形式・移行忠実性 | 全件 | 0 | 0 |
| intent 版間の同一性 | 13（12 一致、1 記録済み置換） | 0 | 0 |
| 設定の生成（generate_params → generated/params/。firmware_config.trial.yaml を追加） | 生成 | 0 | 0 |
| 設計整合性（17 ルール） | 13 | 0 | 4（DR-04 5、DR-05 2、DR-10 2、DR-11 59） |
| 検査器の試験 | 68 | 0 | 0 |
| gouda_core 単体試験（Mac・VM、caf4ee8） | 129（Mac では 1 件 skip、VM ではすべて実行） | 0 | 0 |
| firmware 中核ホスト試験（g++、仮値ヘッダ。TS-17・18・19・29 の卓上 stub） | 274 checks | 0 | 0（実機未実行） |
| firmware ビルド（esp32dev・esp32dev_trial） | 2 | 0 | 0（書き込み未実施） |
| 工程5-1〜5-5 の ROS 上の試験（Ubuntu） | 合格 | 0 | 0（センサー・ESP32・実車は未接続） |
| ソフト試験（TS-01〜34） | 12（TS-07・12・13・17・18・19・23〜28・29・30 のうち stub 範囲） | 0 | 22（未実行または一部のみ。TS-31〜33 は一部を VM で実行: 作業記録。TS-34 は 1 回目が条件の外で不合格、2 回目は原図は整合・2D 変換は不合格（G-FLOOR-REFLECTION）） |
| 判断台帳 | 116 件（DEC-109〜DEC-114・DEC-117・DEC-118 を recorded、DEC-115・DEC-116 を pending で追加。pending 16: DEC-021・022・024・050・077・078・079・098・099・100・101・104・105・107・115・116） | | |

## 承認待ち・実測待ち・人の作業・提案

- **承認待ち（第25便、REV-044）**: DEC-101 旧実装のファイル（scripts/、gouda_gui/ など、third_party/external.repos、patches/）の扱い。推奨: 案 A（旧 scripts/setup.sh を止まるようにし、残りは 5-6 の設計で再利用の有無を確かめてから整理）。止まる作業: なし。
- 人の作業（VM）: 古い NetworkManager の接続 gouda-hesai 2 つ（enp0s5 に 192.168.1.100）の削除の判断、時刻同期の有効化（`sudo timedatectl set-ntp true`）。
- **承認待ち・実測（第24便、REV-042）**:
  - DEC-098 地図の変換の暫定の推奨値（PRM-33 0.1 m、PRM-34 0.1 m、PRM-35 0.15 m、PRM-36 1.2 m、PRM-38 1、PRM-62 0.5 m、PRM-63 10 度、PRM-64 1.0 m。高さは地面から）。推奨: 承認。止まる作業: 実車の設定での自動変換と地図タブの既定値。
  - DEC-097 の「条件付き承認」の条件の内容（回答に記載なし。確認中）。
  - 実測 DEC-099（XT-32 で地面が映るか）、DEC-100（移動して作った原図の点の密度、GLIM の処理周期・CPU 負荷・保存時間）。実機試験 TS-34 で測る（人の協力: 移動しての地図作成）。
  - 回答済み: DEC-093（高さの基準は地面）、DEC-094（B）→ DEC-096（C: 測ってから決める）、DEC-095（3D 点群地図と段差・坂の地図も作る）、DEC-097（A、条件付き）。
- **承認待ち（第18便、REV-027 で登録）**:
  - DEC-077 新 firmware の DAC 電圧の初期登録値（旧 firmware 記載の要求値 2500／230／4700／4700 mV を Q-03 実測までの初期値として承認するか）。推奨: 承認。止まる作業: 実車向け firmware の書き込み。
  - DEC-078 基本契約 5 件の stub 試験を 5-5 の完了条件に含める案（`docs/implementation_stages.md` §5）。推奨: 含める。
  - DEC-079 手動仲裁の既存値の維持（deadzone 8 %、中立安定 200 ms）。推奨: 維持。
  - 人の確認対象: プロトコル v4 で旧 v3 と異なる振る舞い（`docs/esp32_protocol_v4.md` §7。BT 途絶で PC 指令源を無効化しない等）。
- 前便からの回答待ち: intent 同一性チェッカーが記録済み置換を合格扱いにする変更の可否、122 件の design_status の扱い（推奨: 変えない）、旧 scripts の統合、rosbag の対象 topic（後工程）。
- 実測待ち: `generated/measurement_plan.md`（PRM-09・14・15・16・39〜49 を含む。承認済みの PRM-08・13 は除外済み）。PRM-16 は 5-6 の前に決める必要あり（motion_hold の期限切れ判定 PRM-42 が周期発行を前提とするため）。
- 実機照合待ち: DEC-050（配線・firmware・操作結果）、DEC-024（Q-09）。技術調査: DEC-021（Q-02）、DEC-022（Q-03）。
- 提案（承認済み仕様ではない）: `proposals/undetectable_faults_r2.md`、`proposals/intent_edit_requests.md` §2、`docs/git_management_plan.md`。

## 原本未照合

- 実車PC の Nav2 はパッケージ版（1.3.13）で照合。バイナリ内の IDL は直接読んでいない。
- 実機 ESP32 の配線・現在の firmware（DEC-050 未実施）。CLAUDE.md の先頭 1〜17 行の欠落は推測のまま。
- 前回分: 公式ページからリンクされた PDF、未読の図版。

## 次の作業

- DEC-076 の順序: (1) 工程5-3 の流れをセンサー有りで試験（実データで原図→変換。TS-27 の未確認項目）。センサー接続状況を人に確認してから。(2) 工程5-5 の実車試験（人の判断・協力。先に DEC-077・079 の回答→`esp32dev` ビルドに DAC 値→書き込み→卓上で TS-17〜19 の実機確認→DEC-050 の実機照合）。
- 地図: DEC-098 の承認後に暫定値を設定へ反映。移動しての地図作成の実機試験（TS-34）の解析と記録（DEC-099・DEC-100）。
- 点群の配送の欠落（G-DDS）の調査: GLIM が受け取る周期の測定、Fast DDS の共有メモリ転送の容量・受信バッファの比較（上流は改変しない）。
- 並行して進められる基盤作業: PRM-16 の扱いの整理（承認事項）、Nav2 の cmd_vel 型（PRM-12）の決定に備えた ND-11 の TwistStamped 対応、5-6 の設計。
- 止まっている: 実車の設定での自動変換と地図タブの既定値（DEC-098）、実車向け firmware の書き込み（DEC-077）、実車試験、DEC-050。

## 主要ファイルの場所（CLAUDE.md 1.9 の対応表。パスはリポジトリ `tsukuba-autonomous-robot/` 相対）

| 役割 | 場所 | 備考 |
|---|---|---|
| 設計意図（人が所有） | `design/intent.md` | 第11版（SHA a7a03a31…、106 行。82 行: DEC-113、14 行: DEC-118 を人が編集）。旧版は `baselines/migration_v1/intent.md`、`baselines/intent_history/` |
| 正本（YAML） | `design/model.yaml`、`design/schema.json`（1.1） | 変更は `revisions/REV-xxx.yaml` → `tools/apply_revision.py`。最新 REV-059。次は REV-060、DEC-119 |
| 正本（Markdown） | `design/docs/` | `map_conversion.md`（地図の変換と地図作成の実機試験の手順）、`sensor_supervision.md`、`implementation_stages.md`、`esp32_protocol_v4.md`（5-5 のプロトコルと firmware の振る舞い）、`vehicle_output_timing.md`、`speed_filter_design.md`、`regulations_2026.md`、`git_management_plan.md` |
| 判断台帳 | `model.yaml: decisions`（DEC-001〜118） | ビュー: `generated/pending_classification.md`、`conflicts.yaml`、`intent_open_items.yaml`、`generated/human_decisions_r2.md` |
| ゲート3 承認の対象 | `design/baselines/gate3_2026-10-09/` | 最終承認はコミット f208066 |
| 検査器・ルール一覧・試験 | `tools/validate_model.py`、`tools/check_design.py`、`rules/` | `rules/README.md` |
| スクリプト | `tools/` | `run_checks.py`、`render_views.py`、`generate_params.py`（trial ファイルも生成）、`apply_revision.py` |
| 生成物（手編集禁止） | `generated/`（`params/` に node 別設定と `*.trial.yaml`、`firmware_config.yaml`・`.trial.yaml`）、`conflicts.yaml`、`intent_*.yaml`、`reports/*.json` | firmware のビルド時ヘッダ `firmware/gouda_esp32_v4/include/gouda_v4/build_config.hpp` はビルド時に生成（コミットしない） |
| 提案 | `proposals/` | 承認済み仕様として使わない。最新: `sleep_inhibit_plan.md`（DEC-104）、`ground_estimation_design.md`（DEC-107。`ground_estimation_plan.md` を置き換え） |
| 調査・証拠 | `research/` | `vehicle_pc/`（工程 5-1〜5-5 の試験記録、夕方の解析 `2026-10-14_evening_*`）、`joystick270_firmware/`、`upstream_jazzy/` |
| 報告・作業記録 | `reports/`、`reports/worklog/` | 最新 `2026-10-17_rev058_059_recorder_glim_fix.md`（その前 `2026-10-17_rev056_057_localization_verification.md`、 `2026-10-17_rev051_localization_selection.md`、`2026-10-14_evening_maps_rosbag_analysis.md`）。引き継ぎ `reports/handover_2026-10-17.md`（前回 `handover_2026-10-14.md`） |
| ロボット実装（新） | `gouda_interfaces/`（SoftwareMode・DecisionEvent・MotionHold・StartAutonomy・ConvertMap）、`gouda_core/`（recorder・mode_manager・monitor（地図タブの入力検査 map_tab.py）・map_creator（変換 map_convert.py、解析 map_inspect.py）・sensor_supervisor・motion_controller・vehicle_bridge、esp32_protocol・esp32_sim、web/、test/ に Ubuntu 試験 script）、`gouda.sh`（start／stop／status のみ、環境変数なし）、`setup.sh`（PC のセットアップ）、`update.sh`（main への更新）、`third_party/drivers.repos`（ドライバの commit）、試験用 `gouda_core/test/stack.sh` | 工程5-1〜5-5 |
| firmware（新） | `firmware/gouda_esp32_v4/` | `include/gouda_v4/{protocol,config,control}.hpp`、`src/main.cpp`、`tools/gen_build_config.py`、`test/host/`。旧 `firmware/gouda_esp32`・`gouda_dualsense_usb` は置き換え対象 |
