# 作業記録 2026-10-23 第147便: NTRIP の中継を TLS（stunnel4）で包む実装（REV-172、DEC-361 回答）

## 読んだもの

- 作業ツリー `31a6e1d` ＋ 未コミットの変更（第145便まで）。status.md、第144・145便の作業記録、DEC-139・156・361・362。
- `gouda_core/gouda_core/ntrip_relay.py`・`sensor_supervisor_node.py`、`gouda_core/test/test_ntrip_relay.py`・`test_sensor_supervisor_relay.py`、`setup.sh`。

## 1. 人の指示（原文）

「認証系を直して」。方法の問い（AskUserQuestion）への回答：「stunnel4 で包む (Recommended)」。
DEC-361 案 a の実装の許可（DEC-106）として扱った。台帳に原文で記録（REV-172）。

## 2. 行ったこと

- 確かめ（読むだけ・診断）: VM で stunnel4 5.72 の .deb を `apt-get download`＋`dpkg -x`（~/upstream_pkgs/stunnel、導入していない）。設定を `-fd 0`（標準入力）で受けること、
  証明書の連鎖とホスト名を確かめて caster に TLS でつながること（認証なしの source table の要求だけで確認）、待ち受けを始めたときのログの行
  （LOG6「Service [ntrip] (FD=n) bound to …」）を確かめた。
- 実装（DEC-361 案 a）:
  - `ntrip_relay.py`: str2str は 127.0.0.1 の口にだけつなぐ（relay_commands に local_port）。stunnel4 の設定（client・accept 127.0.0.1・connect caster・sni・verifyChain・
    CAfile /etc/ssl/certs/ca-certificates.crt・checkHost・delay）を作る stunnel_config、待ち受けの行の判定、stunnel4 のログを種類（connected・connect_failed・
    certificate_rejected・tls_failed・closed・stunnel_exited）だけにする tls_event／parse_tls、read_status に TLS の種類の変化の通知を足した。build_relay は
    stunnel4 がなければ起動しない（理由「stunnel4 is not installed: … the credentials are never sent in plaintext」）。起動のコマンドは
    `python3 -m gouda_core.ntrip_relay_runner` で、接続の情報は標準入力（launch_input）で渡す。中継を起動しないときも USB2 の by-id を見張る。
  - `ntrip_relay_runner.py`（新規）: 空いた loopback の口を取り、stunnel4 を `-fd 0` で起動（設定は標準入力）、待ち受けの行を見てから str2str を起動。str2str の
    標準エラーはそのまま流し、stunnel4 のログは「[TLS] <種類>」だけを出す。どちらかが終われば他方を止め、str2str の終了コードで終わる。SIGINT・SIGTERM で両方を止める。
    時間の値は置かない（待ちは子の出来事で終わる）。
  - `sensor_supervisor_node.py`: Driver に launch_input（標準入力に書く。記録しない）。中継の TLS の種類の変化を `ntrip_tls_state` として記録。
  - `setup.sh`: apt の一覧に stunnel4・ca-certificates。
  - 試験: `test_ntrip_relay.py`（str2str が caster に直接つながらない、argv に接続の情報がない、stunnel4 なしでは起動しない、設定が証明書を確かめ認証を含まない、
    TLS の種類の分類と行を渡さないこと、偽の stunnel4＋str2str で runner を通した端から端、待ち受ける前に終わる stunnel4 では str2str を起動しない）、
    `test_sensor_supervisor_relay.py`（偽の stunnel4＋str2str で supervisor の起動・記録に秘密が出ない、ntrip_tls_state が出る、起動しない中継の評価で落ちない）。
- VM の Gouda への反映（手動モードを 2 回確かめた後）: 3 つのコード・2 つの試験・setup.sh を ~/gouda_ws に写して `gouda.sh stop`→`start`（2 回）。

## 3. 原因の分類（1.6）

- 元の問題（平文で認証を送る中継）: 実装（中継の部品に TLS のない str2str を選び、TLS 専用の caster につないでいた）。中継の層で直した。
- 反映の 1 回目の回帰: 起動しない中継（stunnel4 がない）を評価すると、`_observe` が LiDAR の枝に落ちて `AttributeError: 'Driver' object has no attribute 'host_ip'` で
  見張りの thread が止まった（第107便からの既知の不具合が、今回の変更で車載の設定でも起きるようになった）。分類は実装。起動しない中継も USB2 の by-id を
  見張るようにして直した（`host_ip` の一般の直しは別の承認事項のまま）。回帰の試験を足した。
