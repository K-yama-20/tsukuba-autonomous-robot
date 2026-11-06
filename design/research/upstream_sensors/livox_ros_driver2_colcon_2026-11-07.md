# livox_ros_driver2 を build.sh でなく colcon で作る（A1、2026-11-07）

- 区分：基盤（setup.sh の作り方の変更と、その先行事例・試行・A2 の手順の記録）
- 人の許可：DEC-474・DEC-475（原文は design/revisions/REV-259.yaml）。DEC-443 の採否（別の作業場所 `<workspace>_livox`）は変えず、理由のコメントだけを改めた
- 読んだコミット：9c449b5。作業ツリーは他のセッションと共有で、未コミットの変更がある（gouda.sh・gouda_core/launch/gouda_nav2.launch.py は変更あり、gouda_core/gouda_core/mid360_config.py は未追跡）。この記録はその作業ツリーの内容で照合した
- 変えたファイル：setup.sh（17・22〜24・39・41〜42・147・191・193・196〜211 行）、third_party/drivers.repos のコメント（8〜10 行）。update.sh は変えていない（38 行の `exec bash "$repo/setup.sh"` で setup.sh を呼ぶだけ）
- 上流のソースは、固定の commit を clone して直接読んだ（livox_ros_driver2 21445540f0d100dc86a7e6df312dd70bbdb4afdf、Livox-SDK2 c0796f04c143143899c87a773d9f6b7136453c0b）

## 1. 結論

1. setup.sh は、固定の commit の追跡ファイルを `git archive` で `<workspace>_livox/stage/livox_ros_driver2` に写し、`package_ROS2.xml` を `package.xml` として置いて、その写しだけを colcon で作る。CMake の引数は build.sh jazzy と同じ `-DROS_EDITION=ROS2 -DDISTRO_ROS=jazzy`。checkout は変えない
2. colcon が失敗したら setup.sh は止まる（STOPPED、終了コード 1、stamp は書かない）。stamp が合えば何もしない
3. stamp の中身を「commit」から「commit colcon」に変えた。9c449b5 の setup.sh（build.sh）で作った install は、次の setup.sh で一度だけ作り直される
4. ワークステーションでの試行で、build.sh で作った install と、ファイルの一覧（159 個）・CMake の引数・ライブラリの大きさが同じだった。内容が違うのは、install の絶対パスを含む 2 つのファイルだけ（パスを置き換えると同じ）
5. build.sh と同じ引数なので、CMAKE_BUILD_TYPE は空で、コンパイルの flag に `-O` がない（最適化なし）。変えるかは承認事項として issue #87 に登録した

## 2. 上流のソースで確かめたこと

