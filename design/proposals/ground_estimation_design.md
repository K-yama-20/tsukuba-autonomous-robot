# 地面の推定の設計（人の方針 DEC-108 に基づく。提案。実装は許可まで行わない）

状態: 提案。`ground_estimation_plan.md`（REV-049）を人の方針（DEC-108、原文は判断台帳）で置き換える。承認事項は DEC-107（承認後に正本 docs/map_conversion.md §2 と map_convert.py へ反映）。
前提の未回答: DEC-098（変換の暫定値）、DEC-105（IMU と LiDAR の傾き）、PRM-05（base_link の高さ）。
根拠の記録: FILE-GROUND-PLAN-CHECK（submap ごとの地面の山）、FILE-GROUND-DESIGN-CHECK（GLIM の dump の軌跡の補正）。

## 1. 方針への評価

### 妥当な点（そのまま採る）

| 方針 | 根拠 |
|---|---|
| 判定単位を「取得走行 × 部分地図」にする | GLIM の submap は連続した時間の窓（屋外の中央値 2.2 s、廊下 55 s。重なりなし）。2 層の地面（屋外）は別の submap に分かれるので、submap ごとに判定すれば層を分けられる |
| 軌跡の真下を起点にする | 分析（FILE-GROUND-PLAN-CHECK (2)）で、屋外では想定の高さの ±0.4 m の窓に鋭い山（窓の点の 47 %）。経路の近くは LiDAR の死角の外（1 m 以上）で地面が映る（DEC-099: 1 m 以内の格子の 33〜40 % に低い点） |
| 上下非対称の受け入れ幅 | 廊下の床の反射は床より 0.2〜1.8 m 下、屋外の別の層は 1.8 m 下。上側は縁石・段差で 0.15〜0.2 m 程度。下側を狭く、上側を段差の上限まで |
| 最低点に一本化しない | 今の方式の失敗の直接の原因（最低点が反射・別の層） |
| 傾きを重力方向で測る | GLIM の地図座標は IMU で重力に合わせた z（ただし G-MAP-TILT の 4 度のずれが残る。§5 の失敗モード） |
| 「地面かどうか」と「走行可能か」を分ける | 縁石の下・側溝は地面だが通れない。Nav2 の costmap には走行可能性だけを渡す |
| 通過した空間の自動チェック | 正解データが要らず、最も重大な誤り（通路を障害物にする）を直接測る |

### 修正が必要な点（根拠つき）

1. **軌跡は dump の `traj_lidar.txt` から取り、submap の `data.txt` の frame の姿勢は使わない。**
   `data.txt` の `T_world_lidar` は odometry のままで、loop closure の補正が入っていない（屋外で `traj_lidar.txt` との差が中央値 1.66 m、最大 6.7 m。FILE-GROUND-DESIGN-CHECK）。`traj_lidar.txt` は補正後の submap 原点 `T_world_origin` から作られ、点も同じ `T_world_origin` で地図座標へ移るので、同じ補正が掛かる。stamp は両者で一致する（609/611、6149/6177 が照合できた。残りは submap に入らなかった frame）。
2. **「センサーの Z − H」は使わず、姿勢込みで接地点を予測する**（方針 B のとおり）。LiDAR 座標の下向き単位ベクトル（取付の回転で base の −z を LiDAR 座標へ）を姿勢で回し、`p_contact = p_sensor + R_world_lidar · (R_lidar_base · [0, 0, −H_design])`。坂で 4 度傾いた地図（G-MAP-TILT）では、単純な Z − H は経路から 4 m 離れると 0.3 m ずれる。
3. **H の設計値の構成を一つに決める**（二重加算の防止）。
   - センサーから地面までの高さ = base_link の高さ（PRM-05、base_footprint → base_link）＋ LiDAR の base_link からの取付高さ（/config の `lidar_mount_z_m`）。
   - /config の値は「base_link からの取付位置」と定義されている（RQ-I081 の入力）。PRM-05 が未確定の間は、/config の取付高さだけで H_design を作り、窓を広げる（§4）。実測で得た H と H_design の差は DecisionEvent と manifest に残す。
