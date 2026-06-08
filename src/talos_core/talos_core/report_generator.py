"""Generate natural language situation reports from detection results."""

import json
import os

from openai import OpenAI


REPORT_SYSTEM_PROMPT = """\
당신은 재난 현장 보고 전문가입니다.
로봇이 수집한 탐지 데이터를 바탕으로 간결하고 명확한 한국어 상황 보고서를 작성합니다.

보고서 형식:
1. 각 방별 탐지 결과 요약
2. 발견된 위험 요소 강조
3. 생존자 발견 시 구조 권고
4. 전체 상황 종합 평가

톤: 전문적이고 긴급한 군사/소방 보고 스타일
"""


class ReportGenerator:
    """Converts detection results into natural language reports via GPT."""

    def __init__(self):
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise RuntimeError('OPENAI_API_KEY 환경변수가 설정되지 않았습니다.')
        self.client = OpenAI(api_key=api_key)

    def generate(self, mission_results: list) -> str:
        """Generate a situation report from mission results.

        Args:
            mission_results: list of dicts like:
                [
                    {"room": "room_left", "detections": [{"class": "person", "count": 1}]},
                    {"room": "room_right", "detections": []},
                ]

        Returns:
            Natural language situation report string.
        """
        if not mission_results:
            return '탐색 완료: 탐지된 객체가 없습니다.'

        # Check if any detections at all
        has_detections = any(
            r.get('detections') for r in mission_results
        )

        if not has_detections:
            rooms = [r['room'] for r in mission_results]
            return f'탐색 완료: {", ".join(rooms)} 구역을 확인했으나 특이사항 없습니다.'

        # Use GPT for detailed report
        data_str = json.dumps(mission_results, ensure_ascii=False, indent=2)
        user_msg = f'다음 탐색 결과를 바탕으로 상황 보고서를 작성하세요:\n\n{data_str}'

        try:
            response = self.client.chat.completions.create(
                model='gpt-4o',
                messages=[
                    {'role': 'system', 'content': REPORT_SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_msg},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e:
            # Fallback to simple report
            return self._fallback_report(mission_results)

    def _fallback_report(self, mission_results: list) -> str:
        """Generate a simple report without GPT."""
        lines = ['=== 탐색 결과 보고 ===']

        room_names = {
            'office_a': '사무실 A',
            'office_b': '사무실 B',
            'server_room': '서버실',
            'hallway': '복도',
            'base': '건물 외부 기지',
        }

        for result in mission_results:
            room = room_names.get(result['room'], result['room'])
            detections = result.get('detections', [])

            if not detections:
                lines.append(f'  [{room}] 특이사항 없음')
            else:
                for det in detections:
                    cls_names = {
                        'person': '사람',
                        'fire': '화재',
                        'hazmat': '위험물',
                    }
                    cls = cls_names.get(det['class'], det['class'])
                    count = det.get('count', 1)
                    lines.append(f'  [{room}] {cls} {count}건 탐지')

        lines.append('=== 보고 종료 ===')
        return '\n'.join(lines)
