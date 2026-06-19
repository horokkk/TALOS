"""360-degree area scanner using YOLO detections + color-based fallback."""

import asyncio
import time

import numpy as np
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray


# HSV color ranges for fire (red) and hazmat (orange)
# Red wraps around hue=0, so we use two ranges
RED_LOWER_1 = np.array([0, 120, 100])
RED_UPPER_1 = np.array([10, 255, 255])
RED_LOWER_2 = np.array([170, 120, 100])
RED_UPPER_2 = np.array([180, 255, 255])
ORANGE_LOWER = np.array([11, 120, 100])
ORANGE_UPPER = np.array([25, 255, 255])

# Skin tone ranges for person detection (Gazebo person model)
SKIN_LOWER = np.array([5, 30, 80])
SKIN_UPPER = np.array([17, 170, 255])

# White clothing detection for Gazebo person_standing model
# Low saturation + high value = white (walls are gray = lower value)
WHITE_MAX_SAT = 40    # Saturation below this = desaturated (white/gray)
WHITE_MIN_VAL = 200   # Value above this = bright white (not gray wall)

# Minimum pixel ratio to count as a detection
COLOR_MIN_RATIO = 0.005
PERSON_MIN_RATIO = 0.003  # Lower threshold for person (smaller visual footprint)


class Scanner:
    """Rotates the robot 360 degrees while collecting YOLO + color detections."""

    ROTATION_SPEED = 0.3       # rad/s
    ROTATION_DURATION = 22.0   # seconds (~360 degrees at 0.3 rad/s)
    COLLECT_INTERVAL = 0.5     # seconds between detection snapshots

    def __init__(self, node: Node):
        self.node = node
        self.cmd_vel_pub = node.create_publisher(Twist, '/cmd_vel', 10)
        self._latest_detections = []
        self._latest_image = None

        # Subscribe to YOLO detections
        self.det_sub = node.create_subscription(
            Detection2DArray,
            '/yolo/detections',
            self._detection_callback,
            10,
        )

        # Subscribe to camera for color-based fallback
        self.img_sub = node.create_subscription(
            Image,
            '/camera/image_raw',
            self._image_callback,
            10,
        )

        self.node.get_logger().info('Scanner initialized (YOLO + color fallback)')

    def _detection_callback(self, msg: Detection2DArray):
        """Cache the latest YOLO detection results."""
        self._latest_detections = []
        for det in msg.detections:
            for result in det.results:
                self._latest_detections.append({
                    'class': result.hypothesis.class_id,
                    'score': result.hypothesis.score,
                })

    def _image_callback(self, msg: Image):
        """Cache the latest camera image for color analysis."""
        self._latest_image = msg

    def _detect_by_color(self) -> list:
        """Detect fire (red) and hazmat (orange) by color in the camera image."""
        if self._latest_image is None:
            return []

        msg = self._latest_image
        # Convert ROS Image to numpy (RGB8 or BGR8)
        height = msg.height
        width = msg.width
        if msg.encoding in ('rgb8', 'RGB8'):
            img = np.frombuffer(msg.data, dtype=np.uint8).reshape(height, width, 3)
        elif msg.encoding in ('bgr8', 'BGR8'):
            img = np.frombuffer(msg.data, dtype=np.uint8).reshape(height, width, 3)
            img = img[:, :, ::-1]  # BGR to RGB
        else:
            return []

        # Convert RGB to HSV manually (avoid cv2 dependency)
        img_float = img.astype(np.float32) / 255.0
        r, g, b = img_float[:, :, 0], img_float[:, :, 1], img_float[:, :, 2]
        cmax = np.maximum(np.maximum(r, g), b)
        cmin = np.minimum(np.minimum(r, g), b)
        diff = cmax - cmin

        # Hue
        h = np.zeros_like(cmax)
        mask_r = (cmax == r) & (diff > 0)
        mask_g = (cmax == g) & (diff > 0)
        mask_b = (cmax == b) & (diff > 0)
        h[mask_r] = (60 * ((g[mask_r] - b[mask_r]) / diff[mask_r]) + 360) % 360
        h[mask_g] = (60 * ((b[mask_g] - r[mask_g]) / diff[mask_g]) + 120) % 360
        h[mask_b] = (60 * ((r[mask_b] - g[mask_b]) / diff[mask_b]) + 240) % 360
        h = h / 2  # Scale to 0-180 range (OpenCV convention)

        # Saturation
        s = np.zeros_like(cmax)
        s[cmax > 0] = (diff[cmax > 0] / cmax[cmax > 0]) * 255

        # Value
        v = cmax * 255

        total_pixels = height * width
        results = []

        # Detect red (fire)
        red_mask_1 = (h >= RED_LOWER_1[0]) & (h <= RED_UPPER_1[0]) & \
                     (s >= RED_LOWER_1[1]) & (v >= RED_LOWER_1[2])
        red_mask_2 = (h >= RED_LOWER_2[0]) & (h <= RED_UPPER_2[0]) & \
                     (s >= RED_LOWER_2[1]) & (v >= RED_LOWER_2[2])
        red_ratio = (np.sum(red_mask_1) + np.sum(red_mask_2)) / total_pixels
        if red_ratio > COLOR_MIN_RATIO:
            results.append({'class': 'fire', 'score': min(red_ratio * 20, 0.95)})

        # Detect orange (hazmat)
        orange_mask = (h >= ORANGE_LOWER[0]) & (h <= ORANGE_UPPER[0]) & \
                      (s >= ORANGE_LOWER[1]) & (v >= ORANGE_LOWER[2])
        orange_ratio = np.sum(orange_mask) / total_pixels
        if orange_ratio > COLOR_MIN_RATIO:
            results.append({'class': 'hazmat', 'score': min(orange_ratio * 20, 0.95)})

        # Detect skin tone (person) — exclude pixels already counted as fire/orange
        skin_mask = (h >= SKIN_LOWER[0]) & (h <= SKIN_UPPER[0]) & \
                    (s >= SKIN_LOWER[1]) & (s <= SKIN_UPPER[1]) & \
                    (v >= SKIN_LOWER[2])
        skin_mask = skin_mask & ~red_mask_1 & ~red_mask_2 & ~orange_mask
        skin_ratio = np.sum(skin_mask) / total_pixels

        # Detect white clothing (Gazebo person_standing wears white shirt)
        # White = low saturation + high brightness (gray walls have lower brightness)
        white_mask = (s < WHITE_MAX_SAT) & (v > WHITE_MIN_VAL)
        white_mask = white_mask & ~red_mask_1 & ~red_mask_2 & ~orange_mask
        white_ratio = np.sum(white_mask) / total_pixels

        # Combine skin + white clothing for person detection
        person_ratio = skin_ratio + white_ratio
        if person_ratio > PERSON_MIN_RATIO:
            results.append({'class': 'person', 'score': min(person_ratio * 15, 0.90)})

        return results

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

            # Collect YOLO detections
            for det in self._latest_detections:
                cls = det['class']
                if cls not in all_detections:
                    all_detections[cls] = {'max_score': 0.0, 'count': 0}
                all_detections[cls]['count'] += 1
                all_detections[cls]['max_score'] = max(
                    all_detections[cls]['max_score'], det['score']
                )

            # Collect color-based detections
            for det in self._detect_by_color():
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

        # Aggregate results — each class detected = 1 per scan location
        # (color detection can only detect presence, not count individuals)
        results = []
        for cls, info in all_detections.items():
            results.append({
                'class': cls,
                'count': 1,
                'confidence': round(info['max_score'], 2),
            })

        self.node.get_logger().info(f'Scan complete. Detected: {results}')
        return results
