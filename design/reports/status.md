# 現状の要約（status.md）

最終更新：2026-10-21（REV-117、第84便）。

**引き継ぎ: `reports/handover_2026-10-21.md`**（次のチャットの最初に貼るプロンプトは §0。人の判断待ちの一覧は §5。前回の引き継ぎは `handover_2026-10-17.md`、その §5「Global_localization または Navigation のノードの実装の検討」は未着手）。

**第84便: 次のチャットへの引き継ぎ**（`reports/handover_2026-10-21.md`）。
- 第60〜83便の状態、守ること、人の判断待ち（実装の許可 6 件、決定待ち）、人の作業（ESP32 の書き込みなど）をまとめた。変更はすべて未 commit（HEAD 3341602）。人の申告（2026-10-21）: ESP32 に firmware を書き込み済み。

**第83便: 変更セットの試し適用（--dry-run --check）**（作業記録 `reports/worklog/2026-10-21_bin083_trial_check.md`）。
- 記録の誤りが増えた（第70〜82便で 6 件）ため、`apply_revision.py REV-xxx --dry-run --check` を追加。正本を書かずに検査し、新しい違反だけを示す（あれば終了コード 1）。過去の誤り 2 種を再現して検出を確認。以後は試し適用の後に本適用する。

**第82便: intent.md 第13版、DEC-168 の解消、PRM-10、PRM-78（REV-116・117、DEC-179）**（作業記録 `reports/worklog/2026-10-21_rev116_117_intent_v13_prm78.md`）。
- intent.md 第13版（16 行：自動復帰は上限なく 50 回ごとに理由を記録）を記録、RQ-I086。DEC-168 解消、PRM-10＝理由を記録する区切り 50。影響は G-RECOVERY-COUNT（工程 5-7）。DEC-172: PRM-78 最大後退速度 0.472 m/s（1.7 km/h）、motion_controller での使用は許可待ち。設計検査 違反 0・未判定 5。移行の照合の intent.md の違反は解消。

**第81便: 12 件の試験の修正、intent.md 第12版（REV-114・115、DEC-178）**（作業記録 `reports/worklog/2026-10-21_rev114_115_intent_v12_tests.md`）。
- 試験の修正で gouda_core 単体は Mac 208 合格・VM 216 合格（不合格 0）。intent.md 第12版（107 行、RQ-I085）を記録。rosbag のポップアップは今のまま。**その後 intent.md 16 行が人に編集された（未記録、第13版）**: 「復旧回数が50回を超える度に、理由を記録する。」。意味を確認中（DEC-168）。設計検査 違反 0・未判定 5。

**第80便: ESP32 の USB の切断回数の表示と記録（REV-112・113、DEC-177）**（作業記録 `reports/worklog/2026-10-21_rev112_113_usb_link_counts.md`）。
- 人の承認で実装。vehicle_bridge が事前地図作成・自律走行のセッションの中だけ数え（一時停止・再開で継続）、vehicle/link_status（IFD-51）に出す。monitor は上部と ESP32 の欄に常に表示（ポップアップなし）。切断の記録の理由の文を固定。VM で結合確認。事前地図作成で数えるには DEC-169 の configure の実装が要る（許可待ち）。設計検査 違反 0・未判定 5。

**第79便: vehicle_bridge の USB 再接続（REV-111、DEC-176）**（作業記録 `reports/worklog/2026-10-21_rev111_usb_replug_reconnect.md`）。
- 切断を記録してポートを閉じ、udev のイベントで同じ by-id の名前を開き直して HELLO から再開。lifecycle は変えず、自律走行は切断で一時停止しない（人の決定）。firmware は変えていない（手動は USB に依らない）。VM の単体 5 件合格、実機は未確認。設計検査 違反 0・未判定 5。

**第78便: 「後で検証する項目」の文書（VL-01）**（作業記録 `reports/worklog/2026-10-21_bin078_deferred_verification.md`）。
- 人の指示（転送）で新規 `docs/deferred_verification.md` を作り、VL-01（PC がシリアルを開くと ESP32 がリセットされるか。今のコードは DTR・RTS を設定しない、旧 bridge は False にしていた）を追加。未検証。

**第77便: DR-15 の走査の改訂（REV-110、DEC-175）、uptime_ms の確認、USB の差し直しの改善案**（作業記録 `reports/worklog/2026-10-21_rev110_dr15_scan_usb_uptime.md`）。
- DR-15 はコードだけ（文章を除く）を Python・web・firmware・シェルで走査し、時間の値も未判定にする（`tools/hardcode_scan.py`、許容の一覧 `tools/hardcode_allowlist.json` は空）。DR-15 未判定 19 件。uptime_ms は STATUS を作った時刻と確認（コードの読みのみ）。USB の差し直しの再接続は案のみ（許可待ち）。設計検査 違反 0・未判定 5。

**第76便: 書き込みを待たない方式、rosbag の非同期の停止と進捗、gouda.sh stop の進捗（REV-108・109、DEC-174）**（作業記録 `reports/worklog/2026-10-21_rev108_109_nonblocking_rosbag_stop.md`）。
- 人の許可で実装。vehicle_bridge は os.write で待たない。rosbag の停止はすぐ返し、保存の始まりと同時に monitor のポップアップで進捗、上限なし。gouda.sh stop は上限なし、PRM-77（1 s）ごとに GLIM・rosbag の保存の大きさを表示。VM で実機の rosbag と単体（既知の 12 件以外合格）、ポップアップは DEMO で確認。設計検査 違反 0・未判定 5。commit はしていない。

**第75便: DEC-173（時間の値の扱い）（REV-107）**（作業記録 `reports/worklog/2026-10-21_rev107_dec173_time_values.md`）。
- 通知の集約と STATUS の送信時刻はすでに実装済み（第73便の報告の誤りを訂正）。gouda.sh stop の上限の撤去、rosbag の停止の強制終了の廃止と進捗の表示は人の決定、実装は許可待ち。設計検査 違反 0・未判定 5。

**第74便: 転送された人の発言の記録（REV-106、DEC-170〜172）**（作業記録 `reports/worklog/2026-10-21_rev106_relay_speed_deadband.md`）。
- DEC-170: 最高速度の規則（SR-06・07）は車椅子側の速度上限で守る（人の確定、安全の前提）。DEC-171: 不感帯の補償 案 A を方針として承認（実装は許可待ち）、後退 1.7 km/h の申告。**承認待ち（新規）DEC-172**: 後退の正規化。設計検査 違反 0・未判定 5。

