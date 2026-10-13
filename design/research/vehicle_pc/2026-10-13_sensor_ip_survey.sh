#!/usr/bin/env bash
# センサの IP・接続の調査（工程5-3 実機試験の準備。DEC-080）。実車PC（Ubuntu）で人が実行する。
# 結果はこのファイルと同じ場所に 2026-10-13_sensor_ip_survey.txt として保存する:
#   bash design/research/vehicle_pc/2026-10-13_sensor_ip_survey.sh 2>&1 | tee design/research/vehicle_pc/2026-10-13_sensor_ip_survey.txt
# 設定は変えない（読み取りだけ）。sudo は tcpdump にだけ使う。過去の記載値（LiDAR 192.168.1.201、PC 192.168.1.100、UDP 2368、PTC 9347）は
# docs/gouda_runbook.md のもので、今回の現物で再確認する。IMU（ADIS16607-2）は USB シリアルで IP を持たない。
set -o pipefail
LAN="${LAN:-enx6c6e0754b24a}"     # 過去記録の USB-LAN。違う場合は LAN=<IF名> を付けて実行
echo "== date: $(date -Is)  host: $(hostname)  commit: $(git rev-parse --short HEAD 2>/dev/null)"
echo "== 1. インターフェースと IP"; ip -br link; ip -br addr
echo "== 2. NetworkManager の接続（LiDAR 用プロファイルが有線 IF に載っているか）"; nmcli -t device status; nmcli -t connection show
echo "== 3. 近傍テーブル（すでに通信したことがある機器）"; ip neigh
echo "== 4. LiDAR の UDP 受信を 10 秒待つ（送信元 IP = LiDAR、宛先 IP:port = LiDAR に設定された PC 宛先）"
sudo timeout 10 tcpdump -i "$LAN" -n -c 5 udp 2>&1 | tail -8
echo "== 5. 既知アドレスへの到達確認（応答がなければ IP が違う）"; ping -c 2 -W 1 192.168.1.201; (timeout 3 bash -c 'cat < /dev/null > /dev/tcp/192.168.1.201/9347' && echo "PTC 9347 open") || echo "PTC 9347 closed/unreachable"
echo "== 6. 同一 /24 の機器一覧（arp-scan か nmap があれば）"
if command -v arp-scan >/dev/null; then sudo arp-scan --interface="$LAN" --localnet; elif command -v nmap >/dev/null; then nmap -sn -n "$(ip -4 -o addr show "$LAN" | awk '{print $4}')"; else echo "arp-scan/nmap なし。4 の tcpdump の送信元 IP を使う"; fi
echo "== 7. IMU（USB シリアル）"; ls -l /dev/serial/by-id/ 2>&1; lsusb; dmesg 2>/dev/null | grep -i "tty\|cdc_acm\|ftdi\|usb" | tail -10
echo "== 8. ドライバの有無"; source /opt/ros/jazzy/setup.bash 2>/dev/null; ros2 pkg list 2>/dev/null | grep -i "hesai\|adi_\|imu" || echo "(ROS パッケージに hesai/adi が見つからない)"; ls -d ~/gouda_ws/src/*/ 2>/dev/null
echo "== done"
