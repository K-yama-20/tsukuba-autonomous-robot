# 作業記録 2026-10-22 第130便: 点群の送受信の無駄の調べと、costmap の入力の作り直しの提案

## 読んだもの

- リモートの main `d85a56d`（PR #18 のマージ）を `git archive` で書き出した写し（作業ツリーは別のセッションが使用中のため触れていない）。手元の作業ツリーは `31a6e1d` ＋ 未コミットの変更（第127〜129便、別のセッション）。
- status.md（第126便の時点）、DEC-107・108・122・192・193、PRM-05・66・70・71、ND-09、RQ-I072・C-017、TS-37。
- 上流のソース: Nav2 1.3.13（observation_buffer.cpp、obstacle_layer.cpp、voxel_layer.cpp、controller_server.cpp）、HesaiLidar_ROS_2.0 e7e112f（source_driver_ros2.hpp、config.yaml）、glim_ros2 v1.2.2（glim_ros.cpp、rviz_viewer.cpp）、Autoware Core の ndt_scan_matcher_core.cpp（main。インストール済みの版とは未照合）、spatio_temporal_voxel_layer 2.5.5、perception_pcl jazzy ブランチ（2.6.5）。
- 車両の VM: SSH が接続できず（タイムアウト）、読めていない。

## 1. 人の指示（原文）

- 「現状のgouda内でのデータの送受信の無駄を探索せよ。リモートの最新のmainを見ること。特に点群データの扱いに無駄があるようだ」
- 「1、2の問題の改善に進む。改善案を採用した際のデメリットを考えよ。特に、9hz分をそのまま捨ててしまうより、10hz分を平均してからコストマップを作った方がロバスト性が高くなるのであれば9hz分をそのまま捨ててしまうのはもったいない」
- 「では、これらのデメリットを解決する手段を考えよ。特に、小さい障害物が消えてしまったり、遠い点を消してしまうことによるデメリットは無視できない。高さで切る基準の座標系が変わっているのも問題である。」
- 人の回答（原文）:
  「A: 許可する。
  B: 
  C: その案でも良いと思うが、スタート地点からロボットが進むにつれて段々標高が低くなって1.2mを下回るとまずいことになるのか？2.2kmの周回だから、多少の標高の上下はあると思うよ。障害物はLivox MID-360を入手したので、それでガンガン避けていこうって感じです。
  D: 採用
  E: 実行してもかまわない。」
  （A: costmap の格子に合わせて実点を残す間引き。B: 遠い点を光線の消去用に残す。C: base_link 基準の帯と柱の扱い。D: 前処理ノードを lifecycle にして lifecycle_manager に監視させる。E: NDT の前処理は段階 1 では分けたまま。いずれもこのチャットの AI の案の記号）
- 「C: 地面をRANSACで推定しよう。それなら解決かな？
  MID-360は前方の足元が主に見えています。よって、xt-32でも障害物を認識しておく必要はありますが、どうでしょうか。」
- 「自作プログラムよりも、なるべく既存の公開されているプログラムを使ってこれらの課題を解決できないか考えたい。複数エージェントを起動して、徹底的に調べよ。」
- 「Write a proposal in design/proposals: stage 1 = pcl_ros band/crop + STVL for the local costmap, global stays ObstacleLayer; MID-360 via livox_ros_driver2; list approval items (frustum clearing, decay, D revised, A superseded) and measurement items. No implementation.」

**台帳への登録はまだ**: 上の A・C・D・E の回答は、この便では判断台帳に登録していない（作業ツリーの model.yaml を別のセッションが未コミットで変更中のため、REV を当てなかった）。チャットにしか残っていない決定なので、次の登録で原文のまま記録する。

## 2. 分かったこと（コードと上流のソースで確かめた事実）

- 生の XT-32 点群（64,000 点 × 26 B ＝ 1.66 MB、10 Hz）を、自律走行中に GLIM・gouda_a3_points・controller_server・planner_server の 4 プロセスが別々に購読。地図作成の間は GLIM だけ。monitor は購読していない（DEC-281）。
- costmap は 2.5 m／3.0 m（`obstacle_max_range`・`raytrace_max_range` が未設定で上流の既定）までしか使わないのに、全点を TF 変換してから捨てる。global は 1 Hz の更新で 10 回のうち 9 回、local は 5 Hz で半分を捨てる。
- 高さの帯 PRM-70・71 は正本では base_link 基準だが、Nav2 は odom・map の z で当てている（原因の分類: 設計、定義と実装の不一致）。odom は GLIM の 3 次元の推定で、開始地点から下ると低い物が見えなくなる。VoxelLayer の柱も odom に固定。
- `expected_update_rate` が未設定で、点群の途絶を Nav2 が検出しない。
- rosbag が `-a` で記録（GLIM の rviz_viewer は購読者がいると点群の変換を始める）。Hesai driver は毎フレーム printf を起動ログへ。
- XT-32（取り付け高さ 1.015 m、最下のビーム −16.02°）は車体の周り約 3.5 m の地面が見えない。

## 3. 調査（4 つのエージェントを並行に起動）

前処理・転送／地面の推定／Nav2 の層／MID-360 の統合。apt の有無は packages.ros.org の Jazzy の索引で、振る舞いはソースで確かめた（各報告の「確認」の部分）。要点は提案 `proposals/costmap_inputs_stvl_mid360_2026-10-22.md` に書いた。主な事実:
- STVL 2.5.5（apt）: z の上限なし、錐台で消す、減衰で記憶、`combination_method` は 0・1 だけ（自分でソースを確かめた）。帯は global frame の z。
- pcl_ros（apt 2.6.5）: `input_frame` で変換して切り、`output_frame` 空なら元の frame に戻す。出力の購読者がいないと入力を外す。component として登録（いずれも jazzy ブランチで自分で確かめた）。lifecycle ではない。
- DEC-108 の要件をすべて満たす地面の推定の既製品はない。
- livox_ros_driver2 は apt になくソースビルド。同期モードに未解決の不具合。

生の報告は作業用の一時領域にあり、リポジトリには入れていない。

## 4. 行ったこと

- 提案 `design/proposals/costmap_inputs_stvl_mid360_2026-10-22.md` を新規に作成（承認事項 P-1〜P-9、実測 M-1〜M-11 は仮の番号、台帳に未登録）。
- 番号は reserve_ids.py で予約（第130便のみ。REV・DEC は取っていない）。
- コード・設定・正本（model.yaml）・生成物は変えていない。

## 5. 自律判断した変更

- なし（提案の文書と記録だけ）。

## 6. 検査・試験

- 設計検査（run_checks.py）: 未実行（正本を変えていない。作業ツリーは別のセッションの変更を含む）。
- 単体試験: 未実行（コードの変更なし）。
- 実機の計測: 未実行（VM に接続できない）。

## 7. 残るリスク

- 人の回答 A・C・D・E が台帳に未登録（チャットにしか残っていない）。
- 提案の前提（STVL・pcl_ros の振る舞い）は上流のソースを読んで確かめたが、実機の版で動かしてはいない（M-1〜M-3）。
- 今の構成のまま実車で Nav2 を動かす場合、K-3（標高で帯がずれる）と K-5（途絶を検出しない）は残っている。

## 8. 次に進められる作業と止まっている作業

- 進められる: 提案の承認事項・実測の項目と人の回答の原文の台帳への登録（作業ツリーが空いたら）。記録した rosbag を使った M-1〜M-3 の計画。
- 止まっている: 段階 1 の実装（P-1〜P-8 の承認待ち、DEC-106）。VM での計測（接続できない）。
