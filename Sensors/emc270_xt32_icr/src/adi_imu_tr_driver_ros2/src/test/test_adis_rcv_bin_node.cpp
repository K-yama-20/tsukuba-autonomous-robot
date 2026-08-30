// Layer 3: ROS2 node integration tests for ImuNodeRcvBin.
// Gated by IMU_DEVICE environment variable (same as Layer 2).
// See doc/test_plan_gen2.md for the overall plan.

#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <cstdlib>
#include <future>
#include <memory>
#include <mutex>
#include <string>
#include <thread>

#include <adi_imu_tr_driver_ros2/srv/simple_cmd.hpp>
#include <diagnostic_msgs/msg/diagnostic_array.hpp>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <tf2_msgs/msg/tf_message.hpp>

#include "adis_rcv_bin.h"
#include "adis_rcv_bin_node.hpp"

using SimpleCmd = adi_imu_tr_driver_ros2::srv::SimpleCmd;
using namespace std::chrono_literals;

class AdisRcvBinNodeHwTest : public ::testing::Test
{
 protected:
  std::shared_ptr<ImuNodeRcvBin> node_;
  std::shared_ptr<rclcpp::Node> test_node_;
  std::unique_ptr<rclcpp::executors::MultiThreadedExecutor> exec_;
  std::thread spin_thread_;
  std::string device_;

  void SetUp() override
  {
    const char* env = std::getenv("IMU_DEVICE");
    if (env == nullptr || env[0] == '\0') {
      GTEST_SKIP() << "IMU_DEVICE not set; skipping node test.";
    }
    device_ = env;

    // Probe device before constructing the node. The node's Prepare()
    // retries Open() forever on failure, so we must verify openability
    // up front to avoid hangs.
    {
      AdisRcvBin probe;
      if (!probe.Open(device_)) {
        GTEST_SKIP() << "Cannot open " << device_ << "; check cable/permissions.";
      }
      probe.Close();
      std::this_thread::sleep_for(100ms);
    }

    rclcpp::init(0, nullptr);

    rclcpp::NodeOptions options;
    options.append_parameter_override("device", device_);

    node_ = std::make_shared<ImuNodeRcvBin>(options);
    test_node_ = std::make_shared<rclcpp::Node>("layer3_test_helper");

    exec_ = std::make_unique<rclcpp::executors::MultiThreadedExecutor>();
    exec_->add_node(node_);
    exec_->add_node(test_node_);
    spin_thread_ = std::thread([this]() { exec_->spin(); });
  }

  void TearDown() override
  {
    if (exec_) {
      exec_->cancel();
    }
    if (spin_thread_.joinable()) {
      spin_thread_.join();
    }
    node_.reset();
    test_node_.reset();
    exec_.reset();
    if (rclcpp::ok()) {
      rclcpp::shutdown();
    }
  }

  // Call /imu/cmd_srv synchronously and return the response.
  SimpleCmd::Response::SharedPtr CallCmd(const std::string& cmd,
                                          const std::vector<std::string>& args = {})
  {
    auto client = test_node_->create_client<SimpleCmd>("/imu/cmd_srv");
    if (!client->wait_for_service(2s)) {
      ADD_FAILURE() << "/imu/cmd_srv not available";
      return nullptr;
    }
    auto req = std::make_shared<SimpleCmd::Request>();
    req->cmd = cmd;
    req->args = args;
    auto future = client->async_send_request(req);
    if (future.wait_for(3s) != std::future_status::ready) {
      ADD_FAILURE() << "Service call timed out (cmd=" << cmd << ")";
      return nullptr;
    }
    return future.get();
  }
};

// /imu/data_raw が 1 秒で 50 メッセージ以上配信され、frame_id が "imu" であること
TEST_F(AdisRcvBinNodeHwTest, Node_PublishImuRaw)
{
  std::atomic<int> count{0};
  std::mutex mtx;
  sensor_msgs::msg::Imu last;

  auto sub = test_node_->create_subscription<sensor_msgs::msg::Imu>(
      "/imu/data_raw", 10, [&](sensor_msgs::msg::Imu::SharedPtr msg) {
        std::lock_guard<std::mutex> lk(mtx);
        last = *msg;
        count++;
      });

  std::this_thread::sleep_for(1s);

  EXPECT_GE(count.load(), 50) << "Too few /imu/data_raw messages in 1s: " << count.load();
  std::lock_guard<std::mutex> lk(mtx);
  EXPECT_EQ(last.header.frame_id, "imu");
}