- 試験で見つけた runner の競合（stunnel4 が待ち受ける前に終わると、出力の終わりを待ち受けと取り違える）: 実装。listening の印を分けて直した。

## 4. 検査・試験

対象: 作業ツリー（`31a6e1d` ＋ 未コミットの変更 ＋ この便の変更）。
- Mac: `/opt/anaconda3/bin/python3 -m unittest discover -s gouda_core/test` → 293 件 OK（skip 11。supervisor の試験は ROS がないので skip）。
- VM（作業ツリーを ~/gouda_unit_tree_bin146 に写した。名前の番号は作業の途中で付けたもの。ROS_DOMAIN_ID 83）: 293 件 OK。1 回目は runner の競合で 1 件不合格 → 直して 3 回続けて全件 OK。
  supervisor の中継の試験 3 件は VM で実行され合格。
- 端から端（VM、実の stunnel4 5.72＋実の str2str、Gouda の ntrip_relay の関数を使う試験用のスクリプト。受信機が外れていたので出力は USB2 でなくファイル、GGA は str2str の -p で
  市役所付近の公開の座標）: stunnel4 が待ち受け、str2str は waiting → connected、30 秒で 28197 バイト、RTCM3 の frame 181（1005・1029・1033・1074・1084・1094・1114・1124・1230）。
  TLS の種類は connected。平文で caster に送ったものはない。
- VM の Gouda（反映の後）: launch のログに Traceback 0。4 つの機器（XT-32・IMU・GNSS・NTRIP 中継）の見張りの記録あり（どれも未接続）。中継は「stunnel4 is not installed」で起動しない。
  str2str・stunnel は動いていない。モードは MANUAL。
- 設計検査（REV-172 の後）: `{"合格": 12, "違反": 0, "未判定": 5}`。DR-15 の未判定 35（増えていない）、DR-17 合格。移行の違反・検査器の試験の不合格 1 件は intent.md の未記録の編集による既存のもの。
- 未実行: Gouda の supervisor が実の stunnel4 で中継を起動し、受信機の USB2 に RTCM を書いて RTK fix になること（stunnel4 が VM に導入されていない、受信機が外れている）。

## 5. 残るリスク

- stunnel4 の導入（`bash setup.sh`、sudo）は人の作業。導入するまで RTK は使えない（平文で送ることもない）。
- 認証は今も str2str の argv に入る（同じ PC のプロセスの一覧で見える。DEC-139 で受け入れ済みのリスク）。caster の名前は argv から消えた。
- stunnel4 の分類の文言（TLS_EVENTS）は 5.72 の実のログで connected・bound だけを確かめた。失敗の文言（証明書の拒否など）は実のログで確かめていない。
- DEC-362（パスワードの変更）は回答待ち。変える場合も、stunnel4 を入れた後なら平文では送られない。

## 6. 次

- 人：`bash setup.sh` で stunnel4 を入れる → 受信機をつなぐ → Gouda の monitor・記録で ntrip_tls_state connected、ntrip_relay_state connected、PVTGeodetic の mode（RTK）を確かめる。
- 2 アンテナの向きが出ない件（第144便）は別。
- コミットはまだ。

## 7. 追記：受信機を VM につないだ後の確認（2026-10-23 23:48〜23:52、読むだけ）

- 人が stunnel4 を入れた（dpkg.log 21:21:09 install stunnel4 3:5.72-1build2）。Gouda はその後 21:26 に起動していた。人が受信機を Parallels で VM に接続した。
- supervisor が自動で GNSS のドライバと中継を起動した（再起動なし）。記録：`ntrip_relay_state` input waiting → `ntrip_tls_state` TLS connected → `ntrip_relay_state` input connected。
  **TLS での caster への接続は、Gouda の実の経路で成り立った**（stunnel4・str2str とも動作、pgrep -l で確認）。
- 受信機は測位していない：PVTGeodetic は mode 0・error 1（測定が足りない）・nr_sv 255・mean_corr_age 65535 を 23:49〜23:52 の 4 回とも。AttEuler も mode 0・error 1。
  19:57 には単独測位・衛星 16 だった。**衛星を受けていないので、RTK になるかは確かめられない**。原因（アンテナの位置・接続、屋内）は未確認。
- 補正のバイト数が増えているかは、記録が状態の変化だけなので見ていない。
