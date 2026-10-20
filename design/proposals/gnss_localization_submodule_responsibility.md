# gnss_localization_submodule の責務と非責務（提案 第1版。2026-10-19）

状態: **提案**（AI が新しく作った案）。承認済みの仕様ではない。正本（model.yaml）・生成物・人の drawio・Google スプレッドシートは変えていない。

## 0. 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`
- `design/docs/SystemArchitecture.drawio`（作業ツリーの版。人が編集中で未 commit）: セル `LHcLvlGkRA-CqYbzRrZq-2`「gnss_localization_submodule」（ROS_DOMAIN_ID = 99 の中）、その中にセル `805Qo-s3WLsUmU50dQsv-3`「MRTKLIB」。入る線は `LHcLvlGkRA-CqYbzRrZq-3`（Septentrio mosaic-go G5 P6 → gnss_localization_submodule）だけ。**出る線はない**。説明の文もない。
- Google スプレッドシート Gouda_architecture_detail（ID 1YsDMMmeVlaqwRGtAY7-fJNq4Pycb_bJa-KiKO9JsEwE）のシート「モジュール定義」を CSV で書き出して読んだ。最後の行が `gnss_localization_submodule`、Module_ID は空、実装場所 = PC、ほかの列はすべて空。M-007 Global_localization・M-008 local_odometry の行も読んだ（ローカルの `design/docs/Gouda_architecture_detail.xlsx` には gnss の行はない）。
- 正本: ND-19、ND-07、IFD-47〜50、G-GNSS-NO-HEADING、G-INIT-POSE-GNSS、DEC-124・130・131・133・135・137・139
- 提案: `gnss_initial_pose_design.md`（第3版）、`ntrip_gga_proposal.md`
- 調査: `research/gnss_mosaic_g5_dual_antenna_2026-10-19.md`
- VM の `~/MRTKLIB`（h-shiono/MRTKLIB、v0.7.11、`dd325d6`）の README と `mrtk --help`（読むだけ）

## 1. 前提として分かっていること（事実）

| 項目 | 内容 | 出典 |
|---|---|---|
| 受信機 | mosaic-go G5 P6、デュアルアンテナ。USB のシリアル 2 本（USB1 はドライバ、USB2 は空き）。今は単独測位だけ（約 6.4 m）、方位は出ない（副アンテナの観測がない）。第41便の照会では能力 Main+Aux1・方位の許可あり、frontend mode は Nominal。DualAnt にするかは DEC-144（回答待ち） | ND-19、G-GNSS-NO-HEADING、第41便の作業記録 |
| 既存のドライバ | septentrio_gnss_driver 1.4.8（ND-19）が IFD-47〜50 を出す。受信機の中の測位エンジンの結果（PVT・AttEuler）を ROS にする | ND-19 |
| 補正 | ネットワーク RTK（Point One、NTRIP）。受け方は DEC-139 が回答待ち（推奨 案 B1: PC の str2str が NTRIP と USB2 を中継） | DEC-139 |
| MRTKLIB | RTKLIB の改修版。`mrtk run`（rtkrcv＝リアルタイム測位）、`post`（後処理）、`relay`（str2str）、`convert`（RINEX へ）、`dump`。RTK・PPP・PPP-AR・CLAS PPP-RTK・MADOCA に対応 | VM の README |
| 承認済みの方針 | GNSS で初期位置を取り人が確認（DEC-124）。enu→map の static TF（DEC-131）。T3 の形の初期化で、条件は DEC-137（人の操作で開始、失敗は止めて表示、未収束でも警告だけ、人の指定を残す、対応のある地図だけ、PC 再起動後も同じ、方式によらない契約）。較正はソフトウェアで、実データで検証してから（DEC-135） | 判断台帳 |
| 保留 | 走行中の発散の監視と再初期化（T4、DEC-134） | 判断台帳 |

## 2. 位置づけの解釈（推測を含む）

- 名前の「submodule」と、Global_localization と同じ ROS の枠の中にあることから、**Global_localization（M-007）に初期位置と絶対位置の観測を渡す下位のモジュール**と読んだ（推測。drawio に出る線がないため）。
- 中に MRTKLIB があることから、**補正の中継・生データの記録・後処理の道具を持つ**と読んだ。MRTKLIB で位置そのものを計算するか（`mrtk run`）は描かれていない。→ Q-A

## 3. 責務（案）

1. **GNSS の測位結果を一つの「品質付きの絶対位置・方位」にまとめる**
   - ドライバの出力（IFD-47〜50）から、位置・方位・それぞれの品質区分（RTK fix／float／DGNSS／単独／なし、方位の有効・無効）・衛星数・共分散・補正の経過時間・観測時刻をまとめて出す。
   - 位置と方位は別々に品質を判定する（DEC-130 の仕様 T5 の考え方。今は方位が出ないため、位置だけ有効の状態がありうる）。
