"""360-degree area scanner using YOLO detections."""

import asyncio
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from vision_msgs.msg import Detection2DArray


class Scanner:
    """Rotates the robot 360 degrees while collecting YOLO detections."""

    ROTATION_SPEED = 0.3       # rad/s
    ROTATION_DURATION = 22.0   # seconds (~360 degrees at 0.3 rad/s)
    COLLECT_INTERVAL = 0.5     # seconds between detection snapshots

    def __init__(self, node: Node):
        self.node = node
        self.cmd_vel_pub = node.create_publisher(Twist, '/cmd_vel', 10)
        self.detections = []
        self._latest_detections = []

        # Subscribe to YOLO detections
        self.det_sub = node.create_subscription(
            Detection2DArray,
            '/yolo/detections',
            self._detection_callback,
            10,
        )
        self.node.get_logger().info('Scanner initialized')

    def _detection_callback(self, msg: Detection2DArray):
        """Cache the latest YOLO detection results."""
        self._latest_detections = []
        for det in msg.detections:
            for result in det.results:
                self._latest_detections.append({
                    'class': result.hypothesis.class_id,
                    'score': result.hypothesis.score,
                })

    async def scan_area(self) -> list:
        """Perform 360-degree scan and return aggregated detections.

        Returns:
            list of dicts: [{"class": "person", "count": 2}, ...]
        """
        self.node.get_logger().info('Starting 360-degree area scan...')
        all_detections = {}

        # Rotation command
        twist = Twist()
        twist.angular.z = self.ROTATION_SPEED

        start_time = time.time()

        while (time.time() - start_time) < self.ROTATION_DURATION:
            # Publish rotation command
            self.cmd_vel_pub.publish(twist)

            # Collect current detections
            for det in self._latest_detections:
                cls = det['class']
                if cls not in all_detections:
                    all_detections[cls] = {'max_score': 0.0, 'count': 0}
                all_detections[cls]['count'] += 1
                all_detections[cls]['max_score'] = max(
                    all_detections[cls]['max_score'], det['score']
                )

            await asyncio.sleep(self.COLLECT_INTERVAL)

        # Stop rotation
        stop_twist = Twist()
        self.cmd_vel_pub.publish(stop_twist)

        # Aggregate results — report unique classes detected
        results = []
        for cls, info in all_detections.items():
            results.append({
                'class': cls,
                'count': max(1, info['count'] // 5),  # Deduplicate repeated frames
                'confidence': round(info['max_score'], 2),
            })

        self.node.get_logger().info(f'Scan complete. Detected: {results}')
        return results
