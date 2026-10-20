# septentrio_gnss_driver 1.4.8 のソースの確認（2026-10-19。手順 1: シリアルの開き方、configure_rx が書くストリーム、Boot への保存）

- 読んだもの: https://github.com/septentrio-gnss/septentrio_gnss_driver の tag v1.4.8（commit 5613af2969e3f4aac4ddc0b819e773d43a71ce9b）を AI の作業領域に clone して読んだ（build・実行はしていない）。VM に入っている apt の版は ros-jazzy-septentrio-gnss-driver 1.4.8-2noble.20260916.090359。apt の build が同じ tag のソースからかは**原本未照合**（版の番号だけ一致）。なお connect() のログは「This is ROSaic driver version 1.4.7」と出す（communication_core.cpp 189 行付近。文字列の更新漏れと推測）。
- Boost は VM の /usr/include/boost（BOOST_VERSION 108300）を読んだ。
- 行番号は上の commit のもの。

## 1. シリアルの開き方

| 項目 | 事実 | 場所 |
|---|---|---|
| 端末の設定 | Boost.Asio の serial_port::open が tcgetattr のあと `cfmakeraw`（_DEFAULT_SOURCE のとき。そうでなければ ICANON・ECHO・ECHONL・ISIG・IEXTEN・ICRNL・IXON・OPOST などを外す）、IGNPAR・CREAD・CLOCAL を付けて tcsetattr | /usr/include/boost/asio/detail/impl/posix_serial_port_service.ipp の open() |
| 8N1・フロー制御 | ドライバが baud・パリティなし・8 bit・stop 1 を設定。`serial.hw_flow_control` が "RTS|CTS" でなければ flow_control::none（IXON・IXOFF・CRTSCTS を外す） | include/septentrio_gnss_driver/communication/io.hpp 416〜434 行 |
| 低遅延 | ioctl TIOCSSERIAL で ASYNC_LOW_LATENCY | io.hpp 437〜441 行 |
| baud | 現在値から目標（gnss.yaml の serial.baudrate 921600）へ段階的に変える。USB の CDC-ACM では意味を持たない（推測） | io.hpp 444〜 |
| 開けないとき | 1 秒ごとに開き直す（無期限） | io.hpp 390〜411 行 |

結論: ドライバがポートを開けば raw・エコー無効になる（人の資料 §2 の条件を満たす）。ただし Boost が設定するのはドライバのファイル記述子を開いた時で、ほかのプログラム（診断の cat など）が同じポートを別の設定で開くと条件は崩れる（資料 §7）。

## 2. 接続の最初に送るもの

- `resetMainConnection()`: エスケープの列 `\rSSSSSSSSSS\r\r` を 3 回送り、受信機の応答のプロンプトから接続先の名前（USB1 など）を得る（communication_core.cpp 1056〜1070 行）。configure_rx が false でも送る（configureRx() の冒頭で必ず呼ぶ。302 行）。

## 3. configure_rx が true のときに受信機へ書くもの（configureRx()、communication_core.cpp 286 行〜）

| 順 | コマンド | 意味 | 人の資料との関係 |
|---|---|---|---|
| 1 | `sso, all, none, none, off` と `sno, all, none, none, off`（331〜332 行） | **受信機のすべての SBF・NMEA の出力のストリームを止める**（どの接続先のものも） | 人が調査で設定した Stream4（USB1/Support/sec1）も止まる。資料 §5「変更前に gso を取得し、既存用途を上書きしない」に反する |
| 2 | `grc`、`sntp, on`（template の ntp_server: true）、`sgd`（datum）、`sao, Main/Aux1`（gnss の種類）、`sga, MultiAntenna`、`sto, <heading>, <pitch>` | 受信機の能力の照会、NTP の server を有効、測地系、アンテナ、マルチアンテナ、主→副の方位・仰角のオフセット | `sto` の値は get_spatial_config_from_tf のとき TF から（§4） |
| 3 | `sso, Stream1..n, <主接続先>, <SBF blocks>, <周期>` | ドライバ自身の SBF のストリームを Stream1 から順に設定 | Stream 番号は 1 から（Res1〜4 は使わない） |
| 4 | RTK: `snts, <id>, Client, ...`（ntrip）、`sdio, <port>, <rtk_standard>, +SBF+NMEA` と GGA の `sno`（serial / ip_server） | 補正の入力と GGA の出力 | 案 B（serial）は §5 |
| 5 | **`eccf, Current, Boot`（1015 行）** | **今の設定を Boot に保存する（起動のたびに毎回）** | 資料 §6「Boot 保存は必要な設定が確定してから、明示的に行う別工程とする」に反する |

