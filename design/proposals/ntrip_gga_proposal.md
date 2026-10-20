# DEC-139（ネットワーク RTK の受け方）と GGA の出し方の提案（第3版。実装は承認の後）

状態: 提案。2026-10-19（第1版）。人の指示（DEC-140 の回答）「GGA の出し方は DEC-139 と一緒に提案すること」による。

第3版（2026-10-20）: 人が案 B1 を採用（DEC-139）。同じ回答の条件「NRTKのパスワード、ユーザー名等はリモート、git, ログ、rosbag, 記録文書にも載せてはならない。」に沿う B1 の設計の案を §5 に、検査ルールの案を §6 に足した（承認事項 DEC-151・DEC-152。実装はしていない）。

第2版（2026-10-20）: 人の指示（分岐したチャットでの検討の共有）により案 B3（Gouda の専用 node）と、B1 との比較・共通の注意を足した（§2・§2.1・§2.2）。測位（RTK を含む）は受信機の中で計算され、PC は補正を中継するだけ。案 A・案 C は今の接続（USB のシリアル 2 本、Ethernet・TCP/IP なし）ではできない。

前提（確かめた事実）:
- 補正は Point One の TrueRTK（NTRIP、truertk.pointonenav.com、有料。DEC-125）。
- mosaic-go は VM に USB で、シリアルの 2 本だけ（if00 = USB1、if02 = USB2）。USB イーサネットはない（2026-10-19、VM で確認）。受信機の中の NTRIP の機能はインターネットに出られないので使えない（DEC-139 の案 A は今の接続では不可）。
- configure_rx は true（DEC-140）。ドライバは主接続先 USB1 で SBF を受け、`rtk_settings.serial_1` を書けば、受信機の別の接続先（例 USB2）で補正を受け、そこへ GGA を出す設定もする（FILE-SEPTENTRIO-SOURCE-REVIEW §5: `sdio, USB2, <rtk_standard>, +SBF+NMEA` と `sno, StreamN, USB2, GGA, <周期>`、send_gga が auto なら sec1）。
- VM の apt に RTKLIB（rtklib 2.4.3.b34、str2str を含む）と ros-jazzy-ntrip-client 1.4.1 がある（未導入）。

## 1. 推奨: 案 B1（ドライバが USB2 を補正の入力・GGA の出力にし、PC の str2str が NTRIP と USB2 を中継する）

```
Point One caster ──RTCM──► str2str（PC）──RTCM──► /dev/serial/by-id/...-if02（受信機の USB2: 補正の入力）
                 ◄──GGA───           ◄──GGA───  （受信機が USB2 に出す GGA、1 秒ごと）
受信機の USB1（/dev/serial/by-id/...-if00）──SBF──► septentrio_gnss_driver（ND-19）
```

- **GGA の出し方**: 受信機が USB2 に GGA を出す（ドライバの `rtk_settings.serial_1.send_gga: auto` → `sec1`）。GGA は受信機の今の位置なので、ネットワーク RTK（仮想基準点）の caster が必要とする位置になる。PC は GGA を作らない（Gouda が位置を作り替えない）。
- **中継**: RTKLIB の `str2str -in ntrip://<ユーザ>:<パスワード>@<caster>:<ポート>/<マウントポイント> -out serial://<USB2 の by-id>:<baud> -b 1`。`-b 1` は出力（シリアル）から受けたバイトを NTRIP の入力へ返す設定で、GGA を caster に送る。VM の MRTKLIB の `mrtk relay`（str2str の移植。同じ書式）でもよい。どちらも `serial://` の path は `/dev/` の後ろを書く形で、開いたポートを raw・エコー無効にする（MRTKLIB は src/stream/mrtk_stream.c の openserial で確認。apt の rtklib は同じ由来のコードと推測、未確認）。
- **Gouda への組み込み**（承認の後に設計）: sensor supervisor が GNSS のドライバの後に str2str を子プロセスとして起動し、USB2 の by-id の名前で見張る（DEC-141 の規則）。接続先・認証は公開しないファイル（`<data_root>/config/gnss_rtk.yaml`）から読む。RTK の状態は PVTGeodetic の mode で monitor に出る（実装済み）。
- **ドライバの設定に足すもの**（gnss_config の差し込み）: `rtk_settings.serial_1: {port: USB2, rtk_standard: <RTCMv3 か auto>, send_gga: auto, keep_open: <true か false>}`。keep_open が false なら、ドライバの終了で USB2 の補正の入力と GGA のストリームが戻される。

