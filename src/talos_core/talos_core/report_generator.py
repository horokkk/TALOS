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
        if api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None

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
            return '미션 실패: 탐색을 수행하지 못했습니다.'

        # Check if ALL rooms were skipped (navigation failure)
        all_skipped = all(r.get('skipped', False) for r in mission_results)
        if all_skipped:
            rooms = [r.get('room', '?') for r in mission_results]
            return f'미션 실패: {", ".join(rooms)} 구역에 접근하지 못했습니다. 경로가 차단되었을 수 있습니다.'

        # Check if any detections at all
        has_detections = any(
            r.get('detections') for r in mission_results
        )

        if not has_detections:
            visited = [r['room'] for r in mission_results if not r.get('skipped')]
            skipped = [r.get('room', '?') for r in mission_results if r.get('skipped')]
            msg = f'탐색 완료: {", ".join(visited)} 구역을 확인했으나 특이사항 없습니다.'
            if skipped:
                msg += f' ({", ".join(skipped)} 구역은 접근 실패)'
            return msg

        if self.client is None:
            return self._fallback_report(mission_results)

        # Use GPT for detailed report
        data_str = json.dumps(mission_results, ensure_ascii=False, indent=2)
        user_msg = f'다음 탐색 결과를 바탕으로 상황 보고서를 작성하세요:\n\n{data_str}'

        try:
            response = self.client.chat.completions.create(
                model='gpt-4o-mini',
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
        """Generate a detailed report without GPT."""
        from datetime import datetime

        room_names = {
            'office_a': '사무실 A (서측)',
            'office_b': '사무실 B (북동측)',
            'server_room': '서버실',
            'hallway': 'L자 복도',
            'base': '건물 외부 기지',
        }

        cls_names = {
            'person': '생존자',
            'fire': '화재',
            'hazmat': '위험물질',
        }

        cls_emoji = {
            'person': '[생존자]',
            'fire': '[화재]',
            'hazmat': '[위험물]',
        }

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        lines = [
            f'{"=" * 50}',
            f'  TALOS 재난 현장 상황 보고서',
            f'  보고 시각: {timestamp}',
            f'  탐색 구역: {len(mission_results)}개 구역',
            f'{"=" * 50}',
            '',
        ]

        # Per-room details
        total_persons = 0
        total_fires = 0
        total_hazmats = 0
        alert_rooms = []

        for i, result in enumerate(mission_results):
            room = room_names.get(result['room'], result['room'])
            detections = result.get('detections', [])
            skipped = result.get('skipped', False)

            lines.append(f'[구역 {i + 1}] {room}')

            if skipped:
                lines.append(f'  - 접근 실패: 네비게이션 경로를 확보하지 못했습니다.')
            elif not detections:
                lines.append(f'  - 이상 징후 없음. 구조적 안전 확인.')
            else:
                for det in detections:
                    cls = det.get('class', 'unknown')
                    count = det.get('count', 1)
                    confidence = det.get('confidence', 0.0)
                    label = cls_names.get(cls, cls)
                    tag = cls_emoji.get(cls, f'[{cls}]')

                    if cls == 'person':
                        total_persons += count
                        lines.append(f'  - {tag} {label} {count}명 발견 (신뢰도 {confidence:.0%}) — 즉각 구조 필요')
                        alert_rooms.append((room, 'person', count))
                    elif cls == 'fire':
                        total_fires += count
                        lines.append(f'  - {tag} {label} 감지 {count}건 (신뢰도 {confidence:.0%}) — 진화 요청')
                        alert_rooms.append((room, 'fire', count))
                    elif cls == 'hazmat':
                        total_hazmats += count
                        lines.append(f'  - {tag} {label} 감지 {count}건 (신뢰도 {confidence:.0%}) — 접근 통제 권고')
                        alert_rooms.append((room, 'hazmat', count))
                    else:
                        lines.append(f'  - [{cls}] {count}건 탐지')

            lines.append('')

        # Summary
        lines.append(f'{"─" * 50}')
        lines.append(f'[종합 평가]')

        if not alert_rooms:
            lines.append(f'  전 구역 탐색 완료. 특이사항 없음.')
            lines.append(f'  건물 내 즉각적 위험 요소는 발견되지 않았습니다.')
        else:
            if total_persons > 0:
                lines.append(f'  - 생존자 총 {total_persons}명 확인. 긴급 구조대 투입이 필요합니다.')
            if total_fires > 0:
                lines.append(f'  - 화재 {total_fires}건 감지. 소방 진화팀 즉시 투입 요망.')
            if total_hazmats > 0:
                lines.append(f'  - 위험물질 {total_hazmats}건 확인. 해당 구역 접근 통제 및 HAZMAT 팀 요청.')

            lines.append('')
            lines.append(f'[우선 조치 대상]')
            for room, cls, count in alert_rooms:
                label = cls_names.get(cls, cls)
                lines.append(f'  → {room}: {label} {count}건')

        lines.append('')
        lines.append(f'  TALOS 탐색 로봇 — 보고 종료.')
        lines.append(f'{"=" * 50}')

        return '\n'.join(lines)