4. **走行 ID は「原図 ID + submap 番号」で十分。ただし submap 内の再通過を検出して分割する。**
   廊下の submap は 55 s あり、折り返しを含む。submap 内で軌跡が同じ xy（1.5 m 以内）に 10 s 以上の間隔で戻る区間は、別の「通過」として分けて判定する（§3 A-2）。
5. **候補の採用条件に、点の「上下の整合」を足す。** 候補の高さの直下（0.3 m 以内）に別の候補があれば、上の候補は物の上面か反射の対か判別できないので、支持点数が多い方を採り、少ない方を「未確定」にする（一本化ではなく、採用順の規則）。
6. **拡張の打ち切り R_max は、submap の軌跡からの距離で測る**（地図全体の軌跡ではない）。別の submap の軌跡に近い格子は、その submap が判定する。
7. **動的物体（押している人）**: 経路の真後ろ（車体の後方 0.5〜2 m、幅 1 m）の物の高さの点は、支持点にも障害物にも使わず「未確定」にする。廊下の地図で経路の左側全長に物の高さの点があり（ゴミ箱が判別できなかった原因の候補）、人の可能性が高い。範囲は設定にする。

## 2. 処理フロー（モジュール単位）

```
原図（dump）
 ├─ M1 読み込み ──────────── submap（点・T_world_origin・frame の stamp）、traj_lidar.txt、/config、正本の値
 │        ↓
 ├─ M2 対応付け ──────────── submap ごとの「通過」の列（stamp 範囲、補正後の姿勢の列）、整合の検査の結果
 │        ↓
 ├─ M3 H の推定 ──────────── 通過ごとの H（設計値 ± 制約）、局所平面、失敗の理由
 │        ↓
 ├─ M4 起点の確定 ─────────── 通過ごとの起点の格子（RANSAC で確定した地面の高さ・法線・信頼度）
 │        ↓
 ├─ M5 拡張 ───────────────── 格子ごとの状態・地面高さ・信頼度・走行 ID・方式（submap ごと）
 │        ↓
 ├─ M6 統合 ───────────────── 地図全体の格子（食い違いの解決、確率的な統合）
 │        ↓
 ├─ M7 分類と走行可能性 ──── 2D 占有格子（Nav2）、負の障害物の候補、表示用の図
 │        ↓
 └─ M8 検証 ───────────────── 通過空間のチェック、指標、manifest への記録。失敗なら M0 へ
M0 従来方式（フォールバック） ─ 今の下側の包絡。manifest に方式と理由を記録
```

| モジュール | 入力 | 出力 |
|---|---|---|
| M1 読み込み | dump（`%06d/points_compact.bin`、`data.txt`、`traj_lidar.txt`）、/config、正本（PRM-05、PRM-62〜64、新しい設定） | submap[i] = {点（地図座標）、frame の stamp}、軌跡 {stamp → T_world_lidar}、H_design、R_lidar_base |
| M2 対応付け | submap[i]、軌跡 | 通過[i][k] = {stamp 範囲、姿勢の列（補間済み、停止中の重複を間引き）}、検査 = {stamp の照合率、補正の整合の残差} |
| M3 H の推定 | 通過、点、H_design、窓 | 通過ごと: {H_est、局所平面（法線・残差）、支持点数、失敗の理由} |
| M4 起点 | 通過、H_est、点 | 起点の格子の集合（高さ・法線・残差・支持点数・信頼度） |
| M5 拡張 | 起点、点、格子の候補、しきい値 | 格子ごと（submap ごと）: 状態・高さ・信頼度・走行 ID・方式 |
| M6 統合 | 全 submap の格子 | 地図全体の格子（同上＋寄与した走行 ID の列） |
| M7 分類 | 統合した格子、点、帯の設定 | 2D 占有格子、負の障害物の候補、slope/step/height の図 |
| M8 検証 | 2D 占有格子、軌跡、車体の寸法 | 合否（通過空間の障害物 0）、指標、manifest |

## 3. 疑似コード（関数単位。値はすべて引数）

### A. 対応付け（M1・M2）

