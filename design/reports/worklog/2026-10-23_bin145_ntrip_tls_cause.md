# 作業記録 2026-10-23 第145便: NTRIP が使えない原因の調べ（REV-170、DEC-361・362）

## 読んだもの

- 作業ツリー `31a6e1d` ＋ 未コミットの変更（第144便まで）。status.md、第144便の作業記録、`gouda_core/gouda_core/ntrip_relay.py`・`gnss_config.py`・`sensor_supervisor_node.py`、
  提案 `ntrip_gga_proposal.md`・`gnss_improvements_2026-10-22.md`、記録 `research/gnss_no_tracking_investigation_2026-10-22.md`、DEC-139・156・298・301。
- RTKLIB の src/stream.c（tomojitakasu/RTKLIB、ブランチ rtklib_2.4.3、2026-10-23 に取得）、VM の MRTKLIB の src/stream/mrtk_stream.c。

## 1. 人の指示（原文）

「NTRIPが使えない原因を徹底的に調べろ」

調べの指示として扱った。DEC-301（caster への接続だけの確かめ、pending）の中身を、この指示で行った。実装・設定の変更はしていない。

## 2. 分かったこと

- **原因（事実）**: gnss_rtk.yaml の caster の port は **TLS 専用**。平文の要求は 0.13 s で接続をリセットされ、1 バイトも返らない。同じ host・port に TLS（TLSv1.3）でつなぐと、
  v1 の要求に「ICY 200 OK」、v2 に「HTTP/1.1 200」、source table の要求に SOURCETABLE（836 バイト）が返った。**認証と mountpoint は正しく受け付けられている**。
- apt の str2str（rtklib 2.4.3.b34）の NTRIP の client は平文の TCP だけで、TLS の処理がない（stream.c の reqntrip_c・rspntrip_c、ssl・tls の語なし）。VM の MRTKLIB にもない。
  したがって今の中継（DEC-139 の案 B1）は、この caster には**何度やり直してもつながらない**。中継の状態が「input waiting」のまま 0 バイトだったこと（第114便・第144便）と合う。
- 中継の失敗の理由が今まで見えなかったのは、秘密を出さないため str2str の msg の欄を全部捨てているため（第129便の記録の指摘と同じ）。
- 未確認: TLS で GGA を送った後に RTCM が流れること。20:06 ごろ受信機の USB が VM から外れ（/dev/serial/by-id が消えた）、GGA の位置が得られず ntrip_probe3.py は未実行。
  外れた後、GNSS のドライバは "terminate called after throwing an instance of 'std::system_error' what(): Invalid argument" で落ちた記録がある。私の診断は受信機のシリアルの口に触れていない（外れた原因は未確認。19:3x にも一度外れている）。
- 2 アンテナ（第144便）は別の問題で、この便では調べていない。

## 3. 原因の分類（1.6）

- 実装（中継の部品の選び方）: 中継に TLS のない str2str を選んだ（第66便の時点で Point One が v1・TLS なしを受け付けるかは未確認と書いていた：DEC-298）。直し方は承認事項 DEC-361。
- 物理特性・環境（受信機の USB の外れ）: 未解決として残す。

## 4. AI の誤り

- 診断の最初の 2 つのスクリプト（ntrip_probe.py、ntrip_probe2.py の平文の v1）で、TLS を先に試さずに、認証つきの平文の要求を 5 回送った。
  str2str も起動のたびに同じ平文の要求を送っていた。確認事項 DEC-362（パスワードの変更の検討）にした。
- ntrip_probe.py は、位置が渡らず GGA を送っていないのに「GGA sent: True」と出す表示の誤りがあった（結果の解釈には影響しない。results.txt に注記）。

## 5. 行ったこと

- 診断用のスクリプト 3 つ（`research/vehicle_pc/2026-10-23_ntrip_tls_probe/`）を VM の ~/claude_scratch で実行。接続の情報はスクリプトが自分で gnss_rtk.yaml から読み、
  出力は種類・状態の番号・バイト数だけ。位置は一時ファイル（umask 077、実行後に削除）でだけ渡した。gnss_rtk.yaml の中身は表示していない。
- 番号を予約（REV-170、DEC-361・362、第145便）。REV-170 を `--dry-run --check`（新しい違反 0）の後に適用。証拠 4 ファイルを登録。

## 6. 検査・試験

対象: 作業ツリー（`31a6e1d` ＋ 未コミットの変更 ＋ REV-170）。
- `apply_revision.py REV-170 --dry-run --check` → 新しい違反 0・未判定 0。本適用 exit 0。render_views・generate_params・render_migration_review → 実行。
- `run_checks.py` → exit 1。design_check `{"合格": 12, "違反": 0, "未判定": 5}`。移行の違反と検査器の試験の不合格 1 件（88 件中）は、intent.md の未記録の編集による既存のもの。
- 未実行: TLS での RTCM の受信（上記）、単体試験（コードを変えていない）。

## 7. 承認・確認待ち

- DEC-361（中継の TLS 対応：推奨 a stunnel4。apt の導入は人）、DEC-362（パスワードの変更の検討）。関係: DEC-298（v1・TLS なしの受け入れの問い。TLS 専用と分かったので前提が変わる）、DEC-301（この便で実施）。

## 8. 残るリスク・次

- RTCM が実際に流れるか、受信機が RTK fix になるかは未確認。受信機の USB が VM につながり直した後、ntrip_probe3.py（TLS＋GGA、RTCM の数と種類だけを出す）で確かめられる。
- 2 アンテナの向きが出ない件（第144便）は別に調べる。
- コミットはまだ。
