# KUAMS (team 2564, Tsukuba Challenge 2025): what written sources say

Researched 2026-10-23. Sources were read with curl, WebFetch, the J-STAGE API and gh.
Labels used below:
- **[read]**: stated in the cited source.
- **[inferred]**: my own reasoning, not stated anywhere.
- **[not found]**: searched for, but no prose source found.

## 0. The main gap

The team's own write-up is **"つくばチャレンジ2025における関西大学計測・知能システム研究室の取り組み"**
at https://tsukubachallenge.jp/2025/reports/report_2564.pdf. It returns **HTTP 401** (participants only).
Its title is listed on https://tsukubachallenge.jp/2025/records/reports. [read]

The team also gave a talk at the TC2025 Symposium (2026-02-07, slot 11:15–11:35). The slot was labelled
"初参加で初完走チームによる発表" (talk by a first-time team that finished on its first try).
Source: https://tsukubachallenge.connpass.com/event/380575/ [read]
I found no slides or video of that talk. The YouTube channel @tsukubachallenge has no symposium video.

As a result, I found **no prose source** for any of the following:
- crosswalks or signals, the checkpoint, the park or lawn, slopes, crowds, or other robots
- speed settings
- why the team chose its methods for Tsukuba specifically
- incidents during TC runs

The participant report and the symposium talk are where these would be. You could ask the team for them
(Prof. 前 泰志, or GitHub kzm784 / RACC-MAN) or get them through participant access.

## 1. Identity, team and history

- **Team 2564:** 関西大学 計測・知能システム研究室. Robot: KUAMS. Representative: **前 泰志** (Yasushi Mae), 関西大学.
  Source: https://tsukubachallenge.jp/2025/teams/list [read]
- **Developer's name:** written **八木 一馬** (Kazuma Yagi), not 一真, in J-STAGE author metadata. At the time he was in the Graduate School of Science and Engineering, Kansai University; B.E. 2024. [read]
  - J-STAGE ROBOMECH2025 2A2-R12: https://www.jstage.jst.go.jp/article/jsmermd/2025/0/2025_2A2-R12/_article/-char/ja/
  - Author bio in the JRM papers below.
- **What KUAMS stands for:** "Kansai University Autonomous Measurement System", built on a **WHILL Model CR**.
  - The kuams README lists Livox Mid-360, Ubuntu 22.04 and ROS 2 Humble: https://github.com/kzm784/kuams [read]
  - The JRM papers describe KUAMS as WHILL Model CR + **Velodyne VLP-16** horizontal at 1.0 m, on an i7-12700H laptop with 16 GB RAM. [read]
  - The 2026 JRM paper built its map from **Livox MID-360** LiDAR+IMU data using GLIM. [read]
  - I found no prose saying which LiDAR KUAMS carried on the TC2025 course. [not found]
- **Earlier Kansai University entries came from a different lab.** In TC2023 (2343) and TC2024 (2469), Kansai entered as **ロボット・マイクロシステム研究室** (青柳 誠司), robot **KUARO**. [read]
  - TC2023: the report title says the robot was developed on a WHILL Model CR.
  - TC2023 final run: 9 min, ended at 市役所西直線, no milestones.
  - TC2024 final run: 6 min, 90 m, ended at 本庁舎南.
  - Sources: https://tsukubachallenge.jp/2023/records/reports, https://tsukubachallenge.jp/2024/records/reports, and the final-run sheets linked from /2023/records/final and /2024/records/final.
  - The symposium billed KUAMS 2025 as a "first participation" team.
  - [inferred] The two labs share staff: Mae and Aoyagi co-author each other's papers. KUAMS is the Mae-lab line.
- **Kansai's other TC-related work** (Aoyagi group: RTK-GNSS, LIO+GNSS, navigation without point-cloud maps) is a separate line, not KUAMS. [read: different authors and robot]
  - SCI'24 talks: https://sci24.iscie.or.jp/authors/294/
  - JRM 37(5) 1145, "Autonomous Driving of Mobile Robot Based on LIO and GNSS".

## 2. TC2025 results (official sheets)

### Final run (本走行), 2025-12-07

Source: Google Sheet linked from https://tsukubachallenge.jp/2025/records/final, exported as CSV: https://docs.google.com/spreadsheets/d/1iaw7ZpQhZkE2mpo7Z32uIfZj6kFD_93Aee2RyIzMuFI [read]

