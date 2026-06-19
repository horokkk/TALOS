"""Main ROS 2 node — CLI input → LLM parse → dispatch → report."""

import asyncio
import math
import threading
import time

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from geometry_msgs.msg import PoseWithCovarianceStamped

from talos_core.llm_parser import LLMParser
from talos_core.navigator import Navigator
from talos_core.scanner import Scanner
from talos_core.action_dispatcher import ActionDispatcher


class MissionNode(Node):
    """TALOS mission control node.

    Reads text commands from CLI, parses via LLM, executes mission,
    and prints situation reports.
    """

    def __init__(self):
        super().__init__('talos_mission_node')
        self.get_logger().info('=== TALOS Mission Node 시작 ===')

        # Initialize components
        self.llm_parser = LLMParser()
        self.navigator = Navigator(self)
        self.scanner = Scanner(self)
        self.dispatcher = ActionDispatcher(
            self, self.navigator, self.scanner
        )

        if self.llm_parser.client is None:
            self.get_logger().warn(
                'OPENAI_API_KEY 미설정 — 키워드 기반 파싱 모드로 동작합니다'
            )
        else:
            self.get_logger().info('LLM 파서 준비 완료 (GPT-4o-mini)')

        self.get_logger().info(
            f'사용 가능한 방: {self.navigator.get_available_rooms()}'
        )

        # Wait for Nav2 to be ready
        self.get_logger().info('Nav2 액션 서버 대기 중...')
        if self.navigator.nav_client.wait_for_server(timeout_sec=30.0):
            self.get_logger().info('Nav2 준비 완료!')
        else:
            self.get_logger().warn('Nav2 서버 응답 없음 — 계속 진행합니다')

        # Publish initial pose to match Gazebo spawn position
        self._publish_initial_pose()

        self.get_logger().info('명령을 입력하세요 (종료: quit/exit)')

    def _publish_initial_pose(self):
        """Set AMCL initial pose to match Gazebo spawn (0, -4.5, yaw=1.57)."""
        pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 10
        )
        time.sleep(1.0)  # Wait for publisher to connect

        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x = 0.0
        msg.pose.pose.position.y = -4.5
        msg.pose.pose.position.z = 0.0
        yaw = 1.57
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        msg.pose.covariance[0] = 0.25
        msg.pose.covariance[7] = 0.25
        msg.pose.covariance[35] = 0.07

        pub.publish(msg)
        self.get_logger().info('초기 위치 설정 완료: (0.0, -4.5, yaw=1.57)')

    async def run_mission(self, command: str):
        """Parse and execute a single mission command."""
        self.get_logger().info(f'명령 수신: "{command}"')

        # Step 1: Parse command via LLM
        self.get_logger().info('LLM 파싱 중...')
        try:
            steps = self.llm_parser.parse(command)
        except Exception as e:
            self.get_logger().error(f'LLM 파싱 실패: {e}')
            return

        self.get_logger().info(f'미션 스텝 {len(steps)}개 생성:')
        for i, step in enumerate(steps):
            self.get_logger().info(f'  [{i + 1}] {step}')

        # Step 2: Execute mission
        self.get_logger().info('미션 실행 시작...')
        try:
            report = await self.dispatcher.execute(steps)
        except Exception as e:
            self.get_logger().error(f'미션 실행 실패: {e}')
            return

        # Step 3: Print report
        self.get_logger().info('--- 상황 보고 ---')
        print('\n' + '=' * 50)
        print(report)
        print('=' * 50 + '\n')


def input_loop(node: MissionNode, loop: asyncio.AbstractEventLoop):
    """Run CLI input loop in a separate thread."""
    while rclpy.ok():
        try:
            command = input('\nTALOS> ')
        except (EOFError, KeyboardInterrupt):
            break

        command = command.strip()
        if not command:
            continue
        if command.lower() in ('quit', 'exit', 'q'):
            print('TALOS 종료...')
            rclpy.shutdown()
            break

        # Schedule mission on the event loop
        future = asyncio.run_coroutine_threadsafe(
            node.run_mission(command), loop
        )
        try:
            future.result(timeout=300.0)
        except TimeoutError:
            node.get_logger().error('미션 실행 시간 초과 (300초)')
        except Exception as e:
            node.get_logger().error(f'미션 실행 에러: {e}')


def main(args=None):
    rclpy.init(args=args)
    node = MissionNode()

    # Create async event loop for mission execution
    loop = asyncio.new_event_loop()

    # ROS executor in a thread
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    # Async event loop in a thread
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()

    # CLI input in main thread
    try:
        input_loop(node, loop)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
