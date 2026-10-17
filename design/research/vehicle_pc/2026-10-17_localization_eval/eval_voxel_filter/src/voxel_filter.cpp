// Evaluation helper (not Gouda product code): range crop + voxel-grid downsampling (x y z) of a PointCloud2, same header.
#include <pcl/filters/voxel_grid.h>
#include <pcl/point_types.h>
#include <pcl_conversions/pcl_conversions.h>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
class VoxelFilter : public rclcpp::Node {
 public:
  VoxelFilter() : Node("eval_voxel_filter") {
    leaf_ = declare_parameter("leaf_size", 0.5); rmin_ = declare_parameter("min_range", 1.0); rmax_ = declare_parameter("max_range", 100.0);
    pub_ = create_publisher<sensor_msgs::msg::PointCloud2>("output", rclcpp::SensorDataQoS());
    sub_ = create_subscription<sensor_msgs::msg::PointCloud2>("input", rclcpp::SensorDataQoS().keep_last(declare_parameter("input_depth", 10)),
      [this](sensor_msgs::msg::PointCloud2::ConstSharedPtr m) { cb(m); });
  }
 private:
  void cb(const sensor_msgs::msg::PointCloud2::ConstSharedPtr & m) {
    pcl::PointCloud<pcl::PointXYZ>::Ptr in(new pcl::PointCloud<pcl::PointXYZ>), crop(new pcl::PointCloud<pcl::PointXYZ>), out(new pcl::PointCloud<pcl::PointXYZ>);
    pcl::fromROSMsg(*m, *in);
    for (const auto & p : in->points) { const double r2 = p.x * p.x + p.y * p.y + p.z * p.z; if (std::isfinite(r2) && r2 >= rmin_ * rmin_ && r2 <= rmax_ * rmax_) crop->points.push_back(p); }
    crop->width = crop->points.size(); crop->height = 1;
    pcl::VoxelGrid<pcl::PointXYZ> vg; vg.setInputCloud(crop); vg.setLeafSize(leaf_, leaf_, leaf_); vg.filter(*out);
    sensor_msgs::msg::PointCloud2 o; pcl::toROSMsg(*out, o); o.header = m->header; pub_->publish(o);
    if (++n_ % 50 == 0) RCLCPP_INFO(get_logger(), "%zu -> %zu points", crop->points.size(), out->points.size());
  }
  double leaf_, rmin_, rmax_; size_t n_ = 0;
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr pub_;
  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr sub_;
};
int main(int argc, char ** argv) { rclcpp::init(argc, argv); rclcpp::spin(std::make_shared<VoxelFilter>()); rclcpp::shutdown(); return 0; }
