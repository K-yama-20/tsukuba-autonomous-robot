# 作業記録 第146便：monitor の waypoint タブで waypoint セットの選択欄に届かない不具合（REV-171、DEC-363）

日付：2026-10-23
読んだコミット：31a6e1d（作業ツリーにはほかのセッションの未コミットの変更あり）
読んだもの：design/reports/status.md（第145便まで）、CLAUDE.md の共通ルール、gouda_core/web/index.html・style.css・app.js

## 人の指摘と回答（原文は DEC-363）
- 指摘：「gouda_moniotrのwaypointが、下にスクロールできなくてwaypointファイルの選択が出来ない問題を解決する方策を提示せよ」
- 案 A・B・C を示し、回答「Bで」。B は A と組み合わせる前提と説明していたので、A＋B として実装した（解釈は DEC-363 の note）。

## 原因（分類：実装）
- `.screen` が `height: 100vh; overflow: hidden`、`.panel` が `overflow: hidden`。`.grid-wp` は行の高さを決めておらず、パネルをスクロールさせる指定もなかった。
- 右パネル `#wp-edit-panel` の区間の速度上限表と保存済みセットの一覧は waypoint・セットの数だけ長くなり、その下の「AUTO 自律走行の準備」（`#auto-set` など）がパネルの外に押し出されて操作できなかった。
- 地図タブは `.grid-maps .panel { overflow: auto; }` で同じ問題を避けていた。

## 変更（承認 DEC-363）
- `gouda_core/web/index.html`：AUTO の欄（セットの選択・プレビュー・初期位置・地図作成の終わりの姿勢）を右パネルの一番上に移した。要素の id は変えていない。発進準備シーケンスの案内を「waypoint タブ右の一番上「AUTO 自律走行の準備」」に直した。
- `gouda_core/web/style.css`：`.grid-wp` に `grid-template-rows: minmax(0, 1fr); min-height: 0;`、`.grid-wp .panel { overflow: auto; }`、`#wp-edit-panel .events { flex: 0 0 auto; max-height: 8em; }`（パネルがスクロールすると警告欄が高さ 0 に縮むのを防ぐ）。
- モード・開始の条件・送る要求は変えていない。app.js は変えていない（app.js の差分は第141便の未コミットの変更）。

## 検査・試験
- デモ：`design/.venv/bin/python gouda_core/test/demo_monitor_server.py 8765` を作業ツリーで起動し、組み込みのブラウザで 1600×900 に設定。試験用の行（区間表 40・保存済み 25・範囲 20）を JavaScript で入れて確認した。
  - 右パネル：scrollHeight 1734 / clientHeight 760、overflow auto。`#auto-set` はパネルの上（top 144 px）に見える。一番下までスクロールすると保存済みの最後の行（bottom 844）がパネルの下端（868.5）の内側に入る → 合格。
  - 画面全体は縦にスクロールしない（document の高さ 900）。
  - 左パネル：範囲 20 行で地図の表示域が 163 px に縮む。縮み方は変更前と同じで（flex: 1; min-height: 0）、今回の変更で起きたものではない。
- 単体試験：`/opt/anaconda3/bin/python3 -m unittest discover -s gouda_core/test`（31a6e1d ＋ 作業ツリー）→ 287 件、エラー 3（skip 10）。3 件とも test_ntrip_relay で、ほかのセッションが変更中の ntrip_relay.py（TLS 対応、DEC-361）の引数の変更による。今回の変更とは無関係。
  `python3 -m unittest test_monitor_server test_monitor_core` → 27 件、OK。
- 設計：`apply_revision.py REV-171 --dry-run --check` → 新しい違反 0・未判定 0。適用後に render_views・generate_params・render_migration_review（いずれも終了コード 0）、`run_checks.py` → 終了コード 1。
  設計検査は違反 0・未判定 5（合格 12）。移行の違反 2 件・検査器の試験の不合格 1 件（test_real_model）・input_integrity の FAIL は、intent.md の未記録の編集（AR-017 待ち）による既存のもの。
- 実車の monitor の画面：未実行（VM の Gouda には反映していない）。

## 承認事項・実測待ち
- DEC-363：回答済み（実装の許可）。新しい承認待ち・実測待ちはない。

## 残るリスク
- 左パネルは範囲の表が長いと地図の表示域が小さくなる（既存）。パネルはスクロールできるようになったので操作はできる。地図の最低の高さを決めるかは未提案。
- 1100 px より狭い画面の配置は確かめていない。

## 更新した生成物
- render_views・generate_params・render_migration_review で再生成（REV-171 は model を変えないので、記録の一覧の変化だけ）。

## 次の作業
- VM に反映して実際の画面で確かめる（人の指示があれば）。コミットはまだ。→ §追記で実施。

## 追記：VM の Gouda への反映と実際の monitor の画面での確認（2026-10-23）

人の指示（原文）「Push it to the VM's Gouda and check it on the real screen. Check the mode first.」

- モードの確認（写す前に別の手順で）：VM の monitor の /api/state で MANUAL・idle・run_id なし・受信あり（state_revision 194）。永続の記録も manual（human_pause_or_end true）。走行の試行中ではないので進めた。
- 写す前の照合：VM の `~/gouda_ws/src/tsukuba-autonomous-robot` は c2b8d65 ＋ 未コミットの変更。VM の index.html・style.css は 31a6e1d（この便の変更の元）と同じ、app.js は手元と同じことを diff で確かめた。
- 写したもの：index.html・style.css の 2 ファイルを scp で上書き。monitor は install/gouda_core/share/gouda_core/web → build → src へのリンクで読むので、colcon build と gouda.sh の再起動はしていない。install 側から読んだ SHA-256 が手元と一致（index.html 1fbb64f2fb75…、style.css 3b568b5e605e…）。
- 確認：SSH の転送（localhost:18080 → VM の 127.0.0.1:8080）で内蔵ブラウザから開き、1600×900 で waypoint タブを表示。
  - 新しい配置が配信されている：右パネルの最初の見出しが「AUTO 自律走行の準備」、overflow auto、読み込まれた CSS に `.grid-wp { … grid-template-rows: minmax(0px, 1fr) … }` と `.grid-wp .panel { overflow: auto; }`。画面全体は縦にスクロールしない（900）。
  - 今の VM のデータ（保存済みセット 4、セットの選択肢 4、区間表 0 行）ではパネルに収まる（scrollHeight 761 / clientHeight 760）。
  - あふれる場合：自分のタブの DOM にだけ試験用の行（区間表 40・保存済み 25）を入れて確かめた（VM には何も送っていない）。scrollHeight 1439 / clientHeight 760、セットの選択欄は見える、一番下までスクロールして最後の行に届く → 合格。確認後にページを読み直して試験用の行を消した。
- 確認の後もモードは MANUAL・idle・run_id なし・state_revision 194（変化なし）。転送の SSH は閉じた。
- 未実行：人が実際に waypoint を多数置いた状態での操作（今の確認は試験用の行による）。