| ファイル（commit 2144554） | 行 | 内容 |
|---|---|---|
| build.sh | 21〜23 | 引数 `jazzy` で ROS_VERSION=ROS2、ROS_DISTRO=jazzy |
| build.sh | 34〜36 | `../../build/`・`../../devel/`・`../../install/` を消す（置かれた作業場所の全体） |
| build.sh | 50〜55 | `package_ROS2.xml` を checkout の `package.xml` に写し、`launch_ROS2/` を `launch/` に写す |
| build.sh | 65 | `colcon build --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=jazzy`（作業場所の全体を探す。build type は渡さない） |
| build.sh | 70〜72 | `launch/` を消す。`set -e` がなく colcon の終了コードを見ないので、失敗しても止まらない（最後の命令は popd） |
| .gitignore | 3 | `package.xml` は無視の対象（`launch/` は対象でない） |
| CMakeLists.txt | 2・187 | `ROS_EDITION` が `ROS1` のときだけ ROS 1 の側、それ以外は ROS 2 の側 |
| CMakeLists.txt | 82〜84 | 既定の build type（Release）は ROS 1 の側だけ。ROS 2 の側にはない |
| CMakeLists.txt | 225 | `ament_auto_find_build_dependencies()`：package.xml を読む |
| CMakeLists.txt | 249 | `find_library(LIVOX_LIDAR_SDK_LIBRARY liblivox_lidar_sdk_shared.so /usr/local/lib REQUIRED)`：/usr/local/lib のほか、CMAKE_PREFIX_PATH なども探す |
| CMakeLists.txt | 252〜254 | `find_path(LIVOX_LIDAR_SDK_INCLUDE_DIR NAMES livox_lidar_api.h livox_lidar_def.h REQUIRED)` |
| CMakeLists.txt | 285〜293 | `DISTRO_ROS` が humble か jazzy なら `rosidl_get_typesupport_target`。それ以外は古い方法で、新しい rosidl では include のディレクトリが NOTFOUND になる（上流 issue #223 の症状） |
| CMakeLists.txt | 315〜318 | `rclcpp_components_register_node(... EXECUTABLE livox_ros_driver2_node)` |
| CMakeLists.txt | 331〜334 | `ament_auto_package(INSTALL_TO_SHARE config launch_ROS2)`：share に入るのは config/ と launch_ROS2/。build.sh が作る launch/ は入らない |
| package_ROS2.xml | 4・33 | name は livox_ros_driver2、build_type は ament_cmake |
| ament_cmake_core 2.5.6（Jazzy、ワークステーションの /opt/ros/jazzy） | ament_package_xml.cmake 68〜73 | package.xml は `PROJECT_SOURCE_DIR` から読む（DIRECTORY の引数がなければ）。ament_auto はこの引数を渡さないので、package.xml は CMakeLists.txt の隣に要る |
| Livox-SDK2 c0796f0 sdk_core/CMakeLists.txt | 143〜146 | 静的・共有ライブラリを `lib`、公開 header を `include` に入れる |

ドライバのソース（src/）に apr の header を include する箇所はない（grep で確認）。CMakeLists.txt の `pkg_check_modules(APR apr-1)` は REQUIRED でない。

## 3. 先行事例（CLAUDE.md 1.11）

探した場所と検索語：

- 上流 Livox-SDK/livox_ros_driver2 の issue と PR（`gh search issues` / `gh search prs`。検索語：colcon build、package.xml、build.sh、jazzy、ROS_EDITION、rosdep、CMake）
- fork の一覧（star の多い順の 15 件）と、そのうち 2 件の枝・README・package.xml
- GitHub のコード検索（検索語：`DROS_EDITION=ROS2`）。上位の 6 件の該当行を読んだ
- colcon と ament の機能（COLCON_IGNORE、`--base-paths`、colcon.pkg、ament_package_xml）
- 既存の調査台帳 design/research/vehicle_pc/2026-11-06_mid360_connection/ledger.yaml の R-OF-08・R-C-02〜R-C-05

