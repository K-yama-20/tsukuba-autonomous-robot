# livox_ros_driver2 の写しに patch を当て、MID-360 の状態の通知を /diagnostics に出す（2026-11-07）

- 区分：実装（DEC-494 の推奨 A。人の回答「A で進める」の記録は親が判断台帳に書く）。センサーをつないだ実機の試験は未実行
- 読んだコミット：9c449b5。作業ツリーは他のセッションと共有で、未コミットの変更がある（setup.sh・README.md・third_party/drivers.repos は A1 の変更の上に重ねた）
- 上流のソースは固定の commit の clone を直接読んだ：livox_ros_driver2 21445540f0d100dc86a7e6df312dd70bbdb4afdf、Livox-SDK2 c0796f04c143143899c87a773d9f6b7136453c0b。通信プロトコルは Sensors/MID-360/official/github/livox_wiki_en の livox_eth_protocol_mid360.md 380〜396 行
- 変えたファイル：third_party/patches/livox_ros_driver2/（新）、setup.sh、third_party/drivers.repos（コメントだけ）、README.md（MID-360 のドライバの 2 か所）、この文書

## 1. 要点

1. patch は 1 本：`third_party/patches/livox_ros_driver2/0001-publish-lidar-state-push-on-diagnostics.patch`（382 行。説明 25 行と `git diff` 357 行）。既存の 4 ファイルに 13 行を足すだけで、消す行・変える行はない。新しいファイルは 3 つ（261 行）
   - `src/call_back/lidar_status_info.h`（125 行、ROS なし）：JSON の解析（同梱の rapidjson の document.h だけ。上流の lds_lidar.h と同じ）、許可の一覧、level の決め方
   - `src/call_back/lidar_status_publisher.{h,cpp}`（30・106 行、ROS 2 だけ）：publisher、SDK の callback の登録、thread の扱い
   - `src/livox_ros_driver2.cpp`（+4、CRLF のファイル）：`InitLdsLidar()` が成功した後に `LidarStatusPublisher::Start(*this)`
   - `src/driver_node.cpp`（+6）：`~DriverNode()` の最初に `LidarStatusPublisher::Stop()`
   - `CMakeLists.txt`（+2）：`find_package(diagnostic_msgs REQUIRED)` と新しい .cpp。`package_ROS2.xml`（+1）：`<depend>diagnostic_msgs</depend>`
2. setup.sh は、写しを作る処理を関数 `make_livox_copy` にまとめ、3 節（rosdep が読む manifest）と 5 節（colcon が作る写し）の両方で使う。patch は名前の順に `git apply` で当て、当たらなければ止まる。stamp に patch の名前と中身の hash を入れた
3. 点群・IMU・設定の書き込みの経路は変えていない（patch が足すのは上の 13 行と新しいファイルだけ。ROS 1 の build は新しいコードを含まない）

## 2. 決めた約束との対応

| 約束 | 実装 | 確かめた試験 |
|---|---|---|
| topic は絶対名 `/diagnostics`、型 DiagnosticArray、QoS は rclcpp の既定 | `create_publisher<DiagnosticArray>("/diagnostics", 10)`（lidar_status_publisher.cpp） | harness：node の名前空間 `trial_ns` でも `/diagnostics`、reliable・volatile（7 節） |
| callback ごとに 1 つ、stamp は受けたときの ROS の時刻 | callback の中で `clock->now()`、array は毎回 1 つ | harness：3 回の push で 3 つ、stamp は push の前の時刻以上 |
| status は 1 つ、name `mid360`、hardware_id 空、message `info push` | 固定の文字列 | harness |
| level：4 つのモジュールの段階の最大、0 OK・1 WARN・2/3 ERROR、なければ STALE | `LevelFromDiagStatus`・`Summarize` | 単体試験（モジュールごと、値ごと） |
| values：14 個の key だけ、SDK の名前のまま、文字列。配列は JSON の配列の文字列 | `kAllowedKeys` の順。整数は十進、整数の配列は `[a,b]`（空白なし）、文字列は中身 | 単体試験：SDK の書き方の見本（全 key）から 14 個だけ、sn・mac・アドレスが値に出ない |
| core_temp は 0.01 ℃ の整数のまま | 数をそのまま文字列に | 単体試験（`4512`、`-1050`） |

約束が決めていない所で、AI が決めたこと（自律判断。記録のためだけの値で、走行の判断には使わない。違う扱いがよければ直す）：