**第73便: DR-15 の未判定 11 件の調査（調査のみ）**（作業記録 `reports/worklog/2026-10-21_bin073_dr15_literal_audit.md`、報告 `reports/dr15_literal_audit_2026-10-21.md`）。
- 11 件はどれも PRM の写しではない（7 件は偶然・誤検出）。設定にない時間の値: vehicle_bridge のシリアル（0.2・0.05・0.5 s）、recorder の 30 s、gouda.sh の 30・10 s（PRM-37 と食い違いの可能性）など。宣言するか許容するかは人の判断待ち。変更なし。

**第72便: PRM-49 を 50 ms に（REV-105、DEC-169）、検査件数の訂正**（作業記録 `reports/worklog/2026-10-21_rev105_prm49_50ms.md`）。
- PRM-49＝50 ms。firmware 再ビルド成功、ホスト試験 OK 278。vehicle_bridge を事前地図作成モードでも起動する件は、起動の段階を人に確認中。設計検査 違反 0・**未判定 5**（DR-15 11 件が REV-103 から。第70・71便の「未判定 4」は誤り）。commit はしていない。

**第71便: A9・A10 の実施、DEC-078・163 の回答、DEC-168（REV-104）**（作業記録 `reports/worklog/2026-10-21_rev104_a9_a10_dec078_163_prm10.md`）。
- 人の許可で test_vehicle_core.py の trial ファイルの前提を直し（12→3 件の不合格）、ホスト試験に PC 途絶後の手動の試験を追加（OK 260）。DEC-078・163 answered、RQ-I020 に補足。**承認待ち（新規）DEC-168**: PRM-10 無制限が intent.md:16 と食い違う。gouda_core 単体 12 件不合格（期待値が古い 2、対角 1 mV、test_motion_core の trial 前提 9）は許可待ち。commit はしていない。

**第70便: DEC-166、車体出力の実車の設定値（REV-103）**（作業記録 `reports/worklog/2026-10-21_rev103_dec166_vehicle_values.md`）。
- 人の回答（原文は台帳）: PRM-14 0.1、09 0.35、41 0.05、16 0.2、42 0.5、15 1.5 s、61 CP2102N の by-id、39 1.111 m/s、40 0.97 rad/s。motion_controller・vehicle_bridge の設定がそろった。A9・A10・方針11 は内容の確認中。人が intent.md に 107 行目を追記（第12版の記録が必要）。設計検査 違反 0・未判定 4。commit はしていない。

**第69便: DEC-164 の回答、firmware のコメントの修正（REV-102）**（作業記録 `reports/worklog/2026-10-21_rev102_dec164_comment.md`）。
- 人の許可。main.cpp の「gain 1x」→「gain 2x (GA=0)」（動作は不変）。`pio run -e esp32dev` 成功、ホスト試験 OK 256、設計検査 違反 0・未判定 4。commit はしていない。

**第68便: DEC-161・DEC-162 の回答（REV-100・101）**（作業記録 `reports/worklog/2026-10-20_rev100_101_dec161_162_answers.md`）。
- 人の回答（原文は台帳）: DEC-162 は電源を切る順番（車体→基板）の運用で扱い、プルダウンは付けない。DEC-161 は不要。REV-100 の ND-17 の追記が DR-06 に当たり REV-101 で書き直した。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第67便: DEC-160 の回答、実車向け firmware のビルド（REV-099）**（作業記録 `reports/worklog/2026-10-20_rev099_dec160_firmware_build.md`）。
- 人の回答（原文は台帳）: 最大 4720・最低 280・フルスケール 4720 mV。設定の検査に合格。`pio run -e esp32dev` 成功（has_config=true）、ホスト試験 OK 256。書き込みは人。test_vehicle_core.py は trial ファイルがなく 12 件不合格（許可待ち）。DEC-161・162・164 は未決。commit はしていない。

**第66便: 案 B1 の段 4、setup.sh に rtklib、apt の str2str の確認（REV-098）**（作業記録 `reports/worklog/2026-10-20_rev098_b1_step4_rtklib.md`、記録 `research/upstream_sensors/rtklib_2.4.3b34_str2str_review_2026-10-20.md`）。
- 人の許可（DEC-165）。setup.sh の apt に rtklib。apt の str2str は raw・エコー無効、URL のデコードなし、状態の形は同じ、NTRIP v1・TLS なし（認証は暗号化されずに流れる）。Point One が v1 を受け付けるかは原本未照合。
- 単体（Mac）: GNSS・NTRIP は合格。`test_vehicle_core.py` の 12 件が失敗（別のセッションの REV-095〜097 の後。DEC-160 の矛盾を含む。そのセッションが対応）。commit はしていない。人の作業: VM で `bash setup.sh`。

**第65便: ESP32 の DAC 出力と基板の配線の実測の記録（REV-097）**（作業記録 `reports/worklog/2026-10-20_rev097_esp32_dac_wiring.md`）。
- 分岐セッションの引き継ぎを記録（人の発言・実測は転記）。DAC は 2 倍の倍率で、フルスケールは USB 5V の実電圧（無負荷 4.72 V）。4800 mV は今の給電では出せない。**承認・実測待ち（新規）DEC-161〜164**（フルスケールの実測、R7 除去で EMC の入力が浮く件（安全）、RQ-I020 の補足、コメントの修正）。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第64便: DAC の最小・最大の変更と STATUS 周期（REV-096）**（作業記録 `reports/worklog/2026-10-20_rev096_dac_range_status_period.md`）。
- 人の指示（DEC-159、原文は台帳）: 中立 2500・最大 4800・最小 200 mV、STATUS 500 ms。PRM-44・45・49 を更新・承認。最大 4800 がフルスケール 4700 を超え firmware の設定検査が不合格（DAC に書かない）。**承認待ち（新規）DEC-160**: フルスケールの値。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第63便: DEC-077・DEC-079 の回答（REV-095）**（作業記録 `reports/worklog/2026-10-20_rev095_dec077_079_answers.md`）。
- 人の回答（原文は台帳）。PRM-43〜46＝2500／230／4700／4700 mV（旧 firmware の値、測定値ではない。Q-03 の確認は残る）、PRM-47＝半径 8 %、PRM-48＝200 ms を承認。人の申告: EMC-270 の基準電圧は未接続、ESP32 から出して GND で返す。firmware_config.yaml に入った。PRM-49（STATUS 周期）が未確定のため実車向けビルドはまだ has_config=false。PRM-46 の「x,y軸の合計値」の意味を人に確認中。
- 全検査: 設計検査 違反 0・未判定 4。移行の照合の違反は drawio（以前から）と extraction 内の .DS_Store（Finder、10-19）。commit はしていない。

