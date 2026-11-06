# 第205便 作業記録：gouda.sh の systemd 化と電源投入での自動起動の案（REV-223、DEC-434・435）

- 日付：2026-11-06
- 読んだコミット：7f0c7ae（作業ツリーに未コミットの変更あり。ほかのセッションと共有）
- 読んだもの：CLAUDE.md、`design/reports/status.md`、`gouda.sh`、ND-01、DEC-009・090・091・104・106・174、`design/proposals/sleep_inhibit_plan.md`、`gouda_core/gouda_core/mode_core.py`（decide_boot）
- 人の指示：「gouda.shをsystemdにしたい。」。自動起動の質問への回答「電源投入で自動起動」。どちらも DEC-434 に原文で記録した

## したこと

- 案を書いた：`design/proposals/systemd_autostart_plan_2026-11-06.md`（提案）。入口は `bash gouda.sh start／stop／status` のまま、中身を system unit `gouda.service` にして setup.sh で enable。停止は SIGINT・上限なし・SIGKILL なし（DEC-174 と同じ）、Restart=no。
- REV-223 で DEC-434（回答の記録）と DEC-435（実装の許可と Q2〜Q5、承認待ち）を登録した。
- 先行事例：Web 検索で robot_upstart（Jazzy の文書あり、Clearpath が使用）。gouda.sh の検査と DDS profile を通らない起動経路になるので不採用の案。ライセンス・`.launch.py` での使い方は未確認。他チームの事例は未調査。

## 自律判断

- 入口を gouda.sh に残す形を推奨にした。理由：DEC-090 の一つの起動経路と、起動前の検査・DDS profile を保つため。採否は DEC-435 で人が決める。
- 起動直後のモードは実装を読んで確認した（記録なし・前回手動なら手動走行、それ以外は一時停止で自律走行を再び許可しない）。自動起動でもこの振る舞いは変わらない見込み（コードは変えないため）。

## 原因の分類（1.6）

- 修正なし（新しい要望の記録と案）。

## 検査・試験

- `apply_revision.py REV-223 --dry-run --check`：新しい違反 0、新しい未判定 0。その後に適用。
- `render_views.py`・`generate_params.py`・`render_migration_review.py`：終了コード 0。
- `run_checks.py`（作業ツリー 7f0c7ae＋未コミット）：終了コード 1。設計検査 違反0件・未判定5件（合格 12）。generate_params・intent_identity は PASS。input_integrity・migration_validator・migration_tests の FAIL は、第184便で記録済みの不一致（`SystemArchitecture.drawio` と `.DS_Store`）で、今回の変更によるものではない（migration_validator.txt の違反の path を確認。REV-223・DEC-435 は改訂の一覧に出るだけ）。
- 単体試験・VM・実車：未実行（コード・設定は変えていない）。

## 承認事項・実測待ち

- 承認待ち：DEC-435（Q1 実装の許可、Q2 目的、Q3 スリープの抑止 DEC-104 を一緒に入れるか、Q4 自動起動を止める手段、Q5 PC の電源を切るときの保存の待ち方）。
- 実測待ち：なし（ネットワークの待ち時間で問題があれば別途）。

## 残るリスク

- 電源投入で、人がいなくてもセンサーのドライバ・vehicle_bridge・monitor が動き、ESP32 が繋がっていれば接続する（AI の懸念は 1 回述べた。判断は人）。
- OS の停止のときに、保存を待つ間の停止の処理全体の上限との関係は未確認（Q5）。
- system service から systemd-inhibit が取れるかは未確認（推測）。

## 更新した生成物

- `design/model.yaml`（REV-223 の適用：DEC-434・435）、`design/generated/` の再生成（スクリプトで）、`design/reports/` の検査結果。

## 次の作業（REV-224 の前）

- 進められる：DEC-435 の回答の後に、VM の試験用ワークスペースで unit の試作と §6 の試験。
- 止まっている：systemd 化の実装（DEC-435 の Q1 待ち）。

## 追記：方針転換（REV-224、DEC-435 の回答、DEC-436）

- 人の回答（DEC-435 に原文）：systemd 化はせず、PC の起動時に端末を開き最初のディレクトリを tsukuba-autonomous-robot にするだけにする。あわせて「source は毎回読み込まなくていいのか」の質問。
- systemd の案の提案書の冒頭に、採用しない旨を追記した（本文は記録として残す）。
- x86 の車載 PC を読み取りだけで確認（ssh、grep と ls）：~/.bashrc に ROS の読み込みはない、~/.config/autostart はない、gnome-terminal はある、自動ログインは無効。
- 質問への回答（DEC-436 の note）：gouda.sh は自分で setup.bash を読むので gouda.sh の前の source は不要。ros2・colcon・試験を端末で直接打つときは、新しい端末ごとに source が要る。
- DEC-436（承認待ち）：setup.sh で端末の自動起動（~/.config/autostart の .desktop）と ~/.bashrc の source を入れる案。代替は端末だけ、または開いた端末の中だけで source。
- 検査：`apply_revision.py REV-224 --dry-run --check` で新しい違反 0・未判定 0、適用、再生成 3 件は終了コード 0。`run_checks.py` の結果は status.md に書く。
- 人の指摘（原文）：「端末を自動起動させると、シャットダウンできなくなるでしょうが」。AI の見方（未確認、推測）：シェルだけの端末は止めない見込み。端末の中で前面のコマンド（ros2 topic echo、gouda.sh stop の待ちなど）が動いていると、閉じる確認や「作業中のアプリ」の表示で止まる見込み。Gouda が動いたままの停止は端末の有無によらない別の問題。実装の前に VM で確かめる（未実行）。DEC-436 の回答の時にあわせて記録する。
- 次の作業：DEC-436 の回答の後に setup.sh の変更と VM での確かめ。x86 への反映は人の操作（update.sh / setup.sh）。