- モジュールの段階が 4〜15（通信プロトコルにない値）のときは ERROR にした（知らない値を正常や警告に寄せないため）
- `lidar_diag_status` が符号なしの整数でない、または 0xFFFF を超えるときは STALE（判定できない。値は許可の一覧なので values には出る：文字列なら文字列のまま、数なら数）
- 許可の key でも、値が整数・整数の配列・文字列のどれでもなければ出さない（小数、object、整数以外を含む配列、真偽値、null。SDK c0796f0 は許可の key をそう書かない。将来の SDK が入れ子でアドレスなどを入れても漏らさないため）
- 文字列の値（`status_code`。SDK は 32 byte を 16 進で空白区切りの文字列にする）は、JSON の引用符を付けずに中身をそのまま
- JSON として読めない通知も 1 つ出す（STALE、values なし。約束の「callback ごとに 1 つ」に合わせた）
- dev_type（機種）で絞らない。MID-360 以外の機種がつながっても name は `mid360`（Gouda は MID-360 が 1 台）
- 例外は callback の中で捕まえ、node の logger に WARN で出す（SDK の thread に例外が出ると std::terminate になるため）
- 当たらない patch は 3 節で止まる（3 節でも同じ写しを作るため）。このとき Gouda の作業場所の build（5 節の前半）は実行されない。A1 の「ドライバの build の失敗は Gouda の build の後」とは止まる所が違う

## 3. thread の扱いと根拠

- SDK は callback を自分の thread で呼ぶ：通知の受信（`Mid360CommandHandler::OnCommandCmd`、mid360_command_handler.cpp 86〜90 行）から `GeneralCommandHandler::PushLivoxLidarInfo`（general_command_handler.cpp 589〜597 行）が、SDK の `dev_type_mutex_` を持ったまま呼ぶ。登録（`SetLivoxLidarInfoCallback`、general_command_handler.h 98〜101 行）は lock なしで関数のポインタを書くだけで、走っている callback を待つ手段はない
- そこで、publisher・clock・logger を 1 つの mutex で守る状態に置き、その状態は解放しない（`new` したまま。SDK の thread が static の破棄より後に呼んでも壊れたメモリに触れない）
  - callback：mutex を取り、`Stop()` の後なら何もせずに戻る。そうでなければ解析して publish する
  - `Stop()`：同じ mutex の下で publisher と clock を捨てる。戻った後は publish が走っていないし、始まらない。`~DriverNode()` の最初に呼ぶので、node が壊れるより前。SDK はその後 `~Lddc` で終わる（Lddc は DriverNode の member で、destructor の本体の後に破棄される：driver_node.cpp 34〜39 行、lddc.cpp 80〜91・186〜199 行）
  - SDK の callback への登録を外す処理（`SetLivoxLidarInfoCallback(nullptr, nullptr)`）は入れていない。lock なしの書き込みが SDK の thread の読み込みと競合するため（上流の他の callback の登録と同じく、登録は SDK の初期化の後に 1 回だけ）
- lock の順序：SDK の thread は `dev_type_mutex_` → この mutex。`Start()`・`Stop()` はこの mutex を持ったまま SDK を呼ばない（`Start()` は mutex を放してから `SetLivoxLidarInfoCallback`）。逆順にならないので dead lock はない
- rclcpp の publish を executor でない thread から呼んでよい根拠（Jazzy、ワークステーションの /opt/ros/jazzy、rcl 9.2.11・rclcpp 28.1.22）
  - `rcl/publisher.h` 297〜316 行：`rcl_publish()` は、publisher と message への access が同期していれば thread safe。`rcl_publish()` と `rcl_publisher_fini()` を同時に呼ぶのは不可 → mutex で `Stop()`（publisher の破棄）と publish が重ならない
  - `rclcpp/publisher.hpp` 299〜300 行：intra-process が無効（既定）なら `publish()` は `do_inter_process_publish()`（rcl_publish）だけ
  - `rcl/time.h` 505〜528 行：`rcl_clock_get_now()` は thread safe（ROS time では atomics）
  - 上流のドライバ自身も、点群と IMU を自前の thread（`PointCloudDataPollThread`・`ImuDataPollThread`）から publish している（livox_ros_driver2.cpp 184〜185・196〜214 行）
- 残る注意：`rcl/publisher.h` 290〜292 行のとおり reliable の publish は待つことがある。待つ間は SDK の command の thread も止まる（keep last 10 で実際に待つかは未確認。7 節の harness では 4 thread × 500 回の push で問題は出ていない）

## 4. setup.sh（作業ツリーの sha256 b103bf7d71f8040c8181e80b89801a1c6b4a8f59548f56b1ff3a1753fde64366 の行番号）

- 20〜25 行（先頭の説明の 5 節）：patch を写しに当てること、patch が変わったときも作ること、当たらなければ止まること
- 44〜67 行：`livox_patch_dir`、関数 `livox_patches`（`*.patch` を `LC_ALL=C sort` の名前の順）、`livox_patch_sum`（各 patch の名前と sha256 を並べた sha256）、`make_livox_copy <空のフォルダ>`
  - 固定の commit を `git archive | tar -x` で写す（A1 と同じ）
  - patch を 1 つずつ `GIT_CEILING_DIRECTORIES=<写しの親> git -C <写し> -c core.autocrlf=false apply --whitespace=nowarn <patch>`。リポジトリの外として動くので path は写しから取る（親のフォルダが git のリポジトリでも、その一部として扱わない）。`git apply` は patch の全部を当てるか、何も当てない
  - 当たらなければ `stop`（どの patch か、固定の commit、run_tests.sh の案内）
  - 最後に package_ROS2.xml を package.xml に写す（patch の後）