**第62便: コードレビューの指摘 8 件の修正（REV-094）**（作業記録 `reports/worklog/2026-10-20_rev094_review_fixes.md`）。
- 人の許可（DEC-158）。中継の状態の追跡を起動ごとに新しく、標準エラーは例外があっても読み続ける、数値の値に引用符の案内、URL の伏せ字を最後の @ まで、秘密のファイルは 1 回だけ読む、中継を Driver の項目で扱う（key の分岐を削除）、supervisor の中継の試験（偽の str2str、VM で実行）。
- 単体: Mac 199 件合格・3 件 skip、VM 202 件合格。全検査: 設計検査 違反 0・未判定 4。commit はしていない。次: 段 4 の許可待ち。

**第61便: 自律走行に要る node と詳細設計書の照合（調査のみ）**（作業記録 `reports/worklog/2026-10-20_bin061_autonomy_node_inventory.md`）。
- 自律走行の node は正本 ND と launch で 20 余り。ND-07 は未実装（TR-05 で開始を拒否）。スプレッドシートは module 単位で node の一覧なし、不採用の Safety_gate 等が自律走行の行に残る、ND-18・ND-13・ND-19 の行なし、M-039 が二つの意味（section_executor と GNSS）で衝突。正本も ND-10 の内部 node 名の一部、Hokuyo の扱い、ND-08 の lifecycle の食い違いあり。登録は人の了承待ち。正本・コードは変えていない。検査は未実行。

**第60便: 案 B1 の段 3、中継の起動の実装（REV-093）**（作業記録 `reports/worklog/2026-10-20_rev093_b1_step3_relay.md`）。
- 人の許可（DEC-157）。supervisor が str2str を PRM-76 で見張って起動する。起動用の command（秘密）はメモリだけ、記録は伏せ字の command と状態の変化だけ。終了しても作り直さない。新しい `gouda_core/gouda_core/ntrip_relay.py`。
- 単体: Mac 194 件合格・1 件 skip、VM 195 件合格。全検査: 設計検査 違反 0・未判定 4。ROS 上の動きは未確認（段 4・6）。commit はしていない。次: 段 4 の許可待ち。

**第59便: DEC-156 の回答（REV-092）**（作業記録 `reports/worklog/2026-10-20_rev091_b1_step3_design.md` の追記）。
- 人の回答「DEC-156 を承認する。」。段 3 の設計（提案 §9、終了の扱いは案 A）が決まった。次: 段 3 の実装の許可待ち。commit はしていない。

**第58便: 案 B1 の段 3 の設計の案（REV-091）**（作業記録 `reports/worklog/2026-10-20_rev091_b1_step3_design.md`）。
- 中継（str2str）を supervisor の子プロセスにし PRM-76 で見張る。起動の時の記録が全 command をそのまま書くことを確かめ、記録用と起動用の command を分ける案に。標準エラーからは状態だけを取り、終了しても同じ同一性では作り直さない（提案 §9）。
- 承認待ち（新規）DEC-156。実装はしていない。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第57便: Google スプレッドシートの gnss_localization_submodule の行の記入**（作業記録 `reports/worklog/2026-10-20_bin057_sheet_gnss_row.md`）。
- 人の指示「spreadsheetを更新せよ」で、内蔵ブラウザから「モジュール定義」41 行目（M-039）を記入し、CSV の書き出しで確かめた。内容は草案（独立の供給元、受信機の中で測位、NTRIP は str2str で中継、未承認の点は備考）。リポジトリの xlsx の写しは変えていない。提案の文書は第1版のまま（第2版は未作成）。検査は未実行。

**第56便: 案 B1 の段 2、gnss_config の実装（REV-090）**（作業記録 `reports/worklog/2026-10-20_rev090_b1_step2_gnss_config.md`）。
- 人の許可（DEC-155）。gnss_rtk.yaml は ntrip の節だけを読み、誤り・広い権限・旧い書式では使わない。ドライバには NTRIP の値を渡さず、有効なときだけ serial_1.port = USB2（PRM-75）。ドライバは補正なしでも起動する。
- 単体: Mac・VM とも 188 件合格・1 件 skip。全検査: 設計検査 違反 0・未判定 4。commit はしていない。VM の Gouda には入っていない。次: 段 3 の許可待ち。

**第55便: DEC-154 の回答と PRM-75・76（REV-089）**（作業記録 `reports/worklog/2026-10-20_rev089_dec154_prm75_76.md`）。
- 人の回答「DEC-154 を承認する。」。PRM-75（補正の入力の接続先 USB2）、PRM-76（中継の接続先 if02 の by-id）を承認値で足した。生成物の septentrio_gnss_driver.yaml に入った（gnss_config はまだ読まない）。
- 全検査: 設計検査 違反 0・未判定 4。単体 184 件合格。commit はしていない。次: 段 2 の実装の許可待ち。

**第54便: 案 B1 の段 2 の設計の案（REV-088）**（作業記録 `reports/worklog/2026-10-20_rev088_b1_step2_design.md`）。
- gnss_rtk.yaml は ntrip の節（5 項目）だけ、中継だけが読む。誤りのときは中継だけ止め、ドライバは補正なしで起動。新しい PRM 2 つ（受信機の接続先の名前 USB2、中継の接続先 if02 の by-id）。他は雛形のまま（提案 §8）。
- 承認待ち（新規）DEC-154。実装はしていない。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第53便: 案 B1 の段 1、記録の伏せ字（REV-087）**（作業記録 `reports/worklog/2026-10-20_rev087_b1_step1_redaction.md`）。
- 人の許可（DEC-153）。sensor supervisor が他のプロセスの command line を記録する前に、ntrip の URL 全体と URL の user:password を伏せ字にする（device_watch.redact_command・command_lines）。
- 単体の試験 5 件を追加。Mac・VM（一時の写し）とも 184 件合格・1 件 skip。全検査: 設計検査 違反 0・未判定 4。commit はしていない。VM の Gouda には入っていない。
- 次: 段 2 の許可待ち。

**第52便: DEC-151 の回答と実装の段（REV-086）**（作業記録 `reports/worklog/2026-10-20_rev086_dec151_steps.md`）。
- 人の回答: 「DEC-151 を承認する。実装の各段はそれぞれ許可を求めること。」
- 実装を 6 段に分けた（提案 `proposals/ntrip_gga_proposal.md` §7）。段 1（記録の伏せ字）の許可待ち。実装はしていない。commit はしていない。

