"""Evaluation helper (not product code) for autoware_ndt_scan_matcher + autoware_ekf_localizer: at the reference stamp >= start
time, take the reference LiDAR pose (TUM), convert it to the forward-facing evaluation base frame (R_lidar_base = Rz(yaw)),
optionally perturb it (dx, dy in the map frame, dyaw), optionally refine it with the NDT Monte Carlo service (ndt_align_srv),
publish it to the EKF initial pose topic, then activate the EKF and the NDT (trigger_node, SetBool true).
usage: python3 a3_init.py <ref_tum> <start_stamp> <dx> <dy> <dyaw_deg> <use_align 0|1> [base_yaw_in_lidar_deg=-99.2]"""
import sys, math, time, numpy as np, rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from geometry_msgs.msg import PoseWithCovarianceStamped
from std_srvs.srv import SetBool


def qmul(a, b):
    x1, y1, z1, w1 = a; x2, y2, z2, w2 = b
    return (w1*x2 + x1*w2 + y1*z2 - z1*y2, w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2, w1*w2 - x1*x2 - y1*y2 - z1*z2)


def main():
    a = sys.argv[1:]; ref, t0, dx, dy, dyaw, use_align = a[0], float(a[1]), float(a[2]), float(a[3]), float(a[4]), a[5] == '1'
    byaw = float(a[6]) if len(a) > 6 else -99.2
    rclpy.init(); n = Node('a3_init', parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)])
    T = np.loadtxt(ref); k = int(np.searchsorted(T[:, 0], t0)); r = T[k].copy()
    h = math.radians(byaw) / 2; q = qmul(tuple(r[4:8]), (0, 0, math.sin(h), math.cos(h)))      # base = lidar * Rz(byaw)
    h = math.radians(dyaw) / 2; q = qmul((0, 0, math.sin(h), math.cos(h)), q); r[1] += dx; r[2] += dy
    m = PoseWithCovarianceStamped(); m.header.frame_id = 'map'
    p = m.pose.pose; p.position.x, p.position.y, p.position.z = r[1:4]; p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w = q
    m.pose.covariance[0] = m.pose.covariance[7] = 0.25; m.pose.covariance[14] = 0.01; m.pose.covariance[21] = m.pose.covariance[28] = 0.01; m.pose.covariance[35] = 0.07
    while rclpy.ok() and n.get_clock().now().nanoseconds * 1e-9 < r[0] + 1.0:
        rclpy.spin_once(n, timeout_sec=0.05)
    now = n.get_clock().now(); m.header.stamp = now.to_msg()
    if use_align:
        from autoware_internal_localization_msgs.srv import PoseWithCovarianceStamped as AlignSrv
        cli = n.create_client(AlignSrv, '/ndt_align_srv'); cli.wait_for_service(timeout_sec=10.0)
        req = AlignSrv.Request(); req.pose_with_covariance = m
        fut = cli.call_async(req); rclpy.spin_until_future_complete(n, fut, timeout_sec=120.0)
        res = fut.result(); n.get_logger().info(f'ndt_align_srv: success={getattr(res, "success", None)}')
        if res is not None and getattr(res, 'success', False): m = res.pose_with_covariance; m.header.stamp = n.get_clock().now().to_msg()
    pub = n.create_publisher(PoseWithCovarianceStamped, '/initialpose3d', 1)
    for _ in range(10): rclpy.spin_once(n, timeout_sec=0.05)
    pub.publish(m); n.get_logger().info(f'initialpose3d at {r[0]:.3f} -> {m.pose.pose.position.x:.2f}, {m.pose.pose.position.y:.2f} (perturbation {dx}, {dy}, {dyaw} deg, align {use_align})')
    for srv in ('/ekf_trigger_node', '/ndt_trigger_node'):
        c = n.create_client(SetBool, srv); c.wait_for_service(timeout_sec=10.0)
        f = c.call_async(SetBool.Request(data=True)); rclpy.spin_until_future_complete(n, f, timeout_sec=10.0)
        n.get_logger().info(f'{srv}: {f.result()}')
    rclpy.spin(n)


if __name__ == '__main__':
    main()