- 169〜174 行（3 節）：rosdep が読む manifest を、`make_livox_copy` で一時フォルダに作った写しの package.xml にした（`diagnostic_msgs` が入る）。checkout は変えない
- 213〜218・220〜225・231 行（5 節）：stamp を `<commit> colcon patches <patch の hash>` にした。A1 の stamp（`<commit> colcon`）とは合わないので一度だけ作り直す。作り直しは `make_livox_copy "$livox_stage"`。作ってある場合の表示に patch の名前を足した
- `third_party/drivers.repos`：コメントの 11・12 行を足し、13 行を「The checkouts are used unmodified」にした（値は変えていない。yaml として 4 件のまま読めることを確かめた）
- README.md：46 行（MID-360 のビルドの説明）に patch のことを足し、188 行（stage の説明）に「patch を当て」を足した。39 行の「改変しません」は `~/gouda_ws/src` の XT-32・IMU のドライバの話なので変えていない
- `third_party/patches/livox_ros_driver2/.gitattributes`：`*.patch -text -whitespace`（src/livox_ros_driver2.cpp の hunk が CRLF を含むので、git に行末を変えさせない）

## 5. 先行事例（CLAUDE.md 1.11）

探した場所と検索語：上流 Livox-SDK/livox_ros_driver2 の issue #80 と PR（`gh search prs`。検索語：SetLivoxLidarInfoCallback、diagnostic、temperature、core_temp、status push、hms、info callback、status、health、state）、issue（diagnostics）、fork（piappl、TU Darmstadt）、GitHub のコード検索（`SetLivoxLidarInfoCallback`、`SetLivoxLidarInfoCallback diagnostic_msgs`、`SetLivoxLidarInfoCallback core_temp`、`SetLivoxLidarInfoCallback rclcpp`）、ROS 2 の diagnostic_updater、親の調査（issue #93）

| 候補 | 内容 | ROS 2 Jazzy | ライセンス | 保守 | 実機での例 | 採否と理由 |
|---|---|---|---|---|---|---|
| 上流 issue #80（2023-09-11、open） | MID-360 の core_temp を topic で出してほしい。コメントは 2023-10 と 2026-04-15（Livox Viewer なしで温度を読みたい）。紐づく PR はない | — | — | 回答なし | — | 根拠として使う。PR はこの issue に向ける |
| 上流 PR #192「Feature/diagnostic」（piappl の fork、2025-05-09、2025-05-14 に未マージで closed） | 接続の検出の応答で `QueryLivoxLidarInternalInfo` を呼び（状態の通知ではなく問い合わせ）、lidar_diag_status と hms_code を diagnostic_updater で出す。IMU の単位の変更、設定ファイル、SDK を ROS の package として依存させる変更などと一緒に 33 ファイル | jazzy の枝 | fork は NOASSERTION（上流は MIT） | fork の最後の push は 2025-05-15、star 0 | 未確認 | 不採用。温度（core_temp）を出さない、関係のない変更が多い、diagnostic_updater と SDK の package 化で依存が増える、閉じられた。hms_code の読み方（上位 16 bit が番号、下位 8 bit が段階）は参考。この patch は hms_code を解釈せずそのまま出す |
| TU Darmstadt の fork（jazzy、2a60447、2026-10-23） | parameter `publish_diagnostics` で、相対名 `diagnostics` に 1 秒の wall timer で時刻同期と packet の状態を出す（src/livox_ros_driver2.cpp 208〜257 行。AI が gh api で読んだ） | 対応 | NOASSERTION（台帳の記載） | 活発 | 未確認 | 不採用。状態の通知の callback を使わず、温度・診断コードは出ない（REV-260 の DEC-479 の調べと同じ） |
| groupe-carvi/carvi_livox_sdk2（Rust の SDK2 の wrapper、MIT、2026-06 更新） | `SetLivoxLidarInfoCallback` を client_data を null にして trampoline の関数で登録し、Drop で null に戻す（src/lib.rs 1002〜1012・1635〜1641 行。gh api で該当の行だけ読んだ） | ROS ではない | MIT | 2026-06 | 未確認 | 考え方を参考（client_data を使わない）。ROS に出す部分はない |
| Livox-SDK2 の見本 livox_lidar_quick_start（c0796f0） | 同じ callback で通知を画面に出す（main.cpp 251〜257・280 行） | — | MIT | 上流 | — | 作り方の元（初期化の後に登録） |
| ROS 2 の diagnostic_updater（ros-jazzy-diagnostic-updater 4.2.7、ワークステーションに入っている） | 決まった周期（parameter `diagnostic_updater.period`、既定 1.0 秒：diagnostic_updater.hpp 353〜392 行）で status を集めて出す。name の付け方は実装の .cpp にあり未照合 | 対応 | BSD-3-Clause（package.xml） | ROS の公式 | 未確認 | 不採用。約束（通知ごとに 1 つ、stamp は受けた時刻）は周期で出す作りと合わず、依存が増える。DiagnosticArray を直接出すほうが小さい |
| GitHub のコード検索 | `SetLivoxLidarInfoCallback` の 100 件は SDK の写しと上の Rust の wrapper だけ。diagnostic_msgs・core_temp・rclcpp との組み合わせは 0 件 | — | — | — | — | 状態の通知を ROS に出す既製の実装は見つからなかった |

