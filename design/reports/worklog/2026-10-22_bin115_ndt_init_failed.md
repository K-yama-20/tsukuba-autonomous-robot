# 第115便：自律走行開始で ND-07 が推定不能（init_failed）になる件（REV-143、DEC-279・280）

日付：2026-10-22

## 読んだもの

- コミット `a27de9e`（main）。VM の `~/gouda_ws` も a27de9e。Gouda は人が起動したもの（止めていない）。
- `design/reports/status.md`、第114便の作業記録、`gouda_core/gouda_core/global_localization_node.py`、`gouda_core/launch/gouda_localization_a3.launch.py`。

## 人の指示（原文）

- 「自律走行開始しても、推定不能とばかり出る」（monitor の記録の貼り付けつき。0:51:28 に TR-07「TR-05 failed: gouda_global_localization: 推定不能 (init_failed: ndt_align_srv did not succeed (no map->odom is published))」）

## 分かったこと

- 00:48〜00:52 の 5 回とも、A3 の起動から 1.5〜3 秒で ndt_align_srv が失敗した。NDT のログは毎回「No InputSource. Please check the input lidar topic」だけ。地図は読めている（No InputTarget は出ていない）。
- ND-07 はサービスが現れるのを待つだけで、点群が NDT に届くのを待たずに ndt_align_srv を呼ぶ（`_initialize`）。
- Autoware の ndt_scan_matcher 1.9.0（VM の版）のソース `ndt_scan_matcher_core.cpp` を読んだ。点群は、点 0、TF の失敗、最大距離 < required_distance（10 m）のとき捨てられる。最大距離の不足はログに出ず /diagnostics だけ。
- XT-32 の点群（IFD-21）は正常。1 通を読むと、点 64000、最大距離 74.75 m、遅れ 0.1 秒、frame xt32_link。hesai_ros_driver は RELIABLE で出し、1 通 1664000 バイト。
- 受け渡しの量（一時的な Python の購読、10 秒）
  - BEST_EFFORT：0 通。2 回目は 8 通。
  - RELIABLE：73 通。最初の 1 通まで 3.0 秒。
  - BEST_EFFORT ＋ UDP の受信バッファ 4 MB の Fast DDS の profile（その試験のプロセスだけ）：75 通。
  - net.core.rmem_default は 212992、rmem_max は 4194304。RMW は既定（Fast DDS）。Fast DDS の profile は Gouda にはない。
- pcl_ros の filter_crop_box_node を、別の名前空間（/probe_tmp）で一時的に動かした。
  - 入力を BEST_EFFORT で購読する。出力に購読者がいるときだけ入力を購読する。
  - 18 秒で 3 通しか出さなかった（12 秒の試験では 1 通）。
- 結論（推論）：A3 の最初の段（CropBox）にほとんど点群が届かない。そのうえ ND-07 は点群を待たずに呼ぶので、毎回 No InputSource になる。

## 原因の分類（1.6）

- 実装：ND-07 が、NDT が点群を受け取る前に ndt_align_srv を呼ぶ。待ち方を変えるのは振る舞いの変更なので、承認事項 DEC-280 にした。
- 設定：1.66 MB の点群を BEST_EFFORT で受けるための受信バッファが足りない。承認事項 DEC-279 にした。
- 呼び直しの追加（DEC-280 の案 c）は、原因を隠すので推奨しない。

## 自律判断した変更

- なし（コード・設定は変えていない）。記録だけ。

## 承認事項と実測待ち

- DEC-279（pending）：点群の受け渡し。推奨は案 a。gouda.sh start で起動するノードに Fast DDS の profile を与え、UDP の受信バッファを大きくする。
- DEC-280（pending）：ND-07 の初期化の待ち方。推奨は案 a。NDT の /diagnostics が、点群を保存したと示すまで待つ。待つ間は IFD-53 に理由を出す。

## 実行した検査・試験

- `design/.venv/bin/python design/tools/apply_revision.py REV-143 --dry-run --check`（a27de9e の作業ツリー）：新しい違反 0、新しい未判定 0。
- REV-143 の適用（a27de9e の作業ツリー）。render_views.py、generate_params.py、render_migration_review.py は終了コード 0。
- `design/.venv/bin/python design/tools/run_checks.py`：終了コード 1。
  - design_check・generate_params・intent_identity は合格。
  - input_integrity・migration_validator・migration_tests は違反。
    - 違反の中身は 3 つ。原本 `design/docs/SystemArchitecture.drawio` のハッシュの不一致（FILE-DRAWIO）、`extraction_20261008_01a11af4` の `.DS_Store` 2 つ、intent の旧要求の行。
    - drawio は、この便の開始のときすでに作業ツリーで変更されていた（git status で ` M`、`.bkp` あり）。Claude は変えていない。
    - REV-143 に由来する違反はない。原本の変更をどう扱うかは人の判断。
- VM での確かめ：上の一時的な購読と pcl_ros の一時的な起動だけ。どれも終了を確かめた。Gouda のノードとパラメータは変えていない。
- 単体試験：未実行（コードは変えていない）。

## 残るリスク

- GLIM（ND-08）が点群を BEST_EFFORT で受けているなら、オドメトリも同じく点群が足りない。今回は GLIM が止まっていて、確かめていない。
- 屋内で点群の最大距離が 10 m 未満だと、DEC-279 を直しても NDT は点群を捨てる。今はログに出ない。
- monitor の points が RECEIVED でも、BEST_EFFORT の購読者に十分届いているとは限らない。

## 更新した生成物

- REV-143 の適用で model.yaml に DEC-279・280 を足した。生成物はスクリプトで作り直した。

## 次の作業

- 止まっている：実車での自律走行開始（DEC-279・280 の回答待ち）。
- 回答の後：直す、VM の試験、実車で初期化を確かめる。GLIM の購読の QoS も確かめる。
