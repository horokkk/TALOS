"""LLM-based natural language command parser using GPT-4o Function Calling."""

import json
import os

from openai import OpenAI


# Function schema for GPT Function Calling
MISSION_FUNCTION = {
    'name': 'execute_mission',
    'description': (
        'Execute a disaster search mission. Parse the user command into '
        'a sequence of action steps for the robot to follow.'
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'steps': {
                'type': 'array',
                'description': 'Ordered list of mission steps',
                'items': {
                    'type': 'object',
                    'properties': {
                        'action': {
                            'type': 'string',
                            'enum': ['go_to', 'scan_area', 'report', 'return_to_base'],
                            'description': 'Action primitive to execute',
                        },
                        'target': {
                            'type': 'string',
                            'description': 'Target room name (for go_to action)',
                        },
                        'detect': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': 'Object classes to look for during scan',
                        },
                        'on_detect': {
                            'type': 'string',
                            'enum': ['report', 'retreat', 'continue'],
                            'description': 'What to do when target object is detected',
                        },
                    },
                    'required': ['action'],
                },
            },
        },
        'required': ['steps'],
    },
}

SYSTEM_PROMPT = """\
당신은 재난 탐색 로봇 TALOS의 미션 플래너입니다.
사용자의 자연어 명령을 구조화된 미션 스텝으로 변환합니다.

사용 가능한 구역:
- office_a: 사무실 A (왼쪽)
- office_b: 사무실 B (오른쪽)
- hallway: 복도
- base: 건물 외부 기지 (시작 위치)

탐지 가능한 객체:
- person: 사람 (생존자/부상자)
- fire: 화재 (빨간 원통)
- hazmat: 위험물 (주황색 박스)

가능한 액션:
- go_to: 지정된 방으로 이동
- scan_area: 현재 위치에서 360도 스캔
- report: 지금까지의 탐지 결과 보고
- return_to_base: 기지로 복귀

규칙:
1. 방에 가서 확인 = go_to + scan_area
2. "전체" 또는 "다" = 모든 방 순차 탐색
3. 마지막에는 항상 report + return_to_base
4. on_detect가 "retreat"이면 해당 객체 발견 시 즉시 후퇴
"""


class LLMParser:
    """Parses natural language commands into structured mission steps."""

    def __init__(self):
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise RuntimeError(
                'OPENAI_API_KEY 환경변수가 설정되지 않았습니다. '
                'export OPENAI_API_KEY=your-key 로 설정하세요.'
            )
        self.client = OpenAI(api_key=api_key)

    def parse(self, user_command: str) -> list:
        """Parse user command into mission steps.

        Args:
            user_command: Natural language command (Korean or English)

        Returns:
            list of step dicts: [{"action": "go_to", "target": "room_left", ...}, ...]
        """
        response = self.client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': user_command},
            ],
            functions=[MISSION_FUNCTION],
            function_call={'name': 'execute_mission'},
            temperature=0.0,
        )

        # Extract function call arguments
        fn_call = response.choices[0].message.function_call
        if fn_call is None:
            return self._fallback_parse(user_command)

        try:
            args = json.loads(fn_call.arguments)
            steps = args.get('steps', [])
        except (json.JSONDecodeError, KeyError):
            return self._fallback_parse(user_command)

        return steps

    def _fallback_parse(self, command: str) -> list:
        """Simple keyword-based fallback if LLM parsing fails."""
        steps = []

        # Determine target rooms
        rooms = []
        if '전체' in command or '다' in command or '모든' in command or '훑' in command:
            rooms = ['office_a', 'hallway', 'office_b']
        elif 'a' in command.lower() or '왼' in command or 'A' in command:
            rooms = ['office_a']
        elif 'b' in command.lower() or '오른' in command or 'B' in command:
            rooms = ['office_b']
        elif '복도' in command or 'hall' in command.lower():
            rooms = ['hallway']
        else:
            rooms = ['office_a', 'hallway', 'office_b']

        # Determine on_detect behavior
        on_detect = 'report'
        if '나와' in command or '빠져' in command or '후퇴' in command or 'retreat' in command.lower():
            on_detect = 'retreat'

        # Build steps
        for room in rooms:
            steps.append({'action': 'go_to', 'target': room})
            steps.append({
                'action': 'scan_area',
                'detect': ['person', 'fire', 'hazmat'],
                'on_detect': on_detect,
            })

        steps.append({'action': 'report'})
        steps.append({'action': 'return_to_base'})

        return steps