自作の範囲：callback の登録と publisher（約 100 行）、解析と level（約 125 行、ROS なし）。上の候補は温度を出さないか ROS でない。未調査：つくばチャレンジの他チームの実装。

## 6. 試験（実行したものだけ）

### 6.1 単体試験（ROS なし）

- 試験：`third_party/patches/livox_ros_driver2/test/test_lidar_status_info.cpp`（9 個の試験、148 の確認）。通知の見本は `LivoxLidarStateInfoToJson` の書き方（rapidjson の PrettyWriter、同じ key・型・順）で作り、全 key（sn・mac・product_info・各 *_ipcfg・ntp_server_ip を含む）を入れた。アドレスは RFC 5737 の文書用、シリアル番号・MAC は作り物
- 確かめること：許可の一覧の外の key が出ない（値の文字列にもアドレス・シリアル番号・製品名が出ない）、14 個の key の順と値、level（モジュールごとに 1・2・3・4・15、混在）、lidar_diag_status がない・型が違う・範囲外のときの STALE、JSON でない入力・null、配列の文字列（`[0,0,0,0,0,0,0,0]`、uint32 の最大値）、負の core_temp、uint64 の最大値、int64 の負、小数・object・入れ子の配列・真偽値・null を出さない、順は許可の一覧の順
- 実行：`bash third_party/patches/livox_ros_driver2/test/run_tests.sh <livox_ros_driver2 の checkout>`（固定の commit を写し、setup.sh と同じ git apply で patch を当て、`-std=c++14` と `-std=c++17`、`-Wall -Wextra -Wpedantic -Werror` で build して実行）
  - Mac（Apple clang 21.0.0、上流の clone）：最終の patch（sha256 4b0b06dc…）で「148 checks, 0 failed」が 2 回（c++14・c++17）
  - ワークステーション（g++ 13.3.0、試行の checkout）：同じ patch で「148 checks, 0 failed」が 2 回。終了コード 0
- 試験が効くことの確認（Mac、header の写しを壊して）：sn を許可に足す → 6 件失敗、段階 3 を WARN → 6 件、STALE の既定を OK → 14 件、小数を出す → 1 件、配列に空白 → 2 件。parse error の確認を外す変更は失敗が 0（rapidjson は parse error で document を null にするので、`IsObject()` の確認だけで同じ結果になる。同値の変更）

### 6.2 setup.sh の節の写しでの試行（ワークステーション）

場所：Ubuntu 24.04、Jazzy のシミュレーション用のワークステーションの新しい空のフォルダ `~/livox_patch_trial_20261107`（以下 `<trial>`）。A1 の `~/livox_colcon_trial_20261107` は読むだけ（警告の比較）。sudo は使っていない。ドライバは起動していない。

方法：`make_trial.sh` が setup.sh から次の部分を行の印で抜き出し、そのまま `trial_setup_livox.sh` にした（`cmp` で setup.sh の行と同じことを確かめた）。

- 40〜67 行（変数と関数）、130〜166 行（2 節）、170〜174 行（3 節の livox の manifest の部分。その後に、試行だけの `rosdep check`（入れない）と manifest の depend の表示を足した）、200〜238 行（5 節の MID-360 の部分）
- 5 節は A1 と同じ 3 行だけを置き換えた（SDK を `<trial>/sdk_prefix` に入れる、sudo と ldconfig なし）。`workspace`・`repo`・`pins`（Livox の 2 件）は試行の値。`<trial>/repo/third_party/patches/livox_ros_driver2/` は作業ツリーの写し
- 5 節の中で止まることを見るために、3 節を除いた `trial_sec5_only.sh` も作った

