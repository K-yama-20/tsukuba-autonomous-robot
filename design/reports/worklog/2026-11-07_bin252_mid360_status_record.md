# 第252便 作業記録：MID-360 の状態・温度・診断コードを log と rosbag に記録する（DEC-479・DEC-494 の A、REV-278）

- 日付：2026-11-07
- 読んだコミット：作業の前半は共有の作業ツリー（9c449b5 の上に他のセッションの未コミットの変更）。後半は c8bf7bb（chat/mid360-a1-2026-11-07、A1 だけのコミット。統合ブランチ 9acdc7f の上）
- 作業したブランチ：`chat/mid360-status-2026-11-07`（worktree `tsukuba-worktrees/mid360-status`、c8bf7bb から切った）
- 区切りで作ったコミット：e0bdd8a（第252便の変更と REV-278 の適用）。この行を書いた記録のコミットはその次
- このセッションは、第235便のセッションから人が分けたもの（fork）。第247便（REV-274）の続き
- 読んだもの：CLAUDE.md（1.1〜1.14。作業の途中で 1.14 の worktree の規則が入った）、REV-274 の DEC-494、issue #93、`gouda_core/gouda_core/recorder_node.py`・`recorder_core.py`、上流 Livox-SDK2 c0796f0 の `parse_lidar_state_info.cpp`（`LivoxLidarStateInfoToJson`）・`include/livox_lidar_api.h`・`samples/livox_lidar_quick_start/main.cpp`、公式の通信プロトコル `livox_eth_protocol_mid360.md` 338〜396 行（リポジトリの外）

## 人の回答（原文）

- 質問「DEC-494 は推奨の A（ドライバの写しに patch）で進めますか？」への回答：「A で進める」（DEC-494）
- 作業の途中の人の指示：「今後、並列のチャットは git worktree で作業する。…」（共有の作業ツリーを便ごとにコミットする作業は、他のセッションが担当した）、「何をしているの？」

## 変更

| ファイル | 内容 |
|---|---|
| `third_party/patches/livox_ros_driver2/0001-publish-lidar-state-push-on-diagnostics.patch`（新） | 上流 2144554 に当てる patch。SDK の `SetLivoxLidarInfoCallback` を登録し、状態の通知を受けるたびに `/diagnostics` に DiagnosticArray を 1 つ出す。既存の 4 ファイルは行を足すだけ（+13 行）、新しいファイル 3 つ（`src/call_back/lidar_status_info.h`、`lidar_status_publisher.{h,cpp}`） |
| `third_party/patches/livox_ros_driver2/.gitattributes`（新） | `*.patch -text -whitespace`（patch が CRLF を含むため） |
| `third_party/patches/livox_ros_driver2/test/`（新） | `run_tests.sh`、`test_lidar_status_info.cpp`（ROS なしの単体試験） |
| `setup.sh` | A1（c8bf7bb）の上に：`make_livox_copy`（固定の commit を写し、patch を名前の順に当て、当たらなければ止まる）、3 節の rosdep は patch 後の manifest を読む、5 節の stamp に patch の hash |
| `third_party/drivers.repos`（コメント）、`README.md`（46・188 行と「リポジトリの中」の表） | patch の説明 |
| `gouda_core/gouda_core/mid360_config.py` | `DIAGNOSTIC_NAME = 'mid360'` |
| `gouda_core/gouda_core/recorder_core.py` | `diagnostic_payloads(msg, name)`（ROS なしで試験できる取り出し） |
| `gouda_core/gouda_core/recorder_node.py` | `/diagnostics` を購読し、name mid360 の status をすべてログ（events.jsonl）に書く |
| `gouda_core/test/test_recorder_diagnostics.py`（新） | 9 件 |
| `design/research/upstream_sensors/livox_ros_driver2_status_patch_2026-11-07.md`（新） | 約束との対応、thread の根拠、先行事例、試験と証拠の sha256、上流 #80 への PR の本文の下書き（英語、投稿していない） |
| `design/revisions/REV-278.yaml`（新、適用した） | DEC-494 answered、ND-20・ND-04・IFD-27 の修正 |

## 部品のあいだの約束（このセッションが決めた）

- topic は `/diagnostics`（DiagnosticArray、rclcpp の既定の QoS）、通知 1 回に 1 つ
- status は name `mid360`、hardware_id は空、message `info push`
- level は lidar_diag_status の 4 つのモジュールの段階の最大：0 OK、1 WARN、2・3 ERROR、ないとき STALE（通信プロトコル 0x800E の定義）
- values は許可した 14 項目だけ：cur_work_state、core_temp（0.01 ℃ の整数のまま）、powerup_cnt、last_sync_time、time_offset、time_sync_type、status_code、lidar_diag_status、lidar_flash_status、FW_TYPE、hms_code、version_app、version_loader、version_hardware。SDK の JSON に入るシリアル番号・MAC・アドレスは出さない
- 記録のためだけ。走行の判断には使わない（DEC-456 は pending のまま）

## 自律判断とその理由

