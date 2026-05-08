#!/usr/bin/env python3
"""ROS 2 Foxy bridge from geometry_msgs/Twist to Unitree B2 sport requests.

The node subscribes to /cmd_vel and forwards velocity commands to the Unitree
ROS 2 interface used by unitree_ros2 / unitree_sdk2:

  topic: /api/sport/request
  msg:   unitree_api/msg/Request
  api:   1008 (Move)

The bridge keeps republishing the latest command at a fixed rate so B2 keeps
moving while navigation is actively sending commands, and it sends a zero
velocity command after a timeout to stop the robot safely.
"""

from __future__ import annotations

import json
import math
import os
import socket
from typing import List, Optional, Sequence, Tuple

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

try:
	from unitree_api.msg import Request
except ImportError as exc:  # pragma: no cover - runtime dependency guard
	raise ImportError(
		"Failed to import unitree_api.msg.Request. Source the Unitree ROS 2 "
		"environment built from unitree_ros2 before running this node."
	) from exc


DEFAULT_NETWORK_INTERFACE = "enp44s0"


def _available_interfaces() -> List[str]:
	try:
		return [name for _, name in socket.if_nameindex()]
	except OSError:
		return ["lo"]


def _pick_interface() -> str:
	preferred = os.environ.get("UNITREE_NETWORK_INTERFACE", "").strip() or DEFAULT_NETWORK_INTERFACE
	interfaces = _available_interfaces()
	if preferred and preferred in interfaces:
		return preferred

	for name in interfaces:
		if name != "lo":
			return name
	return "lo"


def _configure_cyclonedds_environment() -> str:
	"""Ensure CycloneDDS points at a real interface before rclpy initializes."""
	interfaces = _available_interfaces()
	requested = os.environ.get("UNITREE_NETWORK_INTERFACE", "").strip() or DEFAULT_NETWORK_INTERFACE

	if requested:
		if requested not in interfaces:
			raise RuntimeError(
				f"Requested network interface {requested!r} not found. "
				f"Available interfaces: {', '.join(interfaces)}"
			)
		selected = requested
	else:
		selected = _pick_interface()

	# Always overwrite stale CYCLONEDDS_URI to avoid startup failure due to old NIC names.
	os.environ["CYCLONEDDS_URI"] = (
		"<CycloneDDS><Domain><General><Interfaces>"
		f'<NetworkInterface name="{selected}" priority="default" multicast="default" />'
		"</Interfaces></General></Domain></CycloneDDS>"
	)
	os.environ["UNITREE_NETWORK_INTERFACE"] = selected
	print(f"[b2_cmd_vel_bridge] Using CycloneDDS interface: {selected}")
	return selected