| 回 | 目的 | 結果 |
|---|---|---|
| runA | 空から（clone、SDK、patch を当てたドライバ） | 終了 0。「livox_ros_driver2: applied 0001-…」が 3 節と 5 節で出た。colcon 16.9 秒。stamp `2144554… colcon patches 35c91e1d…` |
| runB | もう一度 | 終了 0。「livox_ros_driver2 2144554 is built (patches: 0001-…)」、作り直しなし（ライブラリの時刻が同じ） |
| runC | A1 の形の stamp（`<commit> colcon`）を置いて | 終了 0。一度だけ作り直した |
| runD | patch の 1 行目を変えて（当たる） | 終了 0。作り直した。stamp の hash が変わった（08c5f13f…） |
| runE・runF | 元に戻して、もう一度 | 作り直し（hash は 35c91e1d… に戻る）、作り直しなし |
| runG | 当たらない patch `0002-trial-broken.patch` を足して（1 つ目のファイルの hunk は当たり、2 つ目は当たらない） | 終了 1。3 節で `error: patch failed: package_ROS2.xml:1` と `STOPPED: the patch …/0002-trial-broken.patch does not apply to livox_ros_driver2 2144554; …`。stamp・ライブラリはそのまま |
| runG5 | 同じ patch で、5 節だけの写し（stamp を壊して） | 終了 1。5 節で同じ STOPPED。build・install は消された後（A1 の build の失敗と同じ）。写しの CMakeLists.txt に 0002 の 1 つ目の hunk の行は 0（patch の一部だけは当たらない）、0001 の行はある |
| runH・runI | 0002 を除いて、もう一度 | 作り直し、作り直しなし |
| runJ・runK | setup.sh の最終の形（`-c core.autocrlf=false` を足した後）を抜き出し直し、patch の説明の行を変えた版で | 作り直し、作り直しなし |
| runL・runM | 最終の patch（sha256 4b0b06dc…、rapidjson の writer.h を使わない版） | 作り直し（16.2 秒）、作り直しなし。stamp `2144554… colcon patches e5b5befb…` |

3 節の `rosdep check`（試行だけ。入れない）：毎回「System dependencies have not been satisfied: apt libapr1-dev, apt libaprutil1-dev」だけ（A1 と同じ apr。diagnostic_msgs は /opt/ros/jazzy にあり満たされている）。

確かめたこと（`checks.sh`、runL の後の checks_final3.txt。`source /opt/ros/jazzy/setup.bash` と `<trial>/gouda_ws_livox/install/local_setup.bash` の後）：

- `ros2 pkg prefix livox_ros_driver2`：`<trial>/gouda_ws_livox/install/livox_ros_driver2`
- `ros2 pkg executables livox_ros_driver2`：`livox_ros_driver2 livox_ros_driver2_node`
- `ros2 pkg xml livox_ros_driver2`：`<depend>diagnostic_msgs</depend>` がある（他の depend は元のまま）
- `ros2 pkg prefix diagnostic_msgs`：`/opt/ros/jazzy`
- `ros2 interface package livox_ros_driver2`：CustomPoint と CustomMsg（元のまま）
- `ros2 interface show diagnostic_msgs/msg/DiagnosticArray`：header、status（OK=0・WARN=1・ERROR=2・STALE=3、level・name・message・hardware_id・values）
- `ros2 component types`：`livox_ros_driver2` に `livox_ros::DriverNode`
- `ldd`：`libdiagnostic_msgs__rosidl_typesupport_cpp.so`・`libdiagnostic_msgs__rosidl_generator_c.so` が /opt/ros/jazzy/lib、SDK は `<trial>/sdk_prefix/lib`、not found なし
- `nm -DC`：`LidarStatusPublisher::Start(rclcpp::Node&)`・`Stop()`・`OnLidarInfo(...)` があり、`SetLivoxLidarInfoCallback` は未定義（SDK から）
- 写し：`src/call_back/` に新しい 3 ファイル。package.xml は patch 後の package_ROS2.xml と同じ。CMakeLists.txt に `find_package(diagnostic_msgs REQUIRED)`
- checkout：HEAD は固定の commit、`git status --porcelain --ignored` は 0 行
- build の警告：`pub_handler.cpp:466` の未使用の変数の 1 件だけ。A1 の patch なしの build の log と同じ。新しいファイルを通る include の警告は 0
  - 途中の版（rapidjson の writer.h を使っていた版、runA〜runK）では、同梱の rapidjson の `internal/dtoa.h` 36 行が `-Wpragmas` の警告を 1 件足していた。最初の確認の grep（新しいファイルの名前を含む行だけを見ていた）はこれを見落とした。値の文字列を自前で作るように直し（原因の分類：実装）、確認を「全部の警告と A1 の log の比較」に直した（試験の基盤）
- CMakeCache：`diagnostic_msgs_DIR` は /opt/ros/jazzy/share/diagnostic_msgs/cmake、`CMAKE_BUILD_TYPE` は空（A1 と同じ）

### 6.3 ROS の上での試し（harness。リポジトリには入れていない）