| 候補 | 内容 | ROS 2 Jazzy | ライセンス | 保守 | 実機での例 | 採否と理由 |
|---|---|---|---|---|---|---|
| 上流の build.sh jazzy（9c449b5 の setup.sh の方式） | 2 節の表のとおり | 対応（1.2.6） | MIT | 最新の commit は 2026-09-21 | 多数（MID-360 の利用者の多く） | 不採用。作業場所の build/・install/ を消す、checkout に package.xml を書く、colcon が失敗しても止まらない。CMake の引数だけを採る |
| 上流 PR #46（Ericsii、2023-05、open・未マージ）「Delete build.sh & merge ROS1/2 into one package」 | build.sh を消し、package.xml をリポジトリに置き、ROS の版を環境変数で判定する | コメントで Jazzy（2026-03）・Kilted（2025-12）で動いたとの報告 | MIT（上流と同じ） | 未マージのまま | コメントでの利用の報告のみ | 不採用。上流のソースを変える（DEC-075）。上流が取り込めば build.sh も写しも要らなくなる（台帳 R-C-02） |
| 上流 PR #143（2024-08、closed・未マージ） | build.sh なしで colcon で作れるよう CMakeLists.txt を直す | Humble の頃 | MIT | 閉じられた | 未確認 | 不採用。ソースを変える |
| 上流 PR #236（2026-02、closed・未マージ） | ROS_DISTRO を環境変数から自動で判定する | Jazzy で試したとの記載 | MIT | 閉じられた | 未確認 | 不採用。ソースを変える |
| 上流 PR #258（2026-08、closed・未マージ） | SDK を add_subdirectory で一緒に作る（/usr/local に入れない） | 未確認 | MIT | 閉じられた | 未確認 | 不採用。ソースを変え、SDK の入れ方が DEC-442 の方式と違う |
| tu-darmstadt-ros-pkg/livox_ros_driver2 の jazzy の枝（fork、star 42、2026-10-29 更新） | package.xml をリポジトリに置き、自前の fork の SDK を ROS の package として依存させる。依存に cloudini_ros・fmt・diagnostic_msgs を足している | 対応（枝の名前と README） | GitHub の判定は NOASSERTION（本文は未確認） | 活発（上流より 28 commit 進み、2 commit 遅れ） | 未確認 | 不採用。DEC-442 は公式の 2 つを固定する方針。依存が増える |
| Ericsii/livox_ros_driver2（PR #46 の元、star 45、2025-07 更新） | PR #46 と同じ | 同上 | GitHub の判定は NOASSERTION | 2025-07 が最後 | 未確認 | 不採用（PR #46 と同じ理由） |
| JacopoPan/aerial-autonomy-stack（tools_and_docs/docker/aircraft.dockerfile、MIT、2026-11 更新） | checkout に package_ROS2.xml を package.xml として写し、launch_ROS2 を launch に写して `colcon build --symlink-install --packages-select livox_ros_driver2 --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=jazzy -DCMAKE_BUILD_TYPE=Release` | 対応 | MIT | 活発 | 未確認 | 一部を採る。CMake の引数（ROS_EDITION・DISTRO_ROS）を採る。checkout に書く点は採らない。Release は採らない（DEC-475 は build.sh と同じ引数。#87） |
| ethz-asl/BIEVR-LIO（docker/scripts/build_ros2.sh、BSD-3-Clause） | 同じく checkout に写して `--cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=jazzy --packages-select livox_ros_driver2`。ドライバと SDK は第三者の fork | 対応 | BSD-3-Clause | 2026-08 更新 | 未確認 | 引数の裏付けとして参考。fork を使う点は採らない |
| mit-acl/sando（docker/Dockerfile、BSD-3-Clause、2026-10 更新） | ドライバを専用の作業場所に写し（cp -r）、写しの側で package.xml を置いて colcon で作る | Humble の引数 | BSD-3-Clause | 活発 | 未確認 | 考え方を採る（写しを作ってから作り、元の checkout を汚さない）。違い：Gouda は `git archive` で固定 commit の追跡ファイルだけを写す |
| url-kaist/se3-lio（docker/ros2/Dockerfile、GPL-2.0） | Humble で古い commit に固定。新しい master では引数 HUMBLE_ROS がなくなったとの注記 | Humble | GPL-2.0 | 2026-09 更新 | 未確認 | 参考。引数の名前は commit で変わる（2144554 は DISTRO_ROS）。commit を固定する理由の一つ |
| ROS 2 の binary の package（rosdistro の jazzy/distribution.yaml、apt） | apt で入れられれば自分で作らずに済む | — | — | — | — | なし。rosdistro master の jazzy/distribution.yaml（2026-11-07 取得）に livox の行がなく、ワークステーションの apt に ros-jazzy-livox-* がない |
| colcon.pkg・`--metadata` で package の種類を colcon に教える | checkout の外から package の情報を与える | — | — | — | — | 不採用。colcon が認識しても、ament_cmake の CMakeLists.txt 自体が package.xml を読む（2 節の ament_package_xml）。colcon.pkg を checkout に置けば checkout を汚す |
| 上流 issue #26（2023-03、closed）・#131（open）・#223（open） | #26：保守者は ROS 1・2 の枝を分けず、colcon で作れる新しいスクリプトを出すと回答（未実現）。#131・#223：引数なしの colcon で LIVOX_INTERFACES_INCLUDE_DIRECTORIES が NOTFOUND | — | — | — | — | 根拠として使う。DISTRO_ROS を渡さないと失敗する（CMakeLists.txt 285〜293 行と一致） |

