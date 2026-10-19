<!-- 2026-10-18 に人が DEC-132 の回答の中に引用した調査結果の写し（原文のまま。AI は編集していない）。人の言葉は「DEC-132：次の調査結果が出ていることから、再検討してソフトウェア較正の可能性を探れ」。判断台帳 DEC-132。 -->
## 結論

- **ほぼすべてソフトウェアで推定（校正）できます。** 実測値を初期値（事前情報）とし、NDTの自己位置を基準にしたバッチ最小二乗で補正するのが標準的な方法です。
- 問題の構造はハンドアイキャリブレーションと同じです。「NDTで求めた`base_link`の姿勢」と「GNSSの観測値」を対応付けて、外部パラメータを解きます。
- ただし、**パラメータごとに推定に必要なロボットの運動が違います。** 必要な運動をしていないデータでは、そのパラメータは推定できません（他の量と区別できず、吸収されてしまう）。
- 以下の名称・数値はすべて参考値です。

## パラメータごとの推定可否

| パラメータ | 推定できるか | 必要な運動・観測 | 区別しにくい相手 |
|---|---|---|---|
| 主アンテナの水平位置（`ant_x`, `ant_y`） | ○ | Yawを大きく変える（8の字走行、左右両方向の旋回、その場旋回） | 直進だけだとT1の平行移動に吸収される |
| 主アンテナの高さ（`ant_z`） | △ | roll/pitchが変わる走行（傾斜区間） | 平地ではT1のzオフセットと区別できない |
| 取付Yaw（`mount_yaw_offset`） | ○ | GNSS方位とNDTのYawの比較（静止でも可） | T1のyaw（位置データから別に決めれば分離できる） |
| 基線のpitch/rollのずれ | ○ | 基線方向の傾きとIMUの傾きの比較 | IMUの取付誤差 |
| アンテナ間隔（基線長） | ○（受信機が推定） | 受信機がFix解から基線ベクトルを直接求める | ― |
| 時刻遅延（GNSSの遅れ） | ○ | 前進と後退、速度の変化 | 一方向に一定速度で走るだけだと`ant_x`と区別できない |

- **基線長**
  - アンテナ間の基線長は、受信機が搬送波位相からmm単位で求めています。巻尺による実測値より正確なことが多いです。
  - Fix中の基線長の長期平均を設定値として使い、実測値は初期値と誤Fix判定の基準にします。
  - 位相中心のずれは、同じ型番のアンテナをコネクタの向きを揃えて取り付ければ相殺されます。
- **高さ（`ant_z`）の影響は小さい**
  - 平地では推定できませんが、誤差はT1のzに吸収されるため実害はほとんどありません。
  - 例：高さに5cmの誤差があっても、5°の傾斜で生じる水平誤差は約4mmです。
- **基準になるのはNDTが出す`base_link`**
  - 推定されるのは「NDTが出力する`base_link`」から見たアンテナ位置です。
  - `base_link`→LiDARの外部パラメータに誤差があっても、その分も含めて吸収されます。
  - したがって、TFを変えたら校正をやり直します。

## 定式化（T1とT2を統合した同時推定）

- 推定する変数：( \theta, t ) （T1）、( l ) （レバーアーム）、( \psi_m ) （取付Yaw）、必要なら ( \Delta t ) （時刻遅延）
- 位置の残差
  [
  r^{pos}_i = R_z(\theta)\left(p^{map}_{base,i} + R^{map}_{base,i}\, l\right) + t - p^{enu}_{ant,i}
  ]
- 方位の残差
  [
  r^{yaw}_i = \mathrm{wrap}\left(\psi^{enu}_{gnss,i} - \psi^{map}_{base,i} - \theta - \psi_m\right)
  ]
- 事前情報（実測値）の残差
  [
  r^{prior} = \left( l - l_{meas},\ \psi_m - \psi_{m,meas} \right)
  ]
- 各残差をそれぞれの標準偏差で割って重みを揃え、Huber損失などのロバスト最小二乗で解きます。
- 事前情報を入れる効果
  - 観測できない方向（例：平地での`ant_z`）は実測値のまま残る
  - 推定結果が数値的に安定する
- **推定後の標準偏差を事前の標準偏差と比べる**と、データからその値がどれだけ決まったか（可観測性）を判定できます。

## データ取得の走行パターン（参考）

- 上空が開けた場所で、RTK Fixが続く状態で行います。
- 8の字走行（左右両方向の旋回を含む）：水平レバーアーム用
- その場旋回（差動駆動の場合）：水平レバーアームを効率よく推定できる
- 前進と後退、低速と高速：時刻遅延と`ant_x`を分けるため
- 静止区間を複数のYawで取る：取付Yaw用
- 傾斜区間（あれば）：`ant_z`用
- サンプル間の相関を抑えるため、一定距離ごと・一定時間ごとに間引きます（例：0.2s間隔、0.5m間隔）。

## 実装例（オフラインのバッチ校正）

- 入力は、時刻同期とRTK Fix・NDTスコアによる選別が済んだ配列を想定しています。
- `psi_enu`はENU定義（東を0、反時計回りが正）に変換済みの方位です。
- `th0`, `t0`には、前回のSVD位置合わせ（T1）の結果を初期値として与えます。