ドライバの node も SDK も起動せず、作った `liblivox_ros_driver2.so` を読み込む小さなプログラム（`<trial>/harness`）で、`LidarStatusPublisher` だけを動かした。SDK の `SetLivoxLidarInfoCallback` は harness 自身の定義に置き換わる（ELF の symbol の探索は実行ファイルが先）。DDS は ROS_DOMAIN_ID=213、`ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` で、他のシミュレーションと混ざらないようにした。

結果（最終の patch。`harness exit=0`、「OK (0 failures)」。前の版の library でも 3 回同じ結果）：

- `Start()` は callback を 1 回登録し、client_data は null
- publisher：node の名前空間が `trial_ns` でも topic は `/diagnostics`、型 `diagnostic_msgs/msg/DiagnosticArray`、reliable・volatile（history と depth は rmw の graph の情報に出ないので、確かめたのは code の `10` だけ）
- 別の thread からの 3 回の push で 3 つの array。どれも status は 1 つ、name `mid360`・message `info push`・hardware_id 空、frame_id 空、stamp は push の前の時刻以上
  - 1 つ目（lidar_diag_status 16 = scan のモジュールが警告、sn・mac・アドレスを含む）：level 1（WARN）、values は `cur_work_state=1 core_temp=4512 lidar_diag_status=16 hms_code=[0,0,0,0,0,0,0,0]` だけ
  - 2 つ目（lidar_diag_status なし）：STALE、values 1 つ。3 つ目（JSON でない）：STALE、values なし
- 4 つの thread が休まず push する間に `Stop()`：Stop の前に 12,850 回 push、11,682 個を受けた。Stop が戻った後の push 2,262,790 回は何も出さず、受けた stamp で Stop が戻った時刻より後のものは 0（いちばん新しい stamp は Stop が戻る 0.045 ms 前）。その後の push も受けない。`/diagnostics` の publisher は 0
- harness の不具合を 2 回直した（試験の基盤。合否の基準は変えていない）：SDK のライブラリへの `-rpath-link` がなく link できなかった、spin_some の前に executor から node を外していなかった

### 6.4 その他

- `bash -n setup.sh`：Mac と、ワークステーションの GNU bash 5.2.21 の両方で通った。`bash -n run_tests.sh` も通った
- shellcheck：Mac にもワークステーションにもなく、未実行
- `git apply` の行末：global の `core.autocrlf=true` を与えても patch は当たり、src/livox_ros_driver2.cpp の 239 行はすべて CRLF のまま（Mac で確認）。setup.sh と run_tests.sh は `-c core.autocrlf=false` を付けた
- 実車（Dell）での setup.sh、センサーをつないだ試験、gouda_recorder との結合：未実行

証拠（リポジトリの外、`<trial>` に置いた。sha256）：

| ファイル | sha256 |
|---|---|
| setup.sh.working_tree（作業ツリーの setup.sh の写し） | b103bf7d71f8040c8181e80b89801a1c6b4a8f59548f56b1ff3a1753fde64366 |
| make_trial.sh | 74d509e9ed17bbd94c8275ed0289d9e39ded37b99a44e732558b8626cc203dad |
| trial_setup_livox.sh（runJ〜runM） | d5b61d8e6dd8d7dd88db82eb3433f89773a5a9c757d99e66110118b44d004804 |
| trial_sec5_only.sh（最終） | c464d0e155ce12bce7b9215da3d6ee89be519530ed43d938a1aac7786986a6a9 |
| seq1/trial_setup_livox.sh（runA〜runI） | 5d7c70099f7d6027c71df7fbd4e285fc71248fb01c4697d4e1fff087d56bce42 |
| sec5.diff | 4e97c93f3514f19f4c87a918c9c53d5e2df2a06a199b18a05fc64bdd8cf33acb |
| sequence.sh・sequence.txt | e2da92c91dff9ce56e3cb7ec9b48434745c0ff4057942a146da9308c3df2d2fc・d61c8bcf4e3abfbbc3303c240639938be69c4c92a7ab090154bd79fca6375e30 |
| sequence2.sh・sequence2.txt | e14f4b9cda7552392698c441c23e5bbf10c4c9bf01eed0878da8e7461d20e8c3・bf6bdbb7eb903aa78a70f529605a7652692f186a2c690858668b4aa6af84c588 |
| sequence3.sh・sequence3.txt | 9f25e8f31621aef73814f73b25a24d63e068e252a0fbb4bab23015c7a9ee998d・8bba2beaeab08d069c682f6b930872ee042c759ace562666c619a903244813af |
| checks.sh（最終）・checks_final3.txt | f3dee90f13c62f9bd701583bac50de400df487e434ee7d6c802e429eef7e10ee・b4f30e3b20669e2f9e5177f0e555e71641addfce5f53521994a9ee8e76bbb3c3 |
| 0002-trial-broken.patch | f2bef40731df5cefd397ce025e10f47725cca1bed78f4618b5cbfdcaf7420141 |
| runA〜runI.log | 78212eca…（A）、c91a88c0…（B）、451fb8f9…（C）、d5d7541f…（D）、a1a0d8f2…（E）、55ad2262…（F）、1bf45f15…（G）、3feaaaae…（G5）、35f83994…（H）、2e032ad6…（I） |
| runJ・runK・runL・runM.log | ec36fb07…、3c354101…、8e90713a5…、af90203f… |
| harness/harness.cpp・harness/CMakeLists.txt | 65e0760fe6c92c7d0eb61ea316740e47a3a3f655371b92229aabf4376d6c22aa・259c3f28e626a7569e6dafb0db751c1ea4a2144eca74bc59e14ee73509925411 |
| harness_run.txt（最終） | 44d179000821deba644792f510d0d4c72fafe22919636fa4bdb6af60f8636e34 |
| 最終の patch・test_lidar_status_info.cpp・run_tests.sh（作業ツリーと同じ） | 4b0b06dc7c6d259a9a470b678d6d6ed5c06440d925254023cc6b98263aa4c518・8635aceb9b69ebc5c5a4f1beeffc55e03bffd77789ea4392667d5067da2f61d1・3c72eb966a0eb16ac5210d328c8bdba73522d505b1351cddc00e236384a7576c |

