# 문서

| 분류 | 파일 | 내용 |
| --- | --- | --- |
| 아키텍처 | [architecture/system_architecture.svg](architecture/system_architecture.svg) | 구성도: 컨테이너 · Docker 네트워크 · MSA 서비스와 Spring Boot 내부 계층 · 서비스별 DB(옆 저장소) · 로봇 브리지(수평 연결) |
| | [architecture/system_cycle.svg](architecture/system_cycle.svg) | 시스템 사이클: 인증 · 점검 미션 · 사진 분석 · 판정·재점검 · 관제·조종 · 예외·복구를 번호 순서로(주기·시간은 코드 기준) |
| | `architecture/build_*.py` | 위 SVG 생성 스크립트(`svg.py` 공용): `python3 docs/architecture/build_architecture.py` · `build_cycle.py` |
| 계획 | [plan/ROADMAP.md](plan/ROADMAP.md) | 향후 프로젝트 계획: 1순위 analysis-service 소화기 AI 판독(구현 방식 · 데이터 · 단계 · 완료 기준) |
| 실행 안내 | [guide/RUNNING.md](guide/RUNNING.md) | 구성·폴더 구조·시험 시설과 지도·주행 설정·화면·알려진 한계 |
| | [guide/DOCKER_GUIDE.md](guide/DOCKER_GUIDE.md) | 설치부터 실행·초기화·문제 해결까지 단계별 안내(macOS·Linux·Windows PowerShell) |
| 스토리보드 | [storyboard/web_storyboard.svg](storyboard/web_storyboard.svg) | 화면 구조도·흐름도·화면 설계 |
| | [storyboard/web_screen_tree.svg](storyboard/web_screen_tree.svg) | 화면 트리 |
| | [storyboard/web_service_scenario.svg](storyboard/web_service_scenario.svg) | 가상 서비스 흐름 |
| | `storyboard/build_*.py` | 위 SVG 생성 스크립트: `python3 docs/storyboard/build_storyboard.py` 등 |

빠른 실행 명령만 보려면 저장소 루트의 [도커_실행.md](../도커_실행.md) 를 본다.