**第51便: DEC-139 の回答（案 B1）と秘密の扱い（REV-085）**（作業記録 `reports/worklog/2026-10-20_rev085_dec139_b1_secrets.md`）。
- 人の回答: 「B1を採用する。NRTKのパスワード、ユーザー名等はリモート、git, ログ、rosbag, 記録文書にも載せてはならない。」
- 漏れうる経路をソースで確かめた（中継の引数、supervisor の cmdline の記録、str2str の状態の出力、ドライバの params）。対策の案を提案 `proposals/ntrip_gga_proposal.md` 第3版 §5 に。
- 承認待ち（新規）: DEC-151（B1 の実装の案）、DEC-152（秘密を書かない検査ルールの案）。実装はしていない。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第50便: DEC-139 に案 B3 を追加（REV-084）**（作業記録 `reports/worklog/2026-10-20_rev084_dec139_option_b3.md`）。
- 人の指示で、提案 `proposals/ntrip_gga_proposal.md` を第2版に（案 B3: Gouda の専用 node が NTRIP と USB2 を中継。B1 との比較、共通の注意）。DEC-139 の note に追記。
- 推奨は変えない: まず B1（str2str か mrtk relay）で RTK fix を確かめ、必要なら後で B3。実装はしていない（DEC-106）。
- 全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第49便: DualAnt の後のドライバの屋内の検査（REV-083）**（作業記録 `reports/worklog/2026-10-20_rev083_gnss_driver_indoor_check.md`、記録 `research/vehicle_pc/2026-10-20_gnss_driver_indoor_check_dualant.txt`）。
- 受信機を VM につなぎ直した後、ドライバが by-id の USB1 で起動し設定を終えた（拒否は既知の sntp だけ）。方位のオフセット 90 度（/config revision 18）。PVT・方位・観測 10 Hz。
- 屋内のため観測 0、測位・方位とも mode 0（期待どおり）。干渉・なりすましなし。受信機のポートには触れていない。
- 次: 屋外で副アンテナと方位の確認。全検査: 設計検査 違反 0・未判定 4。commit はしていない。Gouda は VM で動いている。

**第48便: 複数のセッションの番号の重なりの解消と、登録済みの証拠のファイルの修正（REV-081・082）**（作業記録 `reports/worklog/2026-10-20_rev081_082_shared_numbering.md`）。
- 人の指示「この問題を解決せよ」（DEC-150）。status.md の便を時系列に並べ直した（第45便 P6 の調査、第46便 運用の条件、第47便 ガイドとアンテナ間隔）。
- **REV・DEC・便の番号は `design/tools/reserve_ids.py` で予約してから使う**（排他的なファイルの作成。apply_revision は予約だけの REV を拒否する。試験 5 件合格）。別のセッションにも知らせた。
- AI の誤りを直した: REV-075 で登録した証拠のファイル 2 つに後から追記して SHA-256 が合わなくなっていた。元に戻し、追記を FILE-MOSAIC-MRTK-QUERY-FOLLOWUP に分けた（REV-082）。
- 全検査: 設計検査 違反 0・未判定 4。移行の検査の違反は人の drawio と .DS_Store だけ。commit はしていない。

**第47便: mosaic-go の使い方のまとめと開発のセッションへの共有、アンテナ間隔の確認（REV-080）**（作業記録 `reports/worklog/2026-10-19_p6_dual_antenna_survey.md` の追記、記録 `research/mosaic_go_g5_p6_usage_guide_2026-10-20.md`）。
- 位置・速度・方位は受信機の中で計算され、RTKLIB は NTRIP の中継（str2str）だけ、という整理を開発のセッションに送った（情報の共有）。
- 人が /config に GNSS のアンテナ位置を入れた（main (0.45, 0.17, 0.77)、aux1 (0.45, -0.17, 0.77) m、左右 0.34 m）。人の確認 DEC-149: 0.34 m が正しく、DEC-130 の 0.6 m は古い値。
- 全検査（REV-080 適用後）: 終了コード 1。設計検査 違反 0・未判定 4。不合格は人の drawio と .DS_Store の不一致だけ（以前と同じ）。commit はしていない。受信機には触れていない。

**第46便: 本番と実験の運用の条件の記録**（作業記録 `reports/worklog/2026-10-20_rev079_operation_condition.md`）。
- 分岐したセッションで人が発言した条件を原文で記録（DEC-147）: 本番はスタート位置に並んだらすぐ発進。fix を待つ時間は取れるが、八の字旋回などはできない。実験は手間をかけてよい。今の設計（較正は実験、本番は静止の初期化）と食い違わない。
- 承認待ち（新規）DEC-148: intent.md:14 への追記の案（`proposals/intent_edit_requests.md` §3）。
- 全検査: 設計検査 違反 0・未判定 4。commit はしていない。Gouda は VM で止めたまま。

**第45便: mosaic-G5 P6 のデュアルアンテナの方法の調査**（作業記録 `reports/worklog/2026-10-19_p6_dual_antenna_survey.md`、記録 `research/gnss_mosaic_g5_p6_dual_antenna_survey_2026-10-19.md`）。
- 公式のサポート記事と Hardware Manual v2.0.0（2026-05）: P6 は方位に対応するが出荷時は無効、DualAnt → Boot 保存 → reset で有効。第43〜44便の手順と同じ。ROS ドライバ・ArduPilot・PX4 は sfm を送らない。
- 条件: 前置増幅 15〜35 dB（AGC 30〜50 dB）、2 本の差 5 dB 以内、ANT_2 を空けない。屋外の確かめ方は記録 §5。受信機・VM には触れていない。検査は未実行。
- 2026-10-20 追記: 人が渡した Reference Guide v1.1.1 で照合（記録 §7）。Nominal は「普通は SingleAnt、方位が主目的の製品では DualAnt」→ P6 では単一アンテナ。原本未照合は解消。firmware の更新は不要。

**第44便: DualAnt の Boot 保存と受信機の reset**（作業記録 `reports/worklog/2026-10-19_rev075_mosaic_dual_antenna_query.md` の追記）。
- 人の許可（DEC-146）で Gouda を止め、USB2 から eccf, Current, Boot と exeResetReceiver, Hard, none を送った。reset で USB が切れ返答は記録できず。by-id は作り直された（if02 は ttyACM2 に）。
- reset の後: gfm **DualAnt**、gga MultiAntenna, Fixed。Boot 保存と reset は効いた。
- **Gouda は VM で止めたまま**。次: Gouda を起動し、屋外で副アンテナの観測と方位を確かめる。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第43便: sfm, DualAnt を Current にだけ送った**（作業記録 `reports/worklog/2026-10-19_rev075_mosaic_dual_antenna_query.md` の追記）。
- 人の許可（DEC-145）で USB2 から送った。gfm Nominal → sfm, DualAnt 受理（$R:）→ gfm DualAnt。Boot 保存・再起動はしていない。効くのは次の reset から（マニュアル 1.0.1）。
- **注意**: ドライバ（configure_rx true）は起動のたびに eccf, Current, Boot を送るので、Gouda の再起動や USB の抜き差しでドライバが起動し直すと DualAnt が Boot に保存される。Gouda は VM で動いたまま。
- 次（人の判断）: Gouda を止めて Boot 保存と受信機の reset、屋外で副アンテナの観測と方位を確かめる。全検査: 設計検査 違反 0・未判定 4。commit はしていない。