## 7. 残るリスク・未確認

- センサーをつないだ確認がない：MID-360 が実際に送る key の集合と周期、callback が本当に呼ばれること（PC が push_msg_ip の送り先であることが前提：mid360_config.py 43 行）。単体試験の見本は SDK のソースから作ったもので、実機の JSON ではない
- Dell での setup.sh は未実行。`ros-jazzy-diagnostic-msgs` が Dell にあるかは未確認（なければ 3 節の rosdep が入れる）
- reliable の publish が待つと、その間 SDK の command の thread が止まる（keep last 10 で待つかは未測定）
- 当たらない patch は 3 節で止まり、Gouda の作業場所の build（5 節の前半）も実行されない（2 節の自律判断。承認がよければ戻す）
- patch は DEC-075 の例外。固定の commit を変えるたびに run_tests.sh と build を確かめる。patch の src/livox_ros_driver2.cpp の hunk は CRLF を含むので、エディタで開いて保存すると当たらなくなりうる（.gitattributes で git には行末を変えさせない）
- 同じ process に DriverNode が 2 つあると、状態は 1 つで、後の `Start()` が上書きする（上流も SDK は process に 1 つ）
- ROS 1 では何も出ない（ROS 1 の build は未実行）
- name は機種によらず `mid360`、hardware_id は空（約束どおり。上流向けには 8 節で相談の点にした）
- design/research/upstream_sensors/README.md の一覧、README.md の「リポジトリの中」の表には、この文書と third_party/patches/ を足していない（触ってよいファイルの外）
- harness は `<trial>` にだけあり、リポジトリの試験に入っていない

## 8. PR の本文の下書き（英語。上流 issue #80 に向ける。投稿していない）

### Title

Publish the LiDAR state push (core temperature, diagnostic status, HMS codes) on /diagnostics (ROS 2)

### Body

Closes #80 (draft; not tested with a connected LiDAR yet, see "Testing").

**Problem**

Mid-360 (and the other LiDARs handled by Livox-SDK2) periodically push their state information (command 0x0102,
"LiDAR Information Push"): working state, core temperature (`core_temp`, 0.01 °C), the per-module diagnostic level
(`lidar_diag_status`), the HMS diagnostic codes (`hms_code`), firmware versions and time-sync state. Livox-SDK2 already
parses the push and hands it to the callback registered with `SetLivoxLidarInfoCallback` as a JSON string
(`LivoxLidarStateInfoToJson`, `sdk_core/command_handler/parse_lidar_state_info.cpp`; the quick-start sample prints it).
livox_ros_driver2 never registers that callback (`src/lds_lidar.cpp` registers only the info-change callback, and
`SetLidarPubHandle` only the point cloud and IMU ones), so none of this reaches ROS. Today the only way to see the
temperature or a warning is Livox Viewer, and a node can only notice a problem when the point cloud stops (#80, and
the 2026-04 comment asking for the temperature without the viewer).

**Change** (ROS 2 only; the ROS 1 build is not touched)