利点: Gouda の独自のコードは子プロセスの起動と見張りだけ。GGA は受信機が出し、補正は受信機が使う（RTK の計算は受信機）。RTKLIB は広く使われている（intent 82 行の OSS の扱い）。

注意:
- str2str の引数にパスワードが入り、同じ PC の利用者からはプロセスの一覧で見える（車載 PC は一人で使う前提。気になる場合は別の方法を検討）。
- USB2 を開くのは str2str だけにする（資料 §7）。ドライバが起動のたびに受信機の全出力を止めるので、今 USB2 に流れている NMEA はドライバの起動の後は GGA だけになる。
- 未確認（**原本未照合**）: RTKLIB の `serial://` の path の書き方（/dev/ の後ろを書く形か）と、開いたポートを raw にするか（導入の前に RTKLIB のソースで確かめる）。Point One のポート・マウントポイント・GGA の要否・RTCM の版（人の契約の資料で確かめる）。

## 2. 代わりの案

| 案 | 内容 | 評価 |
|---|---|---|
| B3（第2版で追加） | Gouda の中に専用の node を作る。node が caster に HTTP でつなぎ（認証・マウントポイント）、届いた RTCM をそのまま USB2 に書き、USB2 の GGA を読んで caster に返す。中身は解釈しない | 状態を topic・monitor に出せ、パスワードがプロセスの一覧に出ない。NTRIP の接続・再接続・途切れの検出・シリアルの読み書きを自作して試験する必要（§2.1） |
| B2 | ros-jazzy-ntrip-client（ROS の node）で NTRIP を受け、RTCM を ROS の topic に出す。GGA はドライバの NMEA の topic から渡す。RTCM を USB2 へ書く node は独自に作る | 独自の node が要る。ドライバは RTCM を ROS の topic から受けない（ソースの確認の範囲） |
| C | 受信機の USB イーサネットを有効にできるか調べ、PC から NAT でインターネットに出して受信機の中の NTRIP を使う（ドライバの rtk_settings.ntrip_1） | 受信機に USB イーサネットの設定があるかは未確認。PC の転送の設定（sudo）が要る。GGA は受信機が直接送る |
| A | 受信機の中の NTRIP（今の接続） | 不可（インターネットに出られない） |

### 2.1 B1 と B3 の比較

| | B3（専用 node） | B1（str2str） |
|---|---|---|
| 作るもの | NTRIP の接続・再接続・途切れの検出・シリアルの読み書きを自作して試験 | 起動と見張りだけ |
| 状態の表示 | 補正の届いた量、最後に届いてからの時間、caster との接続を topic・monitor に出せる | 標準出力を読むしかない |
| パスワード | 公開しないファイルから読み、プロセスの一覧に出ない | 引数に入り、プロセスの一覧に見える |
| 記録 | ROS の log と rosbag に残る | 別のログ |
| 不具合の範囲 | NTRIP の作法（v1・v2、chunked の転送など）を正しく実装する必要 | 広く使われていて実績がある |

### 2.2 どの案にも共通する注意

- 受信機の側の設定（USB2 で RTCM を受け、GGA を 1 秒ごとに出す）は、configure_rx true（DEC-140）のドライバが `rtk_settings.serial_1`（port: USB2）で行う。どの案でも同じ。
- USB2 を開くのは中継（str2str か node）だけにする（人の資料 §7）。USB2 で受信機に照会するときは中継を止める。
- 補正が止まっても受信機は単独測位に戻るだけで、中継は車体の動きに関わらない。ただし RTK fix の状態は初期化（DEC-133）の判断の材料なので、補正の途切れは monitor に出す意味がある。
- 古い補正が届き続けるような異常は中継では見分けられない。受信機が出す補正の年齢（PVTGeodetic の mean_corr_age）で判断する。
- 接続先と認証は、公開しないファイル `<data_root>/config/gnss_rtk.yaml` に人が書く。リポジトリには入れない。
- 未確認（**原本未照合**）: Point One のポート、マウントポイント、GGA が要るか、RTCM の版。人が契約の資料で確かめる。

### 2.3 AI の推奨（判断は人）

- **まず案 B1 で RTK fix が出ることを確かめ、必要なら後で案 B3 に置き換える。** 最初から自作すると、fix が出ないときに原因（補正の契約、受信機の設定、自作のコード）を切り分けにくいため。