**第42便: gnss_localization_submodule の責務と非責務（提案）**（作業記録 `reports/worklog/2026-10-19_gnss_submodule_responsibility.md`、提案 `proposals/gnss_localization_submodule_responsibility.md`）。
- drawio の新しい箱（中に MRTKLIB、入力は mosaic-go だけ、出力の線なし）とシートの空の行に対し、責務・非責務・シートの行の案を作った。承認待ち Q-A〜Q-F（位置の計算は受信機かMRTKLIBか、Global_localization の下位か、出力の座標、enu→map の発行元、方位なしの初期化、シートへの書き込み）。正本は変えていない。検査は未実行。

**第42便: DEC-144 の承認と frontend mode の値の照会**（作業記録 `reports/worklog/2026-10-19_rev075_mosaic_dual_antenna_query.md` の追記）。
- 人が DEC-144 を承認（先に値の一覧を照会して報告）。`help, setFrontendMode` は引数名 fmMode だけで値の一覧を返さず、`help, fmMode` はエラー。firmware 1.1.x の資料も見つからない。DualAnt が 1.1.1 の値かは未確認のため、設定には進まず報告した（REV-076）。
- 全検査: 設計検査 違反 0・未判定 4。移行の検査は第41便と同じ（人の drawio・.DS_Store）。commit はしていない。Gouda は VM で動いたまま。

**第41便: 副アンテナの確認（マニュアルと MRTKLIB での照会）**（作業記録 `reports/worklog/2026-10-19_rev075_mosaic_dual_antenna_query.md`、記録 `research/gnss_mosaic_g5_dual_antenna_2026-10-19.md`・`research/vehicle_pc/2026-10-19_mosaic_mrtk_query.txt`）。
- 人の確認: アンテナを入れ替えても main 側だけ受信（アンテナ・ケーブルは正常）。
- 人の許可（DEC-143）で MRTKLIB の mrtk relay から USB2 に照会だけ: 能力 Main+Aux1、許可は 2 本のアンテナと方位、方位の計算 MultiAntenna, Fixed、**frontend mode は Nominal**（マニュアル 1.0.1 の値 SingleAnt・DualAnt にない。意味は原本未照合）。型・許可は原因ではない。
- マニュアル（Hardware Manual §4.2.3.2）: 2 本で動かすには setFrontendMode DualAnt を Boot に保存して再起動する。承認待ち（新規）**DEC-144**（値の一覧の照会 → DualAnt・Boot 保存・再起動 → 屋外で確認）。
- 全検査: 設計検査 違反 0・未判定 4。移行の検査は人の drawio と macOS の .DS_Store 2 件（AI は触っていない）。commit はしていない。Gouda は VM で動いたまま。

**第40便: GNSS のドライバの最初の起動（VM）**（作業記録 `reports/worklog/2026-10-19_rev073_gnss_first_start.md`、記録 `research/vehicle_pc/2026-10-19_gnss_first_start.txt`）。
- ブランチを commit（3341602）・push、人が VM を更新。gouda.sh start でドライバが USB1（by-id）で起動し設定を終えた。受信機は `sntp, on` を拒否（ファームウェア 1.1.1）。
- 起動の後の gso: Stream1（状態、500 ms）・Stream3（PVT・方位など、100 ms）が USB1、ほかは off。USB2 の NMEA は止まった。
- 屋内で単独測位（衛星 13〜17、水平精度 約 11 m）。屋外でも単独測位（衛星 16〜21、約 6.4 m）。**方位は出ない**: 観測は主アンテナだけで、副アンテナの観測が一つもない（G-GNSS-NO-HEADING、REV-074）。Gouda は VM で動いたまま。

**第39便: 最初の起動の前の受信機の記録**（作業記録 `reports/worklog/2026-10-19_rev072_mosaic_before_first_start.md`、記録 `research/vehicle_pc/2026-10-19_mosaic_before_first_start.txt`）。
- 人の許可（DEC-142）で USB2 から照会。gso: Stream1〜3 は off、Stream4〜10・Res1〜4 は空（10/17 の Stream4 は残っていない）。getDataInOut: 全接続先が入力 auto・出力 SBF+NMEA。USB2 の NMEA では単独測位。
- 最初の CR で受信機の入力に残っていた GGA の断片が無効なコマンドになった（以前に NMEA が送り返されていた。設定は変わっていない）。
- 生の記録は位置を含むので VM にだけ置いた。commit はしていない。

**第38便: DEC-140 の回答（configure_rx true）、起動の前後の記録の道具、DEC-139 と GGA の提案**（作業記録 `reports/worklog/2026-10-19_rev070_071_dec140_query_tool_ntrip.md`）。
- PRM-74 を承認値 true に。**このブランチで Gouda を起動するとドライバが起動し、受信機の全出力を止めて Boot に保存する**（VM の ~/gouda_ws は main なので、まだ起動しない）。
- 記録の道具 `gouda_core/gouda_core/septentrio_query.py`（照会だけ、by-id、raw・エコー無効を確かめてから）。単体 180 件（Mac・VM）合格。実行は人の許可の後。
- 提案 `proposals/ntrip_gga_proposal.md`: DEC-139 の推奨を案 B1 に（ドライバが USB2 を補正の入力・GGA の出力に、RTKLIB の str2str が中継。GGA は受信機が 1 秒ごと）。
- 全検査は終了コード 1（人の drawio だけ）。commit はしていない。

**第37便: 人の指示 DEC-141（PRM-65 の承認、by-id の名前だけ、DEC-140 の材料）**（作業記録 `reports/worklog/2026-10-19_rev069_by_id_prm65_dec140_material.md`）。
- PRM-65 を承認値（serial:/dev/serial/by-id/usb-Septentrio_Septentrio_USB_Device_0100012541-if00、USB1）に。configure_rx を PRM-74（未確定、DEC-140）にし、決まるまでドライバを起動しない。
- 実装: IMU・GNSS とも /dev/serial/by-id/ の名前だけを受け付け、それ以外はドライバを起動せず理由を記録。単体 177 件（Mac・VM）合格、同時接続で番号が入れ替わっても取り違えないことを確認。
- DEC-140 の材料: `proposals/mosaic_receiver_setup_configure_rx_false.md`（USB1 の 2 つの SBF のストリーム、sga・sto、人の手順、Boot には保存しない）。ドライバは起動しておらず、受信機のポートには触っていない。
- 全検査は終了コード 1（人の drawio だけ）。commit はしていない。