自作の範囲：setup.sh の約 10 行（写しを作り colcon を呼ぶ）。上の候補はどれも、ソースを変えるか、checkout に package.xml を書くので、DEC-075 と「checkout を汚さない」を同時に満たさない。写しの考え方（sando）と引数（aerial-autonomy-stack・BIEVR-LIO・上流 build.sh）を組み合わせた。

未調査：つくばチャレンジの他チームの作り方（検索では見つけていない）。

## 4. setup.sh の方式

5 節の MID-360 の部分（177〜212 行）：

1. SDK は今までどおり（/usr/local に sudo で入れて ldconfig。stamp `sdk_build/.gouda_installed_commit`）
2. ドライバの stamp `install/.gouda_built_commit` の中身が「固定の commit と ` colcon`」で、`install/livox_ros_driver2/lib/liblivox_ros_driver2.so` があれば何もしない
3. そうでなければ：
   - `sdk/COLCON_IGNORE` と `src/COLCON_IGNORE` を置く（手で `colcon build` を `<workspace>_livox` で実行しても、写しだけが package になる。印がないと SDK も checkout も plain cmake の package として見つかる：6 節の試行 R1）
   - `stage/`・`build/`・`install/` を消す（作り直しは毎回まっさら。前の build.sh の残りも消える）
   - `git -C <checkout> archive <固定の commit> | tar -x -C stage/livox_ros_driver2`、`package_ROS2.xml` を `package.xml` に写す
   - `(cd <workspace>_livox && colcon build --base-paths <workspace>_livox/stage --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=jazzy) || stop ...`
   - ライブラリがあることを確かめ、stamp を書く

Gouda の作業場所の build（`--symlink-install`）とは別で、ドライバは build.sh と同じく `--symlink-install` なし（share の config は写しになる）。並列の数は setup.sh の 174 行（CMAKE_BUILD_PARALLEL_LEVEL・MAKEFLAGS の既定 2）に従う。

## 5. Gouda 側との組み合わせ（ソースと試行で確認）

| Gouda 側 | 読むもの | colcon の方式での結果 |
|---|---|---|
| gouda_core/gouda_core/mid360_config.py の find_template（133〜137 行） | `<share>/config/MID360_config.json` | ある（CMakeLists.txt 331〜334 行で config/ が share に入る）。試行で checkout の config/MID360_config.json と同じ内容。作業ツリーの mid360_config.py の写しで find_template と write_driver_config が通った（RFC 5737 の文書用のアドレスで試した） |
| gouda_core/launch/gouda_nav2.launch.py の _mid360_ready（29〜48 行） | `get_package_share_directory('livox_ros_driver2')` | install/local_setup.bash を読めば見つかる。colcon が失敗した後は local_setup.bash はあるが package は見つからず（PackageNotFoundError）、launch は「not installed or not loaded」として XT-32 だけで動く（試行 run7） |
| gouda.sh（97〜98 行、未コミットの変更） | `${workspace}_livox/install/local_setup.bash` | colcon が install の直下に作る（試行で確認。失敗した後もある） |
| mid360_config.py の DRIVER_PACKAGE・DRIVER_EXECUTABLE（35 行） | livox_ros_driver2 / livox_ros_driver2_node | `ros2 pkg executables livox_ros_driver2` が `livox_ros_driver2 livox_ros_driver2_node` |
| build.sh が share に置いていたもの | config/・launch_ROS2/・msg/・ament と colcon の環境ファイル | 同じ。build.sh の launch/ は share に入らない（CMake が入れるのは launch_ROS2/）。Gouda は上流の launch を使わない（gouda_nav2.launch.py が Node を直接作る） |

## 6. ワークステーションでの試行

