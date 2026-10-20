# 作業記録 2026-10-21 第90便: 分岐セッションの D10・D11 の回答（転記）の反映：Nav2 の実車の値、PRM-39、地図の変換の値（REV-122、DEC-192〜195、DEC-098）

## 読んだもの

- コミット `34bc9e0`（ブランチ design/field-mapping-2026-10-14。作業ツリーの変更は人のファイルだけ）。分岐先は 8f50ef5 を読んだ（転記による）。
- 転記（人がこのメインのチャットに貼ったもの）: 分岐セッションが人に示した D10・D11 の判断材料と、人の回答の原文（原文 1〜3）。
- `design/model.yaml` の PRM-01・02・05・06・11・17・18・33〜36・38・39・62〜64・66〜73、DEC-098・166、G-RECOVERY-COUNT、RQ-I012。`design/intent.md` の 15・100 行。
- コード: `gouda_core/gouda_core/nav2_config.py`、`gouda_core/test/test_nav2_config.py`・`test_motion_core.py`・`stage55_probe.py`。上流の雛形 `design/research/upstream_jazzy/nav2_bringup/params/nav2_params.yaml`・`nav2_bt_navigator/behavior_trees/navigate_through_poses_w_replanning_and_recovery.xml`。

## 人の回答（原文、分岐セッションからの転記）

DEC-192 の answer_verbatim に原文 1、DEC-193・DEC-194 に原文 2、DEC-098 に原文 2・3 を記録した。着手は、第89便の commit・push の後に人がこの転記を貼ったことを指示とした（AI の解釈。これまでの転記と同じ扱い）。

## 変更

- REV-122:
  - DEC-192（Nav2 の値）、DEC-193（PRM-39、DEC-166 の値を置き換え）、DEC-194（PRM-18＝9999999 の振る舞いの変化）を answered で記録した。DEC-098 を answered にした（推奨値。PRM-36 は 1.35 m）。DEC-195（intent.md の改訂案）を pending で登録した。
  - Nav2 の実車の値を承認値にした。PRM-11 0.7 m、PRM-17 20 Hz、PRM-18 9999999、PRM-66 1.25 m/s、PRM-67 1.0 rad/s、PRM-68 1.2 m/s²、PRM-69 [[0.55, 0.30], [0.55, -0.30], [-0.24, -0.30], [-0.24, 0.30]]、PRM-70 −0.065 m、PRM-71 1.185 m（地面から 1.35 m − PRM-05 0.165 m）、PRM-72 0.5 m、PRM-73 2.0 rad/s²。
  - PRM-39 を 1.25 m/s にした。
  - 地図の変換の値を承認値にした。PRM-33 0.1、PRM-34 0.1、PRM-35 0.15、PRM-36 1.35、PRM-38 1、PRM-62 0.5、PRM-63 10、PRM-64 1.0。
  - G-RECOVERY-COUNT に、BT の recovery の回数と理由の記録を足した。
  - 試し適用は、新しい違反 0。新しい未判定 6 件は、既存の DR-15 の行の見出しの文が変わったもの（下の注）。そのあと本適用し、再生成した。
- 提案: `design/proposals/intent_edit_requests.md` §4（intent.md:100 の車体の寸法と「人は乗らない」）。`design/proposals/dr15_allowlist_proposal_2026-10-21.md` に注を足した（同じ数が増えたが、行と数は同じ）。
- 生成物: gouda_nav2・bt_params・controller_server・gouda_map_creator の trial ファイルは、承認値がそろったので作られなくなった（git では削除）。tbd が残るのは gouda_mode_manager（PRM-37）と gouda_monitor（PRM-19・20）だけ。

## 自律判断した変更（理由）

- PRM-01・02 は変えなかった。どちらも intent.md:100（全長 1,010 mm × 全幅 598 mm）の写しで、人の申告（足置きを外した、横幅 60 cm）は上位の要求と食い違う。CLAUDE.md 1.1 により黙って適用せず、DEC-195 で intent.md の改訂を求めた。Nav2 が使うのは PRM-69（footprint）なので、自律走行の設定は止まらない。
- 車輪の間隔 530 mm は、新しい PRM にしなかった。使う設定がなく、新しい PRM は人の許可が要るため（DEC-106）。DEC-192 と PRM-69 の解釈に記録した。
- PRM-71 は、人の「地面から135cm」を base_link 基準に換算して 1.185 m とした（nav2_config は base_link 基準で使う）。換算の式と、PRM-05 が記載値（実測していない）であることを書いた。

## 検査・試験（コミット 34bc9e0 ＋ 作業ツリー）

