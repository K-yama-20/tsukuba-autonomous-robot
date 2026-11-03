# 生データの一覧（2026-11-03 の実車の測定）

- 作成：2026-11-04（第207便、DEC-427）
- 人の指示（原文）：「生データもpushせよ。」
- `vehicle_measurements_2026-11-03.md` の 3 章と 9 章の「リポジトリには `result.json` と `meta.json` だけ」「生データは公開リポジトリに入れていない」は、この指示で置き換える。その文書はハッシュで固定しているので書き換えない

## このフォルダにある生データ

`runs/` の次の 4 件。それぞれ `imu.csv`、`status.csv`、`command.csv`、`events.jsonl`。

- `motion_start_20261103_055359`（T 解除）
- `motion_start_20261103_061316`（遅れ）
- `motion_start_20261103_074043`（t_lock）
- `motion_start_20261103_082639`（T ロック）

## まだ x86 にしかないもの

x86 に接続できなかったので入っていない（2026-11-04 に確認）。

- `motion_start_20261103_072516`、`073345`、`080357`、`090206`
- `run-f890dddb` の rosbag `bag_02`

## ハッシュ（sha256）

```
e5ee7031c0d4a21f771d9e55ab6b333f891d551e6eafd4aaf93333f273273f2f  motion_start_20261103_055359/imu.csv
ee36c991efa2448e23499502c7ee2a41401fdc146e7a06a532d4c7a3ed4822e2  motion_start_20261103_061316/imu.csv
95c37d203e5da223af24fcd19339f95d53d406a9dca10df5eafbe6c357745c5f  motion_start_20261103_074043/imu.csv
354220f8cabee53eaa62fa7f8218e9eec12ae1ac7ce24c6aad93a53e6b075b1b  motion_start_20261103_082639/imu.csv
bed63b8d43b624d8a058ad364180882a2e4478ec9c5f09ff70d6bc22188d806d  motion_start_20261103_055359/status.csv
d2fe40f16bfcd6be2eb46034ed20c6efea476ccea9485ec2dde2122a3e9a5ad5  motion_start_20261103_061316/status.csv
13f7ace4d776b8bfbfd9b983a9ba0d1afb4f5b99815f071d8b535ee101ae5190  motion_start_20261103_074043/status.csv
fb309a8c98a44d6ee2e8744c57ffa71968262d86918b4ea232940084542dfa9a  motion_start_20261103_082639/status.csv
fecc18efdc5ab22950fb813f0b79359b7f9254bf02c821766b973c37bc24e0f8  motion_start_20261103_055359/command.csv
1a2a80de174cc972fc1a6c9a1a9a170c720bb70d8fb94996a5f57f5b91703acc  motion_start_20261103_061316/command.csv
91eca25d6035154b42fbd25fab25a2486ad93317fe8d719f56da9e8a07430b49  motion_start_20261103_074043/command.csv
e3b413750227cc68000d105b9fcea851abb2641adf1cada93989209fcf63695b  motion_start_20261103_082639/command.csv
b5b2e9daed8dfd8883b0f1840ec9d7d3564f1f932d91086a9ced5f60012b7b85  motion_start_20261103_055359/events.jsonl
f9f7edde04457fc7912c52c6bbe14120069b21d5edb449b2548d73e83a8dce15  motion_start_20261103_061316/events.jsonl
179fba4b30543c72de3e700c0ebcb299b36ae7e8526e05ac4aeef1a7e3dc6e0c  motion_start_20261103_074043/events.jsonl
af5e6b3fe3ef8f74db8efde803a58cfa2abb2168ef8c696f2d6918eec7f9b87c  motion_start_20261103_082639/events.jsonl
```