2. **座標の変換**
   - 主アンテナの位置をレバーアーム（TF の base_link→gnss_link）で base_link の位置にし、地図に GNSS との対応（DEC-135 の結果、manifest）があれば map 座標にする。対応がない地図では map 座標の値を出さない（DEC-137 の 7a）。
   - 方位の定義の変換（NED/ENU、取付 Yaw）。
3. **GNSS による初期化の手順（仕様 T3 の形、DEC-133・137）**
   - monitor から「GNSS で初期化」の要求を受けて始める。静止中の値を集めて平均し、初期姿勢と共分散を Global_localization に送り、Global_localization が返す収束の結果を受けて、成否と理由を出す。
   - 失敗したら止めて理由を出す（自動でやり直さない）。開始の可否は決めない（未収束でも警告の材料を出すだけ）。
4. **enu→map の static TF の発行の候補**（DEC-131。発行元は「選んだ地図を知る node」。ND-03 とどちらにするかは Q-D）
5. **ネットワーク RTK の補正の中継**（DEC-139 が案 B1 で承認された場合。MRTKLIB の `mrtk relay` で NTRIP → 受信機の USB2、受信機の GGA → NTRIP）。接続先・認証は人が置く非公開のファイルから読むだけ。
6. **後処理・診断の材料を残す**
   - 補正の接続の状態（接続中・切断・経過時間）を診断として出す。
   - 必要なら生データ（SBF）を残し、RINEX への変換・後処理（`mrtk convert`・`post`）で較正の検証（DEC-135）に使えるようにする（オフラインの道具として。走行中の判断には使わない）。
7. **自分の状態の公開**: 初期化中／有効／GNSS 不可／地図の対応なし、と最終更新時刻。heartbeat は出すが、**自律走行の必須の入力にはしない**（§5）。

## 4. 非責務・やらないこと（案）

| やらないこと | 理由・担当 |
|---|---|
| map→odom の推定・発行 | Global_localization（ND-07）だけが発行者。重複させない |
| odom→base_link、車体速度の推定 | local_odometry |
| 走行中の自己位置の書き換え・自動の再初期化 | T4 は保留（DEC-134）。誤った fix で位置がずれるのを防ぐ |
| 自律走行の開始・継続の許可、停止の判断・執行 | safety_supervisor・Safety_gate。GNSS の品質は警告の材料にとどめる（DEC-137 の 3b） |
| 受信機の設定の管理（出力の構成、Boot への保存） | ドライバ（ND-19、configure_rx、DEC-140） |
| シリアルの USB1 を開くこと | ドライバが専有。二重に開かない |
| 地図と GNSS の対応の計算（較正） | オフラインの道具（gnss_calibration.py、map_creator 側）。結果を読むだけ |
| 時刻の配布・センサーの同期 | PPS はハードウェア（mosaic → XT-32・IMU の線）。このモジュールは PC の時刻を使う |
| GNSS の値と他の推定の融合（EKF） | 仕様 T5（任意）。今回は対象外 |
| 画面の表示・人の操作の受付 | gouda_monitor。このモジュールは状態と結果を出すだけ |
| NTRIP の認証情報の保存 | 人が置く非公開のファイル。リポジトリ・ログに書かない |
| 地図作成の間の GNSS の記録 | 既に実装（DEC-126）。このモジュールを経由させるかは任意 |

## 5. 異常時の振る舞い（案）

- fix でない・古い・方位が無効: 品質区分で区別して出し、古い値を新しい時刻で出さない。「使えない」を有効な 0 にしない。
- GNSS が使えない・地図に対応がない: 「GNSS で初期化」を受け付けず理由を出す。人の指定（IFD-39）はそのまま使える。
- このモジュールが止まっても、自律走行の準備・走行は止めない（人の指定で代えられるため）。止まったことは表示する。
- 補正が切れた: RTK fix から落ちたことを品質で示すだけ。走行は止めない。

## 6. 安全上の注意（1.4・1.5 に従い明記）

- GNSS の誤った fix（マルチパス・float の誤判定）で、初期位置が別の場所になる危険がある。対策は人の確認（intent 体験 9、DEC-124）と、Global_localization の収束の確認。**このモジュールの品質区分を安全の根拠にしない**。
- 方位は今は出ない（G-GNSS-NO-HEADING。原因の候補は frontend mode、DEC-144）。方位なしで初期化するかは承認事項（Q-E）。

## 7. スプレッドシートの行の案（「モジュール定義」の列の順）

