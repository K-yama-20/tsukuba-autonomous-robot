# 第255便 作業記録：共有の作業ツリーの未コミットの変更を便ごとにコミット（REV-281、DEC-499）

- 日付：2026-11-07
- 読んだコミット：9c449b5（開始時の HEAD。未コミットの変更 541 件、第184〜254便）
- 作業したブランチ：design/mppi-sim-2026-11-03（共有の作業ツリー。DEC-501 の Q1 で統合ブランチになった）
- 区切りで作ったコミット：9c449b5 の上に 2702b0b〜99a5be6 の 36 件（下の表）と、この記録のコミット（自分の ID は書けないので、次の記録か status.md の更新で示す）。push はしていない
- 読んだもの：CLAUDE.md（1.1〜1.13）、status.md、第184〜254便の作業記録の「変更」の表、design/revisions/REV-192〜282 の見出し、model.yaml の revisions の順、各チャットからの便とファイルの対応の連絡
- このセッションは MID-360 のメインチャットから渡された指示で始めた。

## 人の指示（原文、DEC-499）

> 今後、並列のチャットは git worktree で作業する。
> まず今の共有の作業ツリーの変更を、チャットごと・便ごとに区切ってコミットせよ（push はしない）。どのファイルがどの便のものかは作業記録で確かめ、他のチャットの途中の変更は混ぜない。
> reserve_ids.py の予約の印を、全 worktree で共有する場所に移し、PRM・IFD・ND の番号も予約できるようにせよ。CLAUDE.md の規則も合わせて直す案を出せ。
> 以後、各チャットは自分の worktree とブランチで作業し、区切りごとにコミットする。統合は統合ブランチで merge し、生成物は merge の後に生成し直す。
> 車載 PC にはファイルを手で写さない。統合ブランチのコミットを checkout して反映し、記録にコミット ID を書く。今の車載 PC のローカル変更は消さずに退避する。

- 伝達の経路：MID-360 のメインチャットが原文を引用して渡した。この記録の AI は人の発言を直接は見ていない。
- 同じ指示を受けたセッションが他に 3 つあり、分担した：便ごとのコミットとこの記録はこの便。reserve_ids.py の共有化・CLAUDE.md の案・worktree と車載 PC の手順は「並列チャットを git worktree の運用に移す」のセッション（第257便。案への人の回答は DEC-501「推奨どおりで」、REV-283）。「つくばチャレンジ走行戦略」は model.yaml の当て直しの試し（結果を受け取った）。ND-11・MID-360 プラン・確認走行・停止点の各セッションは、便とファイルの対応を連絡してきた（データとして使った）。

## コミット（9c449b5 の上、first-parent の順）

