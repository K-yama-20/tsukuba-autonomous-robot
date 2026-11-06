// Unit tests without ROS of src/call_back/lidar_status_info.h (patch 0001): which keys of a state push are kept, how
// their values are written, and the level. The pushes are written the way Livox-SDK2 c0796f0 writes them
// (LivoxLidarStateInfoToJson in sdk_core/command_handler/parse_lidar_state_info.cpp: rapidjson PrettyWriter, the same
// key names, value types and order). Addresses are from the documentation range 192.0.2.0/24 (RFC 5737); the serial
// number, MAC and product text are made up.
// Run by run_tests.sh.

#include <cstdint>
#include <cstdio>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include "call_back/lidar_status_info.h"
#include "rapidjson/prettywriter.h"

namespace {

using livox_ros::lidar_status::Level;
using livox_ros::lidar_status::LevelFromDiagStatus;
using livox_ros::lidar_status::Summarize;
using livox_ros::lidar_status::Summary;
using Values = std::vector<std::pair<std::string, std::string>>;
using Writer = rapidjson::PrettyWriter<rapidjson::StringBuffer>;

int g_checks = 0;
int g_failures = 0;

#define CHECK(cond)                                                       \
  do {                                                                    \
    ++g_checks;                                                           \
    if (!(cond)) {                                                        \
      ++g_failures;                                                       \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);         \
    }                                                                     \
  } while (0)

const char kSn[] = "TESTSN0000000001";
const char kProduct[] = "TEST-PRODUCT 2000/01/01";

void IpCfg(Writer& w, const char* key, const char* ip, unsigned dst, unsigned src) {
  w.Key(key);
  w.StartObject();
  w.Key("ip");
  w.String(ip);
  w.Key("dst_port");
  w.Uint(dst);
  w.Key("src_port");
  w.Uint(src);
  w.EndObject();
}

void UintArray(Writer& w, const char* key, const std::vector<uint32_t>& values) {
  w.Key(key);
  w.StartArray();
  for (uint32_t v : values) {
    w.Uint(v);
  }
  w.EndArray();
}

// status_code as the SDK writes it: the 32 bytes from the last to the first, in hex, separated by spaces.
std::string StatusCodeText() {
  uint8_t code[32] = {};
  code[31] = 0xab;
  code[0] = 0x01;
  std::ostringstream ss;
  for (int idx = 31; idx >= 0; --idx) {
    ss << std::hex << static_cast<uint32_t>(code[idx]);
    if (idx != 0) {
      ss << " ";
    }
  }
  return ss.str();
}

// A push with every key LivoxLidarStateInfoToJson can write, in its order. with_diag false leaves out lidar_diag_status.
std::string FullPush(bool with_diag, uint16_t diag) {
  rapidjson::StringBuffer buf;
  Writer w(buf);
  w.StartObject();
  w.Key("pcl_data_type");
  w.Uint(1);
  w.Key("pattern_mode");
  w.Uint(0);
  w.Key("dual_emit_en");
  w.Uint(0);
  w.Key("point_send_en");
  w.Uint(0);
  w.Key("lidar_ipcfg");
  w.StartObject();
  w.Key("lidar_ip");
  w.String("192.0.2.10");
  w.Key("lidar_subnet_mask");
  w.String("255.255.255.0");
  w.Key("lidar_gateway");
  w.String("192.0.2.1");
  w.EndObject();
  IpCfg(w, "state_info_host_ipcfg", "192.0.2.50", 56201, 56200);
  IpCfg(w, "ponitcloud_host_ipcfg", "192.0.2.50", 56301, 56300);  // the SDK's spelling
  IpCfg(w, "imu_host_ipcfg", "192.0.2.50", 56401, 56400);
  IpCfg(w, "ctl_host_ipcfg", "192.0.2.50", 56101, 56100);
  IpCfg(w, "log_host_ipcfg", "192.0.2.50", 56501, 56500);
  w.Key("vehicle_speed");
  w.Int(0);
  w.Key("environment_temp");
  w.Int(2500);
  w.Key("install_attitude");
  w.StartObject();
  w.Key("roll_deg");
  w.Double(0.0);
  w.Key("pitch_deg");
  w.Double(0.0);
  w.Key("yaw_deg");
  w.Double(0.0);
  w.Key("x_mm");
  w.Uint(0);
  w.Key("y_mm");
  w.Uint(0);
  w.Key("z_mm");
  w.Uint(0);
  w.EndObject();
  w.Key("fov_cfg_en");
  w.Uint(0);
  w.Key("detect_mode");
  w.Uint(0);
  w.Key("func_io_cfg");
  w.StartObject();
  w.Key("IN0");
  w.Uint(0);
  w.Key("IN1");
  w.Uint(0);
  w.Key("OUT0");
  w.Uint(0);
  w.Key("OUT1");
  w.Uint(0);
  w.EndObject();
  w.Key("work_tgt_mode");
  w.Uint(1);
  w.Key("imu_data_en");
  w.Uint(1);
  w.Key("ntp_server_ip");
  w.String("192.0.2.123");
  w.Key("sn");
  w.String(kSn);
  w.Key("product_info");
  w.String(kProduct);
  UintArray(w, "version_app", {1, 2, 3, 4});
  UintArray(w, "version_loader", {5, 6, 7, 8});
  UintArray(w, "version_hardware", {9, 10, 11, 12});
  UintArray(w, "mac", {2, 0, 0, 0, 0, 1});
  w.Key("cur_work_state");
  w.Uint(1);
  w.Key("core_temp");
  w.Int(4512);
  w.Key("powerup_cnt");
  w.Uint(37);
  w.Key("local_time_now");
  w.Uint64(1700000000123456789ULL);
  w.Key("last_sync_time");
  w.Uint64(18446744073709551615ULL);
  w.Key("time_offset");
  w.Int64(-1234567890123LL);
  w.Key("time_sync_type");
  w.Uint(0);
  w.Key("status_code");
  w.String(StatusCodeText().c_str());
  if (with_diag) {
    w.Key("lidar_diag_status");
    w.Uint(diag);
  }
  w.Key("lidar_flash_status");
  w.Uint(0);
  w.Key("FW_TYPE");
  w.Uint(1);
  UintArray(w, "hms_code", {0, 0, 0, 0, 0, 0, 0, 0});
  w.Key("ROI_Mode");
  w.Uint(0);
  w.EndObject();
  return buf.GetString();
}

