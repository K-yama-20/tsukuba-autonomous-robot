# 作業記録 2026-10-20 第66便: 案 B1 の段 4、setup.sh に rtklib、apt の str2str の確認（REV-098）

## 読んだもの

- コミット `3341602` ＋ 未コミットの作業（REV-073〜097。REV-095〜097 は別のセッション）。status.md、`setup.sh`、VM の `apt-cache policy rtklib`、sources.debian.org の rtklib 2.4.3.b34+dfsg-1（`src/stream.c`、`app/consapp/str2str/str2str.c`）。

## 1. 人の許可（原文、DEC-165）

- 「段 4（setup.sh に rtklib、apt の str2str のソースの確認）を許可する。」

## 2. 行ったこと

- `setup.sh`: apt の一覧（wanted）に `rtklib` を足し、先頭の説明に用途（NTRIP の中継 str2str）を書いた。`bash -n` で構文を確かめた。VM への導入はしていない（sudo は人。`bash setup.sh`）。
- apt の str2str のソースの確認（FILE-RTKLIB-STR2STR-REVIEW）: シリアルは raw・エコー無効、URL のデコードはしない（gnss_config の文字の検証は緩めない）、状態の表示の形は ntrip_relay の解釈と同じ、SIGINT・SIGTERM で止まる、trace は既定で無し、NTRIP v1（HTTP/1.0、Basic 認証、Ntrip-Version なし）、TLS なし。
- 番号は reserve_ids.py で予約（REV-098、DEC-165、第66便）。

## 3. 検査・試験

- `apply_revision.py REV-098`、`run_checks.py`（3341602 ＋ 作業ツリー）: 設計検査 違反 0・未判定 4。移行の検査の違反は人の drawio と .DS_Store だけ。
- gouda_core の単体（Mac）: 187 件合格・3 件 skip・**12 件失敗**。失敗はすべて `test_vehicle_core.py`（ESP32 の firmware）で、別のセッションの REV-095〜097（PRM-43〜49 の承認）の後に起きた。この段の変更（setup.sh）とは関係しない。別のセッション（dec-077,079）が原因を 2 層に分けた: (1) 試験の基盤（trial のファイルがない前提）、(2) 設計（PRM-45＝4800 ＞ PRM-46＝4700。DEC-160 の回答待ち）。修正はそのセッションと人の判断。GNSS・NTRIP の試験はすべて合格。

## 4. 残るリスク・人の確認が要ること

- Point One が NTRIP v1・TLS なしの接続を受け付けるか（原本未照合。契約の資料で確かめる）。
- TLS がないため、NTRIP の認証は暗号化されずにネットワークを流れる（base64）。受け入れるかは人の判断（受け入れない場合は TLS に対応する中継を別に検討）。
- Ubuntu の build のソースが Debian の同じ版と同じか（版の番号の一致だけ）。

## 5. 次

- 人の作業: VM で `bash setup.sh`（rtklib の導入）。段 5（monitor）・段 6（VM の試験、屋外の RTK fix）の許可待ち。commit はしていない。
