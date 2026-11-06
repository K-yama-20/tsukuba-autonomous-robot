# 作業記録 2026-11-07 第215便: MPPI の open_loop を /config で切り替える（REV-240、DEC-449、PRM-141）

## 読んだもの

- コミット `9c449b5`（ブランチ design/mppi-sim-2026-11-03）＋作業ツリー（他のセッションの未コミットの変更を含む）。
- `design/reports/status.md`、intent.md 1 行目、第210・212便の作業記録、K-yama-20/tsukuba-autonomous-robot#61。
- 車載 PC（x86）の状態を ssh で読むだけにした（ブランチ、未コミットの件数、経路、起動の log）。Gouda・車体には触れていない。

## 1. 人の指示と回答（原文）

- 「今日の7時までになんとか確認走行合格水準まで持っていきたい。優先順位を付けてプランを立てよう。まずはげんじょうのはあくから。」
- 質問「MPPI の open_loop 切り替え（/config で戻せる形）の実装に着手してよいですか？」→「着手して」（DEC-449）。

## 2. 変更

- 正本：PRM-141（mppi_open_loop、boolean、既定 true）。ND-10・IFD-54 に追記（REV-240）。
- `gouda_core/gouda_core/nav2_config.py`：TUNABLES に mppi_open_loop、`mppi_follow` が FollowPath の `open_loop` に書く。RPP のときは書かない。
- `gouda_core/web/app.js`：/config「Nav2」タブの表示名。
- `gouda_core/test/test_nav2_config.py`：`test_mppi_open_loop`（既定 true、/config で false、RPP では書かない）。`test_mppi_is_the_default` の「雛形から変えた項目」の一覧に open_loop を足した。
- 生成物：`design/generated/params/gouda_nav2.yaml` ほか（generate_params.py・render_views.py・render_migration_review.py）。

## 3. 自律判断

- 既定を true にした。質問の「/config で戻せる形」を「open_loop を既定にして false に戻せる」と AI が読んだもので、人は値を明示していない（DEC-449 の note）。
- 要求の参照は RQ-I091 の後継 RQ-I104 にした（RQ-I091 は superseded）。
- `test_mppi_is_the_default` の一覧への追加は、承認された設計の変更（DEC-449）に伴うもので、値の確かめは新しい試験に置いた。

## 4. 原因の分類（1.6）

- 設定（Nav2 の MPPI の設定）と物理特性（不感帯、DEC-445）。上流の既定では MPPI が実速度を初期状態にし、車速 0 のとき指令が不感帯に届かない（#61）。

## 5. 検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| 変更セットの試し | `apply_revision.py REV-240 --dry-run --check` | 9c449b5＋作業ツリー | 1 回目は違反 1（RQ-I091 が superseded）。直して新しい違反 0・未判定 0 |
| 単体試験（Mac） | `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test` | 同上 | 360 件 OK（skip 15） |
| 設計検査 | `design/.venv/bin/python design/tools/run_checks.py` | 同上 | 終了コード 1。設計検査は違反 0（DR-04 未判定 5、DR-05 未判定 4 ほか）。不合格は既存のもの（input_integrity、migration_validator の drawio、migration_tests の test_real_model） |
| 模擬（ワークステーション、~/gouda_ws_ol、DEC-445 の車体モデル `--m1107`、等速） | `drive_sim.sh free|cone_late`、製品の切り替えのみ（試験用の上書きなし） | ~/gouda_ws_m4x/src の写し＋この便の変更 | 既定（open_loop true）：free 2/2・cone_late 2/2 でゴール、平均 0.37〜0.40 m/s、停止 1.2 s、接触 0、コーンとの最小間隔 0.05・0.18 m。/config で false：free 0/1・cone_late 0/1（進み 0.9 %、平均 0.002 m/s） |
| 生成された設定 | 模擬の出力の nav2_params.yaml | 同上 | 既定の 4 本すべてで `open_loop: true`、/config で false の 2 本で `open_loop: false` を確認 |
| 実車・車載 PC への反映 | — | — | 未実行 |

- 模擬の 1 回目は、作業場所の写しをセンサードライバの下敷きなしでビルドしたため gouda_monitor が落ち、開始が拒否された（試験基盤の誤り）。下敷きを足してやり直した。合否の基準は変えていない。
- 模擬の作業場所の nav2_config.py は ~/gouda_ws_m4x の写し（試験専用の上書きの関数つき）に、この便の 2 か所を足したもの。Mac の作業ツリーと同一のファイルではない。

## 6. 残るリスク

- 実車の open_loop は未確認。open_loop では MPPI が前回の指令から次の指令を作るので、車体が追従しない間も指令が増える。
- 模擬は各条件 1〜2 回で、車体モデルは DEC-445 の各条件 1 回の実測に基づく。旋回の遅れは粗い値。
- コーンとの最小間隔 0.05 m の走行があった（接触は 0）。
- 車載 PC はブランチ dev-tab-vehicle-test＋未コミットの写しで、この便の変更は入っていない。車載 PC の nav2_config.py との差は、この便の変更と、他のセッションの定数 1 行。

## 7. 次

- 人の判断：車載 PC への反映、実車での確認。
- 進行中（別の便）：MPPI の速度の下限（vx_min）の模擬、不感帯を MPPI の中に入れる改造版、MID-360 の最小構成。
- commit はしていない。

## 8. 追記：車載 PC への反映