std::string Find(const Values& values, const std::string& key) {
  for (const auto& kv : values) {
    if (kv.first == key) {
      return kv.second;
    }
  }
  return "<absent>";
}

void TestFullPushKeepsOnlyTheAllowedKeys() {
  const Summary s = Summarize(FullPush(true, 0).c_str());
  const Values expected = {
      {"cur_work_state", "1"},
      {"core_temp", "4512"},  // 0.01 degC, the integer as it is
      {"powerup_cnt", "37"},
      {"last_sync_time", "18446744073709551615"},
      {"time_offset", "-1234567890123"},
      {"time_sync_type", "0"},
      {"status_code", StatusCodeText()},  // the text, without JSON quotes
      {"lidar_diag_status", "0"},
      {"lidar_flash_status", "0"},
      {"FW_TYPE", "1"},
      {"hms_code", "[0,0,0,0,0,0,0,0]"},
      {"version_app", "[1,2,3,4]"},
      {"version_loader", "[5,6,7,8]"},
      {"version_hardware", "[9,10,11,12]"}};
  CHECK(s.values == expected);
  CHECK(s.level == Level::kOk);
  CHECK(StatusCodeText().substr(0, 5) == "ab 0 ");
  const std::set<std::string> allowed = {"cur_work_state", "core_temp", "powerup_cnt", "last_sync_time",
                                         "time_offset", "time_sync_type", "status_code", "lidar_diag_status",
                                         "lidar_flash_status", "FW_TYPE", "hms_code", "version_app",
                                         "version_loader", "version_hardware"};
  for (const auto& kv : s.values) {
    CHECK(allowed.count(kv.first) == 1);
    CHECK(kv.second.find("192.0.2.") == std::string::npos);
    CHECK(kv.second.find(kSn) == std::string::npos);
    CHECK(kv.second.find(kProduct) == std::string::npos);
    CHECK(kv.second.find('\n') == std::string::npos);
  }
  for (const char* key : {"sn", "mac", "product_info", "lidar_ipcfg", "state_info_host_ipcfg", "ponitcloud_host_ipcfg",
                          "imu_host_ipcfg", "ctl_host_ipcfg", "log_host_ipcfg", "ntp_server_ip", "local_time_now",
                          "install_attitude", "func_io_cfg", "environment_temp", "ROI_Mode", "pcl_data_type"}) {
    CHECK(Find(s.values, key) == "<absent>");
  }
}