- `src/call_back/lidar_status_publisher.{h,cpp}` (new): `LidarStatusPublisher::Start(node)` creates a publisher of
  `diagnostic_msgs/msg/DiagnosticArray` on `/diagnostics` (absolute name, rclcpp default QoS: reliable, volatile,
  keep last 10) and registers the SDK callback. For each push it publishes one array with one `DiagnosticStatus`:
  - `header.stamp`: ROS time when the push was received
  - `name`: `mid360`, `hardware_id`: empty, `message`: `info push`
  - `level`: from `lidar_diag_status`, the worst of its four 4-bit module levels (system, scan, ranging,
    communication; protocol: 0 normal, 1 warning, 2 error, 3 safety_err) → `OK` / `WARN` / `ERROR` (2, 3 and undefined
    values above 3); `STALE` when the push carries no usable `lidar_diag_status`
  - `values` (strings), only for these keys and under the SDK's names: `cur_work_state`, `core_temp` (integer,
    0.01 °C, unchanged), `powerup_cnt`, `last_sync_time`, `time_offset`, `time_sync_type`, `status_code`,
    `lidar_diag_status`, `lidar_flash_status`, `FW_TYPE`, `hms_code`, `version_app`, `version_loader`,
    `version_hardware`. Integers are written in decimal, integer arrays as compact JSON (`[0,0,0,0,0,0,0,0]`), the
    one string (`status_code`) as it is; any other kind of value is left out.
  - The push also contains the serial number, MAC address, product string and every IP configuration block
    (`lidar_ipcfg`, `*_host_ipcfg`, `ntp_server_ip`, ...). They are deliberately not copied: `/diagnostics` is often
    recorded and shared, and these identify the unit and the network.
- `src/call_back/lidar_status_info.h` (new, header only, no ROS): parsing with the bundled rapidjson (`document.h`
  only, as `lds_lidar.h` already does), the allow-list and the level, so that it can be unit-tested without ROS.
- `src/livox_ros_driver2.cpp`: call `LidarStatusPublisher::Start(*this)` after `InitLdsLidar()` succeeded (the SDK is
  initialized then). `src/driver_node.cpp`: call `LidarStatusPublisher::Stop()` first in `~DriverNode()`.
- `CMakeLists.txt`, `package_ROS2.xml`: `diagnostic_msgs` (and the new source file).

The point cloud, IMU and configuration code paths are unchanged (the patch only adds lines: +13 in existing files).

**Threading**

The SDK invokes the callback on its own command-handling thread, while it holds an internal lock
(`GeneralCommandHandler::PushLivoxLidarInfo`), and it offers no way to wait for a callback in progress. Therefore:

- the publisher, clock and logger live in a small process-wide state guarded by one mutex; the callback takes the
  mutex, returns at once if `Stop()` has run, otherwise builds and publishes the message;
- `Stop()` clears the state under the same mutex, so after it returns no publish is running or will start, and the
  node can be destroyed (the SDK itself is uninitialized later, in `~Lddc`);
- the state object is never freed, so a late callback from an SDK thread cannot touch freed memory;
- exceptions are caught in the callback and logged (an exception must not unwind into the SDK's thread).

Publishing from a non-executor thread is fine: `rcl_publish()` is documented as thread safe as long as the publisher
is not finalized concurrently (`rcl/publisher.h`), which the mutex guarantees, and `rcl_clock_get_now()` is thread
safe (`rcl/time.h`). The driver already publishes point clouds and IMU data from its own polling threads.
No lock order inversion is introduced: the callback takes only its own mutex, and neither `Start()` nor `Stop()` calls
into the SDK while holding it.

**Testing**

- Unit tests of `lidar_status_info.h` (allow-list, value text, level for each module and value, missing or malformed
  `lidar_diag_status`, invalid JSON), with pushes written exactly the way `LivoxLidarStateInfoToJson` writes them
  (rapidjson `PrettyWriter`, same keys, types and order). g++ 13.3 and clang, `-std=c++14` and `-std=c++17`,
  `-Wall -Wextra -Wpedantic -Werror`.
- colcon build on Ubuntu 24.04 / ROS 2 Jazzy against Livox-SDK2 c0796f0 (`-DROS_EDITION=ROS2 -DDISTRO_ROS=jazzy`):
  the same compiler warnings as without the change (one, the existing unused variable in `pub_handler.cpp`).
  `ros2 component types` still lists `livox_ros::DriverNode`; the custom messages are unchanged.
- A harness (not part of this PR) that loads the built library with a stand-in for `SetLivoxLidarInfoCallback`, calls
  the registered callback from other threads and checks the published messages and the QoS (reliable, volatile), and
  that nothing is published after `Stop()` returned, also with four threads pushing without pause while `Stop()` runs
  (tens of thousands of messages before `Stop()`, none stamped after it).
- Not tested yet: a real Mid-360 (the push period and the exact set of keys a Mid-360 sends), HAP and the other
  models, ROS 1.

**Open points for the maintainers**

- `name` is fixed to `mid360` and `hardware_id` is empty, which fits a single Mid-360. For several LiDARs or other
  models, a name from the device type and the handle, and an opt-in parameter for the serial number in
  `hardware_id`, would be natural. Happy to add that if you prefer it in this PR.
- One message per push, no rate limiting (the device decides the period).
- No ROS 1 support (the ROS 1 build compiles none of the new code).