```python
def load_trajectory(src):
    # traj_lidar.txt: stamp x y z qx qy qz qw （loop closure 後）
    return {round(stamp, 4): (p, q) for stamp, p, q in read_tum(src / 'traj_lidar.txt')}

def check_correction_consistency(src, submap, traj, tol_m):
    # A-2 の検証: data.txt の odom 姿勢に GLIM と同じ補正を掛け、traj_lidar と比べる
    # T_corr = T_world_origin · T_origin_endpoint_L · (T_odom_lidar0)^-1 · T_odom_lidar   （global_mapping.cpp 618〜625 行）
    res = [norm(apply(T_corr(submap, f)) - traj[f.stamp].p) for f in submap.frames if f.stamp in traj]
    return {'matched': len(res) / len(submap.frames), 'residual_max': max(res)}, max(res) <= tol_m and len(res) == len(submap.frames)

def passes_of_submap(submap, traj, revisit_xy_m, revisit_dt_s, stop_dist_m, interp_step_m):
    # 通過 = submap の frame を時間順に並べ、同じ場所（revisit_xy_m）に revisit_dt_s 以上あとで戻ったら切る
    poses = [traj[f.stamp] for f in submap.frames if f.stamp in traj]     # 補正後の姿勢だけ
    poses = drop_stationary(poses, stop_dist_m)                           # 停止中の姿勢の重複を間引く（最初の 1 つを残す）
    segments = split_on_revisit(poses, revisit_xy_m, revisit_dt_s)
    return [interpolate(seg, interp_step_m) for seg in segments]          # 欠損（frame の欠け）は直線で補間、補間した姿勢には印を付ける
```

### B. H の推定（M3）

```python
def contact_point(T_world_lidar, R_lidar_base, H):
    # 姿勢込み: base の真下 H の点を LiDAR 座標で表し、地図座標へ
    return T_world_lidar * (R_lidar_base @ [0, 0, -H])

def estimate_H(pass_, points, H_design, dH_max, r_in, r_out, exclude_rear, ransac):
    # センサー周辺の輪状範囲（r_in: 死角と自車点を除く、r_out: 外側）の点から局所平面を当て、
    # 平面とセンサー姿勢の関係から H を求める。地図全体の分布は使わない
    cand = points_in_annulus(points, pass_, r_in, r_out, exclude_rear)
    cand = cand[within(cand.z, predicted_z(pass_, H_design) - dH_max - slack, predicted_z(pass_, H_design) + dH_max + slack)]
    plane = ransac_plane(cand, ransac)                                    # 法線・残差・インライア
    if plane is None or plane.inliers < ransac.min_points: return fail('support')
    if angle(plane.normal, gravity_up) > ransac.max_tilt_deg: return fail('tilt')
    H_est = median(distance_along_down(pose, plane) for pose in pass_.poses)   # 姿勢の下向きベクトルと平面の交点までの距離
    if abs(H_est - H_design) >= dH_max - eps: return fail('clamped')        # 上限への張り付きは失敗
    if has_competing_plane(cand, plane, sep_m): return fail('competing')     # 別の平面（別の層）が同程度の支持点を持つ
    return ok(H_est, plane)
```

坂・横断勾配のバイアス: 輪状範囲の平面は坂の面そのものを表すので、H は平面までの「法線方向の距離」ではなく「車体の下向き方向の距離」で測る（上の `distance_along_down`）。横断勾配では車体のロールが入るので、姿勢の roll を使う（traj_lidar の四元数）。

### C. 起点と拡張（M4・M5）