場所：シミュレーション用のワークステーション（Ubuntu 24.04.5、amd64、ROS 2 Jazzy）の新しい空のフォルダ `~/livox_colcon_trial_20261107`（以下 `<trial>`）。前の試み `~/livox_trial_20261107` には触れていない。sudo は使っていない。ドライバは起動していない。

版：cmake 3.28.3、g++ 13.2.0、colcon-core 0.21.3、colcon-cmake 0.2.30、colcon-ros 0.5.0、ament_cmake_core 2.5.6。libapr1-dev は入っていない（rosdep の apr の key。Dell では setup.sh の rosdep が入れる。ソースは apr を使わない：2 節）。

setup.sh との差（`trial_setup_livox.sh` は setup.sh の 2 節（108〜142 行）と 5 節の MID-360 の部分（177〜212 行）をそのまま写し、次だけを変えた）：

- `workspace=<trial>/gouda_ws`（よって `<workspace>_livox` は `<trial>/gouda_ws_livox`）、`pins` は drivers.repos の Livox の 2 件だけ（値は同じ）
- SDK：`/usr/local/lib/...` の確認を `<trial>/sdk_prefix/lib/...` に、`sudo cmake --install sdk_build` を `cmake --install sdk_build --prefix <trial>/sdk_prefix` に、`sudo ldconfig` を省いた（sec5.diff）
- ドライバ：`export CMAKE_PREFIX_PATH=<trial>/sdk_prefix`（CMake は /usr/local を既定で探すが、この prefix は探さないため）。colcon の命令は setup.sh と同じ

実行（いずれも `<trial>` で。結果は各 log の値）：

| 回 | 目的 | 結果 |
|---|---|---|
| run1 | 空から（clone、SDK、ドライバ）。stamp の中身が commit だけの版の setup.sh | 終了 0。2 つの checkout は固定の commit。ドライバは colcon で 15.2 秒 |
| run2 | stamp の新しい形（commit colcon）の setup.sh。run1 の stamp は前の形 | 終了 0。一度だけ作り直した。stamp は `2144554… colcon` |
| run3 | もう一度 | 終了 0。「Livox-SDK2 c0796f0 is installed」「livox_ros_driver2 2144554 is built」。作り直しなし（ライブラリの時刻が同じ） |
| run4 | stamp を壊し、`CXXFLAGS="-include /nonexistent_trial_failure.h"` で失敗を入れる | 終了 1。CMake の compiler の確認で失敗し（存在しない header）、colcon が `Failed <<< livox_ros_driver2`、setup の部分が `STOPPED: livox_ros_driver2 did not build ...`。stamp なし、ライブラリなし |
| run5・run6 | 回復と、もう一度 | 終了 0（作り直し）、終了 0（何もしない） |
| run7〜run9 | run4 と同じ失敗の後の install の中身を見て、回復と、もう一度 | run7 終了 1。install/ に local_setup.bash と package の環境ファイルだけがあり、`ros2 pkg prefix livox_ros_driver2` は「Package not found」。run8 終了 0、run9 終了 0（何もしない） |
| R1 | 印（COLCON_IGNORE）なしで package.xml もない状態の `colcon list` | `livox_ros_driver2 src/livox_ros_driver2 (cmake)` と `livox_sdk2 sdk/Livox-SDK2 (cmake)`。印のある `<workspace>_livox` では `livox_ros_driver2 stage/livox_ros_driver2 (ros.ament_cmake)` だけ |
| R2 | 比べるため、同じ commit の写しで上流の `build.sh jazzy`（別のフォルダ `<trial>/ref_buildsh/ws`） | 終了 0。install のファイルの一覧は同じ（159 個）。内容が違うのは share の local_setup.sh と package.sh だけで、install のパスを置き換えると同じ。liblivox_ros_driver2.so（3337328 byte）と livox_ros_driver2_node（257960 byte）の大きさは同じ。cmake_args.last は同じ。build.sh は写しに package.xml を残した（launch/ は消した） |

確認（checks.sh、run1・run2 の後と最後）：

