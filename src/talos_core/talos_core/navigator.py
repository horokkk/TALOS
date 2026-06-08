"""Nav2 NavigateToPose action client for waypoint-based navigation."""

import math

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
import yaml
from ament_index_python.packages import get_package_share_directory
import os


class Navigator:
    """Wraps Nav2 NavigateToPose to provide go_to(room_name) interface."""

    def __init__(self, node: Node):
        self.node = node
        self.nav_client = ActionClient(node, NavigateToPose, 'navigate_to_pose')
        self.waypoints = self._load_waypoints()
        self.node.get_logger().info(
            f'Navigator initialized with rooms: {list(self.waypoints.keys())}'
        )

    def _load_waypoints(self) -> dict:
        """Load room waypoints from waypoints.yaml."""
        try:
            pkg_path = get_package_share_directory('talos_bringup')
            yaml_path = os.path.join(pkg_path, 'config', 'waypoints.yaml')
        except Exception:
            # Fallback for development
            yaml_path = os.path.join(
                os.path.dirname(__file__),
                '..', '..', '..', 'talos_bringup', 'config', 'waypoints.yaml',
            )

        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)

        return data.get('rooms', {})

    def get_available_rooms(self) -> list:
        """Return list of available room names."""
        return list(self.waypoints.keys())

    async def go_to(self, room_name: str) -> dict:
        """Navigate to a named room. Returns result dict."""
        if room_name not in self.waypoints:
            return {
                'success': False,
                'room': room_name,
                'error': f'Unknown room: {room_name}. Available: {list(self.waypoints.keys())}',
            }

        wp = self.waypoints[room_name]
        self.node.get_logger().info(
            f'Navigating to {room_name} at ({wp["x"]}, {wp["y"]})'
        )

        # Wait for Nav2 action server
        if not self.nav_client.wait_for_server(timeout_sec=10.0):
            return {
                'success': False,
                'room': room_name,
                'error': 'Nav2 action server not available',
            }

        # Build goal
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self._make_pose(wp['x'], wp['y'], wp.get('yaw', 0.0))

        # Send goal
        send_goal_future = await self.nav_client.send_goal_async(goal_msg)

        if not send_goal_future.accepted:
            return {
                'success': False,
                'room': room_name,
                'error': 'Goal was rejected by Nav2',
            }

        self.node.get_logger().info(f'Goal accepted, navigating to {room_name}...')

        # Wait for result
        result_future = await send_goal_future.get_result_async()
        status = result_future.status

        if status == 4:  # SUCCEEDED
            self.node.get_logger().info(f'Arrived at {room_name}')
            return {'success': True, 'room': room_name}
        else:
            self.node.get_logger().warn(f'Navigation to {room_name} failed with status {status}')
            return {
                'success': False,
                'room': room_name,
                'error': f'Navigation failed with status {status}',
            }

    async def return_to_base(self) -> dict:
        """Navigate back to base position."""
        return await self.go_to('base')

    def _make_pose(self, x: float, y: float, yaw: float) -> PoseStamped:
        """Create PoseStamped from x, y, yaw."""
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.node.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0

        # Convert yaw to quaternion
        pose.pose.orientation.x = 0.0
        pose.pose.orientation.y = 0.0
        pose.pose.orientation.z = math.sin(yaw / 2.0)
        pose.pose.orientation.w = math.cos(yaw / 2.0)

        return pose