```python
def seed_cells(pass_, H_est, plane, points, grid, seed_r, ransac):
    seeds = []
    for pose in pass_.poses:
        c = contact_point(pose.T, R_lidar_base, H_est)
        cell = grid.cell_of(c); near = points_near(points, c, seed_r)
        p = ransac_plane(near, ransac)                                     # 近傍の実測点で確定
        if p is None or p.inliers < ransac.min_points or p.rms > ransac.max_rms or angle(p.normal, up) > ransac.max_tilt_deg or spread(near) < ransac.min_spread_m:
            continue
        seeds.append(Seed(cell, z=p.z_at(c), normal=p.normal, conf=1.0, run=pass_.id))
    return seeds

def expand(seeds, points, grid, th):
    # th: theta_max_deg, eps_m, up_band_m, down_band_m, step_max_m, min_support, R_max_m, conf_decay, conf_min, consistency_r
    state = {s.cell: Cell('ground', s.z, s.normal, s.conf, s.run, 'new') for s in seeds}
    heap = [(dist_to_path(s.cell), s.cell) for s in seeds]               # 経路に近い順
    while heap:
        _, c = heappop(heap)
        for n in grid.neighbours(c):
            if n in state or dist_to_path(n) > th.R_max_m: continue
            z_pred = state[c].z + local_slope(state, c) @ (n.center - c.center)   # 局所平面で予測
            d = grid.cell_m * hypot(*offset(c, n))
            cands = height_candidates(points, n, grid.cell_m)            # 格子内の点を高さで束ねた候補（複数）
            ok = [k for k in cands
                  if -th.down_band_m <= k.z - z_pred <= th.up_band_m          # 上下別の許容幅
                  and abs(k.z - z_pred) <= d * tan(th.theta_max_deg) + th.eps_m
                  and abs(k.z - state[c].z) <= th.step_max_m
                  and k.support >= th.min_support]
            if not ok:
                state[n] = Cell('undetermined', None, None, 0, None, 'new'); continue   # 空白は飛び越えない
            k = max(ok, key=lambda k: k.support)
            conf = state[c].conf * th.conf_decay
            if not consistent_with_path_ground(state, n, k.z, th.consistency_r): conf *= 0.5   # 経路側の地面との整合
            if conf < th.conf_min: state[n] = Cell('undetermined', k.z, None, conf, None, 'new'); continue
            state[n] = Cell('ground', k.z, refine_normal(state, n), conf, state[c].run, 'new')
            heappush(heap, (dist_to_path(n), n))
    return state
```

`height_candidates` は格子内の点を 0.1 m 刻みで束ね、各束の中央値と点数を候補にする。`local_slope` は信頼度 conf_min 以上の地面の格子だけで最小二乗の平面を更新する（重力方向の z を基準）。

### D. 下方の点・特殊な地形（M5・M7）

```python
def label_below(points, state, grid, reflect_band_m):
    # 地面の推定から外した点を、削除せずにラベルする
    for pt in points:
        g = state.get(grid.cell_of(pt))
        if g and g.state == 'ground' and pt.z < g.z - reflect_band_m:
            pt.label = 'below_ground'      # 反射候補 / 負の障害物（溝・段差下）。M7 で負の障害物の候補の格子にする
```

- 縁石の下・側溝: 拡張が届かなかった格子は「未確定」。走行可能にはしない（M7）。
- 多層（陸橋・スロープ）: submap ごとの判定で、通過の高さに近い層だけが地面になる。別の層は「未確定」か「非地面」。統合（M6）で層の違う判定が同じ格子に来た場合は、高さの差が step_max を超えるので「競合」として残し、走行可能にしない。
- 草地: 支持点の広がり（spread）と残差（rms）が大きい。残差が `grass_rms_m` を超える格子は地面でも信頼度を下げ、走行可能性は別の設定で決める（初期は不可）。
- 動的物体: 経路の真後ろ（§1-7）の点は支持点にも障害物にも使わない。

### E. 出力と統合（M6・M7）

格子ごとの出力: `state ∈ {ground, non_ground, undetermined, negative_obstacle}`、`z_ground`、`conf`、`run_id`（原図 ID + submap + 通過）、`method ∈ {new, legacy}`。

