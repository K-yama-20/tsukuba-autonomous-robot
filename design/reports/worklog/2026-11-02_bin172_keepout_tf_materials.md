# 第172便 作業記録：local の keepout フィルタの TF 失敗の判断材料（読むだけ、実装なし）

- 日付：2026-11-02
- 読んだコミット：f61a71b（作業ツリーに別のチャットの未コミットの記録あり）
- 人の発言（原文）：「"local の keepout フィルタの TF 失敗"という問題について、判断材料をまとめよ」
- 読んだもの：第157・160・163便、DEC-222、run-ff780d47・cdde4c29・574fe6d7 の log、navigation2 1.3.13 の keepout_filter.cpp・costmap_filter.cpp（Mac の一時領域に取得）
- 変更：コード・設定・正本は変えていない。VM は ssh が時間切れで、実機の確認はしていない

## 1. 確かめた事実

- 出ているエラーは「CostmapFilter: failed」で、`transformPose` の文言である。KeepoutFilter::process では、この結果は車体が keepout の中にいるかの判定（is_pose_lethal、override_lethal_cost）だけに使う（ソース）
- マスクを書く本体は別の `lookupTransform(TimePointZero)` を使う。失敗すれば「KeepoutFilter: Failed」と出て中止するが、3 つの log で 0 件。本体の変換は時刻 0（最新）なので、この遅れでは失敗しない
- `tf_->transform` は transform_tolerance（既定 0.1 s。gouda は未設定）の間待つ。エラーの時刻は要求の時刻の約 0.106 s 後（cdde4c29 の例：要求 …257.970、log …258.076）
- エラーの間隔の中央値 0.2 s（cdde4c29 119 件、ff780d47 245 件）。controller の「Control loop missed」から最も近いエラーまでの時間の中央値 0.001 s（両 run）
- run-574fe6d7 の抜粋には 0 件。第163便は同じ走行で map→odom の遅れを 325 回観測しており、抜粋から除かれた可能性がある（未確認）
- DEC-222 の人の回答：「DEC-222: global, localの両方trueとする。反論は認めない。」（REV-136）

## 2. 読み方（推測を含む）

- 第157便の「local では keepout が効いていない」は、ソースからはおそらく誤り。マスクは書かれている。実機の costmap では未確認
- 実際に壊れているのは、local の override（DEC-222）。車体が keepout に入っても is_pose_lethal が真にならず、抜け出す動きが効かない
- 第168便の「0.2 s ごとの約 0.1 s の詰まり」の原因は、この 0.1 s の待ちの可能性が高い（時刻の一致。mutex を持ったまま待つことは未照合）。第168便の voxel layer の推測より有力

## 3. 検査・試験

- log の集計：python（上記の 3 つの log）。単体試験・設計検査・実機の確認は未実行（コードは変えていない）

## 4. 原因の分類（1.6）

- 設計（map→odom の時刻 DEC-285 と、filter が now() で引くことの不整合）

## 5. 承認の候補（DEC にはまだしていない）

- 案 C：map→odom の値はそのままで、stamp を今の時刻に近づけて出す。推奨。ND-07、IFD-25、DEC-285、第160便の候補 C に関係
- 案 A：filter の transform_tolerance を延ばす。待ちが増えるので推奨しない（1.5 の timeout の延長にもあたる恐れ）
- 案 B：local の override を false。DEC-222 に反するので、人が DEC-222 を変える場合だけ
- 確認の試験：マスクの範囲の近くで止まったまま local costmap を記録する（VM か x86 の PC。動かさない）

## 6. 残るリスク・次の作業

- すべてソースと log からの読みで、実機では未確認。MPPI の提案の P1 と local 10 Hz の案に関係する
- 止まっている：確認の試験（VM か x86 の PC への接続）、案の実装（人の承認）

## 7. 追記：他のシステムの調べ（人の発言「KUAMSや他のシステムでは?どうなっている？ 独自実装はなるべく避け、既存のOSSや公開されているプログラムを流用するのが早い。」）

- AMCL（Nav2 1.3.13 amcl_node.cpp 733〜735）：scan の時刻＋transform_tolerance（雛形 1.0 s）で map→odom を出す
- slam_toolbox（jazzy）：一定周期（既定 0.05 s）で、scan の時刻または今の時刻＋transform_timeout（既定 0.5 s）で出す
- robot_localization（jazzy-devel）：出力の時刻＋transform_time_offset（既定 0）。先の時刻にする値がある
- KUAMS（kzm784/kuams@750934a）：params_nav2.yaml に keepout・filter なし。local・global costmap などの transform_tolerance 1.0 s。map→odom は lidar_localization_ros2（enable_map_odom_tf）
- いずれも「少し先の時刻で出す」が一般的で、案 C を独自の仕組みなしで既存の慣習に合わせられる。実機は未確認。コード・設定は変えていない