## 追記（2026-11-07）：端末の自動起動をやめる（REV-227、DEC-436 の回答）

- 人の回答（DEC-436 に原文）：「端末を自動起動させると、シャットダウンできなくなるでしょうが」「端末の自動起動はやめる。私が望んだことを再度整理せよ。認識がズレている」。
- 原因の分類（1.6）：仕様（人の意図の読み違え）。AI が「systemd にしたい」を大きな設計に広げ、AI が作った二択の答えを人の望みとして扱い、「pc起動時にterminalを起動」を自動起動と字義どおりに取った。
- AI の今の理解（人の確認待ち、推測）：自分で開いた端末が最初から tsukuba-autonomous-robot にいて、ROS の環境も読み込み済みであればよい。systemd・自動起動・端末の自動起動は要らない。
- 検査：`apply_revision.py REV-227 --dry-run --check` で新しい違反 0・未判定 0、適用、再生成 3 件は終了コード 0。`run_checks.py` 終了コード 1、設計検査 違反0件・未判定5件。FAIL は既存の不一致（SystemArchitecture.drawio と .DS_Store）だけ。
- 次の作業：人の確認の後に、案と承認事項を出し直す。コード・設定は変えていない。

## 追記（2026-11-07）：望みの確定と実装の案（REV-228、DEC-439・440）

- 人の確認（DEC-439 に原文）：「まさにこのとおり」。望みは、端末を開くたびの cd と source を手でやらずに済ませること。
- 案（DEC-440、承認待ち）：setup.sh が ~/.bashrc の末尾に印の行で囲んだ数行を一度だけ足す（Jazzy の setup.bash、あればワークスペースの install/setup.bash、ホームで始まった端末だけ tsukuba-autonomous-robot に cd）。
- x86 の車載 PC を読み取りだけで確認：~/.bashrc は対話でないシェルで return する、ログインのシェルは bash。
- 検査：`apply_revision.py REV-228 --dry-run --check` で新しい違反 0・未判定 0、適用、再生成 3 件は終了コード 0。`run_checks.py` 終了コード 1、設計検査 違反0件・未判定5件。FAIL は既存の不一致（SystemArchitecture.drawio と .DS_Store）だけ。
- 次の作業：DEC-440 の回答の後に setup.sh と README を変え、VM で確かめる。コード・設定は変えていない。

## 追記（2026-11-07）：実装（REV-230、DEC-440 の回答）

- 人の承認（DEC-440 に原文）：「実装してよい」。
- 変更：`setup.sh` に 7. terminal の節（~/.bashrc の末尾に印の行で囲んだ 3 行を一度だけ足す：Jazzy の setup.bash、あればワークスペースの install/setup.bash、ホームで始まった端末だけリポジトリへ cd）と冒頭の一覧。`README.md` §1 に 7 を追記。
- 自律判断：足す行は `if ...; then ...; fi` の形にした（`[ ] && ...` だと条件が偽のときに .bashrc の最後の終了コードが 1 になるため）。パスは setup.sh の位置から求めて書き込む。
- 試験（作業ツリー 7f0c7ae＋未コミット、Ubuntu の計算機、一時的な HOME。本物の ~/.bashrc は触れていない）：`bash -n setup.sh` OK。setup.sh の 7 の節を切り出し、Ubuntu の既定と同じ対話の判定を先頭に持つ .bashrc で実行。2 回実行で印は 1 つ。対話の端末をホームで開くとリポジトリにいて ROS_DISTRO=jazzy・ワークスペース読込済み、/tmp で開くと /tmp のまま、対話でないシェルは何も読まない、ビルドがないときは Jazzy だけ読んでエラーなし。すべて期待どおり。
- 未実行：setup.sh 全体の実行、x86 の車載 PC への反映（人が `bash update.sh` か `bash setup.sh`）、読み込み済みの端末での colcon build の警告の有無、gnome-terminal の画面での確認。
- 原因の分類：修正なし（新しい要望の実装）。
- 検査：`apply_revision.py REV-230 --dry-run --check` で新しい違反 0・未判定 0、適用、再生成 3 件は終了コード 0。`run_checks.py` 終了コード 1、設計検査 違反0件・未判定5件。FAIL は既存の不一致（SystemArchitecture.drawio と .DS_Store）だけ。
- 残るリスク：~/.bashrc に同じような source をすでに手で書いている PC では二重に読む（害はない見込み）。リポジトリを動かすと書き込んだパスが古くなる（setup.sh を再実行しても印があれば直さない。印の行を消して再実行）。