## 3. 承認していただきたいこと

| 項目 | 内容 | 推奨 |
|---|---|---|
| DEC-139 | 案 B1（ドライバが USB2 を補正の入力・GGA の出力にし、str2str が中継）にする。案 B3（専用 node）は B1 で fix を確かめた後の置き換えの候補 | B1 を承認 |
| （B1 を承認した場合） | rtklib を setup.sh の apt に加える、sensor supervisor が str2str を起動する（新しい子プロセス）、gnss_rtk.yaml の書き方を NTRIP の接続先・認証の形にする、gnss_config に rtk_settings.serial_1 を差し込む | 承認の後に設計と実装（それぞれ許可を得る） |
| 実測・確認 | Point One の接続の情報（ポート、マウントポイント、GGA の要否、RTCM の版） | 人の契約の資料で確かめ、gnss_rtk.yaml に人が書く |

## 4. 最初の起動の前後の記録（DEC-140 の回答の指示）

- 道具 `python3 -m gouda_core.septentrio_query --port <by-id> --label before_first_start --out <file> --reply-wait-s <秒>`（照会だけ: `lif,Identification`・`gso`・`getDataInOut`）。資料 §2・§4・§7 に沿う（by-id の名前だけ、他のプロセスが開いていれば送らない、raw・エコー無効を読み直してから送る、最初に CR、受信を先に始める、応答で判定）。
- 照会は USB2（資料の勧め）で行う。起動の前（Gouda もドライバも止めた状態）と、起動の後（ドライバが USB1 を使っている間に USB2 で）に 1 回ずつ。起動の後の USB2 は、B1 を入れるまでは誰も開いていない。
- 実行は人の許可の後（受信機のポートに触るため: DEC-141 の 3）。待ち時間の値は実行する人が与える。

## 5. 案 B1 の設計の案（第3版。承認事項 DEC-151。実装は承認の後）

### 5.1 秘密の範囲

- 秘密として扱うもの: NTRIP のユーザー名・パスワード。caster の名前・ポート・マウントポイントも契約の情報なので同じに扱う（人の回答の「等」。広く取る）。
- 置き場所: `<data_root>/config/gnss_rtk.yaml`（chmod 600、人が書く）だけ。リポジトリ・GitHub・ログ・rosbag・記録文書（作業記録、status.md、判断台帳、証拠のファイル、チャットへの出力）に載せない。

### 5.2 漏れうる経路（2026-10-20 にソースで確かめたもの）と対策

| 経路 | 事実 | 対策の案 |
|---|---|---|
| 中継のプロセスの引数 | str2str（と mrtk relay）は `ntrip://user:pass@caster:port/mnt` を引数で受ける。同じ PC では /proc/<pid>/cmdline・ps で見える | 引数に入ることは B1 では避けられない（残るリスク。§5.4）。下の対策で、引数がログ・記録に写らないようにする |
| Gouda のログ | `sensor_supervisor_node.py` の `_start` は、機器を使っているプロセスの cmdline（200 文字まで）を device_in_use の記録に書く。この記録はログ・/rosout（rosbag に入る）に出る | cmdline を書く前に `<scheme>://<userinfo>@` を伏せ字にする関数を通す。中継のプロセスは cmdline を一切書かない（pid と「NTRIP の中継」だけ） |
| 中継の起動の記録 | supervisor の driver_started の記録は、今は command を書かない | 中継でも command を書かない（試験で確かめる） |
| str2str の状態の出力 | 標準エラーに `[状態] バイト数 bps <msg>` を出す。NTRIP の msg は `caster:port/マウントポイント`（MRTKLIB の src/stream/mrtk_stream.c で確認。ユーザー名・パスワードは出さない） | supervisor が標準エラーを読み、状態の文字とバイト数・bps だけを取り出して記録する。msg の欄は捨てる。trace は 0（既定、ファイルを作らない） |
| ドライバの設定のファイル | `gnss_config.py` は gnss_rtk.yaml の `rtk_settings` をドライバの params（`<data_root>/run/`）に入れる | B1 では、ドライバに渡すのは `rtk_settings.serial_1`（port USB2・rtk_standard・send_gga・keep_open。秘密を含まない）だけ。gnss_rtk.yaml は `ntrip:` の節（caster・port・mountpoint・user・password）を中継のためだけに持ち、`rtk_settings` に ntrip_1 などの認証の項目があれば起動を拒否する |
| 地図の記録 | 地図に写すのは sensor_config.json だけ（map_database.register_source）。gnss_rtk.yaml は写さない | 変えない（試験で確かめる） |
| AI の作業 | VM で `pgrep -af`・`ps aux` を使うと、引数（パスワード）がチャットと作業記録に写る | 中継を入れた後は、プロセスの確かめに `pgrep -l`（名前だけ）か、伏せ字にしてから表示する。gnss_rtk.yaml を cat しない |

