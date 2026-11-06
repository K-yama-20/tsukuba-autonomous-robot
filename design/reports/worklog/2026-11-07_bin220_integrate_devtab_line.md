# 作業記録 2026-11-07 第220便: dev-tab-vehicle-test 系統の統合（REV-246、DEC-461、REV-200〜205・REV-247〜258）

## 読んだもの

- 共有の作業ツリー：コミット 9c449b5（ブランチ design/mppi-sim-2026-11-03）＋作業ツリー（他のセッションの未コミットの変更を含む）。
- dev-tab-vehicle-test 系統：コミット 69631f8（a88fd04・7f3f2d2 を含む）と、その worktree（`.claude/worktrees/dev-tab-vehicle-test-6eb228`）の未コミットの変更。
- 車載 PC（x86）の `~/gouda_ws/src/tsukuba-autonomous-robot`（ブランチ dev-tab-vehicle-test 9caaa65 とローカルの変更 99 件）。読むだけ。
- 両系統の分かれ目：0e260f3（2026-11-03）。

## 人の指摘と回答（原文、DEC-461）

- 指摘：「一時停止モードは待機モードに名称変更したはずなのに、それが反映されていませんね。旧版に改良を加えている可能性があります。視度チェックせよ」。続けて同じ文で「再度チェックせよ」。
- 調べた結果（AI）：共有の作業ツリーは dev-tab の系統を含んでいなかった。dev-tab の系統にだけあったものは次のとおり。
  - 待機への改名（DEC-413）
  - PRM-45 の 4500 mV（第193便。共有の作業ツリーは 4720 mV のまま）
  - /dev タブ
  - 車体試験の記録
- 回答：「両系統を先に統合」

## 行ったこと

### 番号

`reserve_ids.py` で予約した：REV-246〜258、DEC-461〜473、第220〜234便。対応表は次のとおり。

| dev-tab の番号 | 共有の作業ツリーでの番号 | 理由 |
|---|---|---|
| REV-200〜205、DEC-411〜416、第187〜193便 | そのまま | 共有の作業ツリーに、dev-tab のセッションが取った予約の印だけがあった |
| REV-206〜217 | REV-247〜258 | 共有の作業ツリーで別の内容に使われていた |
| DEC-417〜428 | DEC-462〜473 | 同上 |
| 第194〜207便 | 第221〜234便 | 同上 |
| ND-20 | ND-30 | ND-20 は REV-242 の livox_ros_driver2 |
| IFD-58 | IFD-71 | IFD-58 は REV-238 の global costmap |

### コード（3-way、土台 0e260f3、衝突 0 件）

- 相手は 69631f8 の版。ただし車載 PC で動いている未コミットの版（車載 PC の作業ツリーと dev-tab の worktree で一致）があるファイルは、そちらを使った。対象は次の 11 ファイル。
  - vehicle_core.py（seq の追従）
  - vehicle_test_core.py・vehicle_test_node.py
  - vehicle_tests/motion_start.py・motion_start.yaml
  - docs/vehicle_tests.md
  - 試験 5 件
- 入れたもの
  - /dev タブ（monitor_node.py、web/app.js・index.html・style.css）
  - gouda_vehicle_test（ND-30）、launch・setup.py
  - VehicleTest.action（IFD-71）
  - 待機のボタンの表記
- dev-tab から来たファイルの中の ND-20・IFD-58・DEC・REV・便の番号は、対応表で付け直した。monitor_node.py・launch は、車体試験の行だけを付け直した。
- 入れなかったもの：dev-tab の worktree だけにある試験用の変更。どれも車載 PC にない。
  - drive_sim の 4 ファイル
  - nav2_config.py の GOUDA_TEST_NAV2
  - test_nav2_config.py
- 他のセッションの変更（open_loop、MID-360、Nav2 の失敗での出し直し、ND-11 の速度の帰還）は残っている。

### 記録

