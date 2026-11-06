import rosbag2_py, sys, csv
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
bag, out = sys.argv[1], sys.argv[2]
r=rosbag2_py.SequentialReader(); r.open(rosbag2_py.StorageOptions(uri=bag,storage_id="mcap"),rosbag2_py.ConverterOptions("cdr","cdr"))
types={t.name:t.type for t in r.get_all_topics_and_types()}
r.set_filter(rosbag2_py.StorageFilter(topics=["/esp32/status","/sensors/imu/data"]))
fi=csv.writer(open(out+"/imu.csv","w")); fi.writerow(["t","ax","ay","az","gx","gy","gz","rx_t"])
fe=csv.writer(open(out+"/esp32.csv","w")); keys=["source","reason","manual_x_q10000","manual_y_q10000","applied_x_q10000","applied_y_q10000","target_x_mv","target_y_mv"]; fe.writerow(["t","rx_t"]+keys)
while r.has_next():
    t,d,ts=r.read_next(); m=deserialize_message(d,get_message(types[t]))
    if t=="/sensors/imu/data":
        s=m.header.stamp.sec+m.header.stamp.nanosec*1e-9; a=m.linear_acceleration; g=m.angular_velocity
        fi.writerow([f"{s:.6f}",a.x,a.y,a.z,g.x,g.y,g.z,f"{ts*1e-9:.6f}"])
    else:
        for st in m.status:
            v={kv.key:kv.value for kv in st.values}
            fe.writerow([f"{m.header.stamp.sec+m.header.stamp.nanosec*1e-9:.6f}",f"{ts*1e-9:.6f}"]+[v.get(k,"") for k in keys])