- `ros2 pkg executables livox_ros_driver2`：`livox_ros_driver2 livox_ros_driver2_node`
- share/livox_ros_driver2：cmake、config（MID360_config.json を含む 8 個）、environment、hook、launch_ROS2（11 個）、msg、rust、package.xml と環境ファイル
- ldd の not found：SDK の prefix を読み込みの経路に入れないと、liblivox_ros_driver2.so の `liblivox_lidar_sdk_shared.so => not found` だけ（setup.sh では /usr/local/lib と ldconfig で解決する所）。`LD_LIBRARY_PATH=<trial>/sdk_prefix/lib` では 10 個のファイルのどれにも not found がなく、SDK は `<trial>/sdk_prefix/lib/liblivox_lidar_sdk_shared.so` に解決した
- CMakeCache：`LIVOX_LIDAR_SDK_LIBRARY` と `LIVOX_LIDAR_SDK_INCLUDE_DIR` は `<trial>/sdk_prefix` の下、`CMAKE_HOME_DIRECTORY` は stage の写し、`CMAKE_BUILD_TYPE` は空。CXX_FLAGS は `-std=gnu++17 -fPIC -Wall -Wextra -Wpedantic -Wno-unused-parameter -fopenmp -fPIC`（`-O` なし。build.sh の R2 も同じ）
- checkout：2 つとも HEAD は固定の commit で、`git status --porcelain` も `git status --porcelain --ignored` も空（build.sh と違い、package.xml も残らない）
- stage の package.xml は package_ROS2.xml と同じ内容

証拠（リポジトリの外、`<trial>` に置いた。sha256）：

| ファイル | sha256 |
|---|---|
| drivers.livox.repos | cc6e6eb53615762c532f6513d05635b6182bb89e6f951b8f064db5c0eed37222 |
| trial_setup_livox.run1.sh（run1） | ccef214111298095118f7d0978f0d65ea2465d0cadf71e2e9d8b5ca1312e0666 |
| trial_setup_livox.sh（run2〜run9） | 02cde4b95dd23330b41152672d49097ac60fcdcc07dd693eaf85b58ed1eded23 |
| sec5.diff | 0d229cc7d58a69885db7b11504f0c198b1a3274bd19d7086bbcbe0c6f0ce580f |
| checks.sh | b736b61ab3c8c3c56d881f4c98bf17ab236c2e90307d2443b85fc2c8ee32be95 |
| sequence.sh | a4f8fd4fb4b5d70574eb219467e38e3a8981790d5bf882024bd177e11bbc4a9e |
| reference.sh | 141cd507caee3fd644f2458068d3533d4dd685e5c56338040a3d87d2f3125a3b |
| run1.log | b5b79a153ee4b1c0959393d7152e61ec91a55682b9973394c328d04257be7411 |
| run2.log | a3ae13855e42932adbfa775a0e13370697a576029eb8bec82f7a3cec9a3b2c61 |
| run3.log | 19e87adf3af2a28a65952cb4c823b97ef540b15342e7091a69a5bbdab5b2ae89 |
| run4.log | a972fde24925572ef76ebe05be5473b5c59c7bf7aa9fd78fac95120b9bdfd7e3 |
| run5.log | b65335235d563341537d7a07996484fb41ad4e1cead0c364ef499f58967a50e7 |
| run6.log | f8bc6af73b2465321674996ae2e8a659e4420110c67a58544bb2f36d98ccc5cd |
| run7.log | a0b7f6319981dc2741e62925f37ca2e0585cb549268c1dfce99be42f9c489ba6 |
| run8.log | ea4a408773f41f2397808ba1bac318ea7ca006f1d6dde980bd4edbc1b1ca0d46 |
| run9.log | 9e09b1a0faa5b65fe38c862524fe18e9462be263e1260b771714121687d7f011 |
| checks_run1.txt | cd99fb48a2d2fba4b77e1bb96554967182fd92679474b55e9f9d9908551a22cb |
| checks_run2.txt | 4e05deefc6b774b0285a2c6a3239ee9c6e2dfdeb9caea435cce188567aec4967 |
| checks_final.txt | da65b767a11890867b4cca7bb7fae496e460d8c4915d3d5a6a992044decc9e3d |
| sequence.txt | 42671c6f4bc0b414e471863c8f616731158dcbdc7f0322b9d62d43676fdb0bba |
| reference.txt | 683a943246e1dccf830bb3770237d4e8da53fd362275cbb1c9a3135d524c2659 |
| ref_buildsh.log | 184de801cb70f705d9b34ab836bc1c74a5a3a74e84684780bd0471f2cb22a0a3 |
| pycheck/gouda_core/mid360_config.py（作業ツリーの写し） | 64372318a53def02c7bac4f66f6e2eeae614cf07b3fcda581c08b94336e481b7 |
| pycheck/gouda_core/sensor_extrinsics.py（同） | 9aedec0cba63f80367a1d36c8ec22c2d083e0a6dd7e6322de8260e2151086539 |