// /tf の quaternion が /imu/data_raw の orientation と一致 (許容範囲内) すること
// — どちらも同じ PublishSample() 呼び出しで発行されるため、姿勢の整合性を確認する
TEST_F(AdisRcvBinNodeHwTest, Node_PublishTf)
{
  std::atomic<int> imu_count{0};
  std::atomic<int> tf_count{0};
  std::mutex mtx;
  double imu_q[4] = {0, 0, 0, 0};
  double tf_q[4] = {0, 0, 0, 0};

  auto imu_sub = test_node_->create_subscription<sensor_msgs::msg::Imu>(
      "/imu/data_raw", 10, [&](sensor_msgs::msg::Imu::SharedPtr msg) {
        std::lock_guard<std::mutex> lk(mtx);
        imu_q[0] = msg->orientation.w;
        imu_q[1] = msg->orientation.x;
        imu_q[2] = msg->orientation.y;
        imu_q[3] = msg->orientation.z;
        imu_count++;
      });

  auto tf_sub = test_node_->create_subscription<tf2_msgs::msg::TFMessage>(
      "/tf", 10, [&](tf2_msgs::msg::TFMessage::SharedPtr msg) {
        if (msg->transforms.empty()) return;
        std::lock_guard<std::mutex> lk(mtx);
        const auto& q = msg->transforms[0].transform.rotation;
        tf_q[0] = q.w; tf_q[1] = q.x; tf_q[2] = q.y; tf_q[3] = q.z;
        tf_count++;
      });

  std::this_thread::sleep_for(1s);

  EXPECT_GT(imu_count.load(), 0);
  EXPECT_GT(tf_count.load(), 0);

  // /tf and /imu/data_raw are published from the same PublishSample() call,
  // so the most recent snapshots should be close (not identical due to
  // independent subscriber callback timing).
  std::lock_guard<std::mutex> lk(mtx);
  EXPECT_NEAR(tf_q[0], imu_q[0], 0.1);
  EXPECT_NEAR(tf_q[1], imu_q[1], 0.1);
  EXPECT_NEAR(tf_q[2], imu_q[2], 0.1);
  EXPECT_NEAR(tf_q[3], imu_q[3], 0.1);
}

// /imu/cmd_srv に cmd="0x30" (NOP) を送ると is_ok=true で応答すること
TEST_F(AdisRcvBinNodeHwTest, Node_CmdSrvNop)
{
  auto res = CallCmd("0x30");
  ASSERT_NE(res, nullptr);
  EXPECT_TRUE(res->is_ok) << "msg: " << res->msg;
}

// /imu/cmd_srv に cmd="0x33" (姿勢リセット) を送ると is_ok=true で応答すること
TEST_F(AdisRcvBinNodeHwTest, Node_CmdSrvResetAttitude)
{
  auto res = CallCmd("0x33");
  ASSERT_NE(res, nullptr);
  EXPECT_TRUE(res->is_ok) << "msg: " << res->msg;
}

// hex として解釈できない文字列を送ると is_ok=false、エラーメッセージ付きで応答
TEST_F(AdisRcvBinNodeHwTest, Node_CmdSrvInvalidCmd)
{
  auto res = CallCmd("not_a_hex");
  ASSERT_NE(res, nullptr);
  EXPECT_FALSE(res->is_ok);
  EXPECT_FALSE(res->msg.empty());
}

// 空文字列の cmd を送ると is_ok=false、エラーメッセージ付きで応答
TEST_F(AdisRcvBinNodeHwTest, Node_CmdSrvEmptyCmd)
{
  auto res = CallCmd("");
  ASSERT_NE(res, nullptr);
  EXPECT_FALSE(res->is_ok);
  EXPECT_FALSE(res->msg.empty());
}

// データを正常受信中は /diagnostics に level=OK のメッセージが配信されること
TEST_F(AdisRcvBinNodeHwTest, Node_DiagnosticOk)
{
  std::atomic<int> count{0};
  std::mutex mtx;
  uint8_t last_level = 255;

  auto sub = test_node_->create_subscription<diagnostic_msgs::msg::DiagnosticArray>(
      "/diagnostics", 10, [&](diagnostic_msgs::msg::DiagnosticArray::SharedPtr msg) {
        if (msg->status.empty()) return;
        std::lock_guard<std::mutex> lk(mtx);
        last_level = msg->status[0].level;
        count++;
      });

  // diagnostic_updater publishes at 1 Hz by default; wait 3 s for confidence.
  std::this_thread::sleep_for(3s);

  EXPECT_GT(count.load(), 0) << "No /diagnostics messages received";
  std::lock_guard<std::mutex> lk(mtx);
  EXPECT_EQ(last_level, diagnostic_msgs::msg::DiagnosticStatus::OK);
}
