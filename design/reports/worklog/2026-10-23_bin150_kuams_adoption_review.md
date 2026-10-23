# 作業記録 2026-10-23 第150便: KUAMS の工夫を取り入れるかの検討の登録（REV-174、DEC-365〜381）

## 読んだもの

- 作業ツリー：`31a6e1d` ＋ 未コミットの変更
  - status.md は第149便（REV-173）の時点
  - ほかのセッションが同じ作業ツリーで第146〜149便を書いていた。それらの REV・作業記録には触れていない
- CLAUDE.md の 1.1〜1.9
- 判断台帳（model.yaml）の DEC-305〜314、DEC-339〜354、DEC-361〜364
- `design/docs/regulations_2026.md`：TK-22〜24、TK-66〜78、EV-15〜29、SP-31〜34
- `design/intent.md`：27 行・102 行。今のファイルは第16版から人が編集している（AR-017 待ち）
- コード
  - `gouda_core/gouda_core/autonomy_core.py`（95〜101 行）
  - `gouda_core/web/app.js`（525〜531 行）
  - `gouda_core/gouda_core/map_convert.py`（36〜41 行）
  - `gouda_core/gouda_core/nav2_config.py`
- 上流 Nav2 1.3.13 のソースの写し（別のセッションの scratchpad の research_c/nav2_1313）
  - `navigate_through_poses_w_replanning_and_recovery.xml`
  - `would_a_controller_recovery_help_condition.cpp`
- KUAMS のコードの写し（kuams@750934a、waypoint_manager@7671afa ほか。リポジトリの外）

## 1. 人の指示（原文）

1. 別のセッション「つくばチャレンジ ロボット調査」が転送してきた指示
   - 「メインのチャットに転送せよ。一個のトピックについて一個以上のエージェントを起動して検討させよ。」
   - この原文は転送文に書かれていたもの。人がこのチャットで直接書いたものではない
2. このチャットでの人の指示
   - 「Reserve IDs and register the approval and measurement items from KUAMS取り入れ検討.md, plus the record corrections, in the decision ledger. No implementation.」

## 2. 行ったこと

- **検討**：6 つのトピックごとに 1 つ、エージェントで検討した。エージェントは読むだけで、リポジトリには書いていない
  1. 推定不能で止まらない方針
  2. 区間ごとの goal と、その区間だけの出し直し
  3. 塞がれた waypoint を飛ばす条件
  4. 信号待ちの待機列か、手動で横断するか
  5. 速度・旋回の上限と collision_monitor
  6. 地図作成の軌跡から waypoint の候補を作る道具
- **提案の置き場**
  - まとめ：`design/proposals/kuams_adoption_review_2026-10-23.md`
  - 各トピックの全文：同じ名前のフォルダの `topic1〜6.md`
  - まとめはリポジトリの外の `reports/KUAMS取り入れ検討.md` の写しで、状態の行と参照先の行だけを直した
- **番号の予約**：`reserve_ids.py --label kuams-adoption-review --decisions 17 --bin` で REV-174、DEC-365〜381、第150便を取った
- **REV-174 の適用**：`--dry-run --check` で新しい違反 0・未判定 0 を確かめてから適用した
- **登録した項目**

  | DEC | 種類 | 内容 |
  |---|---|---|
  | DEC-365 | 承認 | 推定不能を故障の種類で分ける。DEC-342 の案 c の具体化 |
  | DEC-366 | 承認 | 区間ごとの goal と、その区間だけの自動の出し直し。DEC-307 の新しい答え |
  | DEC-367 | 承認 | opt-in で waypoint を飛ばす（DEC-310 の段 3）。DEC-344 (2) の再確認を含む |
  | DEC-368 | 確認 | TK-70 は本走行に適用されるか |
  | DEC-369 | 確認 | 待機列で前が空かないときの扱いと、過去の列の長さ |
  | DEC-370 | 承認 | 待機列の段階 queue_follow を DEC-343 に足す |
  | DEC-371 | 承認 | 大域の上限は変えず区間の速度上限で遅くする。RPP と local costmap の値を PRM にする |
  | DEC-372 | 確認 | collision_monitor の案は intent.md の範囲に入るか |
  | DEC-373 | 承認 | 軌跡から waypoint の候補を作る道具 |
  | DEC-374〜379 | 実測 | トピック 1〜6 の値 |
  | DEC-380 | 確認（technical_pending） | 検討で見つかった実装の抜け：Mission が kind を落とす、waypoint の向きが 0、RPP と local costmap の値が未設計 |
  | DEC-381 | 記録の訂正（recorded） | DEC-343・DEC-345 の note の「規則の原文を読んでいない」を、この項目で置き換える |