| コミット | 便 | 内容 | ファイル数 |
|---|---|---|---|
| 2702b0b | 184 | intent.md 第17版の記録（REV-195〜197、AR-017、DEC-408）と check_design の対応 | 11 |
| cb964bb | 186 | 動き出しの無駄時間（REV-198・199） | 5 |
| a7eadac | 194 | AI と人間の役割分担（REV-206） | 3 |
| af1b048 | 195 | IMU の仕様の規則（REV-207。文書は第213便のコミット） | 3 |
| 1bb7575 | 196・198 | 推定不能でも PRM-136 の間は走り、超えたら自律走行の中で待つ（REV-208〜210・212） | 14 |
| ed266d1 | 197 | お助けの案（REV-211） | 3 |
| 6ff38bc | 199 | XT-32 の見える範囲の台帳（REV-215・216） | 10 |
| 4d53507 | 202・203 | 試験のみ：MID-360 の模擬 段階 1・2、x86 の 30 パターン（REV-213・214・217〜219） | 20 |
| 89fa0ef | 204 | MID-360 の接続試験の計画（REV-220〜222・232・233） | 12 |
| 28c5160 | 206・207 | Nav2 の失敗で待機に入らない決定、DEC-316 を閉じる（REV-225・226） | 4 |
| f874e64 | 208・209 | waypoint を飛ばす工夫の採用と方式（REV-229・231） | 4 |
| 4157f3b | 210・212 | 最低速度・不感帯の実測、DEC-445 の確定（REV-234・236） | 8 |
| dd42f5f | 211・240・253 | waypoint を飛ばす処理（REV-235・238・264・267・279） | 26 |
| c2bf729 | 213 | TR-IMU16607 の設定の確認（REV-237）と IMU の仕様の文書 | 3 |
| 2d96180 | 214 | open_loop・下限の模擬（REV-239） | 9 |
| dbbd8ab | 215 | MPPI の open_loop を /config で（REV-240・243） | 8 |
| 748cb4f | 216 | ND-11 の速度のフィードフォワード＋PI（REV-241） | 33 |
| e67f135 | 217・242 | MID-360 の層と、取り付けを /config で（REV-242・266） | 23 |
| c58b3cc | 219 | Nav2 の失敗で goal を出し直す（REV-245） | 7 |
| 9a816c2 | 220（187〜193・221〜234） | dev-tab-vehicle-test 系統の統合（REV-200〜205・246〜258）。第二の親に 69631f8 | 136 |
| 171aae1 | 235 | MID-360 の接続試験の道具・ドライバの IF・地面分割の調査（REV-259・260） | 56 |
| 19c6de0 | 236 | MPPI の vx_min を /config で（REV-261） | 6 |
| 69561cf | 237 | 速度の目標の緩和と質問（REV-262・270・273） | 17 |
| b46b3b8 | 238 | 試験のみ：確認走行区間のコース | 4 |
| 62c0916 | 251 | 試験のみ：植え込みの始点（drive_sim_course.py の差し込み口を含む） | 4 |
| 20575ba | 239 | 一時停止線（REV-263・268） | 15 |
| 9a4e50e | 241 | ゴールの向きの許容を /config で（REV-265） | 6 |
| cff1185 | 243 | 一時停止線と TK-22〜25（REV-269） | 3 |
| b41eb0f | 244 | DEC-488 の回答（REV-271） | 3 |
| 577b896 | 245・249 | 試験のみ：死角の印の模擬（REV-272・277） | 111 |
| a66aef7 | 246 | 停止距離の解析の準備（REV-275） | 7 |
| a8e15b5 | 247 | DEC-476〜479 の回答（REV-274） | 3 |
| 33b3b1d | 248 | MPPI の速度と旋回の値を下げる（REV-276） | 8 |
| 717dc5b | 250 | MID-360 なしの起動の確認（試験のみ） | 1 |
| c2536c3 | 254 | 停止点での向きと置き方の回答（REV-280） | 3 |
| 99a5be6 | 台帳 | model.yaml・生成物・検査の報告・status.md・troubleshooting/ledger.yaml・旧い予約の印・model_diff_rev-223/224/227/228/230 | 205 |

- commit の作者・コミッター：ryoya-1@g.ecc.u-tokyo.ac.jp（git config）。Claude の attribution は付けていない

## 残した変更（コミットしていない）とその理由

| ファイル | 理由 |
|---|---|
| `gouda_core/gouda_core/recorder_core.py`・`recorder_node.py`、`gouda_core/test/test_recorder_diagnostics.py`、`third_party/patches/`、`design/research/upstream_sensors/livox_ros_driver2_status_patch_2026-11-07.md`、`design/revisions/REV-278.yaml`（予約だけ）、`mid360_config.py` の DIAGNOSTIC_NAME の 4 行 | 第252便（mid360-status-impl、DEC-494）が作業中（作業記録なし） |
| `setup.sh`・`README.md`・`third_party/drivers.repos` | 第235便（colcon でのビルド）と第252便（ドライバの patch）が同じ行に入っている。第252便が途中なので両方とも残した。第235便のコミット 171aae1 にはこの 3 つは入っていない |
| `design/tools/reserve_ids.py`・`design/rules/test_reserve_ids.py`・`design/proposals/worktree_operation_2026-11-07.md`・第257便の作業記録・status.md の第257便の項・`design/revisions/REV-283.yaml`・`update.sh`・`.gitattributes`・`tests/test_update_sh.py`・`design/research/claude_md/` | 第257便が作業中（DEC-501 の回答の後も 05:17 に更新）。そのセッションは「返事があるまで commit しない」と言っていたが、05:21 以降は連絡がつかない（ソケットが消えた） |
| `gouda_core/test/gpu_sim*.py`（5 件）、`design/revisions/REV-244.yaml` | 第218便（gpu-sim-sweep の予約）。作業記録がなく REV-244 は未適用。途中か放棄か決められない |
| `design/revisions/REV-192.yaml` | 予約だけ（2026-11-02、issue-workflow-fork）。中身がない |
| `design/revisions/REV-282.yaml` | 予約だけ。「つくばチャレンジ走行戦略」が放棄（欠番。同時に取った DEC-500・第256便も欠番） |
| `design/docs/.$SystemArchitecture.drawio.bkp`・`docs/architecture/.$SystemArchitecture.drawio.bkp` | 人の drawio の控えと思われる（推測）。人の私的なファイルとして触らない |