checks_run1.txt の Python の確認は、PYTHONPATH の指定の誤り（ROS の PYTHONPATH を上書きした）で ament_index_python を読めず失敗した。checks.sh を直し、checks_run2.txt と checks_final.txt で通った（試験の基盤の誤り。合否の基準は変えていない）。

この試行の setup.sh（作業ツリー、未コミット）の sha256 は 58fd09bea51ae49ec9b6a6386160488fe508cd959cbeb8654bfc9f9050ebc3e0。試行の 2 節・5 節がこの setup.sh の 108〜142 行・177〜212 行と同じことを cmp で確かめた。

## 7. A2：Dell で人が setup.sh を実行する手順

前提：この変更がコミットされ、Dell の `~/gouda_ws/src/tsukuba-autonomous-robot` に入っていること（コミット・push は人の指示で行う）。Gouda は止めておく（setup.sh は Gouda が動いている間は止まる）。センサーはつながっていなくてよい（ドライバは起動しない）。

1. 実行
   - 変更を取り込む場合：`bash update.sh`（main を fast-forward して setup.sh を呼ぶ）
   - 取り込み済みの場合：`bash setup.sh`
2. sudo を聞かれる所
   - 足りない apt の package（apt-get install）、rosdep の初回（rosdep init）と、rosdep install が入れる package（libapr1-dev など）
   - dialout の group（入っていなければ）
   - MID-360 の SDK：`sudo cmake --install`（/usr/local に入れる）と `sudo ldconfig`。SDK の stamp が合わないか、/usr/local/lib/liblivox_lidar_sdk_shared.so がないときだけ
   - LiDAR の LAN の profile（端末で選んだときだけ）
   - ドライバの colcon には sudo は要らない
3. 成功の確かめ方
   - 出力：「== MID-360 ...」の後に colcon の `Finished <<< livox_ros_driver2` と `Summary: 1 package finished`。最後まで進み「== done」が出る。`STOPPED:` が出ない
   - stamp：`cat ~/gouda_ws_livox/sdk_build/.gouda_installed_commit` が `c0796f04c143143899c87a773d9f6b7136453c0b`、`cat ~/gouda_ws_livox/install/.gouda_built_commit` が `21445540f0d100dc86a7e6df312dd70bbdb4afdf colcon`
   - SDK：`ls -l /usr/local/lib/liblivox_lidar_sdk_shared.so /usr/local/include/livox_lidar_api.h`
   - ldconfig：`ldconfig -p | grep liblivox_lidar_sdk_shared` が /usr/local/lib のものを示す
   - ldd：`ldd ~/gouda_ws_livox/install/livox_ros_driver2/lib/liblivox_ros_driver2.so | grep -E 'not found|livox_lidar_sdk'` が `liblivox_lidar_sdk_shared.so => /usr/local/lib/liblivox_lidar_sdk_shared.so` の 1 行だけ（`not found` がない）。先に `source /opt/ros/jazzy/setup.bash` と `source ~/gouda_ws_livox/install/local_setup.bash`
   - 実行ファイル：`ros2 pkg executables livox_ros_driver2` が `livox_ros_driver2 livox_ros_driver2_node`
   - share の config：`ls "$(ros2 pkg prefix livox_ros_driver2)/share/livox_ros_driver2/config/MID360_config.json"`。`ros2 pkg prefix livox_ros_driver2` が `~/gouda_ws_livox/install/livox_ros_driver2` を示す（他の場所に作ったドライバが先に見つからない）
   - checkout：`git -C ~/gouda_ws_livox/src/livox_ros_driver2 status --porcelain` が空
   - 冪等性：もう一度 `bash setup.sh` を実行し、「Livox-SDK2 c0796f0 is installed」「livox_ros_driver2 2144554 is built」が出て colcon が走らない