void TestLevelOfEachModule() {
  CHECK(LevelFromDiagStatus(0x0000) == Level::kOk);
  // one module at a time: system (bits 0-3), scan (4-7), ranging (8-11), communication (12-15)
  for (unsigned shift = 0; shift < 16; shift += 4) {
    CHECK(LevelFromDiagStatus(static_cast<uint16_t>(1u << shift)) == Level::kWarn);
    CHECK(LevelFromDiagStatus(static_cast<uint16_t>(2u << shift)) == Level::kError);
    CHECK(LevelFromDiagStatus(static_cast<uint16_t>(3u << shift)) == Level::kError);  // safety_err
    CHECK(LevelFromDiagStatus(static_cast<uint16_t>(4u << shift)) == Level::kError);  // not defined by the protocol
    CHECK(LevelFromDiagStatus(static_cast<uint16_t>(0xFu << shift)) == Level::kError);
  }
  CHECK(LevelFromDiagStatus(0x1111) == Level::kWarn);   // all warning
  CHECK(LevelFromDiagStatus(0x0121) == Level::kError);  // the worst decides
  CHECK(LevelFromDiagStatus(0x3001) == Level::kError);
}

void TestLevelThroughThePush() {
  CHECK(Summarize(FullPush(true, 0x0000).c_str()).level == Level::kOk);
  CHECK(Summarize(FullPush(true, 0x0010).c_str()).level == Level::kWarn);
  CHECK(Summarize(FullPush(true, 0x0200).c_str()).level == Level::kError);
  CHECK(Summarize(FullPush(true, 0x3000).c_str()).level == Level::kError);
  CHECK(Find(Summarize(FullPush(true, 0x3000).c_str()).values, "lidar_diag_status") == "12288");
}

void TestNoDiagStatusIsStale() {
  const Summary s = Summarize(FullPush(false, 0).c_str());
  CHECK(s.level == Level::kStale);
  CHECK(Find(s.values, "lidar_diag_status") == "<absent>");
  CHECK(s.values.size() == 13);  // the other allowed keys are still there
  CHECK(Find(s.values, "core_temp") == "4512");
}

void TestUnusableDiagStatusIsStale() {
  CHECK(Summarize("{\"lidar_diag_status\": \"0\"}").level == Level::kStale);
  CHECK(Summarize("{\"lidar_diag_status\": -1}").level == Level::kStale);
  CHECK(Summarize("{\"lidar_diag_status\": 65536}").level == Level::kStale);
  CHECK(Summarize("{\"lidar_diag_status\": 1.5}").level == Level::kStale);
  CHECK(Summarize("{\"lidar_diag_status\": [0]}").level == Level::kStale);
  CHECK(Summarize("{\"lidar_diag_status\": 65535}").level == Level::kError);
}

void TestNotAJsonObject() {
  for (const char* info : {"", "not json", "[1,2]", "42", "{\"core_temp\": 1", "{} trailing"}) {
    const Summary s = Summarize(info);
    CHECK(s.level == Level::kStale);
    CHECK(s.values.empty());
  }
  const Summary s = Summarize(nullptr);
  CHECK(s.level == Level::kStale);
  CHECK(s.values.empty());
}

void TestValueText() {
  const Summary s = Summarize(
      "{\"hms_code\": [16777217, 0, 0, 0, 0, 0, 0, 4294967295], \"core_temp\": -1050, \"cur_work_state\": 3}");
  CHECK(Find(s.values, "hms_code") == "[16777217,0,0,0,0,0,0,4294967295]");
  CHECK(Find(s.values, "core_temp") == "-1050");
  CHECK(Find(s.values, "cur_work_state") == "3");
  CHECK(s.level == Level::kStale);
}

void TestOddValuesOfAllowedKeysAreLeftOut() {
  const Summary s = Summarize(
      "{\"core_temp\": {\"ip\": \"192.0.2.10\"}, \"hms_code\": [0, \"192.0.2.10\"], \"version_app\": [[1]],"
      " \"powerup_cnt\": null, \"FW_TYPE\": true, \"time_offset\": 12.5, \"lidar_flash_status\": 1e3,"
      " \"version_loader\": [1, 2.5], \"cur_work_state\": 1}");
  const Values expected = {{"cur_work_state", "1"}};
  CHECK(s.values == expected);
}

void TestOrderIsTheAllowedOrder() {
  const Summary s = Summarize("{\"hms_code\": [], \"sn\": \"x\", \"core_temp\": 1, \"cur_work_state\": 2}");
  const Values expected = {{"cur_work_state", "2"}, {"core_temp", "1"}, {"hms_code", "[]"}};
  CHECK(s.values == expected);
}

}  // namespace

int main() {
  TestFullPushKeepsOnlyTheAllowedKeys();
  TestLevelOfEachModule();
  TestLevelThroughThePush();
  TestNoDiagStatusIsStale();
  TestUnusableDiagStatusIsStale();
  TestNotAJsonObject();
  TestValueText();
  TestOddValuesOfAllowedKeysAreLeftOut();
  TestOrderIsTheAllowedOrder();
  std::printf("%d checks, %d failed\n", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