## 自律判断とその理由

- 分け方：作業記録の「変更」の表、REV の見出しの便、予約の印のラベル、各チャットの連絡で、ファイルと便を対応づけた。1 つのファイルに複数の便が入るコードは、差分のかたまり（`git diff -U0 --histogram`）ごと、混ざるかたまりは行ごとに便を割り当て、9c449b5 にその便までの行だけを当てた中身を `git update-index --cacheinfo` で stage した（作業ツリーのファイルは変えていない）。割り当ては DEC・REV・PRM の番号と識別子で自動で付け、混ざる 25 かたまりを読んで直した
- 同じ関数の中で入り組む便は、同じチャットの便をまとめた（211・240・253、217・242、245・249 など）。第217便と第242便は別のチャットだが、新しい `mid360_config.py` を両方が変えていて分けられないので 1 つにした
- 新しいファイルを複数の便が変えたときは、最後に変えた便のコミットに入れた（例：IMU の仕様の文書は第213便、MID-360 の接続試験の台帳は第235便）
- model.yaml・生成物・検査の報告・status.md・ledger.yaml は最後の 1 つ（99a5be6）にした。理由：REV の適用の順が便の順と入れ違う（例：REV-200〜205 は REV-245 の後、REV-239 は REV-254 の後）ので、便ごとに model.yaml を分けると、検査した model と違う順の model になるか、他の便の REV が混ざる。各 REV の差分は REV のファイルと model_diff_rev-*.md に残る。「つくばチャレンジ走行戦略」の当て直し（9c449b5 の model.yaml に 84 本の REV を今の順で当てる）で、第220便の手の 22 欄を除いて今の model.yaml（sha256 先頭 14ae096b）と一致することを確かめた（そのセッションの報告。写しはそのセッションの scratchpad）
- 第220便のコミットは、第二の親に dev-tab 系統の 69631f8 を付けた merge にした。第220便がその系統を番号を付け直して取り込んだことを履歴に残し、後で同じ系統を二重に取り込まないため。木（tree）はこちらで組んだもので、69631f8 の番号のままのファイルは入っていない
- 途中の便の行を外した：`mid360_config.py` の DIAGNOSTIC_NAME の 4 行（第252便）、`drive_sim_course.py` の COURSE_EXT の差し込み口（第238便のコミットでは外し、第251便のコミットで入れた）、status.md の第257便の 4 行
- 中間のコミットは、生成物が 99a5be6 まで古いまま。単体試験は最後のコミットでだけ実行した

## 承認事項・実測待ち

- 新しい承認事項はない（DEC-499 は人の指示の記録）。push は人の指示で行う（今回はしない）
- 第257便のファイルのコミット（そのセッションか、統合の担当が行う）