終了時（resetSettings()、93〜181 行）: エスケープの列、`sdio, <主接続先>, auto, none`（主接続先の出力を止める）、NTRIP・ip_server・serial の補正の接続を（keep_open でなければ）戻し、ドライバが立てた NMEA のストリーム（GGA）を止める。**SBF のストリームは止めず、Boot への保存もしない**。そのため、起動時に Boot に保存された設定（ドライバのストリーム、sntp など）が受信機に残る。

## 4. TF からの空間の設定（get_spatial_config_from_tf、rosaic_node.cpp 266〜368 行）

- 1 秒待ってから TF を引く。
- receiver_type gnss かつ multi_antenna のとき: vehicle_frame_id から frame_id（主）と aux1_frame_id（副）を引き、heading_offset = atan2(dy, dx)、pitch_offset = atan2(−dz, √(dx²+dy²))（度）を求め、`sto` で受信機に設定する（343〜368 行）。
- **主アンテナの位置（レバーアーム）は gnss の種類では使わない**（ins の種類だけ）。位置の出力はアンテナの位置のまま。Gouda の較正（DEC-135）でレバーアームを推定する設計と合う。
- /config のアンテナの位置が UNKNOWN（中立の値で主・副とも base_link の原点）のとき、dx = dy = 0 で heading_offset は atan2(0, 0) = 0 度になる。実際の取付が前後でなく左右なら、出力の向きは 90 度ずれる。DEC-135 の取付 Yaw の推定で分かるが、/config に人が取付位置を入れれば最初から正しい。

## 5. 案 B（PC の NTRIP クライアント → 受信機のシリアル）への当てはめ

- ドライバの `rtk_settings.serial_1.port` に受信機の接続先名（例 USB2）を書くと、`sdio, USB2, <rtk_standard>, +SBF+NMEA` と GGA の `sno, StreamN, USB2, GGA, sec1` を送る（515〜545 行）。補正の入力を USB2 で受け、GGA を USB2 に出す。PC の NTRIP のクライアントは /dev/serial/by-id/...-if02（USB2）に RTCM を書き、GGA を読んで caster に送る。
- これらも configure_rx が true のときだけで、最後の `eccf, Current, Boot` で保存される。

## 6. 影響（AI のまとめ）

- 「raw・エコー無効」は満たす。
- 「既存のストリームを上書きしない」「Boot 保存は別工程」は、configure_rx が true のままでは満たせない。起動のたびに全出力を止め、Boot に保存する。
- 選べる形（承認事項）:
  - 案 1: configure_rx を true のまま使う（受信機の設定はドライバに任せ、Boot の内容はドライバのものになる）。人の調査の Stream4 は消える。
  - 案 2: configure_rx を false にし、受信機の設定（必要な SBF の block の出力、USB2 の補正の入力と GGA、sto のオフセット、マルチアンテナ）は人の手順（資料 §11 の順序）で一度だけ行い、Boot 保存も人が判断して行う。ドライバは読むだけ（エスケープの列だけは送る）。案 B の補正の設定も手順に入る。
  - ドライバの改変はしない（DEC-075 と同じ方針）。
