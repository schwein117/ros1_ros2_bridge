cmake_minimum_required(VERSION 3.5) # ROS 2 通常建议 3.5+
project(ros1_ros2_bridge)

# 寻找 ament_cmake 宏
find_package(ament_cmake REQUIRED)

# --- 安装 Python 脚本 ---
# 关键修改：ROS 2 的安装路径通常是 lib/<package_name>
install(PROGRAMS
  scripts/cmd_vel_bridge_runner.py
  DESTINATION lib/${PROJECT_NAME}
)

# --- 安装 Launch 文件 ---
install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

# 确保包被 ament 导出
ament_package()