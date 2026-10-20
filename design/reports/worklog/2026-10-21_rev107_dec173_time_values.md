# 作業記録 2026-10-21 第75便: DEC-173（DR-15 の調査の時間の値の扱い）（REV-107）

## 読んだもの

- コミット `33416021655e587d0ae5f2c949d9bf81698ef44e`（作業ツリーは未 commit の変更あり）。`gouda_core/gouda_core/monitor_core.py`（on_decision）、`gouda_core/web/app.js:115`、`firmware/gouda_esp32_v4/include/gouda_v4/control.hpp`（sendStatus）、`vehicle_core.py`（status_key_values）、`recorder_node.py`（_bag_stop、サービス）。

## 人の回答（原文は DEC-173）

通知の集約、STATUS の送信時刻、書き込みの待ちの上限への意見、gouda.sh stop の上限の撤去、rosbag の停止の強制終了の廃止と進捗の表示。

## 確かめた事実

- 通知の集約はすでにある（同じ node・event・transition_id・reason を 1 行、×回数）。第73便の報告の「monitor の通知欄が埋まる」は誤り。報告に訂正を追記した。残る影響は ROS の保持（深さ 50）だけ。
- STATUS には ESP32 の送信時の時刻（uptime_ms）がすでにあり、/esp32/status に出る。
- rosbag の停止は record/rosbag/stop のサービスの中で最大 30 s 待つ（単一の executor を止める）。monitor の応答の待ち PRM-30（5 s）より長くかかると、monitor は失敗と表示する。上限をなくすには非同期の停止が要る。

## 変更

- REV-107（DEC-173）。番号は reserve_ids.py で予約（REV-107、DEC-173、第75便）。コードは変えていない。

## 検査（作業ツリー）

- `design/.venv/bin/python design/tools/run_checks.py`: 終了コード 1。設計検査 合格 12・違反 0・未判定 5。移行の照合の違反は以前から（drawio、.DS_Store、intent.md）。

## 次に進められる作業・止まっている作業

- 許可待ち: gouda.sh stop の上限の撤去、rosbag の非同期の停止と進捗のポップアップ、vehicle_bridge の書き込みの方式（第75便の報告の意見）。
