import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # 获取功能包路径
    pkg_dir = get_package_share_directory('ros1_ros2_bridge')

    return LaunchDescription([
        # 1. 定义参数
        DeclareLaunchArgument(
            'ros2_setup',
            default_value='/opt/ros/foxy/setup.bash',
            description='Path to ROS 2 setup.bash'
        ),
        
        DeclareLaunchArgument(
            'ros1_setup',
            default_value='/opt/ros/noetic/setup.bash',
            description='Path to ROS 1 setup.bash'
        ),

        DeclareLaunchArgument(
            'bridge_all_topics',
            default_value='false',
            description='Enable --bridge-all-topics for dynamic_bridge'
        ),

        # 2. 定义节点
        # 注意：ROS 2 中没有 'type' 属性，只有 'executable'
        Node(
            package='ros1_ros2_bridge',
            executable='cmd_vel_bridge_runner.py',  # 对应 CMakeLists.txt 中安装的文件名
            name='ros1_ros2_dynamic_bridge',
            output='screen',
            arguments=[
                '--ros2-setup', LaunchConfiguration('ros2_setup'),
                '--ros1-setup', LaunchConfiguration('ros1_setup'),
                '--bridge-all-topics', LaunchConfiguration('bridge_all_topics')
            ]
        ),
    ])