- **書き換えなかったもの**
  - DEC-345 は回答済み（確定）なので書き換えていない（CLAUDE.md 1.5）
  - DEC-343 も pending のまま、note を書き換えていない
- コード・設定・正本の値は変えていない（DEC-106）

## 3. 自律判断した変更と理由

- 実測の項目は、トピックごとに 1 つにまとめた。既存の実測の項目と重なるものは、新しく作らずに参照した
  - DEC-346 (1)・(2)、DEC-293、DEC-354、DEC-314、Q-06
- 規則の条文の ID（TK・EV・SP）は model.yaml の実体ではないので、affected_refs には入れなかった。note の文中で regulations_2026.md の番号として書いた
- エージェントの主張のうち、私が照合したものと未照合のものを、note で分けた
  - 照合したもの：規則の条文、intent.md の 27・102 行、autonomy_core.py:100、app.js:529、map_convert.py の軌跡の説明、Nav2 の WouldA…RecoveryHelp、KUAMS の lineup のヘッダのパス
  - 未照合のもの：ComputePathThroughPoses が 1 区間の失敗で全体を失敗にすること（トピック 3 のエージェントの主張）

## 4. 原因の分類（1.6）

DEC-380 の抜けは修正していない。分類だけを示す。

- Mission が kind を落とす：実装
- waypoint の向きが 0：実装
- RPP と local costmap の値が未設計：設定

## 5. 実行した検査・試験

いずれも `31a6e1d` ＋ 作業ツリー、REV-174 の適用後に実行した。

- `apply_revision.py REV-174 --dry-run --check`：新しい違反 0・未判定 0
- `apply_revision.py REV-174`：適用（added_entities 0、modified 0）
- `render_views.py`・`generate_params.py`・`render_migration_review.py`：終了コード 0
- `run_checks.py`：終了コード 1
  - 設計検査は合格 12・違反 0・未判定 5（design_check.txt の要約行）
  - input_integrity の FAIL、移行の違反 2 件、test_real_model の不合格 1 件（88 件中）は、intent.md の未記録の編集（AR-017 待ち）による既存のもの。第149便と同じで、REV-174 による新しい違反はない
- gouda_core の単体試験・VM・実機：未実行（コードを変えていない）

## 6. 承認事項と実測待ち

- **承認待ち**：DEC-365・366・367・370・371・373
- **確認待ち**：DEC-368・369・372・380
- **実測待ち**：DEC-374〜379

## 7. 残るリスク

- エージェントの報告のうち、未照合のもの（Nav2 のソースの一部、計算の前提）が判断の材料に含まれる
- 規則の解釈（TK-70 が本走行に適用されるか）は推測で、DEC-368 の回答が要る
- 「違反 0 件」は安全の証明ではない
  - 重大なハザードは各 DEC の note と提案 §6 にある：コース外れ・車道への進入、stop を越える、待機列での衝突・回り込み、ずれた推定のまま走ること
  - 安全の根拠となる前提は変わらない：ESP32 の watchdog、手動操作の優先、PC の出力の中立化は車体全体の停止の保証ではない

## 8. 更新した生成物の変更箇所

- 生成物は render_views・generate_params・render_migration_review で作り直した
- REV-174 は decisions だけを足したので、設定の値（params）は変わらない
  - generated の多くのファイルが git の上で M になっているのは、ほかの便の未コミットの変更による

## 9. 次の作業

- **進められる**：回答を待たずにできる基盤作業（1.7）。いずれも正本と挙動は変えない
  - DEC-374〜379 の計測の手順書
  - 解析のスクリプトの下書き
- **止まっている**：DEC-365〜373 の実装（人の回答と DEC-106 の許可の後）
- **人が直すもの**：リポジトリの外の `KUAMSの工夫まとめ.md:64` の記述は、DEC-368 の回答の後に直す