**第36便: 上流 GNSS ドライバのソースの確認（人の手順 1）**（作業記録 `reports/worklog/2026-10-19_rev068_septentrio_source_review.md`、記録 `research/upstream_sensors/septentrio_gnss_driver_1.4.8/source_review_2026-10-19.md`）。
- シリアルは raw・エコー無効で開く。configure_rx true は起動のたびに受信機の全出力を止め、最後に Boot に保存する（人の資料 §5・§6 と合わない）。主アンテナの位置は補正しない（方位のオフセットだけ）。
- 承認待ち（新規）: DEC-140（configure_rx を使うか。推奨は使わない）。人の手順 2（PRM-65 を if00）は承認待ち。ドライバはまだ起動していない。
- 全検査は終了コード 1（人の drawio だけ）。commit はしていない。

**第35便: DEC-125・135・136 の回答、GNSS の較正の検証の道具、mosaic-go の VM への接続**（作業記録 `reports/worklog/2026-10-19_rev067_gnss_calibration_tool_mosaic.md`）。
- 人の回答: DEC-136 承知、DEC-135 一旦承認（人の実験走行の実データで検証、だめなら不採用）、DEC-125 しばらく VM で実機試験・mosaic-go は USB・補正は NTRIP（Point One TrueRTK）。
- 実装: 較正の検証の道具 `gouda_core/gouda_core/gnss_calibration.py`（地図への組み込みはしない）、地図作成の時の /config の写しを原図の横に。単体（Mac 173 件・VM 全件）と VM の記録の試験は合格。
- mosaic-go は VM で if00（USB1）・if02（USB2、NMEA）のシリアルとして見え、USB イーサネットはない。PRM-65 の候補は if00。DEC-139 の案 A は今の接続ではできず、推奨の見直しが要る。
- **注意**: AI がポートを raw・エコー無効にせずに読んだため、NMEA が受信機へ送り返された可能性がある（人の資料 §2）。
- 承認待ち（新規）: DEC-138（VM の起動にも Fast DDS の設定）、DEC-139（NTRIP の受け方）。VM の ~/gouda_ws は main のまま。
- 全検査は終了コード 1（人の drawio だけ）。commit はしていない。

**第34便: GNSS の承認事項の回答の記録と、ソフトウェアでの較正の再検討**（作業記録 `reports/worklog/2026-10-18_rev065_gnss_answers_calibration.md`）。
- 人の回答: DEC-131 承認、DEC-132 は調査結果を添えてソフトウェアの較正の再検討、DEC-133 条件付き承認（条件は DEC-137 の回答で記録: REV-066、分岐したセッション。人の操作で初期化を始める、失敗は止めて表示、未収束でも警告だけ、人の指定を残す、静止の判定と値は実機検証の後、対応のある地図だけ、PC 再起動後も同じ、方式によらない契約）、DEC-128 は許可の取消（不採用）、DEC-134 保留（過剰な安全策の可能性）。
- 再検討（合成のデータ。`research/vehicle_pc/2026-10-18_gnss_calib_feasibility/`）: 較正の走行ならレバーアーム 1〜2 mm・取付 Yaw 0.02 度・遅延 5 ms の誤差で同時に推定できる。ant_z は平地で決まらない。直線だけでは遅延を誤り、標準偏差でも見抜けない。方位の定義の取り違えは残差で分かる。
- 提案 `proposals/gnss_initial_pose_design.md` 第3版 §11。承認待ち DEC-135（ソフトウェアの較正、DEC-127・132 の置き換え）、DEC-136（次の実機試験に較正の動き）。実装はしていない。
- 全検査は終了コード 1（人の drawio だけ）。commit はしていない。

**第33便: DEC-126 の実装（地図作成の間の GNSS の記録）と、人が貼った GNSS の仕様との照合**（作業記録 `reports/worklog/2026-10-18_rev063_gnss_mapping_record.md`）。
- 人の回答: 「DEC-126は許可。」同じメッセージに GNSS 活用の実装仕様の文書（扱いの指示なし。DEC-130、写し `research/gnss_reference_spec_2026-10-18.md`）。
- 実装: 地図作成の間、GNSS（IFD-47〜50。方位の共分散を IFD-50 として追加）を gnss.jsonl に全項目のまま記録し、原図の横に置いて source_manifest.json に SHA-256 と行数を書く。Mac・VM の単体 168 件 OK。VM の試験スタックで地図作成の開始・終了の記録と原図への登録が合格（REV-064、FILE-GNSS-MAPPING-RECORD-VM-TEST）。受信機での実機の記録は未実行。
- 提案 `proposals/gnss_initial_pose_design.md` を第2版に（仕様との照合 §9、上流 README の確認 §10）。新しい承認待ち DEC-131〜134。DEC-128 は取り下げを推奨（代わり DEC-133）。
- 全検査は終了コード 1（人の drawio だけ）。commit はしていない。

**第32便: 工程 5-6 の実装（人の許可 DEC-120〜124）と VM の試験**（作業記録 `reports/worklog/2026-10-17_rev061_062_stage56_implementation.md`、記録 `research/vehicle_pc/2026-10-17_stage56_vm_test.txt`）。
- 人の回答: 「DEC-120〜124 をすべて許可する」。
- 実装: GNSS の取込み（ND-19、supervisor が起動、monitor に表示）、静的 TF（ND-13、/config に GNSS のアンテナ）、Nav2（RPP・NavFn・velocity_smoother・SpeedFilter、collision_monitor なし、自律走行の間だけ active）、mode_manager の TR-05・06・07・08・10・11・12、ND-08（GLIM の odometry だけ＋中継）、ND-11 の TwistStamped、monitor の「自律走行の準備」、setup.sh に Nav2 と GNSS のドライバ。
- 実車では: ND-07 がないため自律走行の開始は拒否。Nav2 は未確定の値（PRM-11・17・18・66〜73）のため起動しない。GNSS は接続先（PRM-65）が未確定のため起動しない（DEC-125）。
- VM の試験（loopback_sim が ND-07・08 の代わり、ESP32 は模擬）: 開始の拒否 2 件、開始 → 適用中で hold の解除 → 最後の waypoint で一時停止（TR-08）、終了・一時停止・再開・走行中の終了。不具合 2 件を直した（SpeedFilter の topic の名前空間、静的 TF の置き換え）。再現しない不具合 1 件（最初の goal の失敗: G-NAV2-FIRST-GOAL）。単体 166 件 OK（Mac・VM）、5-5 と前回の試験の再実行も合格。
- 自律判断で TF の木を直した（base_link→base_footprint。odom→base_link と合わせて base_link の親を一つに）。人の確認を求める。
- 提案: GNSS による初期位置の詳細（`proposals/gnss_initial_pose_design.md`）。承認待ち DEC-126〜129。実測・確認待ち DEC-125。
- 全検査は終了コード 1（原因は人の drawio だけ。設計整合性は違反 0、DR-11 の未判定は 67 件に）。commit はしていない。

