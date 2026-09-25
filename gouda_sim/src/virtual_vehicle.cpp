// Gazebo-only plant adapter. Reuses the production ESP32 arbitration Core.
#include "control.hpp"
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <std_srvs/srv/set_bool.hpp>
#include <nlohmann/json.hpp>
using Json=nlohmann::json;
class VirtualVehicle: public rclcpp::Node {
  gouda_usb::Core core{424242}; uint32_t seq=0; double last=0, v=0, w=0;
  bool pc_loss=false, bt_loss=false; int mx=0,my=0;
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr motor;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status,trace;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr drive,fault;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr manual;
  rclcpp::Service<std_srvs::srv::SetBool>::SharedPtr arm;
  rclcpp::TimerBase::SharedPtr timer;
  uint32_t ms(){return uint32_t(now().nanoseconds()/1000000);}
public:
  VirtualVehicle():Node("gouda_virtual_vehicle") {
    if(!get_parameter("use_sim_time").as_bool())throw std::runtime_error("Gazebo simulation clock required");
    const char* domain=std::getenv("ROS_DOMAIN_ID");
    if(!domain || std::string(domain)!="101")throw std::runtime_error("Simulation requires isolated ROS_DOMAIN_ID=101");
    declare_parameter("forward_gain",1.0);declare_parameter("yaw_gain",2.0);
    declare_parameter("response_tau",.15);declare_parameter("left_gain",.96);declare_parameter("right_gain",1.0);
    motor=create_publisher<geometry_msgs::msg::Twist>("/sim/cmd_vel",10);
    status=create_publisher<std_msgs::msg::String>("/esp32/status",10);
    trace=create_publisher<std_msgs::msg::String>("/gouda/control_trace",10);
    core.bluetooth_connected(0);core.bluetooth_report(0,0,0);
    drive=create_subscription<std_msgs::msg::String>("/gouda/control/drive",10,[this](std_msgs::msg::String::ConstSharedPtr msg){
      if(pc_loss)return;
      try{auto d=Json::parse(msg->data);double age=now().seconds()-d.at("issued_at").at("sec").get<double>()-d.at("issued_at").at("nanosec").get<double>()/1e9;
        if(age<-.05||age>.15)return;
        double f=d.at("forward_norm"),y=d.at("yaw_left_norm");if(!std::isfinite(f)||!std::isfinite(y)||std::abs(f)>1||std::abs(y)>1)return;
        core.receive(gouda_usb::make_command(core.boot_token(),++seq,ms(),{gouda_usb::quantize(-y),gouda_usb::quantize(f)}),ms());
      }catch(const Json::exception&){}
    });
    manual=create_subscription<geometry_msgs::msg::Twist>("/sim/manual",10,[this](geometry_msgs::msg::Twist::ConstSharedPtr msg){
      if(!std::isfinite(msg->linear.x)||!std::isfinite(msg->angular.z))return;
      mx=int(-std::clamp(msg->angular.z,-1.,1.)*511);my=int(-std::clamp(msg->linear.x,-1.,1.)*511);
    });
    fault=create_subscription<std_msgs::msg::String>("/sim/fault",10,[this](std_msgs::msg::String::ConstSharedPtr msg){
      try{auto d=Json::parse(msg->data);if(d.contains("pc_loss"))pc_loss=d["pc_loss"].get<bool>();if(d.contains("bt_loss"))bt_loss=d["bt_loss"].get<bool>();}catch(const Json::exception&){}
    });
    arm=create_service<std_srvs::srv::SetBool>("/gouda/arm",[this](const std_srvs::srv::SetBool::Request::SharedPtr req,std_srvs::srv::SetBool::Response::SharedPtr res){
      if(pc_loss){res->success=false;return;}
      if(req->data)core.receive(gouda_usb::make_command(core.boot_token(),++seq,ms(),{0,0}),ms());
      res->success=core.receive(gouda_usb::make_control(req->data?gouda_usb::Arm:gouda_usb::Disarm,core.boot_token(),++seq,ms()),ms());
      res->message="Simulated MCU; no USB device";
    });
    timer=create_wall_timer(std::chrono::milliseconds(10),[this]{tick();});
  }
  void tick(){
    double t=now().seconds();if(t<=last)return;double dt=std::min(.05,t-last);last=t;
    if(!bt_loss)core.bluetooth_report(mx,my,ms());
    auto a=core.output(ms());auto s=core.status(ms());
    double vf=a.value.forward*get_parameter("forward_gain").as_double();
    double wf=-a.value.right*get_parameter("yaw_gain").as_double();
    // Explicit hypothetical wheel gain asymmetry; not measured chair dynamics.
    double vl=(vf-.275*wf)*get_parameter("left_gain").as_double();
    double vr=(vf+.275*wf)*get_parameter("right_gain").as_double();
    double alpha=1-std::exp(-dt/std::max(.001,get_parameter("response_tau").as_double()));
    v+=alpha*((vl+vr)/2-v);w+=alpha*((vr-vl)/.55-w);
    geometry_msgs::msg::Twist output;output.linear.x=v;output.angular.z=w;motor->publish(output);
    Json d={{"simulation",true},{"boot_token",core.boot_token()},{"owner",s.owner},{"reason",s.reason},
      {"connected",bool(s.flags&1)},{"fresh",bool(s.flags&2)},{"centered",bool(s.flags&4)},{"auto_enabled",bool(s.flags&8)},
      {"applied_forward_norm",s.applied_forward/1000.},{"applied_right_norm",s.applied_right/1000.},
      {"manual_forward_norm",s.manual_forward/1000.},{"manual_right_norm",s.manual_right/1000.},
      {"device_monotonic_ms",ms()},{"requested_mv_x",s.requested_mv_x},{"requested_mv_y",s.requested_mv_y},
      {"simulated_actual_v",v},{"simulated_actual_w",w},{"stamp_sec",t}};
    std_msgs::msg::String msg;msg.data=d.dump();status->publish(msg);trace->publish(msg);
  }
};
int main(int argc,char**argv){rclcpp::init(argc,argv);rclcpp::spin(std::make_shared<VirtualVehicle>());rclcpp::shutdown();}