### 5.3 動き

- gnss_rtk.yaml に `ntrip:` の節があり、USB2 の by-id（`...-if02`）があり、他のプロセスが USB2 を開いていないときに、supervisor がドライバの後に中継を子プロセスとして起動する（DEC-141 の by-id の規則）。どれかが欠ければ起動せず、理由を記録する（秘密を含めない）。
- 中継のソフト: apt の `rtklib` の str2str を setup.sh に足す（推奨。再現できる）。VM の MRTKLIB の `mrtk relay` は手での試験に使える。apt の str2str がポートを raw にするかは、導入の前にソースで確かめる。
- monitor: 中継の状態（動いているか、受けたバイト数、最後に増えてからの時間）と、受信機の補正の年齢（PVTGeodetic の mean_corr_age）・RTK の mode を出す。
- 補正が止まっても受信機は単独測位に戻るだけ。中継の異常で車体を止めない（中継は車体の動きに関わらない）。

### 5.4 残るリスク

- B1 では、同じ PC の利用者（root を含む）は中継の引数を ps で見られる。車載 PC は一人で使う前提。この残るリスクを受け入れられない場合は、案 B3（node が gnss_rtk.yaml から読む。引数に出ない）に置き換える。

## 6. 検査ルールの案（承認事項 DEC-152）

- 新しいルール（案）: 秘密を書かない。`<data_root>/config/gnss_rtk.yaml` が検査を実行する機械にあれば、その `ntrip:` の節の値（user・password・caster・mountpoint）が、リポジトリの作業ツリーの全ファイル、`design/generated/`、`<data_root>/run/` のログと params に現れないことを調べる。ファイルが無ければ「未判定」（理由: 秘密のファイルがない）。
- 単体の試験: 伏せ字の関数、gnss_rtk.yaml の読み方（rtk_settings に認証があれば拒否）、中継の記録に command と msg が入らないこと（偽の値で）。
- 新しい検査ルールの追加は承認事項（CLAUDE.md 1.2）。

## 7. 案 B1 の実装の段（DEC-151 承認の後。各段はそれぞれ人の許可を得てから行う）

| 段 | 内容 | 変えるファイル（予定） | 試験 |
|---|---|---|---|
| 1 | 記録の伏せ字（秘密の対策の前提）: supervisor が他のプロセスの cmdline を記録する前に、`<scheme>://<userinfo>@` を伏せ字にする。振る舞いは他に変えない | `gouda_core/gouda_core/device_watch.py`（伏せ字の関数）、`sensor_supervisor_node.py`（_start の cmdline） | 単体: 伏せ字の関数（ntrip・http・userinfo なし・複数）、device_in_use の記録に偽の認証が残らない |
| 2 | gnss_rtk.yaml の書式: `ntrip:` の節（caster・port・mountpoint・user・password。中継だけが読む）。`rtk_settings` に認証の項目があれば起動を拒否。ドライバに渡す `rtk_settings.serial_1`（port USB2・rtk_standard・send_gga・keep_open）の値の出どころを決める（案: 秘密でないので設計のパラメータ PRM にし、rtk_standard は契約の資料まで tbd） | `gnss_config.py`、正本（PRM の追加は承認事項） | 単体: 読み方、拒否、params に秘密が入らない |
| 3 | 中継の起動: supervisor がドライバの後に str2str を子プロセスとして起動し、USB2 の by-id で見張る。標準エラーから状態の文字・バイト数・bps だけを取り出す。command と msg は記録しない | `sensor_supervisor_node.py`（新しい子プロセス）、正本（USB2 の by-id の PRM） | 単体: 偽の中継（偽の str2str）で起動・停止・記録に秘密が出ない |
| 4 | setup.sh の apt に `rtklib` を足す。導入の前に apt の str2str のソースでポートを raw にすることを確かめる | `setup.sh` | VM: 人が `bash setup.sh`（sudo）、`str2str -h` |
| 5 | monitor: 中継の状態、受けたバイト数・最後に増えてからの時間、補正の年齢（mean_corr_age）、RTK の mode | `monitor_core.py` ほか | 単体: 表示の文字列 |
| 6 | VM の試験: 偽の caster（PC の中の TCP、偽の RTCM）で中継が USB2 に書くこと、記録に秘密が出ないこと。その後、人が gnss_rtk.yaml を書いて屋外で RTK fix | 試験のスクリプト | VM・屋外（人） |