**第31便: DEC-116 の実装（試験スタックの Fast DDS の設定）と、工程 5-6 の Global_localization・Navigation の検討（提案）**（作業記録 `reports/worklog/2026-10-17_rev060_stage56_study_dec116.md`、提案 `proposals/stage56_navigation_localization_plan.md`）。
- 人の回答（DEC-116）: 許可。`gouda_core/test/stack.sh` だけに `gouda_core/test/fastdds_test_stack.xml` を入れた（gouda.sh・x86 機は変えていない）。VM で前回の試験が同じ結果、約 2 MB の点群の配送が 70・86/200 → 178・182/200（FILE-DEC116-FASTDDS）。
- 人の指示（DEC-119）: Global_localization または Navigation のノードの実装を検討して報告。実装なし（DEC-106）。
- 推奨: Navigation（Nav2 の構成と mode_manager の client、TR-05）を先に作り、VM で nav2_loopback_sim を使って車体なしで試験。GNSS の取込み（受信・記録・表示）は次の実機試験の前に。ND-08（GLIM の odometry だけ）は方式に依存しない。ND-07 は DEC-115 と GNSS の初期位置の設計の後。
- 分かったこと: setup.sh は Nav2 を入れない（x86 機の Nav2 の有無は未確認。「実車PC の Nav2 1.3.13」の記録は VM のもの）。ND-13（静的 TF）は未実装。septentrio_gnss_driver は apt に Jazzy 1.4.8。
- 承認待ち（新規）: DEC-120（順序）、DEC-121（Nav2 の導入）、DEC-122（Nav2 の構成の選択、ND-09・ND-13 の直し）、DEC-123（GNSS の取込み、ND-08）、DEC-124（GNSS による初期位置の方針）。
- 全検査は終了コード 1（原因は人の drawio だけ。設計整合性は違反 0）。commit はしていない。

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

- 移行が正確：作業ツリーでは**違反 1 件**（2026-10-18、REV-074 適用後）。人が編集中の移行の原資料 `design/docs/SystemArchitecture.drawio` の SHA-256 が baseline と違う（`reports/input_integrity.json`）。それ以外の原資料・抽出結果・baseline は一致。REV-050 の時点（コミット 6950a1a）では合格。drawio の扱い（新版として記録するか、変更を戻すか）は人の判断。
- 設計検査に合格：**未判定**。設計整合性 17 ルール 違反 0・未判定 4（DR-04 5 件、DR-05 2 件: RQ-I027・RQ-I072 は問題／衝突のみで対応、DR-10 2 件: 版照合、DR-11: 未確定値 59）。検査違反 0 件は未判定の解消でも実車適合の証明でもない。
- ソフト試験合格：**工程5-1〜5-5 が合格**（5-5: TS-07・TS-13・TS-19 PC 側・TS-12・TS-30 を Ubuntu で、TS-17・18・19・29 を firmware 中核のホスト試験と Python 模擬で。FILE-VEHICLE-PC-STAGE55）。5-3・5-4 はセンサーなし、5-5 は ESP32 実機・ゲームパッド・車体なしの範囲。**工程 5-6 は一部**（2026-10-17、VM、loopback_sim を ND-07・08 の代わりに: TS-01・05・15・21 の一部と TS-35〜38 の単体・VM の部分。FILE-STAGE56-VM-TEST。ND-07 は未実装、実車・x86 機は未実行。完了ではない）。TS-02〜04・06・08〜11・14・16・20・22 は未実行。
- 実車検証済み／実車投入可能：**人の判断待ち**。実車試験は未実施。承認済みの実車値は PRM-07・08・13・21 の 4 件のみ。DAC 電圧（PRM-43〜46）・手動仲裁（PRM-47・48）は REV-095 で承認（DEC-077・079）。PRM-49 は REV-096 で 500 ms。最大 4800 mV がフルスケール 4700 mV を超えるため、DEC-160 の回答まで firmware は DAC に書かない。DEC-050 の実機照合は未実施。

## 検査結果の件数（`design/.venv/bin/python design/tools/run_checks.py`、REV-074 適用後の作業ツリーで終了コード 1。原因は人が編集中の drawio だけ。下の表は REV-050 の時点の値で、違う所を注記した）

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
| 判断台帳 | 150 件（REV-085 時点。pending 21: 021・022・024・050・077・078・079・098・099・100・101・104・105・107・115・127・129・134・138・148・152（DEC-139 は REV-085、DEC-151 は REV-086、DEC-154 は REV-089、DEC-156 は REV-092 で answered）。以前の経緯: DEC-150 answered（REV-081）。pending 21（REV-080: DEC-149 recorded、pending は変わらず）: DEC-021・022・024・050・077・078・079・098・099・100・101・104・105・107・115・127・129・134・138・139・148。REV-072: DEC-142 answered、REV-075: DEC-143 answered、REV-076: DEC-144 answered、REV-077: DEC-145 answered、REV-078: DEC-146 answered、REV-079: DEC-147 recorded・DEC-148 pending。以前の経緯: REV-067: DEC-125・135・136 を answered、DEC-138・139 を pending。pending 21: DEC-021・022・024・050・077・078・079・098・099・100・101・104・105・107・115・127・129・134・138・139・140。REV-068: DEC-140 を pending。REV-069: DEC-141 を answered（PRM-65 承認）。REV-070: DEC-140 を answered（PRM-74 承認）。pending は DEC-140 を除いた 20） | | |

## 承認待ち・実測待ち・人の作業・提案

- **承認待ち（第34便、REV-065・066）**: DEC-135（ソフトウェアの較正）、DEC-136（較正の走行）。DEC-133 の条件は DEC-137 で回答済み。DEC-127 は DEC-135 での置き換えを推奨、DEC-129・134 は保留。提案 `proposals/gnss_initial_pose_design.md` 第3版 §11.4。**実測・確認待ち**: DEC-125（x86 機と mosaic-go の接続、RTK の補正の受け方）。DEC-115 は保留のまま（ND-07 が止まっている）。
- **人の確認（第32便）**: 静的 TF の向きを base_link→base_footprint に直した（自律判断、作業記録 §3）。
- 人の作業（第32便）: x86 機への反映（setup.sh が Nav2 と GNSS のドライバを入れる。sudo）。実車値 PRM-65〜73 の決定（Nav2 を実車で起動する前に要る）。

