# TALOS — Tactical Autonomous Locator & Observation System

> LLM 기반 자연어 지휘 재난 탐색 로봇 시뮬레이션

자연어 명령으로 재난 현장을 탐색하고, 생존자·화재·위험물을 탐지하여 보고하는 자율 로봇 시스템입니다.

## Overview

TALOS는 ROS 2 기반 TurtleBot3 시뮬레이션 환경에서 동작합니다. 사용자가 텍스트로 명령을 내리면 GPT-4o-mini가 이를 구조화된 미션으로 변환하고, Nav2 자율주행과 YOLOv8 객체 탐지를 결합하여 재난 현장을 탐색한 뒤 자연어로 상황을 보고합니다.

```
"왼쪽 방이랑 오른쪽 방 다 확인해줘"
        │
        ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  LLM Parser │────▶│ Action Dispatcher │────▶│  Navigator  │
│(GPT-4o-mini)│     │  (미션 시퀀서)     │     │  (Nav2)     │
└─────────────┘     └──────────────────┘     └──────┬──────┘
                            │                        │
                            ▼                        ▼
                    ┌──────────────┐         ┌─────────────┐
                    │   Reporter   │◀────────│   Scanner   │
                    │ (GPT 보고서) │         │ (YOLO 탐지) │
                    └──────────────┘         └─────────────┘
```

## Architecture

| 패키지 | 역할 |
|--------|------|
| `talos_gazebo` | 커스텀 재난 건물 Gazebo 월드 + 프록시 모델 (화재, 위험물) |
| `talos_bringup` | Launch 파일, Nav2/SLAM 설정, 웨이포인트 관리 |
| `talos_core` | 핵심 로직 — LLM 파서, 내비게이터, 스캐너, 리포터, 미션 노드 |
| `yolo_ros` | YOLOv8 ROS 2 래퍼 (외부 패키지) |

## Features

- **자연어 명령 해석**: 한국어/영어 텍스트 → GPT Function Calling → 구조화된 미션 스텝
- **자율 내비게이션**: Nav2 기반 웨이포인트 이동, 기지 복귀
- **객체 탐지**: YOLOv8 실시간 탐지 + HSV 색상 기반 화재/위험물 감지 + 360도 회전 스캔
- **상황 보고**: 탐지 결과를 GPT가 자연어 보고서로 생성
- **다중 방 순차 탐색**: 복합 명령 처리, 결과 누적, 종합 보고

## Tech Stack

- **Robot**: TurtleBot3 Waffle (시뮬레이션)
- **Simulation**: Gazebo Classic
- **Autonomy**: ROS 2 Humble + Nav2
- **Perception**: YOLOv8 via `yolo_ros`
- **Intelligence**: OpenAI GPT-4o-mini (Tool Calling)
- **SLAM**: slam_toolbox

## Quick Start

### Prerequisites

```bash
# ROS 2 Humble + TurtleBot3 + Nav2 + Gazebo 설치 완료 상태
export TURTLEBOT3_MODEL=waffle
export OPENAI_API_KEY=your-api-key-here
```

### Build

```bash
cd ~/jiyoon_workspace/talos_ws
colcon build --symlink-install
source install/setup.bash
```

### Run

```bash
# 터미널 1: 전체 시뮬레이션 실행 (Gazebo + Nav2 + YOLO)
ros2 launch talos_bringup simulation.launch.py

# 터미널 2: 미션 노드 실행
ros2 run talos_core mission_node
```

### 명령 예시

```
> 왼쪽 방 확인해줘
> 1층 전체 훑어봐
> 사람 있으면 알려주고, 위험물 보이면 바로 나와
```

## Project Structure

```
talos_ws/
├── src/
│   ├── talos_gazebo/           # Gazebo 월드 + 모델
│   │   ├── worlds/
│   │   │   └── disaster_building.world
│   │   ├── models/
│   │   │   ├── red_cylinder/   # 화재 프록시
│   │   │   └── orange_box/     # 위험물 프록시
│   │   └── launch/
│   │       └── gazebo.launch.py
│   │
│   ├── talos_bringup/          # Launch + 설정
│   │   ├── launch/
│   │   │   ├── simulation.launch.py
│   │   │   └── nav2.launch.py
│   │   ├── config/
│   │   │   ├── nav2_params.yaml
│   │   │   ├── waypoints.yaml
│   │   │   └── slam_params.yaml
│   │   └── maps/
│   │
│   ├── talos_core/             # 핵심 Python 노드
│   │   └── talos_core/
│   │       ├── llm_parser.py
│   │       ├── action_dispatcher.py
│   │       ├── navigator.py
│   │       ├── scanner.py
│   │       ├── report_generator.py
│   │       └── mission_node.py
│   │
│   └── yolo_ros/               # 외부 YOLO 패키지 (git clone)
│
├── README.md
└── .gitignore
```

## Demo Scenarios

| # | 시나리오 | 설명 |
|---|---------|------|
| 1 | 기본 탐색 | "왼쪽 방 가서 확인해줘" → 이동 → 스캔 → 보고 |
| 2 | 다중 방 탐색 | "1층 전체 훑어봐" → 순차 탐색 → 종합 보고 |
| 3 | 조건부 대응 | "사람 있으면 알려주고, 위험물 보이면 바로 나와" |

## Demo Video

[![TALOS Demo](https://img.shields.io/badge/YouTube-Demo-red)](https://youtu.be/YOUR_VIDEO_ID)

> 데모 영상 (비공개 링크): https://youtu.be/YOUR_VIDEO_ID

## Team

| 이름 | 역할 | 비고 |
|------|------|------|
| 김지윤 (Jiyoon Kim) | 전체 설계 및 구현 (1인 팀) | GitHub: [@horokkk](https://github.com/horokkk) |

Robot Programming — June 2026

## AI 도구 사용 내역

본 프로젝트에서 사용한 AI 도구는 다음과 같습니다:

| AI 도구 | 용도 | 사용 방식 |
|---------|------|----------|
| **OpenAI GPT-4o-mini** | 프로젝트 핵심 기능 | 자연어 명령 파싱 (Tool Calling), 상황 보고서 생성 |
| **Claude (Anthropic)** | 개발 보조 | 코드 작성/디버깅 지원, 발표 자료 제작 보조 |

- GPT-4o-mini는 시스템의 핵심 컴포넌트로, LLM Parser와 Report Generator에서 API를 통해 호출됩니다.
- Claude는 개발 과정에서 코드 작성, 디버깅, 발표 자료 제작에 보조적으로 활용했습니다.
- 전체 시스템 아키텍처 설계, ROS2 노드 구현, Gazebo 환경 구축은 직접 수행했습니다.

## References

- [ROS 2 Humble Documentation](https://docs.ros.org/en/humble/)
- [Nav2 (Navigation2)](https://nav2.org/)
- [Gazebo Classic](https://classic.gazebosim.org/)
- [TurtleBot3 Documentation](https://emanual.robotis.com/docs/en/platform/turtlebot3/overview/)
- [YOLOv8 (Ultralytics)](https://docs.ultralytics.com/)
- [OpenAI API — Tool Calling](https://platform.openai.com/docs/guides/function-calling)
- [slam_toolbox](https://github.com/SteveMacenski/slam_toolbox)

## GitHub

https://github.com/horokkk/TALOS

## License

MIT
