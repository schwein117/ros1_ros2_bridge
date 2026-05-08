#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import signal

def main() -> int:
    parser = argparse.ArgumentParser(description="Run ROS1<->ROS2 bidirectional bridge")
    parser.add_argument("--ros2-setup", required=True, help="Path to ROS2 setup.bash")
    parser.add_argument("--ros1-setup", default="", help="Path to ROS1 setup.bash")
    parser.add_argument("--bridge-all-topics", default="false", choices=["true", "false"])

    # --- 关键修改点 ---
    # 使用 parse_known_args() 代替 parse_args()
    # 这会返回一个元组 (已知参数, 未知参数列表)
    args, unknown = parser.parse_known_args()
    
    # 可选：打印被忽略的参数，方便调试
    if unknown:
        print(f"[Runner] Ignoring unknown ROS arguments: {unknown}")
    # -----------------

    # 1. 检查文件是否存在
    if not os.path.isfile(args.ros2_setup):
        print(f"[Error] ROS2 setup file not found: {args.ros2_setup}", file=sys.stderr)
        return 2
    if args.ros1_setup and not os.path.isfile(args.ros1_setup):
        print(f"[Error] ROS1 setup file not found: {args.ros1_setup}", file=sys.stderr)
        return 2

    # 2. 构建命令
    script_content = ""
    if args.ros1_setup:
        script_content += f"source '{args.ros1_setup}' && "
    script_content += f"source '{args.ros2_setup}' && "
    
    bridge_cmd = ["ros2", "run", "ros1_bridge", "dynamic_bridge"]
    if args.bridge_all_topics == "true":
        bridge_cmd.append("--bridge-all-topics")
        
    script_content += "exec " + " ".join(bridge_cmd)

    print(f"[Runner] Starting bridge:\n{script_content}")

    # 3. 执行命令
    # 使用 shell=True 允许我们 source 环境变量
    process = subprocess.Popen(["bash", "-c", script_content])

    def _forward_signal(sig, _frame):
        if process.poll() is None:
            process.send_signal(sig)

    signal.signal(signal.SIGINT, _forward_signal)
    signal.signal(signal.SIGTERM, _forward_signal)

    return process.wait()

if __name__ == "__main__":
    sys.exit(main())