- REV-200〜205・REV-247〜258：dev-tab の変更セットに、番号の付け直しと先頭の注記を足して適用した。18 件とも、試し適用で新しい違反 0・新しい未判定 0。
- REV-246：DEC-461 を適用した。
- 証拠・基準線・過去の作業記録・試験 1 件：共有の作業ツリーで 0e260f3 から変わっていないものは、dev-tab の版にした（REV-214・217 の VM の表示の置き換え）。
- model.yaml：REV-214・217 が直接入れた置き換えを写した。0e260f3 と同じ値の欄だけで、22 欄。
  - 証拠の sha256 15 件
  - DEC-003・012・053・062・067、V-001 の文
  - 使ったのは一回限りのスクリプト（scratchpad の scrub3way.py。apply_revision.py と同じ ruamel の設定で、その他の行は変わらない）。両方で変わった欄 2 つは IFD-16 で、番号の付け直しによる差だけ。
- 作業記録：dev-tab の 21 件を写した。第194〜207便はファイル名と本文の番号を付け直し、先頭に元の番号を書いた。
- status.md：3-way。dev-tab の項目は見出しの下にまとめて写した。

## 自律判断（理由）

- troubleshooting ledger の TRB-014 を直した。dev-tab の系統で、スキーマに合わない値が入っていた（status「対策済み（模擬で確認、実車は未確認）」、occurrences が文字列）。dev-tab の第233便（元の第206便）の記録にも既知としてある。
  - status は「監視中」にした。元の語は countermeasures の先頭に残した。
  - occurrences は元の文を description に残して、項目の形にした。
  - 意味は変えていない。
- design/docs/gouda_monitor_palette.md（hash 固定の証拠、FILE-MONITOR-PALETTE）を、登録した内容に戻した。
  - dev-tab の a88fd04 は、この中の「一時停止のボタン」を「待機のボタン」に書き換えていたが、sha256 を更新していなかった（dev-tab の系統でも検査違反だった）。
  - 登録済みの証拠は書き換えない規則による。改名は DEC-413 と画面の表記に残っている。
- 統合の作業中に、私のコマンドの誤り（zsh の変数の扱い）で、ファイル名と同じ名前の空のフォルダが 14 個できた。空のフォルダだけを消し、ファイルの変化がないことを確かめた。

## 検査・試験（共有の作業ツリー、9c449b5＋作業ツリー）

- `run_checks.py`：終了コード 1。
  - 設計検査：違反 0・未判定 5。
  - migration_validator の違反は、前からのもの（SystemArchitecture.drawio、.DS_Store 2 つ）だけ。
  - 検査器の試験の失敗は test_real_model の 1 件で、同じ原因。
  - 途中で一時、FILE-MONITOR-PALETTE と証拠 13 件の hash の不一致が出た。直した後は 0 件。第214便の記録が見た「02:27、hash の不一致 13 件」と ledger のスキーマ違反は、この統合の途中の状態。
- Mac：`python3 -m pytest -q gouda_core/test` 406 passed、27 skipped。
- ワークステーション（新しいフォルダ ~/gouda_ws_integ_it、tar の写し）
  - `colcon build --symlink-install --packages-select gouda_interfaces gouda_core`：成功。
  - pytest：431 passed、1 failed。失敗は test_drive_sim_layers の test_patch_copy_only_on_a_copy で、git の checkout の中かどうかを見る試験。写しは git の checkout でないため落ちる（試験の環境による。Mac の checkout では合格）。
  - ND-11 の結合の確認（probe_ffpi.py、ROS_DOMAIN_ID 88）：5 項目すべて PASS。
- 車載 PC：未実行（反映は人の指示待ち）。

## 残るリスク

- 車載 PC の `~/gouda_ws` は、dev-tab の系統に、他のセッションが手で写した変更（open_loop、MID-360 など）を足したもの。統合した作業ツリーとは、ファイルごとに違う可能性がある。反映のときは差分を確かめる。二重に入らないようにする。
- 写した記録の本文の番号は機械的に付け直した。コミット ID と、hash 固定の証拠の中の番号は元のまま。証拠の中の DEC-421 などは、元の dev-tab の番号を指す。
- dev-tab の worktree の試験用の変更（drive_sim など）は入れていない。必要なら別に入れる。

## 更新した生成物

design/generated/ 一式、design/migration_review.md、intent_index.yaml、intent_open_items.yaml、conflicts.yaml、design/reports の検査結果と model_diff。generate_params で firmware_config.yaml の dac_max_mv が 4500 になった。

## 次

- 進められる：ND-11 の速度の帰還の模擬の比較（実行中）、第216便の記録。
- 止まっている（人の指示待ち）
  - 車載 PC への反映
  - コミット・push
  - dev-tab の worktree の扱い（消すか残すか）