class CmdVelToUnitreeBridge(Node):
	"""Convert /cmd_vel into Unitree B2 sport motion requests."""

	MOVE_API_ID = 1008

	def __init__(self) -> None:
		super().__init__("b2_cmd_vel_bridge")

		self.declare_parameter("cmd_vel_topic", "/cmd_vel")
		self.declare_parameter("unitree_request_topic", "/api/sport/request")
		self.declare_parameter("publish_rate_hz", 20.0)
		self.declare_parameter("command_timeout_s", 0.5)
		self.declare_parameter("max_linear_x", 0.5)
		self.declare_parameter("max_linear_y", 0.5)
		self.declare_parameter("max_angular_z", 1.0)
		self.declare_parameter("scale_linear_x", 1.0)
		self.declare_parameter("scale_linear_y", 1.0)
		self.declare_parameter("scale_angular_z", 1.0)
		self.declare_parameter("invert_linear_x", False)
		self.declare_parameter("invert_linear_y", False)
		self.declare_parameter("invert_angular_z", False)
		self.declare_parameter("publish_on_callback", True)

		self._cmd_vel_topic = self.get_parameter("cmd_vel_topic").value
		self._unitree_request_topic = self.get_parameter("unitree_request_topic").value
		self._publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)
		self._command_timeout_s = float(self.get_parameter("command_timeout_s").value)
		self._max_linear_x = float(self.get_parameter("max_linear_x").value)
		self._max_linear_y = float(self.get_parameter("max_linear_y").value)
		self._max_angular_z = float(self.get_parameter("max_angular_z").value)
		self._scale_linear_x = float(self.get_parameter("scale_linear_x").value)
		self._scale_linear_y = float(self.get_parameter("scale_linear_y").value)
		self._scale_angular_z = float(self.get_parameter("scale_angular_z").value)
		self._invert_linear_x = bool(self.get_parameter("invert_linear_x").value)
		self._invert_linear_y = bool(self.get_parameter("invert_linear_y").value)
		self._invert_angular_z = bool(self.get_parameter("invert_angular_z").value)
		self._publish_on_callback = bool(self.get_parameter("publish_on_callback").value)

		self._publisher = self.create_publisher(Request, self._unitree_request_topic, 10)
		self._subscription = self.create_subscription(
			Twist, self._cmd_vel_topic, self._cmd_vel_callback, 10
		)

		self._latest_cmd: Optional[Twist] = None
		self._latest_cmd_stamp = self.get_clock().now()
		self._last_published: Optional[Tuple[float, float, float]] = None

		timer_period_s = 1.0 / self._publish_rate_hz if self._publish_rate_hz > 0.0 else 0.05
		self._timer = self.create_timer(timer_period_s, self._timer_callback)

		self.get_logger().info(
			f"Bridging {self._cmd_vel_topic} -> {self._unitree_request_topic} "
			f"at {self._publish_rate_hz:.1f} Hz (timeout {self._command_timeout_s:.2f} s)"
		)
		self.get_logger().info(
			"Mapping Twist.linear.x/y and Twist.angular.z to Unitree Move(x, y, z)."
		)

	@staticmethod
	def _clamp(value: float, limit: float) -> float:
		if limit <= 0.0:
			return value
		return max(-limit, min(limit, value))

	def _transform_twist(self, twist: Twist) -> Tuple[float, float, float]:
		vx = float(twist.linear.x) * self._scale_linear_x
		vy = float(twist.linear.y) * self._scale_linear_y
		wz = float(twist.angular.z) * self._scale_angular_z

		if self._invert_linear_x:
			vx = -vx
		if self._invert_linear_y:
			vy = -vy
		if self._invert_angular_z:
			wz = -wz

		vx = self._clamp(vx, self._max_linear_x)
		vy = self._clamp(vy, self._max_linear_y)
		wz = self._clamp(wz, self._max_angular_z)

		return vx, vy, wz

	def _build_request(self, vx: float, vy: float, wz: float) -> Request:
		request = Request()
		request.header.identity.api_id = self.MOVE_API_ID
		request.parameter = json.dumps({"x": vx, "y": vy, "z": wz}, separators=(",", ":"))
		return request

	def _publish_velocity(self, vx: float, vy: float, wz: float) -> None:
		request = self._build_request(vx, vy, wz)
		self._publisher.publish(request)
		self._last_published = (vx, vy, wz)

	def _should_stop(self, now) -> bool:
		age_ns = (now - self._latest_cmd_stamp).nanoseconds
		return age_ns > int(self._command_timeout_s * 1e9)

	def _cmd_vel_callback(self, msg: Twist) -> None:
		if any(
			math.isnan(value) or math.isinf(value)
			for value in (msg.linear.x, msg.linear.y, msg.angular.z)
		):
			self.get_logger().warning("Ignoring invalid cmd_vel containing NaN or Inf.")
			return

		self._latest_cmd = msg
		self._latest_cmd_stamp = self.get_clock().now()

		if self._publish_on_callback:
			vx, vy, wz = self._transform_twist(msg)
			self._publish_velocity(vx, vy, wz)

	def _timer_callback(self) -> None:
		now = self.get_clock().now()

		if self._latest_cmd is None or self._should_stop(now):
			if self._last_published != (0.0, 0.0, 0.0):
				self._publish_velocity(0.0, 0.0, 0.0)
				self.get_logger().debug("Published stop command due to cmd_vel timeout.")
			return

		vx, vy, wz = self._transform_twist(self._latest_cmd)
		if self._last_published != (vx, vy, wz):
			self._publish_velocity(vx, vy, wz)

	def stop(self) -> None:
		self._publish_velocity(0.0, 0.0, 0.0)


def main(args: Optional[Sequence[str]] = None) -> None:
	try:
		_configure_cyclonedds_environment()
	except RuntimeError as exc:
		print(f"[b2_cmd_vel_bridge] {exc}")
		return

	rclpy.init(args=args)
	node = CmdVelToUnitreeBridge()

	try:
		rclpy.spin(node)
	except KeyboardInterrupt:
		pass
	finally:
		try:
			node.stop()
		finally:
			node.destroy_node()
			rclpy.shutdown()


if __name__ == "__main__":
	main()