## 実行した検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 分割の再現 | 分割のスクリプトで全部の便を当てた中身と作業ツリーのファイルを比較 | 9c449b5 と作業ツリー | コードの 35 ファイルとも一致（第252便の行を除く） |
| 構文 | 各コミットで stage する .py を `compile()` | 各コミット | 第211便の 1 回目で mode_manager_node.py が IndentationError（下の「原因の分類」）。直した後は全部通った |
| 公開してはいけない情報 | コミットするファイルを IPv4・ホスト名・ユーザー名で grep | 作業ツリー | 新しく入るものはなし（192.168.1.x は XT-32 の LAN の既存の値、Parallels は既存の文） |
| 単体試験（gouda_core） | `PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 -m unittest discover -s gouda_core/test` | c2536c3（台帳のコミットの前、一時的な worktree） | 489 件中 4 失敗・17 エラー。生成物（params）がまだ古いため（test_nav2_config・test_motion_feedback） |
| 単体試験（gouda_core） | 同上 | 99a5be6（一時的な worktree。未コミットの変更なし） | 489 件 OK（skip 35） |
| 設計検査 | `design/.venv/bin/python design/tools/run_checks.py` | 99a5be6（一時的な worktree） | 終了コード 1。design_check PASS（合格 12・違反 0・未判定 5、違反0件・未判定5件）、generate_params PASS、intent_identity PASS。FAIL は input_integrity・migration_validator・migration_tests で、前からの SystemArchitecture.drawio と .DS_Store の hash の不一致 |
| 設計の単体試験 | `python -m unittest discover -s design/rules` | 99a5be6（一時的な worktree） | 88 件中 1 失敗（test_real_model。同じ drawio・.DS_Store の不一致 5 件） |
| reserve_ids の単体試験（第257便の新版） | `python -m unittest design.rules.test_reserve_ids` | 共有の作業ツリー（未コミット、sha256 先頭 fd3c2182） | 15 件 OK |
| REV-281 の試し | `apply_revision.py REV-281 --dry-run --check` | 99a5be6＋作業ツリー | 0 new violations、0 new undetermined |
| REV-281 の適用と再生成 | `apply_revision.py REV-281`、`generate_params.py`、`render_views.py`、`render_migration_review.py` | 同上 | どれも終了 0 |
| 設計検査（REV-281 の後） | `run_checks.py` | 99a5be6＋REV-281（共有の作業ツリー。model.yaml の sha256 先頭 6b0af1e9） | 終了コード 1。design_check PASS（違反0件・未判定5件）、generate_params PASS、intent_identity PASS。FAIL は前と同じ drawio・.DS_Store の 3 つ |
| 車載 PC・実車 | — | — | 未実行（車載 PC には接続していない） |

## 原因の分類（1.6）

- 分割のスクリプトの誤り（実装）：コードの中身を「HEAD＋その便までのかたまり」で作っていたが、かたまりは 9c449b5 との差分なので、HEAD が進んだ後（第211便）では位置がずれた。`compile()` の確かめで stage の途中に止まり、コミットはしていない。stage したものは `git restore --staged`（作業ツリーは変えない）で外し、土台を 9c449b5 に固定して直した。それまでの 12 件のコミットの中身が意図どおりかを、全部のコードのファイルで比べて確かめた（全部一致）

## 見つけたこと（考慮漏れの指摘、1.12）

- 第218便（gpu-sim-sweep）は予約・REV-244・gpu_sim*.py があるが作業記録がない。扱いを人かそのチャットが決める
- 第235便の setup.sh の変更は、第252便が終わるまでコミットできない。第235便の A2（Dell での setup.sh）の前に、両方がそろったコミットが要る
- 車載 PC（x86）の ~/gouda_ws には、第215・217・236・241便のファイルが手で写してある（各セッションの報告）。統合ブランチのコミットを checkout で反映するには、人の push の指示と、第257便の手順（退避の後）が要る
- 中間のコミットは生成物と合っていない（99a5be6 で合う）。中間のコミットを車載 PC に反映しない
- 99a5be6 の status.md の先頭の「最終更新」の行は第178便のままで、この便でも直していない

## 残るリスク

- 行ごとの割り当ての誤り：最後の中身は作業ツリーと一致するが、中間のコミットの間で行が別の便に入っている恐れがある（混ざる 25 かたまりは読んで直した。中間のコミットでの試験は未実行）
- 第257便のファイルは未コミットのまま。そのセッションと連絡がつかない
- 一時的な worktree（scratchpad の wt_test、detached HEAD）は試験のあとに消す

## 生成物の変更箇所

- 99a5be6：作業ツリーの生成物（REV-280 までの model.yaml から 05:01 に作られたもの）をそのまま入れた
- REV-281 の適用による：model.yaml（DEC-499、revisions の REV-281）、generated/gate3_package.md・review_r3.md（DEC-499 の行）、reports/model_diff_rev-281.md、検査の報告

## 次の作業

- 人：push（統合ブランチ design/mppi-sim-2026-11-03）。push の前にメールアドレスを報告する（ryoya-1@g.ecc.u-tokyo.ac.jp）
- 第257便：自分のファイルのコミット、REV-283 の適用
- 第252便：区切りの後に、setup.sh・README.md・drivers.repos（第235便の分も）と recorder のコミット
- 車載 PC：第257便の手順（`design/proposals/worktree_operation_2026-11-07.md` 4.3）で、人の「はい」の後に退避と checkout
- 止まっている作業：第218便の扱い（人かそのチャット）