- 人の回答（原文）：「作業はopes5.5にやらせよ。車載PCに反映して良い」（DEC-459、REV-243）。「opes5.5」は Opus 5.5 と AI が読み、反映の作業を Opus 5.5 の subagent に行わせた。
- 読んだコミット：Mac `9c449b5`＋作業ツリー。車載 PC はブランチ dev-tab-vehicle-test＋未コミットの写し（触れた 4 ファイル以外はそのまま）。

### 反映の前の確認

- 車載 PC の作業用ワークスペース（~/gouda_ws）の Gouda は動いていない。`pgrep -l`／`pgrep -c` で名前だけを見た（コマンド行は表示していない）。動いていたノード群は 3 組とも別の模擬用ワークスペース（他のセッションの模擬、esp32_sim つき）のもので、/proc の cwd と読み込んだライブラリの経路で確かめた。それらには触れていない（模擬側が作業用ワークスペースから読むのは hesai_ros_driver のメッセージのライブラリだけで、今回は作り直していない）。
- 前回の状態記録は mode manual。

### 反映したもの（位置を確かめて差し込む形。各位置が 1 か所だけであることを assert）

| ファイル | 内容 |
|---|---|
| gouda_core/gouda_core/nav2_config.py | TUNABLES の `mppi_open_loop`（PRM-141）と、mppi_follow の `open_loop` の 1 行（＋注釈 1 行） |
| gouda_core/web/app.js | /config の表示名 `mppi_open_loop` の 1 行 |
| gouda_core/test/test_nav2_config.py | `test_mppi_open_loop` と、`test_mppi_is_the_default` の changed の `'open_loop'` |
| design/generated/params/gouda_nav2.yaml | Mac の写しで置き換え。直前の差分は見出しのハッシュの行と `mppi_open_loop: true` の行だけだった |

- ファイル全体の置き換えは gouda_nav2.yaml だけ。nav2_config.py と app.js は Mac の作業ツリーに他の便の変更があるので写していない。
- 控え：車載 PC のホームの下、ワークスペースの外に、変更前の 4 ファイル（sha256 つき）と差し込みのスクリプトを置いた（ディレクトリ名は backup_rev240_ と日時）。

### 実行した検査・試験（車載 PC）

| 項目 | コマンド | 結果 |
|---|---|---|
| 作り直し | `colcon build --symlink-install --base-paths <ws>/src --packages-select gouda_core --executor sequential`（直前 2 回の作り直しと同じ指定で、対象を gouda_core だけにした） | `Summary: 1 package finished`、終了コード 0 |
| 入ったものの確認 | install の egg-link が指す nav2_config.py と、share/gouda_core/web/app.js の実体を grep | nav2_config.py の 140 行目（TUNABLES）・195 行目（mppi_follow）、app.js の 466 行目に mppi_open_loop。--symlink-install なので、どちらも作業ツリーのファイルそのもの（monitor は share/gouda_core/web から配る） |
| 単体試験 | `PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test -p test_nav2_config.py` | `Ran 23 tests`、OK。`-k open_loop -k mppi_is_the_default` で 2 件とも ok |
| 未コミットの件数 | `git status --short \| wc -l` | 前 96、後 99（新たに変更になったのは nav2_config.py・app.js・test_nav2_config.py。gouda_nav2.yaml は元から変更済み） |
| 触れたファイルの差分 | `git diff --stat`（4 ファイル、ブランチの HEAD との差） | 4 files changed, 19 insertions(+), 2 deletions(-) |

- 単体試験の最初の 1 回は、ファイルの経路を直接渡す形（`python3 -m unittest gouda_core/test/test_nav2_config.py`）で、モジュール名の解決に失敗した（ImportError、試験の呼び方の誤り）。discover の形でやり直した。合否の基準は変えていない。

### Mac 側の記録

- `reserve_ids.py --label rev240-deploy --decisions 1` → REV-243、DEC-459。
- `apply_revision.py REV-243 --dry-run --check` → 0 new violations, 0 new undetermined。適用の後、generate_params・render_views・render_migration_review を実行。
- gouda_nav2.yaml の見出しのハッシュが変わった（値は同じ。`mppi_open_loop: true`）。パラメータの値は変わっていないので、車載 PC には写し直していない。車載 PC の写しの見出しのハッシュは Mac と一致しない。
- `run_checks.py`（コミット `9c449b5`＋作業ツリー）：1 回目は migration_tests が 2 件不合格（test_real_model と test_empty_source_refs_is_a_new_violation）。後者は「dry run の間に model.yaml が書き換わった」という失敗で、同じ時刻に別のセッションが REV-241・242 を適用していた（model.yaml の更新時刻 02:12 台）。その試験だけを単独で再実行すると OK、run_checks の再実行では不合格は test_real_model の 1 件（既存、drawio）だけ。設計検査は 2 回とも違反 0 件・未判定 5 件。input_integrity・migration_validator の不合格は既存のもの。
  - 原因の分類（1.6）：断定はしない。作業ツリーを共有するセッションの同時書き込みの可能性が高い（推測）。再実行で消えたが、未解決として残す。

### 実行していないこと

- Gouda の起動、/config の画面の確認、実車：未実行。
- commit・push：未実行。

### 残るリスク

- 実車の open_loop は未確認（6 節のとおり）。次の `gouda.sh start` から既定 true が効く。
- 車載 PC は未コミットの写しが 99 ファイルになった。ブランチの内容とは一致しない。