## 8. 段 2 の設計の案（2026-10-20。承認事項 DEC-154。実装はしていない）

### 8.1 gnss_rtk.yaml の書式（公開しないファイル。人が書く）

置き場所は今と同じ `<data_root>/config/gnss_rtk.yaml`（VM では ~/gouda_ws/gouda_data/config/）。中身は NTRIP の中継（段 3）だけが読む。ドライバには渡さない。

```yaml
# <data_root>/config/gnss_rtk.yaml（例。値はすべて架空。実の値はこのファイルにだけ書く）
ntrip:
  caster: caster.example.invalid   # caster の名前（ホスト名か IP）
  port: 2101                       # caster のポート（整数）
  mountpoint: EXAMPLE              # マウントポイント
  user: example-user
  password: example-password
```

- 5 つの項目がすべて必要。どれかが無い・型が違う（port が 1〜65535 の整数でない、文字列に空白・改行がある、mountpoint に `/` がある）ときは、中継を起動しない。理由の記録には**項目の名前だけ**を書き、値は書かない。
- ファイルの権限: 所有者以外に読み書きの権限があれば（mode & 0o077 ≠ 0）中継を起動しない（ssh の鍵と同じ考え。人が `chmod 600` にする）。理由の記録は「権限が広い」だけ。
- 旧い書式（`rtk_settings` を持つ）は使わない: ファイルに `rtk_settings` があれば、その中身をドライバに渡さず（認証がドライバの params に入らないように）、中継も起動しない。記録は「旧い書式のため使わない（DEC-154）」。
- `ntrip` 以外の項目は読まない（無視して記録に名前だけ書く）。
- ファイルが無いときは今と同じ: 補正なし（単独測位）で、ドライバは起動する。
- 受信機の測位はファイルの有無・誤りにかかわらず続く（補正が無いだけ）。ドライバの起動は止めない。
- NTRIP の版（v1・v2）・TLS は書かない（str2str の NTRIP の client の作法に従う。Point One が v1 を受け付けるかは**原本未照合**。段 4 で apt の str2str のソースを確かめるときに合わせて確かめる）。

### 8.2 ドライバに渡す値（秘密を含まない。公開の設計のパラメータ）

ドライバの params の `rtk_settings` は雛形（upstream の gnss.yaml）を基にし、Gouda が変えるのは `serial_1.port` だけ。

| 項目 | 値 | 出どころ |
|---|---|---|
| `rtk_settings.serial_1.port` | `USB2` | **新しい PRM（案）**: 補正の入力と GGA の出力に使う受信機の接続先の名前。DEC-139（B1）と人の資料（if02 = USB2）から。gnss_rtk.yaml の ntrip が有効なときだけ書く（無いときは雛形の空のまま。受信機の USB2 は今のまま） |
| `rtk_settings.serial_1.rtk_standard` | `auto`（雛形のまま） | 受信機が RTCM の版を自分で判別する。Point One の RTCM の版を知らなくても動く（契約の資料で確かめた後、必要なら別の承認で変える） |
| `rtk_settings.serial_1.send_gga` | `auto`（雛形のまま） | ドライバは GGA のストリームを 1 秒ごとに作る（FILE-SEPTENTRIO-SOURCE-REVIEW §5） |
| `rtk_settings.serial_1.baud_rate` | `115200`（雛形のまま） | USB の CDC では意味を持たない（推測）。中継の str2str にも同じ値を渡す（段 3。新しい値を作らない） |
| `rtk_settings.serial_1.keep_open` | `true`（雛形のまま） | ドライバの終了の後も USB2 の補正の入力を残す（Gouda の止め方に影響しない） |
| `rtk_settings.ntrip_1`・`ip_server_1` | 雛形の空のまま | 使わない |

### 8.3 中継が使う値（段 3 で使う。段 2 では正本に入れるだけ）

