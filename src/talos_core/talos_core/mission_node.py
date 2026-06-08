"""Main ROS 2 node — CLI input → LLM parse → dispatch → report."""

import asyncio
import threading

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor

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

        self.get_logger().info(
            f'사용 가능한 방: {self.navigator.get_available_rooms()}'
        )
        self.get_logger().info('명령을 입력하세요 (종료: quit/exit)')

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
            future.result(timeout=120.0)
        except TimeoutError:
            node.get_logger().error('미션 실행 시간 초과 (120초)')
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
