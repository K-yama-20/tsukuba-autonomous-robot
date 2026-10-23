# 作業記録 第149便：monitor の /config で入力欄と保存ボタンに届かない不具合（REV-173、DEC-364）

日付：2026-10-23
読んだコミット：31a6e1d（作業ツリーにはほかのセッションの未コミットの変更あり。REV-172・第147〜148便はほかのセッション）
読んだもの：design/reports/status.md、第146便の作業記録、gouda_core/web/index.html・style.css・app.js（/config の部分）

## 人の指摘と指示（原文は DEC-364）
- 指摘：「/configのセンサ取り付け方向・座標の設定項目においてスクロールできないため値が入力できない」
- 原因と案を示した後の指示：「Implement the proposed /config scroll fix and check it in the demo monitor.」

## 原因（分類：実装）
- `.panel` が `overflow: hidden` で、はみ出した入力欄は見えず、ホイールでもスクロールできない。
- `.panel.full` が `height: 100%` のまま、サブタブの行の下に置かれ、パネルの下端がタブから約 32 px はみ出していた。
- `.subpane.active { display: block; }` が `.panel` の縦並び（flex）を上書きし、`.cfg` の `overflow: auto` に高さの上限がなく、並びが伸び続けた。
- 再現（変更前、デモ、1600×900、自分のタブの DOM にだけ試験用の入力欄を足して 42 個・UI の表 8 行）：中身 1238 px に対しパネルの見える高さ 775 px、入力欄 12 個と保存ボタンが画面の外。

## 変更（承認 DEC-364）
- `gouda_core/web/style.css`：`.tabpane[data-pane="config"].active` を縦の flex に、表示中のサブタブのパネルを `flex: 1; min-height: 0; overflow: auto`、`.subpane .cfg { flex: 0 0 auto; }`（並びを縮めず、パネル全体をスクロールする）。
- 3 つのサブタブ（センサ取付・座標方向／自律走行の出力／Nav2）に効く。index.html・app.js は変えていない。保存の処理と値の扱いは変えていない。

## 検査・試験
- デモ：`design/.venv/bin/python gouda_core/test/demo_monitor_server.py 8765`（作業ツリー）、内蔵ブラウザ 1600×900。読み込まれた CSS に新しい規則 2 つがあることを確かめた。
  - 3 つのサブタブそれぞれに、自分のタブの DOM にだけ試験用の入力欄 40（とあれば表の行 10）を入れて確認（何も送っていない）：
    - センサ取付：パネル 123〜869 px（タブの中に収まる）、overflow auto、scrollHeight 872 / clientHeight 728、並びは縮まない、先頭の入力欄が見える、一番下で保存ボタンに届く → 合格。
    - 自律走行の出力：scrollHeight 729 / 728、同じ項目 → 合格。
    - Nav2：scrollHeight 820 / 728、同じ項目 → 合格。
    - 画面全体は縦にスクロールしない（900）。
  - センサ取付で、マウスのホイールで下へスクロール：scrollTop 143.5（最大 144）、保存ボタンが見える → 合格。
- 単体試験：`cd gouda_core/test && /opt/anaconda3/bin/python3 -m unittest test_monitor_server test_monitor_core` → 27 件、OK。
- 設計：`apply_revision.py REV-173 --dry-run --check` → 新しい違反 0・未判定 0。適用後に render_views・generate_params・render_migration_review（終了コード 0）、`run_checks.py` → 終了コード 1。
  設計検査は違反 0・未判定 5（合格 12）。移行の違反 2 件・test_real_model の不合格・input_integrity の FAIL は、intent.md の未記録の編集（AR-017 待ち）による既存のもの。
- VM の monitor の画面：未実行（確認しようとした時点で VM の Gouda は止まっていた。`gouda.sh status` → not running。起動していない）。

## 承認事項・実測待ち
- DEC-364：回答済み（実装の許可）。新しい承認待ち・実測待ちはない。

## 残るリスク
- 実際の /config の項目数での見え方は VM で見ていない。
- 1100 px より狭い画面の配置は確かめていない。

## 更新した生成物
- render_views・generate_params・render_migration_review で再生成（REV-173 は model を変えないので、記録の一覧の変化だけ）。

## 次の作業
- VM に style.css を写して、実際の画面で確かめる（Gouda の起動は人の確認の後）。コミットはまだ。→ §追記で実施。

## 追記：VM への反映、Gouda の起動、実際の monitor の画面での確認（2026-10-23）

人の指示（原文）「Copy style.css to the VM, start Gouda with gouda.sh start, and check /config on the real screen.」

- 写す前：`gouda.sh status` → not running。永続のモードの記録は manual（human_pause_or_end true、state_revision 196）。VM の style.css と手元の差は、この便で足した 4 行だけ（diff で確認）。
- 写したもの：style.css を scp で上書き。install 側から読んだ SHA-256 が手元と一致（df5a98705e2c…）。
- 起動：`bash gouda.sh start` → started（pgid 42066）、monitor の /api/state が 200、`gouda.sh status` → running（25 プロセス）。launch のログに Traceback・[ERROR] は 0 行。起動の後のモードは MANUAL・idle・run_id なし（state_revision 197）。
- 確認：SSH の転送（localhost:18080 → VM の 127.0.0.1:8080）で内蔵ブラウザから開き、1600×900。読み込まれた CSS に新しい規則 2 つ。試験用の行は入れず、実際の値だけで確認した。
  - センサ取付・座標方向：入力欄 20、パネル 123〜869 px（フッタより上）、overflow auto、scrollHeight 768 / clientHeight 728。最初は保存ボタンが下で見えない。マウスのホイールで下へ → scrollTop 39.5（最大 40）、保存ボタンが見える → 合格。保存は押していない。
  - 自律走行の出力：入力欄 6、729 / 728、すべて見える → 合格。
  - Nav2：入力欄 3、729 / 728、すべて見える → 合格。
  - 画面全体は縦にスクロールしない（900）。
- 転送の SSH は閉じた。Gouda は起動したまま（MANUAL）。
- 未確認：センサーの受信の状態（今回の確認の対象外。見ていない）。

## 追記：コミットと PR（2026-10-23）

人の指示（原文）「ryoya-1@g.ecc.u-tokyo.ac.jpでpushし、prまでつくれ」

- 共有の作業ツリーには REV-156 以降のほかの作業の未コミットの記録（model.yaml・status.md に混在）があるので、origin/main（d85a56d）から別の worktree を作り、第146便・第149便の web の 2 ファイル（index.html・style.css）だけをコミットした。作業ツリーの diff がこの 2 便の変更だけであることを確かめてから写した。
- コミット 8aa1d9d：author・committer とも aaa111aaa-111a <ryoya-1@g.ecc.u-tokyo.ac.jp>。Claude の共著者の行なし。
- push：fix/monitor-panel-scroll-2026-10-23。PR #19（base main）。CI のチェックはない。MERGEABLE。
- 記録（REV-171・REV-173、DEC-363・364、作業記録 第146便・第149便、status.md）はコミットしていない（ほかの記録とまとめてコミットする）。
