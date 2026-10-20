# apt の rtklib（2.4.3.b34）の str2str の確認（2026-10-20。DEC-151 の段 4）

- 読んだもの: sources.debian.org の rtklib 2.4.3.b34+dfsg-1 のソース（`src/stream.c`、`app/consapp/str2str/str2str.c`）。Web の表示を読んだ（ファイルは取得していない）。VM の apt の候補は `2.4.3.b34+dfsg-1build2`（noble universe、arm64。未導入）。Ubuntu の build が同じ Debian のソースからかは**原本未照合**（版の番号の一致だけ）。
- 行番号は控えていない（Web の表示の要約で確かめた）。

| 項目 | 確かめたこと | Gouda への影響 |
|---|---|---|
| シリアルの開き方（openserial） | `/dev/` の後ろを path にする（`serial://serial/by-id/...:115200` の形）。c_iflag・c_oflag・c_lflag を 0（raw・エコー無効）、VMIN・VTIME 0 | 人の資料 §2 を満たす。MRTKLIB と同じ |
| 速度の表 | 速度の表の外の値で配列の外を読む誤りがある（推測を含む。ループ 13 と判定 14 の食い違い） | Gouda は雛形の 115200（表の中）だけを渡す |
| URL の分け方（decodetcppath） | 最後の `@`、`/` の後のマウントポイント、認証の `:`。**URL のデコードはしない**（MRTKLIB と違う） | gnss_config の文字の検証（DEC-156 §9.5）は必要で、緩められない |
| 書式の区切り | `#` を最後の `#` で探す | `#` を含む値は不可（検証済み） |
| NTRIP の要求 | `GET /<mountpoint> HTTP/1.0`、`User-Agent: NTRIP ...`、認証は Basic（user:password の base64）。`Ntrip-Version: Ntrip/2.0` は送らない（NTRIP v1）。TLS はない | Point One が NTRIP v1・TLS なしの接続を受け付けるかは**原本未照合**（人が契約の資料で確かめる）。TLS がないので、認証は暗号化されずにネットワークを流れる（base64 は暗号ではない） |
| trace | 既定の trace は 0（`-t` なし）。level 5 では要求の全体（base64 の認証を含む）を trace のファイルに書く | Gouda は `-t` を渡さない（試験で引数を確かめている） |
| 状態の表示 | `fprintf(stderr, "%s [%s] %10d B %7d bps %s\n", ...)`、既定 5000 ms（`-d` で変更、help にはない） | ntrip_relay の解釈の形と同じ |
| 終わり方 | SIGINT・SIGTERM で止まる。SIGHUP・SIGPIPE は無視 | supervisor の停止（SIGINT から）で止まる |
| 選択肢 | `-b str_no`（出力から入力へ返す）、`-s` 10000 ms、`-r` 10000 ms、`-fl` trace のファイル | 設計（DEC-156）どおり |