| 列 | 案 |
|---|---|
| Module_ID | M-039（推測。既存の最後が M-038。gouda_section_executor の行に ID がないため、番号の付け方は人が決める） |
| モジュール名 | gnss_localization_submodule |
| 機能ドメイン | localization |
| コンポーネント種別 | estimator（初期化の手順を持つため。processor でもよい） |
| 実装場所 | PC |
| 現状の実装/アルゴリズム | septentrio_gnss_driver 1.4.8（受信機内の測位）、MRTKLIB 0.7.11（補正の中継・後処理）。本体は未実装 |
| 進捗 | 未実装（ドライバの起動・記録は実装済み） |
| 使用モード | 自律走行（初期化）、事前地図作成（記録）。補正の中継は全モード |
| 責務 | GNSS の位置・方位を品質付きで map 座標の観測にまとめ、人の要求で GNSS による初期姿勢を Global_localization に渡し、収束の結果を返す |
| 主入力（要約） | ドライバの位置・品質・方位（IFD-47〜50）、TF（base_link→gnss_link）、選んだ地図の GNSS との対応（manifest）、初期化の要求、Global_localization の収束の結果、NTRIP の補正 |
| 主出力（要約） | 品質付きの GNSS の姿勢（map／ENU）、初期姿勢と共分散、初期化の成否と理由、enu→map の static TF（候補）、補正の接続の診断、状態・更新時刻 |
| 保持する状態 | 初期化の状態、集めたサンプル、選んだ地図の対応の版、補正の接続の状態 |
| 主要設定・パラメータ | 品質の閾値・サンプル数・静止の判定（tbd、DEC-137 の 5・6）、NTRIP の接続先（非公開のファイル） |
| 依存してよいもの | ドライバの topic、TF、地図の manifest、Global_localization の初期化の契約。mission・車両の通信に依存しない |
| 非責務・やらないこと | map→odom・odom→base_link の発行、走行中の自動の再初期化、走行許可・停止、受信機の設定、地図との対応の計算 |
| 異常時の振る舞い | fix なし・古い値・方位無効を区別して出す。使えないときは GNSS の初期化を拒否して理由を出す（人の指定は使える）。止まっても走行は止めない |
| Safety判断責務 | no |
| Safety執行責務 | no |
| 交換可能性・差替条件 | モジュール差替可（品質付きの姿勢と初期化の契約を満たすもの） |
| 起動・停止条件 | 全モードで起動してよい。初期化は自律走行の準備で人の要求のときだけ |
| 定義Status | 草案 |
| 備考 | 誤った fix による初期位置の誤りは人の確認と収束の確認で防ぐ。品質区分を安全の根拠にしない。方位は G-GNSS-NO-HEADING で未解決 |

## 8. drawio に足す線の案（人が編集）

- gnss_localization_submodule → Global_localization（初期姿勢、GNSS の姿勢の観測）
- Global_localization → gnss_localization_submodule（収束の結果）
- Map_Database → gnss_localization_submodule（地図と GNSS の対応）
- gnss_localization_submodule → gouda_logger、gouda_system_status（状態・診断）
- gouda_monitor → gnss_localization_submodule（「GNSS で初期化」の要求）
- septentrio_gnss_driver を描くなら、Septentrio → driver → submodule。USB2 ↔ MRTKLIB（補正・GGA）

## 9. 決めていただきたいこと

| ID | 質問 | 推奨と理由 | 代わりの案 | 決まらないと止まる作業 |
|---|---|---|---|---|
| Q-A | 位置を計算するのは受信機の中（ドライバ）か、MRTKLIB（`mrtk run`）か | **受信機の中**。デュアルアンテナの方位は受信機が出す。MRTKLIB は中継・記録・後処理に使う | MRTKLIB で RTK を計算（補正の受け方・方位の扱いを作り直す必要） | 品質区分の定義、補正の経路 |
| Q-B | このモジュールを Global_localization の下位（同じ process_group）とするか、独立のモジュールとするか | **下位**（名前と drawio の配置に合う。契約は ND-07 と分ける） | 独立のセンサー処理のモジュール | node の配置、起動の条件 |
| Q-C | GNSS の姿勢を map 座標で出すか、ENU だけで出すか | **両方**（map は対応がある地図だけ） | ENU だけ、変換は Global_localization | ND-07 との契約 |
| Q-D | enu→map の static TF の発行元 | **このモジュール**（地図の対応を読むのはここ） | ND-03 | DEC-131 の実装 |
| Q-E | 方位が使えないとき（DEC-144 で方位が出るようになった後も、遮蔽などで起こりうる）に、位置だけで初期化するか | **しない**（向きは人が指定。DEC-137 の 4 で人の指定を残す） | 位置は GNSS、向きは人 | 方位が出ない間の初期化 |
| Q-F | スプレッドシートに §7 の行を書き込んでよいか | 書く場合は「草案」のまま | 人が書く | なし |
