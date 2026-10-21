# 第105便: DEC-225（B＝5.1 m）、作り直した地図の変換と VM の ~/gouda_ws への取り込み（REV-135）

## 読んだもの

- コミット：`3b4fb53`（design/nav2-tab-2026-10-21、PR #14 は未 merge）の上の作業ツリー（REV-133・134 は未 commit で適用済み）。
- VM：`~/gouda_rebuild_2026-10-21/173522/maps/`、`~/gouda_ws/gouda_data/maps/`（index.json と既存の原図 2 つ）、`~/gouda_ws` のコード（3341602）の map_database.py。

## 人の発言（原文）

「DEC-225: B = 5.1にしよう。
VMのメモリは12GBに増強した。

作り直した地図はgouda_wsに入れよ。」

その後（VM が止まっていて接続できなかったとき）：「i boot  the VM. retry」
作業中に：「先ほど作成できなかった地図を再度作成する必要は無い。それ以外のことを実行せよ。」

DEC-225 の answer_verbatim に最初の発言を記録した（REV-135）。後の二つは作業の指示で、この記録に残す。

## 記録（REV-135）

- DEC-225（answered）：B（PRM-97）＝5.1 m。DR-13 は変えない（5.1 は DR-13 に当たらない：DR-13 は 5 と 5.0 を見る）。示した三つの案のうち「B の値を見直す」に近い。
- PRM-97＝5.1 m を承認値に。人の申告（事実として記録）：VM のメモリを 12 GB に増やした（VM で 11 GiB と表示を確認）。

## 実行したこと

- VM は人が設定を変えて止めていた（prlctl list で stopped）。人が起動した後、再起動のため `~/gouda_ws` の Gouda は動いていない（起動はしていない）。
- 生成物（PRM-97 が承認値になり、gouda_map_creator.yaml に corridor_gap_m 5.1）を VM の試験用のワークスペースに写した。
- 作り直した原図 20261019_123731_dc7b4c8a を、承認値だけ（試験用の値なし、実車と同じ）で変換し直した：rev 2（A 1.0 m・B 5.1 m、帯は 1 区間、つながなかった所なし、空き 57931 格子）。製品と同じ手順（MapDatabase.begin_conversion → map_convert.convert → finish_conversion、/config の写し）。
- `~/gouda_ws/gouda_data/maps/` に、原図（source/、source_manifest.json、sensor_config.json、gnss.jsonl）と rev 2 だけを写した（rev 1 は B が試験用の値 1.0 m なので写していない）。`~/gouda_ws` のコードの MapDatabase で index を作り直した。原図と rev 2 の内容ハッシュは manifest と一致（確認）。index には既存の 2 つと新しい原図（119 submaps、rev 2）。
- 20261014_175847 の作り直しは、人の指示でやり直していない。

## 自律判断した変更とその理由

- rev 1 を `~/gouda_ws` に入れなかった：決まっていない値（試験用の B）で作った地図を、走行の地図の選択に出さないため。

## 実行した検査・試験

- `apply_revision.py REV-135 --dry-run --check`：新しい違反 0、新しい未判定 0。
- `run_checks.py`：要約行 `{"合格": 12, "違反": 0, "未判定": 5} 違反0件・未判定5件`、DR-11 30、DR-13 合格、DR-15 31。終了コード 1 の原因は入力の照合の 3 件（前と同じ）。
- Mac 単体：248 合格、8 skip、不合格 0（コードは変えていない）。

## 残るリスク

- `~/gouda_ws` のコードは 3341602（古い）。新しい地図の rev 2 は変換器 0.5 の成果物（map.yaml は帯の地図）だが、`~/gouda_ws` には ND-07・帯の地図の扱い・Nav2 タブなどの新しいコードが入っていない。使うには、main に入った後に update.sh で取り込む必要がある（人の作業。PR #14 と第103〜105便の分はまだ main にない）。
- `~/gouda_ws` の Gouda は VM の再起動で止まっている。

## 次の作業

- 人の判断：DEC-219〜224。PR #14 の merge と、第103〜105便の commit。
