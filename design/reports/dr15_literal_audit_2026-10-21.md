# DR-15 の未判定 11 件と、検査器が見ない数値の調査（2026-10-21、第73便）

対象：作業ツリー（コミット 33416021655e587d0ae5f2c949d9bf81698ef44e ＋未 commit の変更）。各行は実際にソースを開いて読んだ。挙動への影響のうち「推測」と書いたものは試していない。

## 1. DR-15 の 11 件（承認値と同じ数のリテラル）

| # | 場所 | リテラル | 一致した PRM | 何の数か | 判定 |
|---|---|---|---|---|---|
| 1 | gouda_core/glim_runner.py:146 | `time.sleep(0.2)` | PRM-16 | GLIM の終了を待つ間の確認の間隔 | 偶然の一致。ただし設定にない時間の値（§2-6） |
| 2 | gouda_core/speed_mask.py:66・67 | `+ 0.5` | PRM-42 | セルの中心（格子の座標 + 半セル） | 偶然の一致。幾何の定数 |
| 3 | gouda_core/speed_mask.py:76 | `> 0.5` | PRM-42 | 量子化の丸めの判定（半ステップ） | 偶然の一致。数学の定数 |
| 4 | gouda_core/gnss_config.py:21 | `1.5` | PRM-15 | docstring の「CLAUDE.md 1.5」（節の番号） | 誤検出（文章） |
| 5 | gouda_core/sensor_config.py:10 | `1.5` | PRM-15 | docstring の「CLAUDE.md 1.5」 | 誤検出（文章） |
| 6 | gouda_core/nav2_config.py:15 | `0.05` | PRM-41 | docstring。上流の雛形の z_resolution「16 x 0.05 m」の説明。コードは z_resolution を PRM-71 から計算（:110・111） | 誤検出（文章） |
| 7 | gouda_core/map_convert.py:44 | `0.2` | PRM-16 | 変換器の版の文字列 `'gouda_map_convert 0.2 …'` | 誤検出（版番号） |
| 8 | gouda_core/map_convert.py:143・303 | `0.5` | PRM-42 | :143 セルの中心、:303 色の段階の中間（緑→黄→赤の 0.5） | 偶然の一致。幾何・表示の定数 |
| 9 | gouda_core/map_creator_node.py:79 | `0.1` | PRM-14 | 変換の進み具合の表示（10 %） | 偶然の一致。表示の値 |
| 10 | gouda_core/vehicle_bridge_node.py:68 | `timeout=0.05`、`write_timeout=0.2` | PRM-41、PRM-16 | シリアルの読み出しの待ち・書き込みの待ちの上限 | PRM の写しではない。**設定にない時間の値**（§2-1・2） |
| 11 | gouda_core/vehicle_bridge_node.py:79 | `time.sleep(0.5)` | PRM-42 | 読み出し失敗の後、次に試すまでの待ち | PRM の写しではない。**設定にない時間の値**（§2-3） |

結論：11 件のどれも、承認された PRM の値をコードに写したものではない。7 件（#2〜#9 の文章・定数）は偶然の一致か誤検出。#1・#10・#11 は、PRM とは別の、設定に宣言されていない時間の値。

## 2. 設定に宣言されていない時間の値（検査器が見ないものを含む）

検査器（DR-15）は、`gouda_core/gouda_core` と `gouda_core/launch` の `.py` だけを、承認値と同じ数かどうかで調べる。整数（`1`、`30`）、C++（firmware）、シェル（gouda.sh）、JavaScript（web）は調べない。そこで、製品のコード全体から、時間に関わる数値を別に探した（sleep・timeout・wait・join・delay・period などの語と数値の組。grep で 54 行を読み、時間の値を下に挙げた）。