```python
def merge(cells_by_run, th):
    # 同じ格子に複数の走行の判定がある場合
    for cell, items in group_by_cell(cells_by_run):
        g = [i for i in items if i.state == 'ground']
        if len(g) >= 2 and (max(i.z for i in g) - min(i.z for i in g)) > th.step_max_m:
            yield cell, Cell('conflict', None, None, 0, [i.run for i in g], 'new')   # 層の食い違い: 走行可能にしない
        elif g:
            w = [i.conf for i in g]; yield cell, Cell('ground', weighted_median(g.z, w), None, 1 - prod(1 - c for c in w), [i.run for i in g], 'new')   # 確率的な統合（独立とみなす）
        else:
            yield cell, max(items, key=lambda i: i.conf)

def classify(cells, points, h_min_m, h_max_m, occupied_min_points, step_max_m):
    for cell in cells:
        if cell.state != 'ground': cell.traversable = False; continue      # 地面でない所は走行不可（未確定も）
        rel = [pt.z - cell.z for pt in points_in(cell)]
        n_obst = count(h_min_m <= r <= h_max_m for r in rel)             # 局所地面からの相対高さ
        cell.occupied = n_obst >= occupied_min_points
        cell.traversable = (not cell.occupied) and cell.conf >= th.conf_traversable and max_step_to_neighbours(cell) <= step_max_m
```

2 層の位置合わせは分類では直らない。3D 地図として使う場合の別の案（この設計の外）: (1) 原図を作り直す（LiDAR の途切れをなくす）、(2) GLIM の dump を offline で再最適化する（上流の offline viewer の loop closure。上流は改変しない）、(3) submap ごとの地面の高さの差を拘束に加えて submap の姿勢を再推定する（新しい設計。承認事項）。

### F. 検証（M8）

```python
def check_swept_space(occupancy, traj, footprint, h_max_m):
    # ロボットが通過した空間（通過時点の footprint）に障害物判定が出ていないか
    bad = [pose for pose in traj if any(occupancy[c] == OCCUPIED for c in footprint_cells(pose, footprint))]
    return len(bad) == 0, bad
```

## 4. パラメータ表（初期値は案。承認が要る）

| 設定 | 初期値（案） | 根拠 | 調整方法 |
|---|---|---|---|
| H_design | /config の取付高さ（1.015 m）＋ PRM-05（未確定） | 正本の値。二重加算しない | PRM-05 の実測で確定 |
| dH_max（H の補正の上限） | 0.15 m（PRM-05 未確定の間は 0.4 m） | 方針 B。分析では屋外の H が 0.82〜1.02 m、廊下 0.82〜1.19 m（傾き込み） | 実測で H の分布を見て狭める |
| r_in / r_out（輪状範囲） | 1.0 / 4.0 m | 1 m 以内は死角（DEC-099 で 1 m 以内の格子の 33 % にしか地面がない）。4 m を超えると傾きの影響（4 度で 0.28 m） | 死角の実測で r_in |
| exclude_rear（後方の除外） | 後方 0.5〜2.0 m、幅 1.0 m | 押す人 | 自律走行の地図作成では 0 |
| ransac.min_points / max_rms / max_tilt_deg / min_spread_m | 30 / 0.05 m / 15 度 / 0.5 m | 点の密度（屋外 774 点/m²、廊下 206）から 1 m² に数十点 | 密度の実測で |
| seed_r | 1.5 m | 起点の近傍。格子 0.5 m の 3×3 | — |
| theta_max_deg | 10 度（PRM-63） | 既存の設定 | DEC-098 |
| eps_m | 0.03 m | 点の誤差 | — |
| up_band_m / down_band_m | 0.20 / 0.10 m | 上は縁石（15〜20 cm）、下は点の誤差＋緩い下り | 縁石の実測 |
| step_max_m | 0.15 m | 障害物の下限 PRM-35 と同じ | DEC-098 |
| min_support | 3 点 | 0.1 m 格子では 1〜数点しかない（点の間隔 0.3 m）。格子は 0.5 m（PRM-62）で判定し 0.1 m の 2D 地図へ写す | 密度の実測 |
| R_max_m | 6 m | 傾きの影響と密度の低下 | 用途（costmap の幅）で |
| conf_decay / conf_min / conf_traversable | 0.95 / 0.3 / 0.5 | 6 m（12 格子）で 0.54 | 検証の指標で |
| consistency_r | 2.0 m | 経路側の地面との整合を見る距離 | — |
| revisit_xy_m / revisit_dt_s / stop_dist_m / interp_step_m | 1.5 m / 10 s / 0.05 m / 0.25 m | 分析の再通過の定義。停止の判定。格子の半分 | — |
| reflect_band_m | 0.3 m | 床の反射は 0.2 m 以上下 | — |
| grass_rms_m | 0.08 m | 草の高さの目安。未計測 | 草地の実測 |
| h_min_m / h_max_m | 0.05 m / 車高 0.95 m＋0.25 m | 方針 E。PRM-35・36 に相当（PRM-35 は 0.15 m を提案中。どちらにするか承認） | DEC-098 |