- log にも書く：rosbag は人がボタンで始めるもので自動では始まらない（intent 24 行）。log は事前地図作成と自律走行の開始で自動で始まる
- 約束が決めていない細部（patch のサブエージェントが決めた。記録のためだけの値）：モジュールの段階が 4〜15 なら ERROR、lidar_diag_status が読めないときは STALE、読めない通知でも STALE で 1 つ出す、dev_type で絞らない
- ND-20 の内蔵 IMU の項目の「DEC-476〜478（未決）」を、REV-274 の回答に合わせた（意味を変えない整合の修正）
- ND-04 の subscribes_refs に IFD-27 を足した：IFD-27 の consumer には前から ND-04 があった（整合の修正）
- 作業の途中で worktree の規則（1.14）が入ったので、共有の作業ツリーの第252便の変更を、A1 だけのコミット（c8bf7bb）の上の自分の worktree に写し直した。写す前に、共有の作業ツリーの各ファイルと c8bf7bb の版の差が第252便の分だけであることを diff で確かめた。共有の作業ツリーのファイルは書き換えていない

## 承認事項・実測待ち

- DEC-456（つながらない・状態が悪いときの扱い）は pending のまま。この便の記録は走行の判断に使わない
- 通知の周期：資料に書かれていない。P4（T04）でセンサーをつないで測る

## 実行した検査・試験

| 検査 | コマンド | 対象 | 結果 |
|---|---|---|---|
| gouda_core の単体試験 | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=gouda_core python3 -m unittest discover -s gouda_core/test` | worktree（c8bf7bb＋この便の変更） | 498 件 OK（skip 35） |
| patch の単体試験 | `bash third_party/patches/livox_ros_driver2/test/run_tests.sh <上流 2144554 の clone>` | 同上 | -std=c++14・c++17 とも 148 checks, 0 failed（Mac） |
| patch が当たるか | 上流 2144554 を `git archive` で一時フォルダに写し、setup.sh と同じ `git apply` | 同上 | 当たった。新しいファイル 3 つができた |
| setup.sh の構文 | `bash -n setup.sh` | 同上 | 通った。shellcheck は未実行（入っていない） |
| REV-278 の試し | `design/tools/apply_revision.py REV-278 --dry-run --check` | 同上 | 修正 3 件、0 new violations、0 new undetermined |
| REV-278 の適用と再生成、設計検査 | `apply_revision.py REV-278`、`generate_params.py`、`render_views.py`、`render_migration_review.py`、`run_checks.py` | 同上 | 下の「設計検査の結果」 |
| ワークステーションでのビルド（サブエージェントの報告） | setup.sh の節の写しで、patch を当てた写しを colcon でビルド | 共有の作業ツリーの同じ内容 | 空から・2 回目は作り直さない・patch を変えると作り直す・当たらない patch で止まる、が想定どおり。harness で `/diagnostics` の中身と、Stop の後に publish しないことを確かめた |
| センサーをつないだ確認、Dell での setup.sh、gouda_recorder とドライバの結合 | — | — | 未実行 |

### 設計検査の結果

- `run_checks.py` の終了コード 1。design_check PASS、generate_params PASS、intent_identity PASS。FAIL は input_integrity（SystemArchitecture.drawio と .DS_Store 2 つの不一致）、migration_validator、migration_tests で、c8bf7bb の時点と同じ前からのもの
- design_check.txt の要約：合格 12・違反 0・未判定 5（違反0件・未判定5件）
- 生成物の params は、model の hash の行だけが変わった（19 ファイル、各 1 行）

## 原因の分類（1.6）

- patch の途中の版が rapidjson の writer.h を使い、同梱の dtoa.h の警告を 1 件増やしていた（実装）。値の文字列を自前で作るように直し、確認を「全部の警告を A1 の log と比べる」に改めた（試験基盤）。サブエージェントの報告

## 残るリスク

- MID-360 が実際に送る項目と周期は未確認。周期が短いと、events.jsonl の容量と recorder の負荷が増える
- reliable の publish が待つと、その間 SDK の command の thread も止まる（未測定）
- patch は DEC-075 の例外。固定の commit を変えるたびに `run_tests.sh` とビルドを確かめる。patch は CRLF を含むので、エディタで保存し直すと当たらなくなりうる
- 当たらない patch では setup.sh の 3 節で止まり、Gouda の作業場所のビルド（5 節の前半）も実行されない
- recorder_node.py は mid360_config.py を import する。片方だけをコミット・反映すると gouda_recorder が起動しない（このコミットでは両方を入れた）
- 共有の作業ツリーに、第252便の同じ変更と REV-278 の予約の stub（未追跡）が残っている。統合の担当が merge する前に片付ける必要がある（共有の作業ツリーには書かない規則のため、このセッションは触っていない）
- ND-07（global_localization）は /diagnostics を購読しているが、正本の subscribes_refs にない（前からの食い違い。この便では直していない）

## 生成物の変更箇所

- REV-278 の適用による：model.yaml（DEC-494、ND-20・ND-04・IFD-27）、generate_params・render_views・render_migration_review の出力、design/reports の検査結果

## 次の作業

- 人：統合ブランチへの merge（統合の担当）、Dell での `bash setup.sh`（patch を当てたドライバ）、P4 で状態の通知が出ること・周期・項目を確かめる
- 進められる：上流 #80 への PR（投稿は人の指示の後）
- 実車投入可能：人の判断待ち