- `design/.venv/bin/python design/tools/run_checks.py`（REV-122 の後）: 終了コード 1。設計検査は合格 12・違反 0・未判定 5（DR-11 は 49 → 30、DR-15 は 30 のまま）。検査器の試験は 83 件中 1 件不合格（test_real_model。入力の照合の不一致 3 件と同じ原因で、以前から）。
- DR-15 の注: 試し適用で出た「新しい未判定 6 件」は、map_convert.py:143・303、map_creator_node.py:79、speed_mask.py:66・67・76 の既存の 6 行。新しく承認した値（0.5、0.1）も同じ数になり、見出しの「承認値と同じ数（…）」の PRM の並びが変わったため、文字列が変わった。件数は 30 のまま。
- Nav2 の設定の組み立て（scratchpad、上流の雛形から）: `nav2_config.missing` は空。`nav2_config.write(..., trial=False)` で nav2_params.yaml と BT を作れた。controller_frequency 20、RPP の desired_linear_vel 1.25、allow_reversing false、velocity_smoother の max_velocity [1.25, 0, 1.0]・max_accel [1.2, 0, 2.0]、local・global の footprint、inflation 0.5、BT の外側の number_of_retries 9999999 と RemovePassedGoals の radius 0.7 が入っていることを確かめた。
- Mac `cd gouda_core && python3 -m pytest -q test`: 220 passed、8 skipped、**1 failed**（test_nav2_config.py の test_vehicle_files_alone_do_not_build）。
  - 原因の分類（1.6）：試験（試験の基盤）。この試験は「本物の生成物では PRM-66・69 が未確定なので Nav2 を組まない」ことを確かめていた。今回それらが承認値になり、試験の前提（生成物の今の状態）が崩れた。確かめたい規則（実車の値が 1 つでも未確定なら Nav2 を組まない、intent.md:85）は変わっていない。
  - 修正の案（許可待ち、DEC-106）：生成物を一時ディレクトリに写し、実車の値の 1 つ（例：PRM-66 の行）を消した写しで「組まない」を確かめる。本物の生成物では「組める」ことを確かめる。合否の基準（未確定なら組まない）は変えない。
- PRM-39 の変更の影響: 試験のコードに 1.111 や 4 km/h を書いた所はない（grep で確認）。test_motion_core・stage55_probe は承認値を読んで計算するので、1.25 m/s でも合格した。
- VM・実機: 未実行。

## 承認事項・人に伝えること

- DEC-195（pending）：intent.md の改訂（人が編集）。
- 試験 test_nav2_config の修正の許可。
- 注（DEC-192）：PRM-67 の 1.0 rad/s は PRM-40（0.97 rad/s）を少し超えるので、motion_controller で頭打ちになる（分岐セッションで人に伝え済み）。
- 注（今回気づいたこと）：velocity_smoother の後退の上限は、上流の雛形の作りで −1.25 m/s（前進と同じ）になる。車椅子側の後退の上限は 0.472 m/s（PRM-78）。motion_controller は −0.472 m/s で倒し量 −1 に頭打ちにするので、車体が速く後退することはない。ただし、Nav2 が出す後退の指令と実際の速度は合わない。recovery の後退（behavior の backup）は、上流の既定の速度で動く。人の原文「recoveryの後退は自由に使って良い。」。
- 注（DEC-098）：PRM-36 1.35 m は推奨の根拠（全高 0.95 m＋0.25 m）より高い。そのため、地面から 1.2〜1.35 m の枝などが地図の障害物に入り、その下を通る経路が引かれない場合がある（推測）。
- 注（DEC-194）：PRM-18＝9999999 で、計画の失敗による一時停止（TR-07）がほぼ起きなくなる。経路が塞がれている間は recovery（回転・後退・待機）を続ける。BT の recovery の数え方と記録は G-RECOVERY-COUNT（工程 5-7）。

## 残るリスク

- 実車での値の検証は、すべて未実施（速度・加速度・footprint・障害物の高さ）。PRM-05（base_link の高さ）は記載値なので、PRM-71 の換算もそれに依存する。
- 自律走行の開始には、ND-07 と、Nav2 で使える 2D 地図（DEC-107、TS-34）がまだ要る。

## 更新した生成物

- design/generated/params/*（承認値の反映、trial ファイル 4 つの削除）、design/generated/ の各ビュー、design/migration_review.md、design/intent_index.yaml など、design/reports/model_diff_rev-122.md と検査の結果のファイル。

## 次に進められる作業・止まっている作業

- 人の回答待ち: test_nav2_config の修正の許可、DEC-195、DEC-189・190。
- commit・push は人の指示を待つ。

## 訂正・補足（第91便、2026-10-21）

- 上の「Nav2 が出す後退の指令と実際の速度は合わない」は言い過ぎだった。人の説明（DEC-197）のとおり、後退は倒し切りで 0.472 m/s になり、motion_controller の正規化（÷PRM-78）と一致する。合わないのは 0.472 m/s を超える後退の指令だけ。今の設定では、その指令は出ない（RPP は後退しない。BackUp は 0.15 m/s）。検討は `reports/reverse_limit_study_2026-10-21.md`、判断は DEC-198。
- PRM-01・02 は第91便（REV-123、intent.md 第14版）で 0.80 m・0.60 m に、PRM-03 は 1.2 m にした。