| 項目 | 値 | 出どころ |
|---|---|---|
| 中継がつなぐ受信機のポート | `serial:/dev/serial/by-id/usb-Septentrio_Septentrio_USB_Device_0100012541-if02` | **新しい PRM（案）**: PRM-65（if00）と同じ書き方・同じ規則（by-id だけ、DEC-141）。2026-10-19 の VM で確かめた名前 |
| 中継の時間（受信の timeout、再接続の間隔） | str2str の既定（10000 ms・10000 ms）のまま | 新しい値を作らない。変える必要が出たら別の承認 |

### 8.4 gnss_config の変更（段 2 の実装の範囲）

- `read_rtk` を `read_ntrip` に置き換える: (ntrip の dict か None, 記録用の注記)。注記に値は入れない。
- `driver_parameters`: ntrip が有効で新しい PRM（受信機の接続先の名前）があるときだけ `rtk_settings.serial_1.port` を入れる。それ以外の rtk_settings は雛形のまま。gnss_rtk.yaml の中身はドライバの params に一切入らない。
- `KEYS` に新しい PRM 2 つを足す。ただし、どちらも未確定のときに**ドライバの起動は止めない**（補正なしで動く。止まるのは中継だけ）。今の `KEYS`（device・configure_rx）が欠けると起動しない規則とは分けて扱う。
- 試験（架空の値だけ）: 正しいファイル、項目の欠け・型の誤り、権限が広い、旧い書式、ファイルなし。どの場合も、ドライバの params と注記に秘密の値が現れないこと。

### 8.5 承認していただきたいこと（DEC-154）

1. §8.1 の gnss_rtk.yaml の書式と、誤りのときに中継だけを止めドライバは止めない扱い。
2. 新しい PRM 2 つ: 受信機の補正の入力の接続先の名前 `USB2`、中継の接続先 `serial:/dev/serial/by-id/...-if02`。
3. rtk_standard・send_gga・baud_rate・keep_open は雛形のまま（Gouda は変えない）。
4. 段 2 の実装（§8.4）の許可は、1〜3 の後に改めて求める。

## 9. 段 3 の設計の案（2026-10-20。承認事項 DEC-156。実装はしていない）

### 9.1 今の supervisor で確かめたこと（`gouda_core/gouda_core/sensor_supervisor_node.py`）

- ドライバは `Driver`（key・label・見張る機器・command）で表し、udev・ip の出来事で `_evaluate` が機器の同一性を見て、起動・作り直し・停止をする（DEC-088: 同じ同一性では作り直さない）。
- **起動の時の記録（`settings`「sensor supervisor configured」）は、全ドライバの `command` をそのまま書く**（103 行）。中継を同じ形で足すと、引数の認証が記録・/rosout・rosbag に出る。
- 記録（DecisionEvent）は `log/decision` に publish し、同じ文をログ（/rosout）にも書く。
- ドライバの標準出力・標準エラーは捨てていない（ros2 launch のログに入る）。中継の標準エラーをそのまま流すと、NTRIP の状態の msg（caster:port/マウントポイント）がログに入る。

### 9.2 中継の置き方

- 中継を supervisor の 4 つめの子プロセスにする（key `ntrip`、label `NTRIP relay (ND-19)`）。見張る機器は PRM-76（USB2 の by-id）。同一性・起動・停止・作り直しはドライバと同じ仕組み（by-id、DEC-141。tty_users で他のプロセスが USB2 を開いていれば起動しない＝人の資料 §7）。
- 起動の条件（すべて満たすとき）: gnss_config の結果が `corrections`（ntrip の節が有効、PRM-75 がある）、PRM-76 が by-id の名前、`str2str` が PATH にある、GNSS のドライバの設定がそろっている（ドライバの command がある）。欠けるときは理由を記録して起動しない（理由に秘密を書かない）。
- 中継の command（メモリの中だけ）: `str2str -in ntrip://<user>:<password>@<caster>:<port>/<mountpoint> -out serial://<PRM-76 の /dev/ の後ろ>:<baud> -b 1`。baud は雛形の `rtk_settings.serial_1.baud_rate`（115200。新しい値を作らない）。`-s`（timeout）・`-r`（再接続の間隔）・状態の表示の間隔は str2str の既定のまま（10000 ms・10000 ms・5000 ms）。
- ドライバとの順序: 順序は決めない。中継が先に書いた RTCM は、ドライバが USB2 を補正の入力にするまで受信機が捨てるだけ（推測。害はない）。GGA はドライバが設定した後から出る。
- 補正の値を受け取るのは、起動の時に `gc.read_ntrip` を読み直した結果だけ（メモリの中。ファイルの変更は Gouda の再起動で反映。今のほかの設定と同じ）。