- **承認待ち（第25便、REV-044）**: DEC-101 旧実装のファイル（scripts/、gouda_gui/ など、third_party/external.repos、patches/）の扱い。推奨: 案 A（旧 scripts/setup.sh を止まるようにし、残りは 5-6 の設計で再利用の有無を確かめてから整理）。止まる作業: なし。
- 人の作業（VM）: 古い NetworkManager の接続 gouda-hesai 2 つ（enp0s5 に 192.168.1.100）の削除の判断、時刻同期の有効化（`sudo timedatectl set-ntp true`）。
- **承認待ち・実測（第24便、REV-042）**:
  - DEC-098 地図の変換の暫定の推奨値（PRM-33 0.1 m、PRM-34 0.1 m、PRM-35 0.15 m、PRM-36 1.2 m、PRM-38 1、PRM-62 0.5 m、PRM-63 10 度、PRM-64 1.0 m。高さは地面から）。推奨: 承認。止まる作業: 実車の設定での自動変換と地図タブの既定値。
  - DEC-097 の「条件付き承認」の条件の内容（回答に記載なし。確認中）。
  - 実測 DEC-099（XT-32 で地面が映るか）、DEC-100（移動して作った原図の点の密度、GLIM の処理周期・CPU 負荷・保存時間）。実機試験 TS-34 で測る（人の協力: 移動しての地図作成）。
  - 回答済み: DEC-093（高さの基準は地面）、DEC-094（B）→ DEC-096（C: 測ってから決める）、DEC-095（3D 点群地図と段差・坂の地図も作る）、DEC-097（A、条件付き）。
- **承認待ち（第18便、REV-027 で登録）**:
  - （REV-095 で回答済み）DEC-077 新 firmware の DAC 電圧の初期登録値（旧 firmware 記載の要求値 2500／230／4700／4700 mV を Q-03 実測までの初期値として承認するか）。推奨: 承認。止まる作業: 実車向け firmware の書き込み。
  - DEC-078 基本契約 5 件の stub 試験を 5-5 の完了条件に含める案（`docs/implementation_stages.md` §5）。推奨: 含める。
  - （REV-095 で回答済み）DEC-079 手動仲裁の既存値の維持（deadzone 8 %、中立安定 200 ms）。推奨: 維持。
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
- 止まっている: 実車の設定での自動変換と地図タブの既定値（DEC-098）、実車向け firmware の書き込み（DEC-160 のフルスケール待ち）、実車試験、DEC-050。

## 主要ファイルの場所（CLAUDE.md 1.9 の対応表。パスはリポジトリ `tsukuba-autonomous-robot/` 相対）

| 役割 | 場所 | 備考 |
|---|---|---|
| 設計意図（人が所有） | `design/intent.md` | 第11版（SHA a7a03a31…、106 行。82 行: DEC-113、14 行: DEC-118 を人が編集）。旧版は `baselines/migration_v1/intent.md`、`baselines/intent_history/` |
| 正本（YAML） | `design/model.yaml`、`design/schema.json`（1.1） | 変更は `revisions/REV-xxx.yaml` → `tools/apply_revision.py`。最新 REV-074。次は REV-075、DEC-143 |
| 正本（Markdown） | `design/docs/` | `map_conversion.md`（地図の変換と地図作成の実機試験の手順）、`sensor_supervision.md`、`implementation_stages.md`、`esp32_protocol_v4.md`（5-5 のプロトコルと firmware の振る舞い）、`vehicle_output_timing.md`、`speed_filter_design.md`、`regulations_2026.md`、`git_management_plan.md`、`deferred_verification.md`（後で検証する項目） |
| 判断台帳 | `model.yaml: decisions`（DEC-001〜152） | ビュー: `generated/pending_classification.md`、`conflicts.yaml`、`intent_open_items.yaml`、`generated/human_decisions_r2.md` |
| ゲート3 承認の対象 | `design/baselines/gate3_2026-10-09/` | 最終承認はコミット f208066 |
| 検査器・ルール一覧・試験 | `tools/validate_model.py`、`tools/check_design.py`、`rules/` | `rules/README.md` |
| スクリプト | `tools/` | `run_checks.py`、`render_views.py`、`generate_params.py`（trial ファイルも生成）、`apply_revision.py` |
| 生成物（手編集禁止） | `generated/`（`params/` に node 別設定と `*.trial.yaml`、`firmware_config.yaml`・`.trial.yaml`）、`conflicts.yaml`、`intent_*.yaml`、`reports/*.json` | firmware のビルド時ヘッダ `firmware/gouda_esp32_v4/include/gouda_v4/build_config.hpp` はビルド時に生成（コミットしない） |
| 提案 | `proposals/` | 承認済み仕様として使わない。最新: `gnss_initial_pose_design.md`（DEC-126〜129）、`stage56_navigation_localization_plan.md`（DEC-120〜124、許可済み）、`sleep_inhibit_plan.md`（DEC-104）、`ground_estimation_design.md`（DEC-107。`ground_estimation_plan.md` を置き換え） |
| 調査・証拠 | `research/` | `vehicle_pc/`（工程 5-1〜5-5 の試験記録、夕方の解析 `2026-10-14_evening_*`）、`joystick270_firmware/`、`upstream_jazzy/` |
| 報告・作業記録 | `reports/`、`reports/worklog/` | 最新 `2026-10-19_rev073_gnss_first_start.md`（その前 `2026-10-19_rev072_mosaic_before_first_start.md`、`2026-10-19_rev070_071_dec140_query_tool_ntrip.md`、`2026-10-19_rev069_by_id_prm65_dec140_material.md`、`2026-10-19_rev068_septentrio_source_review.md`、`2026-10-19_rev067_gnss_calibration_tool_mosaic.md`、`2026-10-18_rev065_gnss_answers_calibration.md`、`2026-10-18_rev063_gnss_mapping_record.md`、`2026-10-17_rev061_062_stage56_implementation.md`、`2026-10-17_rev060_stage56_study_dec116.md`、`2026-10-17_rev058_059_recorder_glim_fix.md`、 `2026-10-17_rev056_057_localization_verification.md`、 `2026-10-17_rev051_localization_selection.md`、`2026-10-14_evening_maps_rosbag_analysis.md`）。引き継ぎ `reports/handover_2026-10-17.md`（前回 `handover_2026-10-14.md`） |
| ロボット実装（新） | `gouda_interfaces/`（SoftwareMode・DecisionEvent・MotionHold・StartAutonomy・ConvertMap）、`gouda_core/`（recorder・mode_manager・monitor（地図タブの入力検査 map_tab.py）・map_creator（変換 map_convert.py、解析 map_inspect.py）・sensor_supervisor・motion_controller・vehicle_bridge、esp32_protocol・esp32_sim、web/、test/ に Ubuntu 試験 script）、`gouda.sh`（start／stop／status のみ、環境変数なし）、`setup.sh`（PC のセットアップ）、`update.sh`（main への更新）、`third_party/drivers.repos`（ドライバの commit）、試験用 `gouda_core/test/stack.sh` | 工程5-1〜5-5 |
| firmware（新） | `firmware/gouda_esp32_v4/` | `include/gouda_v4/{protocol,config,control}.hpp`、`src/main.cpp`、`tools/gen_build_config.py`、`test/host/`。旧 `firmware/gouda_esp32`・`gouda_dualsense_usb` は置き換え対象 |
