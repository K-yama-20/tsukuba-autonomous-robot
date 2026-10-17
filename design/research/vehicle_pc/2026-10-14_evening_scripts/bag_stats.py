"""Summary of an extracted rosbag (extract_bag.py output): IMU rate/gaps, LiDAR frame rate/gaps/partial frames, packet loss increments.
usage: python3 bag_stats.py <bag.npz> [...]"""
import sys, datetime, numpy as np
hms = lambda t: datetime.datetime.fromtimestamp(t).strftime('%H:%M:%S.%f')[:-4]
for b in sys.argv[1:]:
    d = np.load(b); imu, fr, loss = d['imu'], d['frames'], d['loss']
    print('=====', b)
    st, rt = imu[:, 0], imu[:, 1]; dt = np.diff(st)
    print(f'IMU {len(imu)} msgs {hms(st[0])}-{hms(st[-1])}: rate {len(st)/(st[-1]-st[0]):.2f} Hz, stamp gaps >0.05 s {np.sum(dt>0.05)}, max {dt.max():.3f} s, non-increasing {np.sum(dt<=0)}; |acc| median {np.median(np.linalg.norm(imu[:,5:8],axis=1)):.3f} m/s2')
    fs, frt, n, t0, t1 = fr.T; fdt = np.diff(fs); span = t1 - t0
    print(f'LiDAR {len(fr)} frames {hms(fs[0])}-{hms(fs[-1])}: rate {len(fs)/(fs[-1]-fs[0]):.2f} Hz, header gaps >0.15 s {np.sum(fdt>0.15)} (max {fdt.max():.2f} s); frames with fewer than 64000 points {np.sum(n<64000)} (63744 pts: {np.sum(n==63744)}); frame time span >0.15 s {np.sum(span>0.15)} (max {span.max():.2f} s)')
    for i in np.where(span > 0.15)[0]: print(f'   frame {hms(fs[i])}: {int(n[i])} points over {span[i]:.2f} s')
    lt, tot, lo = loss.T; dl = np.diff(lo)
    print(f'packet loss (/lidar_packets_loss, cumulative): packets {int(tot[-1])}, lost {int(lo[-1])}')
    for i in np.where(dl > 0)[0]: print(f'   {hms(lt[i+1])}: +{int(dl[i])} lost (cumulative packets {int(tot[i+1])}); a frame is 250 packets at 10 Hz')
