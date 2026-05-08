# ros1_ros2_bridge

ROS1与ROS2双向话题桥接，用于宇树B2机器人导航系统集成

## 环境要求

- Ubuntu 20.04
- ROS1 Noetic
- ROS2 Foxy
- unitree_sdk2

---

## 安装步骤

### 1. 编译ros1_bridge

```bash
# 详见
https://github.com/ros2/ros1_bridge
```

### 2. 编译ros1_ros2_bridge

```bash
cd ~/ros1_ros2_bridge_ws
source /opt/ros/foxy/setup.bash

colcon build
```

---

## 使用方法

说明：导航系统在ROS1侧发布 `/cmd_vel`，宇树B2实际通过ROS2话题 `/api/sport/request` 控制运动。因此在启动桥接器前，需要先启动 `b2_cmd_vel_bridge.py`，将速度指令从 `/cmd_vel` 转换为宇树控制请求。

### 终端1（ros2环境）：启动宇树sdk（步骤略）和桥接器

```bash
source /opt/ros/foxy/setup.bash
source ~/ros1_ros2_bridge_ws/install/setup.bash

# 先启动话题转换（/cmd_vel -> /api/sport/request）
python3 b2_cmd_vel_bridge.py

# 再启动ROS1/ROS2桥接器
ros2 launch ros1_ros2_bridge ros1_ros2_bridge.launch.py
```

### 终端2（ros1环境）：启动导航节点

```bash
步骤略
```

---

## 验证

### ROS1发送数据到ROS2

ROS1终端：
```bash
rostopic pub /cmd_vel geometry_msgs/Twist '{linear: {x: 0.2}, angular: {z: 0.1}}' -r 10
```

ROS2终端：
```bash
ros2 topic echo /cmd_vel
```

---

## 故障排查

### 构建错误

检查是否安装了ros1_bridge：
```bash
ros2 pkg list | grep ros1_bridge
```

### 话题未桥接

确保同时激活ROS1和ROS2环境：
```bash
source /opt/ros/noetic/setup.bash
source /opt/ros/foxy/setup.bash
```

### B2无反应

检查话题是否正确发布：
```bash
ros2 topic list
ros2 topic info /cmd_vel
```