```python
# File: calib_gnss_extrinsics.py
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation as Rot

NAMES = ["theta", "tx", "ty", "tz", "ant_x", "ant_y", "ant_z", "mount_yaw"]


def rz(th):
    c, s = np.cos(th), np.sin(th)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def wrap(a):
    return np.arctan2(np.sin(a), np.cos(a))


def calibrate(p_base, R_base, p_enu, psi_enu,
              th0, t0, l_meas, psi_m_meas,
              sig_pos=0.02,
              sig_yaw=np.radians(0.3),
              sig_l_prior=(0.02, 0.02, 0.02),
              sig_psi_prior=np.radians(2.0)):
    """
    p_base : (N,3) NDTによるbase_link位置 [map]
    R_base : (N,3,3) NDTによるbase_link姿勢 [map]
    p_enu  : (N,3) 主アンテナ位置 [enu]
    psi_enu: (N,) GNSS方位（ENU定義）[rad]
    """
    yaw_base = Rot.from_matrix(R_base).as_euler("zyx")[:, 0]
    l_meas = np.asarray(l_meas, dtype=float)
    sig_l_prior = np.asarray(sig_l_prior, dtype=float)

    def fun(x):
        th, t, l, psi_m = x[0], x[1:4], x[4:7], x[7]
        p_ant_map = p_base + np.einsum("nij,j->ni", R_base, l)
        pred = p_ant_map @ rz(th).T + t
        r_pos = ((pred - p_enu) / sig_pos).ravel()
        r_yaw = wrap(psi_enu - yaw_base - th - psi_m) / sig_yaw
        r_prior = np.concatenate([
            (l - l_meas) / sig_l_prior,
            [wrap(psi_m - psi_m_meas) / sig_psi_prior],
        ])
        return np.concatenate([r_pos, r_yaw, r_prior])

    x0 = np.concatenate([[th0], t0, l_meas, [psi_m_meas]])
    res = least_squares(fun, x0, loss="huber", f_scale=3.0)

    # 残差を標準偏差で正規化しているため、(J^T J)^-1 を共分散の近似とする
    cov = np.linalg.inv(res.jac.T @ res.jac)
    std = np.sqrt(np.diag(cov))

    prior_std = {"ant_x": sig_l_prior[0], "ant_y": sig_l_prior[1],
                 "ant_z": sig_l_prior[2], "mount_yaw": sig_psi_prior}
    for name, val, s in zip(NAMES, res.x, std):
        note = ""
        if name in prior_std and s > 0.8 * prior_std[name]:
            note = "  <- データからほぼ決まっていない（運動不足の可能性）"
        if name in ("theta", "mount_yaw"):
            print(f"{name:10s} = {np.degrees(val):9.4f} deg  (std {np.degrees(s):.4f}){note}")
        else:
            print(f"{name:10s} = {val:9.4f} m    (std {s:.4f}){note}")

    return res.x, cov
```

- 拡張
  - 時刻遅延 ( \Delta t ) を変数に加え、NDTの姿勢を ( t_{gnss} - \Delta t ) で補間して評価します。前進と後退の両方のデータが必要です。
  - 基線のpitchのずれは、別の1次元問題として「GNSSが出す基線の傾き − IMUのpitch」の平均で求められます。
- サンプルどうしに相関が残っていると、標準偏差は実際より小さく出ます。判定にはある程度の余裕を持たせてください。

## 結果の検証

- **車体座標系で残差を見る**
  - 校正前の位置残差を`base_link`座標系に変換して平均すると、レバーアームの誤差がそのまま見えます。
  - 校正後にこの平均がほぼ0になれば合格です。
- **Yawに依存するパターンを見る**
  - 横軸をYawにして`enu`系の残差をプロットし、正弦波状のパターンが消えているかを確認します。
- **速度に依存するパターンを見る**
  - 進行方向の残差が速度に比例していれば、時刻遅延が残っています。
- **別の日のデータで検証する**
  - 校正に使っていない走行データで、残差のRMSが改善しているかを確認します。
- **実測値との差を確認する**
  - 推定値と実測値が、実測誤差よりはるかに大きく食い違う場合（例：5cm以上、5°以上）は、TFの定義（符号・軸・フレームの取り違え）を疑います。

## 注意点

- **NDT自体の誤差がそのまま混入する**
  - 特徴の少ない区間や、NDTのスコアが悪い区間は使いません。
  - 推定できる精度の目安：レバーアームは1cm程度、取付Yawは0.1°程度（参考値。環境とデータ量に依存）。
- **オンライン推定について**
  - EKFや因子グラフの状態にレバーアームを加えて逐次推定することもできます。
  - ただし、運動が足りない区間では推定値がふらつきます。オフラインのバッチ校正で値を確定させ、走行中は残差の監視だけにする方が安全です。
- **管理方法**
  - 校正結果は地図ファイル・TFと同じバージョンで管理します。
  - アンテナやLiDARを付け直したら、校正をやり直します。