4. build.sh で作った install が残っている場合（9c449b5 の setup.sh を実行していた場合）
   - 何もしなくてよい。stamp の中身が commit だけなので、新しい setup.sh が `~/gouda_ws_livox/build`・`install`・`stage` を消して一度だけ colcon で作り直す
   - build.sh が checkout に残した `package.xml` は git の無視の対象で、新しい方式では使わない（`git archive` は追跡ファイルだけを写し、src/ には COLCON_IGNORE がある）。消すなら、`cmp ~/gouda_ws_livox/src/livox_ros_driver2/package.xml ~/gouda_ws_livox/src/livox_ros_driver2/package_ROS2.xml` で同じと確かめてから `rm` する（任意）
   - build.sh が途中で止まって checkout に `launch/` が残っていると、setup.sh は 2 節で「local changes」として止まる。`git -C ~/gouda_ws_livox/src/livox_ros_driver2 status --short` が `?? launch/` だけなら、setup.sh の表示どおり stash するか、launch/（launch_ROS2/ の写し）を消してからやり直す
5. 失敗したとき
   - `STOPPED: livox_ros_driver2 did not build ...` が出たら、画面の出力と `~/gouda_ws_livox/log/latest_build` を保存して AI に渡す（アドレス・ホスト名は公開リポジトリに書かない）
   - Gouda の作業場所は 5 節の前半ですでに作られている。setup.sh の 6・7 節（LAN・IMU・時刻の確認、~/.bashrc）は実行されないので、直った後にもう一度 setup.sh を実行する
   - ドライバがない間、Gouda の Nav2 の launch は MID-360 を使わず XT-32 だけで動く（試行 run7 と _mid360_ready のソース。作業ツリーの未コミットの変更に依る）

## 8. 残るリスク・未確認

- Dell での実行は未実行（A2）。/usr/local と ldconfig の経路、sudo の手順、Dell の cmake・colcon の版、`~/.colcon/defaults.yaml` の有無は未確認。試行では SDK を prefix に入れ、CMAKE_PREFIX_PATH と LD_LIBRARY_PATH で代えた
- 最適化なし（CMAKE_BUILD_TYPE が空）。build.sh と同じだが、CPU の負荷と点群の取りこぼしは未測定。issue #87（承認事項、実測が要る）
- 写しは `git archive` に依る。将来の固定の commit が submodule や export-ignore を持つと、写しに入らないものが出る（2144554 にはどちらもない）
- 作り直しのたびに `<workspace>_livox` の build/・install/ を消す。その作業場所には MID-360 のドライバしか置かない前提
- README.md（42・46・187 行）はまだ build.sh の方式を説明している（この作業で触ってよいファイルに入っていない）。setup.sh の最後の「MID-360 driver (not started by Gouda yet)」は 9c449b5 の gouda.sh とは合うが、gouda.sh の未コミットの変更（REV-242）がコミットされると古くなる
- design/research/upstream_sensors/livox_ros_driver2_2144554/SOURCE.txt の「Not checked against the build on the vehicle PC」は、ワークステーションでは確認できたが Dell では未確認のまま
- shellcheck はこの Mac にもワークステーションにも入っておらず、未実行。`bash -n setup.sh` と `bash -n update.sh` は通った