既存の PRM-33・34・38・62〜64 との関係: PRM-34（地面の帯）は「地面からの相対高さ < h_min」に置き換わる。PRM-62（格子）・63（傾き）・64（補う距離）は残る。新しい設定は正本に PRM として追加し、地図タブの入力欄に出す（値は承認が要る）。

## 5. 失敗モードとフォールバック

| 失敗 | 検出 | 扱い |
|---|---|---|
| 軌跡がない（traj_lidar.txt なし、stamp が照合できない） | M2: 照合率 < 0.9 | 原図全体を従来方式（M0）。manifest に `method: legacy, reason` |
| 補正の整合が取れない | M2: 残差 > tol（0.05 m） | その submap は従来方式 |
| H が求まらない（支持点不足・平面の傾き過大・候補の競合・上限への張り付き） | M3 | その通過は起点なし。submap の格子は「未確定」。manifest に理由 |
| 起点が 1 つも確定しない | M4 | 同上 |
| 拡張が届かない格子 | M5 | 「未確定」。走行不可 |
| 層の食い違い | M6 | 「競合」。走行不可 |
| 通過空間に障害物 | M8 | 変換は失敗（rev を公開しない）。地図タブに理由を表示 |
| 地図全体の傾き（G-MAP-TILT） | M3 の平面の法線が重力方向と一定の角度で傾く（submap 間で同じ向き） | 傾きの角度を manifest に記録。4 度までは局所平面で吸収。超えたら失敗 |
| PRM-05 未確定 | M1 | dH_max を広げる（0.4 m）。manifest に記録 |
| 変換時間が上限（新設の設定）を超える | M8 | 失敗（原図は保持） |

## 6. 検証計画

### 正解データ

1. **合成データ（単体試験）**: 平坦路、5 度の坂、3 度の横断勾配、縁石（上り・下り 0.15 m）、側溝（幅 0.3 m、深さ 0.3 m）、走行間の 1.8 m の高さずれ、陸橋（高さ 4 m の面）、草地（高さの散らばり 0.1 m）、床の反射（床の対称）、地面の欠測（2 m の穴）。各シナリオで格子ごとの正解（地面/非地面/走行可）を生成時に持つ。
2. **実機の原図**: VM の 2 回目、x86 の廊下・屋外。正解は (a) 通過空間（軌跡 × footprint）は走行可、(b) 人の記録（ゴミ箱の位置、縁石の位置）は障害物、(c) 壁は障害物。人に記録を依頼する項目: 走行経路の写真と、障害物の位置（出発点からの距離と左右）。
3. **将来**: 地図タブで人が格子を「地面/障害物」とラベルする機能（別の提案）。

### 指標（優先順）

1. 障害物を地面（走行可）と誤判定する率（最優先。合成データの正解と、人の記録の障害物で）。
2. 通過空間の障害物率（0 が合格）。
3. 未確定率、フォールバック率、H の補正量の分布（submap ごと）、経路上の地面の高さと起点の高さの誤差。

### 手順

- 単体試験（合成）→ 実機の 3 原図を分析用に再変換（地図データベースには登録しない）→ 指標を記録 → 人に図を提示 → 承認後に正本へ反映し、次の地図作成の自動変換で使う。

## 7. 承認していただきたいこと（個別）

1. この設計で実装を始めてよいか（単体試験と分析用の再変換まで。実車の設定への反映は別）。
2. §4 の新しい設定の追加と初期値。
3. PRM-05 が未確定の間の扱い（dH_max を 0.4 m に広げる案）。
4. h_min を 0.05 m にするか、PRM-35 の提案値 0.15 m にするか。