### 9.3 秘密を出さないための変更

| 場所 | 変更 |
|---|---|
| 起動の時の記録の `command` | 中継は公開用の command（`ntrip://<redacted>` にしたもの）だけを持ち、Popen に渡す本物の command は別の属性（記録・表示に使わない）。念のため、全ドライバの command を記録の前に `dw.redact_command` に通す |
| `driver_started` などの記録 | 今も command を書いていない。中継でも pid・同一性だけ |
| 中継の標準出力・標準エラー | 標準出力は捨て、標準エラーは supervisor が読む。1 行ごとに状態の文字（E エラー・- 閉・W 待ち・C 接続・A 通信中）、バイト数、bps だけを取り出し、msg の欄は捨てる。取り出せない行は「解釈できない行」と数えるだけで、中身は書かない |
| 状態の記録 | 状態の文字が変わったときだけ `ntrip_relay_state` を記録する（例: 入力 C→A）。バイト数は 5 秒ごとに内部に持ち、記録はしない（段 5 で monitor に出す） |
| device_in_use の記録 | 段 1 の伏せ字（済み） |

### 9.4 終了と作り直し

- 中継が終わった（終了コード）ときは `ntrip_relay_exited` を記録する。**同じ同一性では作り直さない**（DEC-088 と同じ規則。案 A）。str2str はネットワークの切断では終わらず、自分で再接続する（-r）ので、終わるのは USB2 が消えた・引数の誤りなどのとき。USB2 が付け直されれば（受信機の reset を含む）作り直す。
  - 代わりの案 B: 中継だけは終了の後に一定の時間をおいて作り直す（間隔は新しい PRM、承認が要る）。推奨は案 A（規則を一つにする。困ったら案 B を別に提案）。
- gouda.sh stop: 中継も同じプロセスのグループなので、ドライバと一緒に止まる（今の仕組み）。supervisor の shutdown でも止める。

### 9.5 gnss_config の検証の追加（RTKLIB の書き方の制約）

- MRTKLIB の `decodetcppath`（src/stream/mrtk_stream.c）で確かめた: URL は最後の `@` で認証と接続先に分かれ、認証は最初の `:` で user と password に分かれ、接続先の `/` の後がマウントポイント、その後の `:` は別の意味になる。str2str は最後の `#` を書式の区切りに使う。MRTKLIB は user・password を URL のデコードをする。apt の rtklib（2.4.3 b34）がデコードするかは**未確認**（段 4 で確かめる）。
- 追加する検証: `#` を含む値は不可、user に `:` は不可、mountpoint に `:` は不可、caster に `:`・`/`・`@` は不可。不可のときは段 2 と同じく中継を起動しない（項目の名前だけを記録）。
- apt の str2str がデコードするなら、user・password を percent-encoding して渡し、上の制約を緩められる（そのときは別に提案する）。

### 9.6 試験（偽の値・偽の str2str）

- 偽の str2str（試験の中の小さなスクリプト）: 受け取った引数を試験だけが読むファイルに書き、標準エラーに偽の状態の行（偽の caster とマウントポイントの msg を含む）を出す。
- 確かめること: 起動の条件（ファイルなし・誤り・PRM-76 なし・str2str なし・USB2 を他が使用中）で起動しないこと、起動したときの引数が正しいこと、記録（DecisionEvent の reason・details）とログに偽の user・password・caster・port・マウントポイントが一つも出ないこと、状態の変化が記録されること、停止で中継も止まること。
- ROS を使う部分は、今の試験の作り方（ROS なしの部分を関数に分ける）に合わせる。VM の試験スタックでの確かめは段 6。

### 9.7 承認していただきたいこと（DEC-156）

1. §9.2 の置き方（supervisor の子プロセス、PRM-76 で見張る、起動の条件、str2str の既定の値のまま）。
2. §9.3 の秘密の扱い（公開用の command と本物の command を分ける、全 command の伏せ字、標準エラーから状態だけ、状態の変化だけを記録）。
3. §9.4 の案 A（中継が終わっても同じ同一性では作り直さない）。
4. §9.5 の検証の追加。
5. 段 3 の実装の許可は 1〜4 の後に改めて求める。
