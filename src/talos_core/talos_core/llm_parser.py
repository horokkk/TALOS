"""LLM-based natural language command parser using OpenAI tool calling."""

import json
import os

from openai import OpenAI


# Tool schema for OpenAI tool calling
MISSION_TOOL = {
    'type': 'function',
    'function': {
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
    },
}

SYSTEM_PROMPT = """\
당신은 재난 탐색 로봇 TALOS의 미션 플래너입니다.
사용자의 자연어 명령을 구조화된 미션 스텝으로 변환합니다.

사용 가능한 구역 (target 값은 반드시 아래 영어 이름만 사용):
- office_a: 사무실 A. 건물 왼쪽(서쪽)에 위치. "왼쪽 방", "왼쪽 사무실", "A사무실"이라고 하면 여기.
- office_b: 사무실 B. 건물 오른쪽 위(북동쪽)에 위치. "오른쪽 방", "오른쪽 사무실", "B사무실"이라고 하면 여기.
- server_room: 서버실. 건물 중앙 위쪽에 위치한 좁은 방. "서버실", "서버"라고 하면 여기.
- hallway: L자 복도. 건물 중앙과 아래쪽을 연결. "복도", "홀", "밑", "아래"라고 하면 여기.
- base: 건물 외부 기지 (시작 위치). "기지", "출발점"이라고 하면 여기.

중요: "왼쪽 방" = office_a, "오른쪽 방" = office_b. 절대 서버실이 아님!

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
2. "전체" 또는 "다" = 모든 방 순차 탐색 (hallway → office_a → server_room → office_b 순서)
3. 마지막에는 항상 report + return_to_base
4. on_detect가 "retreat"이면 해당 객체 발견 시 즉시 후퇴
"""


class LLMParser:
    """Parses natural language commands into structured mission steps."""

    def __init__(self):
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None

    def parse(self, user_command: str) -> list:
        """Parse user command into mission steps.

        Args:
            user_command: Natural language command (Korean or English)

        Returns:
            list of step dicts: [{"action": "go_to", "target": "room_left", ...}, ...]
        """
        if self.client is None:
            return self._fallback_parse(user_command)

        response = self.client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': user_command},
            ],
            tools=[MISSION_TOOL],
            tool_choice={'type': 'function', 'function': {'name': 'execute_mission'}},
            temperature=0.0,
        )

        # Extract tool call arguments
        tool_calls = response.choices[0].message.tool_calls
        if not tool_calls:
            return self._fallback_parse(user_command)

        try:
            args = json.loads(tool_calls[0].function.arguments)
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
            rooms = ['hallway', 'office_a', 'server_room', 'office_b']
        elif 'a' in command.lower() or '왼' in command or 'A' in command:
            rooms = ['office_a']
        elif 'b' in command.lower() or '오른' in command or 'B' in command:
            rooms = ['office_b']
        elif '서버' in command or 'server' in command.lower():
            rooms = ['server_room']
        elif '복도' in command or 'hall' in command.lower():
            rooms = ['hallway']
        else:
            rooms = ['hallway', 'office_a', 'server_room', 'office_b']

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
