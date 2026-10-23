# 作業記録 2026-10-23 第151便: KUAMS の調査の証拠の登録と、トラブルシューティング台帳への登録（REV-175、TRB-006〜012）

## 読んだもの

- 作業ツリー：`31a6e1d` ＋ 未コミットの変更
  - status.md は第150便（REV-174）の時点
  - REV-174 の DEC-365〜381 が model.yaml にあることを確かめた（17 件）
- CLAUDE.md の 1.1〜1.9
- トラブルシューティング台帳 `design/troubleshooting/ledger.yaml`（TRB-001〜005）とその schema
- 第150便の提案 `proposals/kuams_adoption_review_2026-10-23.md` と topic1〜6.md
- 作業記録 `2026-10-21_rev134_plan_c_driving_nav2.md`（40〜50 行）
- 上流 Nav2 1.3.13 のソースの写し（第150便と同じ）

## 1. 人の指示（原文）

- 「判断台帳等への登録を進めよ」

## 2. 行ったこと

- **番号の予約**：`reserve_ids.py --label kuams-evidence-and-troubleshooting --bin` で REV-175 と第151便を取った
- **証拠の置き場**：`design/research/kuams_tc2025_2026-10-23/` に次を置いた

  | ファイル | 内容 |
  |---|---|
  | `notes.txt` | 出典と照合の状態 |
  | `tc2025_final_run_results_reduced.csv` | 本走行の結果。個人の名前を含む最後の 2 列（備考・随行委員）を除いた。取得した CSV の SHA-256 と、除いたことを notes.txt に明記した |
  | `kuams_repos_read.txt` | 読んだ KUAMS のリポジトリの commit の一覧 |
  | `kuams_comparison.md`・`kuams_summary.md`・`kuams_literature.md` | リポジトリの外の報告の写し |

- **REV-175 の適用**：`--dry-run --check` で新しい違反 0・未判定 0 を確かめてから適用し、上の 6 ファイルを FILE-KUAMS-TC2025-* として証拠に登録した。登録したファイルは、今後は追記しない（ハッシュで固定される）
- **トラブルシューティング台帳への追記**：TRB-006〜012 を足した。今の設定・設計が原因になりうる症状で、第150便の検討で見つかったもの

  | TRB | 状態 | 症状 |
  |---|---|---|
  | TRB-006 | 監視中 | 塞がれた waypoint の代わりの終点が残り、通り過ぎた後に戻る（PRM-11 と NavFn の tolerance の不整合） |
  | TRB-007 | **発生** | 回復が効かない種類の失敗で、PRM-18 に関係なく中止され、待機に入る |
  | TRB-008 | 監視中 | waypoint の向きがすべて 0 のため、最後の点でその場で回る |
  | TRB-009 | 監視中 | RPP の衝突の検査と local costmap が既定値のままで、急に現れた物の前で止まり切れない |
  | TRB-010 | 監視中 | LiDAR の途切れの間の EKF の外挿で、戻ったときに map→odom に段差が入る |
  | TRB-011 | 監視中 | 幅の広い物が waypoint を塞ぐと計画が失敗し続け、滞留する |
  | TRB-012 | 監視中 | 速い旋回で、deskew していない点群が NDT を乱す |

  - TRB-007 には、第104便の VM の試験の 1 回目の TR-07（status 6、error_code 0、受け付けの時間切れ。未解決）を occurrences として書いた
  - 書き換える前の台帳は、セッションの scratchpad に写しを取った。既存の TRB-001〜005 は変えていない
- コード・設定・正本の値は変えていない（DEC-106）

## 3. 自律判断した変更と理由

- **CSV から個人名の列を除いた**
  - 理由：リポジトリは公開されているので、随行委員や備考の人名を入れないため
  - 値は変えていない。変換したことは notes.txt と REV-175 の summary に明記した（1.5「黙って変えない」）
- **提案（proposals）は証拠に登録しなかった**
  - 理由：人の回答で作り直す可能性があり、ハッシュで固定すると直せなくなる（第150便と同じ扱い）
- **台帳の各項目で、事実と推測を分けた**
  - 事実：AI がコードや上流のソースで照合したもの
  - 推測：エージェントの読みで、AI が未照合のもの。推測と明記した
- **TRB の番号の取り方**
  - TRB の番号は reserve_ids.py の対象ではないので、追記の直前に台帳の最後の番号（TRB-005）を確かめてから取った

## 4. 実行した検査・試験

いずれも `31a6e1d` ＋ 作業ツリー、REV-175 の適用後に実行した。

- 台帳の schema の検証（jsonschema）：合格
- `python -m unittest design.rules.test_troubleshooting_ledger`：5 件 OK
- `apply_revision.py REV-175 --dry-run --check`：新しい違反 0・未判定 0
- `apply_revision.py REV-175`：適用（added_files 6）
- `render_views.py`・`generate_params.py`・`render_migration_review.py`：終了コード 0
- `run_checks.py`：終了コード 1
  - 設計検査は合格 12・違反 0・未判定 5
  - 次の失敗は、intent.md の未記録の編集（AR-017 待ち）による既存のもの。第149・150便と同じで、REV-175 による新しい違反はない
    - input_integrity の違反
    - 移行の違反 2 件（intent の版の鎖）
    - 検査器の試験 88 件のうち test_real_model の 1 件の不合格
- gouda_core の単体試験・VM・実機：未実行（コードを変えていない）

## 5. 承認事項と実測待ち

- 新しい DEC はない
- 第150便の DEC-365〜380 は、すべて人の回答待ちのまま
- TRB-006〜012 の対策の候補はどれも承認事項で、DEC-365〜380 のどれかに対応する

## 6. 残るリスク

- 台帳の推測（TRB-006・010・011・012）は、どれも記録の再生や VM の模擬でまだ確かめていない
- TRB-007 の 1 回目の原因は未解決である（再現していない。環境の問題とは断定していない）
- 証拠の写し（比較・まとめ・文献）は、元のファイルが後で変わっても、写しのほうは変わらない
  - `kuams_summary.md` の 64 行は、DEC-368 の回答によっては誤り。訂正は新しいファイルで行う

## 7. 更新した生成物の変更箇所

- render_views・generate_params・render_migration_review で作り直した
- REV-175 は files だけを足したので、設定の値（params）は変わらない

## 8. 次の作業

- **進められる**：DEC-374〜379 の計測の手順書と、解析のスクリプトの下書き（基盤、1.7）
  - 例：TRB-006・011 を確かめる VM の模擬（waypoint の上に障害物を置く）
  - 例：TRB-010 を確かめる途切れの試験
  - これらは試験の基盤であり、正本と挙動は変えない。実行は人の指示の後に行う
- **止まっている**：DEC-365〜373 の実装（人の回答と DEC-106 の許可の後）