- Start order 2: 11:30 start, 12:40 finish, **70 min**, end position "ゴール", **2200 m**.
- Milestones:
  - 確認走行区間: TRUE
  - 2ヶ所の折り返し地点: TRUE
  - 完走 (goal): TRUE
- Optional tasks A, B, C, D1, D2: all **"不実施"** (not attempted).
- 課題達成: ×（不達成）. Remark (備考): "完走".
- **Why the task was not achieved:** the rule needs a finish **plus at least two optional tasks**. KUAMS attempted none. Only Kerberos (2551) achieved the task in 2025. [read: the sheet's header defines 課題達成 as 完走＆選択課題2つ以上]
- KUAMS was one of 7 robots that reached the goal, out of 79 starters (same page). [read]
- [inferred] The run was 70 min for 2200 m, about 0.52 m/s average including stops. It was the slowest of the finishers: Kerberos took 49 min for 2870 m, fuGoW 62 min, UNITE 61 min. This average only bounds the speed setting; I found no stated setting.

### Attendance at experiment days

Source: https://docs.google.com/spreadsheets/d/1hNvhnl9xEnzM55Q_Y4Q0Qe1ZWW09rbD2ruPNLHc4Xy4, linked from /2025/records/experiments [read]

- Attended: 11/8 (第5回), 11/9 (第6回), 12/5 (第8回), 12/6 (第9回), and the final run 12/7.
- Absent: 9/20, 10/4, 10/5, 10/18, 11/29.
- Participation count: 5.
- **確認走行 passed on 第5回 (11/8)**, their first attended day.
- No 記録走行 self-report from KUAMS was in the record-run sheet (1Q0B4FJ…). [read]
- [not found] Anything about what happened on 11/9, 12/5 or 12/6.

## 3. How KUAMS localizes and handles maps (peer-reviewed; tested on campus, not Tsukuba)

### 3a. JRM 37(6) 1355–1364 (2025-12-20, open access, CC BY-ND)

"Observable Point Cloud Filtering from Travel Path for Self-Localization in Wide-Area Environments" (Yagi, Nishimura, Matsunaga, Tsuzuki, Aoyagi, Mae).
https://www.fujipress.jp/jrm/rb/robot003700061355/ , doi:10.20965/jrm.2025.p1355 [read, full PDF]

- **Why:** in wide areas the map has tens of millions of points. Points the robot cannot see waste computation and "can cause mismatches in the localization process" (§1).
- **Method:**
  1. Take the planned waypoint path. Interpolate it every δ = 0.5 m.
  2. At each point, crop the map by sensor range (R_max = 50 m) and vertical FOV (±30°).
  3. Remove occluded points by ray casting through an OctoMap (r = 0.2 m).
  4. Merge the visible points along the path.
- **Map splitting:** a new sub-map starts when the path moves more than **L = 10 m** from the current reference waypoint. The boundary waypoint is called a **"map switching point"**. The robot switches to the next observable map when it reaches that point. 11 segments were used. [read]
- **Mapping:** the wide-area map was built with **GLIM**. Original waypoints, with position and orientation, were set by hand **"at intervals of about 1.0 m"**. [read]
- **Localization:** NDT scan matching via `lidar_localization_ros2` with `ndt_omp`. Resolution 0.1 m, outlier_ratio 0.55. [read]
- **Result:** fewer points and higher NDT fitness, with no significant trajectory difference. The paper introduces the metric LCP (fitness per map point). [read]
- **Future work:** dynamic environments, possibly with online waypoint generation or live map updates. [read]
- [inferred] This matches `observable_pointcloud_map_creator`, `map_change_server` and `waypoint_function_map_change_server`: path-based observable maps, switched at waypoints. Whether these were used at TC2025 is not stated in prose.

### 3b. JRM 38(4) 1073–1082 (2026-08-20, open access)

"Observable Point Cloud Maps for Wide-Area Self-Localization" (Yagi, Nishimura, Okita, Ratsamee, Tsuzuki, Aoyagi, Mae).
https://www.fujipress.jp/jrm/rb/robot003800041073/ , doi:10.20965/jrm.2026.p1073 [read, full PDF]

- **Change from 3a:** the path dependence is removed. The map is split on a **uniform grid** (L = 10, 20 or 30 m tested).
  - Ground points (PMF filter) are voxelised at 1.0 m to make virtual viewpoints at sensor height 1.0 m.
  - Visibility is computed with **Hidden Point Removal** (Katz), with R = αD and α = 100.
  - The robot loads the grid cell's map when it crosses a cell boundary.
- **Assumptions:** a static environment. Dynamic obstacles and map changes are **not** considered. Uniform grid is "not necessarily optimal". [read]
- **Results:** alignment time about constant. Fitness comparable or better than the whole map. LCP is higher with smaller grids. [read]
- [inferred] This matches `map_divider` and `opc_ros2` (grid-based).

### 3c. Conference papers on the same line

- **RSJ2025 2L3-02 (2025-09-04):** "局所自己位置推定のためのグリッド内観測可能点群の生成" (八木 一馬, 西村, 沖田, ラサミー, 都築, 青柳, 前).
  Program: https://ac.rsj-web.org/2025/material/RSJ2025_program_detail_0826.pdf [read: title only]
- **ROBOMECH2024 1P2-N09:** "3次元分割地図を用いた移動ロボットの自己位置推定". The whole 3D map is partitioned to cut localization cost. Abstract only (PDF paywalled).
  https://www.jstage.jst.go.jp/article/jsmermd/2024/0/2024_1P2-N09/_article/-char/ja/ [read]

## 4. Waypoint design ("functional waypoints")

- **ROBOMECH2025 2A2-R12:** "機能的ウェイポイントを利用した自動ドアの通過" (八木, 松永, 鈴木, 高橋, 都築, 青柳, 前).
  https://www.jstage.jst.go.jp/article/jsmermd/2025/0/2025_2A2-R12/_article/-char/ja/ [read: abstract only]
  - It proposes "a functional waypoint management system for navigation with required actions".
  - Waypoints are assigned functions, here RGB-D door recognition. KUAMS passed automatic sliding doors with "over 80% success", even with small localization errors.
- **JRM 35(6) 1503 (2023):** automatic sliding glass door detection and measurement with RGB-D. Robot not named. Cites Nakanoshima Challenge and TC2019.
  https://www.fujipress.jp/jrm/rb/robot003500061503/ [read via WebFetch summary]
- **waypoint_manager refactor-branch README.**
  https://github.com/kzm784/waypoint_manager/tree/refactor [read]
  - The CSV holds id, x, y, z, quaternion, then optional command tokens such as `pause`, `skip` or `wait:3.0`.
  - Each token is sent in order to a waypoint function server.
  - [inferred] The README looks Copilot-generated: PRs #28–31 are Copilot "[WIP] Refactor" PRs.
- **PR titles** (prose only by title). [read: titles]
  - `waypoint_manager`: "Skip function", "Implement pause_end_tool", "implement retry in case of Status ABORTED" (2025-06-05), "ウェイポイント座標基準でスキャン判定を行うように変更" (2025-08-25), "skip_server修正" (2025-08-28).
  - RACC-MAN has a `waypoint_function_lineup_server` repo. [read: name only]
- **waypoint_editor README.** Waypoints are edited on 2D/3D maps, saved as CSV or Nav2 YAML, and can be auto-captured from a localization topic. https://github.com/kzm784/waypoint_editor [read]
- [not found] The waypoint density used on the Tsukuba course, and which functions were placed where (crosswalks, the checkpoint, and so on).

## 5. Lessons learned and failure analysis

[not found] in any accessible prose. Likely sources:
- report_2564.pdf (401)
- the TC2025 symposium talk (2026-02-07)
- possibly a ROBOMECH2026 paper. The J-STAGE API shows no ROBOMECH2026 entries for these authors yet; 2025 proceedings appeared there in December.
- Nakanoshima Robot Challenge 2025/2026: no KUAMS mention found.

## 6. Searches that returned nothing relevant

- WebSearch, Japanese and English: KUAMS, 八木一真, 八木一馬, kzm784, 中之島 2025/2026, KUAMS WHILL, 初完走
- SI2025 detailed program (no Kansai KUAMS talk): https://sice-si.org/si2025/assets/pdf/programs/251209_detailed_program.pdf
- researchmap ymae API (not updated after 2024)
- TC2025 LT list (no KUAMS LT)
- connpass pages for the self-intro and progress-report events
- GitHub issues, PRs and wikis (no wikis exist)