| # | 場所 | 値 | 働き | 影響（推測を含む） | 区分の案 |
|---|---|---|---|---|---|
| 2-1 | vehicle_bridge_node.py:68 | write_timeout 0.2 s | 書き込みが詰まったときの上限 | 書き込みは送信の timer（PRM-14 0.1 s）の中で行い、node は単一の executor（rclpy.spin）。詰まると最大 0.2 s、送信と joystick_command の受信が止まる。0.2 s ＞ PRM-14、0.2 s ＜ PRM-09（0.35 s）・PRM-13（1.0 s）。車体側は PRM-13 の watchdog で中立になるので、安全の最後の砦は変わらない（推測） | 指令の経路の時間の値。PRM として宣言し、PRM-14・09・13 との関係を検査する案（承認） |
| 2-2 | vehicle_bridge_node.py:68 | timeout 0.05 s | 読み出しの待ち（受信スレッドの起床の間隔） | STATUS（PRM-49 50 ms）の受け取りが最大 50 ms 遅れうる。指令の送信には関係しない | 宣言するか、内部の値として理由を書くか（承認） |
| 2-3 | vehicle_bridge_node.py:79 | sleep 0.5 s | 読み出し失敗の後の再試行の間隔 | USB が抜けると、0.5 s ごとに DecisionEvent（serial_error）を出し続ける（毎秒 2 件）。判断の履歴（transient_local、深さ 50）が約 25 秒で埋まり、ほかの判断が新しく接続した monitor から見えなくなる（推測）。【第75便で訂正】monitor は同じ通知を 1 行にまとめて回数を表示する（monitor_core.py の on_decision）ので、monitor の通知欄は埋まらない。埋まるのは ROS の保持（深さ 50）で、あとから接続した購読者だけに影響する。再接続はしない（configure をやり直す必要） | 実装の問題の候補。記録を変化のときだけにする案（承認） |
| 2-4 | vehicle_bridge_node.py:89 | join 1 s | 終了時の受信スレッドの待ち | 停止・cleanup の時だけ | 内部の値として許容の案 |
| 2-5 | recorder_node.py:123 | wait 30 s | rosbag を SIGINT で止めた後の待ち。過ぎると SIGTERM | rosbag の書き終わりに 30 s 以上かかると、途中で止めることになる（推測。大きな点群の bag で起こりうる） | 記録の完全さに関わる。宣言する案（承認） |
| 2-6 | glim_runner.py:146 | sleep 0.2 s | GLIM の終了を待つ間の確認の間隔 | PRM-37 の期限を最大 0.2 s 過ぎる。期限そのものは PRM-37 | 内部の値として許容の案 |
| 2-7 | monitor_server.py:63 | join 5 s | HTTP サーバの停止の待ち | 停止の時だけ | 内部の値として許容の案 |
| 2-8 | septentrio_query.py:86 | sleep 0.01 s | 受信機への問い合わせの道具の読み出しの間隔 | 道具だけ（node ではない） | 内部の値として許容の案 |
| 2-9 | gouda.sh:74 | 20 回 × 1 s | 起動時に monitor の URL を待つ | 過ぎても起動は続く（URL を後で見るよう表示） | 内部の値として許容の案 |
| 2-10 | gouda.sh:88・91 | 30 s、10 s | 停止時、SIGINT の後 30 s で SIGTERM、さらに 10 s で SIGKILL | mode_manager は終了時に GLIM の保存を PRM-37（未確定の間は上限なし）まで待つ。GLIM の保存が 30 s を超えると、mode_manager が SIGTERM・SIGKILL で止まり、原図の登録（地図データベースへの登録）がされない（推測）。GLIM は別のセッションで動くので保存は続く見込み（推測）。PRM-37 の考え方（上限を作らない）と食い違う | **設計の食い違い**。gouda.sh の待ちを PRM-37 と関係づける案（承認） |
| 2-11 | firmware src/main.cpp:20 | kControlPeriodMs 5 ms | Core::tick の間隔 | 期限の判定（PRM-13・21・48）が最大約 5 ms 遅れる。コメントに理由あり | 内部の値として許容の案（理由は書かれている） |
| 2-12 | firmware src/main.cpp:98 | delay(1) | loop の間隔 | 同上 | 内部の値として許容の案 |

時間以外の定数（プロトコルの定数 SERIAL_BAUD 460800、AXIS_LIMIT 10000、kStickRange 512、MASK_MAX 100、SBF の値など）は、プロトコル・機器の仕様の値で、コメントに理由がある。車体の値ではない。

## 3. 検査器（DR-15）の限界

- 文章（docstring・コメント・文字列）の中の数も拾う（#4〜#7）。
- 整数のリテラルを調べない（30、1 など）。firmware（C++）、gouda.sh、web（JavaScript）を調べない。
- 同じファイルに param_key があると、そのファイルの一致を報告しない。
- 承認値と同じ数だけを探すので、承認されていない時間の値（§2）は見つからない。

検査ルールの変更（走査の範囲・方法を広げる、許容の一覧を持つなど）は、承認事項。

## 4. 人に判断を求めること（まとめ）

1. §2-1・2-2・2-3・2-5・2-10 を PRM として宣言する（値は今のまま）か、内部の値として理由をコードに書くか。§2-3 と §2-10 は振る舞いの変更を含む。
2. §2-4・2-6〜2-9・2-11・2-12 を内部の値として許容するか。
3. DR-15 の改良（文章の除外、整数・C++・シェル・JavaScript の走査、許容の一覧）を検査ルールとして追加するか。
