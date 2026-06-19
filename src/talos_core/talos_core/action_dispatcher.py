"""Dispatch parsed mission steps to action primitives."""

from rclpy.node import Node

from talos_core.navigator import Navigator
from talos_core.scanner import Scanner
from talos_core.report_generator import ReportGenerator


class ActionDispatcher:
    """Executes a sequence of mission steps using nav/scan/report primitives."""

    def __init__(self, node: Node, navigator: Navigator, scanner: Scanner):
        self.node = node
        self.navigator = navigator
        self.scanner = scanner
        self.report_generator = ReportGenerator()
        self.mission_results = []

    async def execute(self, steps: list) -> str:
        """Execute mission steps sequentially.

        Args:
            steps: list of step dicts from LLMParser
                [{"action": "go_to", "target": "room_left"}, ...]

        Returns:
            Final report string.
        """
        self.mission_results = []
        current_room = 'base'
        nav_failed = False

        self.node.get_logger().info(
            f'Executing mission with {len(steps)} steps'
        )

        for i, step in enumerate(steps):
            action = step.get('action')
            self.node.get_logger().info(
                f'Step {i + 1}/{len(steps)}: {action}'
            )

            if action == 'go_to':
                nav_failed = False
                result = await self._do_go_to(step)
                if result:
                    current_room = step.get('target', current_room)
                else:
                    nav_failed = True
                    self.node.get_logger().warn(
                        f'Navigation to {step.get("target")} failed, skipping scan...'
                    )

            elif action == 'scan_area':
                if nav_failed:
                    self.node.get_logger().info('Skipping scan — previous navigation failed')
                    self.mission_results.append({
                        'room': step.get('target', current_room),
                        'detections': [],
                        'skipped': True,
                    })
                    continue

                detections = await self._do_scan(step)
                self.mission_results.append({
                    'room': current_room,
                    'detections': detections,
                })

                # Check on_detect condition
                should_retreat = self._check_on_detect(step, detections)
                if should_retreat:
                    self.node.get_logger().warn(
                        'Retreat condition triggered! Returning to base.'
                    )
                    await self.navigator.return_to_base()
                    break

            elif action == 'report':
                pass  # Report is generated at the end

            elif action == 'return_to_base':
                if current_room != 'base':
                    await self.navigator.return_to_base()
                else:
                    self.node.get_logger().info('Already at base, skipping return.')

            else:
                self.node.get_logger().warn(f'Unknown action: {action}')

        # Generate final report
        report = self.report_generator.generate(self.mission_results)
        return report

    async def _do_go_to(self, step: dict) -> bool:
        """Execute go_to action. Returns True if successful."""
        target = step.get('target', '')
        if not target:
            self.node.get_logger().error('go_to step missing target')
            return False

        result = await self.navigator.go_to(target)
        return result.get('success', False)

    async def _do_scan(self, step: dict) -> list:
        """Execute scan_area action. Returns list of detections."""
        detections = await self.scanner.scan_area()
        return detections

    def _check_on_detect(self, step: dict, detections: list) -> bool:
        """Check if on_detect condition requires retreat.

        Returns True if robot should retreat.
        """
        on_detect = step.get('on_detect', 'report')
        if on_detect != 'retreat':
            return False

        # Check if any of the target objects were detected
        detect_targets = step.get('detect', [])
        for det in detections:
            if det.get('class') in detect_targets:
                return True

        return False
