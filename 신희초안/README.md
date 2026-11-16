# TurtleBot3 PBL 팀 회의 자료

2026-11-16 월요일 회의용 · 2026-11-14 정리

Chieftain은 기존 주행 코드를 보유한 팀원의 별칭이다.

## 목적과 현재 구상

개인 개발 희망과 기존 기능 탐색을 팀이 검토할 수 있도록 묶었다. 여러 지점의 화재 위험 관련 점검·이상 재확인·모의 후속 대응을 연결하는 구상을 탐색한다. 배경은 실습실 1개와 산업 현장 10개를 유지하며 사용자·관측 대상·이동의 추가 가치를 보고 좁힌다. ① 웹의 업무·기록, ② PC의 로컬 작업공간·반복 분석, ③ 로봇 실행·수집·통신은 개인 희망이며 주제·임무·구현 범위는 팀 미결정이다.

**먼저 [00 회의 요약](00_MEETING_BRIEF.md)을 읽는다.** 팀 확정과 개인 희망을 구별할 때는 [08 결정 상태](08_DECISIONS_OPEN_QUESTIONS.md)를 확인한다. 개인 희망과 후보를 준비했으며 실제 범위와 구조는 팀과 함께 결정한다.

## 문서 선택 안내

회의 문서는 최상위에 평면 배치했다. 상세 연구 자료의 전달 사본만 research/에 둔다.

| 문서 | 역할·읽을 질문 |
| --- | --- |
| [00_MEETING_BRIEF](00_MEETING_BRIEF.md) | 회의에서 무엇을 먼저 설명하고 의견을 구할까? |
| [01_PROJECT_OVERVIEW](01_PROJECT_OVERVIEW.md) | 배경·장비·경험·현재 범위는 무엇인가? |
| [02_PBL_GOALS](02_PBL_GOALS.md) | 어떤 불편을 해결하고 중간 단계에서 무엇이 남는가? |
| [03_WEB](03_WEB.md) | ①의 화면·백엔드·공식 기록은 무엇을 맡을까? |
| [04_DESKTOP_APP](04_DESKTOP_APP.md) | ②에서 로컬 파일·계산·외부 도구를 어떻게 활용할까? |
| [05_SYSTEM_COMMUNICATION](05_SYSTEM_COMMUNICATION.md) | ③의 실행·수집·상태·중복·복구 책임은 무엇일까? |
| [06_INTERFACES_DEPLOYMENT](06_INTERFACES_DEPLOYMENT.md) | 무엇을 주고받고 어디서 실행·배포할까? |
| [07_FEATURE_CANDIDATES](07_FEATURE_CANDIDATES.md) | 기존 24개와 신규 25~27번의 의미·책임·최소 결과는 무엇인가? |
| [08_DECISIONS_OPEN_QUESTIONS](08_DECISIONS_OPEN_QUESTIONS.md) | 무엇이 희망·제안·미결정이며 원문 간 차이는 무엇인가? |
| [09_INDUSTRY_MEETING_BRIEF](09_INDUSTRY_MEETING_BRIEF.md) | 실습실 + 산업 현장 10개에서 어떤 업무·질문을 비교할까? |
| [10_INDUSTRY_FIRE_RESEARCH](10_INDUSTRY_FIRE_RESEARCH.md) | 화재 위험·실제 로봇 사례·통계의 근거와 확인 한계는 무엇인가? |
| [11_INDUSTRY_FEASIBILITY](11_INDUSTRY_FEASIBILITY.md) | 실습실·산업 모형의 관측 범위·추가 센서·첫 시험·완료 기준은 무엇인가? |
| [선택 부록 · 이전 주행 코드](appendix/driving_reference/README.md) | Chieftain의 코드 중심으로 진행하며 필요할 때 세부 값·처리 참고 |
| [research/README](research/README.md) | 어떤 상세 원본을 선택해 읽고 누락·링크를 확인할까? |

배경을 비교하려면 [09 실습실·산업 후보 요약](09_INDUSTRY_MEETING_BRIEF.md)을 읽는다. 10에는 산업 10개 원문의 논점·검증 근거를 보존하고, 11에는 실습실 자체의 문제와 산업 모형의 시험을 구분해 제시한다. 물류·제조 우선 검토는 과거 분석자의 의견이다. 월요일에는 희망·문제·시험 후보를 공유·탐색하고, 기술적 선택은 준비 정도에 맞춰 진행한다.

## 선택 부록의 위치

주행은 Chieftain의 기존 코드를 중심으로 진행할 가능성이 크다는 사용자 구상이다. [이전 주행 코드 부록](appendix/driving_reference/README.md)은 세부 값이나 구현을 찾아볼 때 선택해 읽는다. 채택 필요성은 현재 동작과 Chieftain의 판단을 기준으로 검토한다. 부록의 과거 설정·실행 의존성은 현재 PBL의 요구사항을 추가하는 근거로 사용하지 않는다.

## Claude Code·Codex에서 읽기

압축을 풀고 이 README가 있는 폴더를 작업 위치로 연다. README 다음에는 질문과 관련된 문서만 선택해 읽는다. 결정 상태의 기준 문서는 08이며, 상세 연구 원문은 필요할 때 검색한다. JetBot MINI는 활용을 기본 전제로 삼는 최신 사용자 설명을 따르고, 과거 연구의 조건부 참여 표현은 08과 대조한다. 과거 파일의 실습실 시나리오는 당시 검토 예시로 읽고, 현재의 11개 배경·화재 관련 목표·개인 희망은 00·02·08·09와 대조한다.

공통 짧은 지침은 [AGENTS.md](AGENTS.md)에 두고 [CLAUDE.md](CLAUDE.md)는 이를 가져온다. README·상세 기획서를 지침에 통째로 가져오지 않는다. Codex는 AGENTS.md를 지침으로 읽고, Claude Code는 CLAUDE.md의 상대경로 import를 지원한다. 로딩은 설치 버전·시작 위치·상위 지침·설정에 영향을 받으므로 새 세션에서 적용 내용을 확인한다. [Codex 공식 안내](https://developers.openai.com/codex/guides/agents-md/) · [Claude Code 공식 안내](https://code.claude.com/docs/en/memory)

질문 예시는 다음과 같다.

> README를 읽고 04·06·08을 중심으로 PC 앱의 첫 완료 범위를 검토해 줘. 필요할 때만 research 원문을 읽고, 다른 배치가 더 낫다면 근거와 함께 제안해 줘.

## 상태와 원본

개인 희망·사용자 조건, 분석자 제안, 팀 미결정을 구분한다. 기능 표의 책임·단계·시험 항목은 채택할 범위를 논의하기 위한 제안이다. 이 자료 정리에서 수행한 검수는 파일·링크·ZIP에 관한 검사이며 새 프로젝트의 환경 구축·실장비 연동 시험은 수행하지 않았다. Jazzy는 한 번 언급한 선택지로 두고 채택·보류·제외는 Chieftain과 Claude Code의 판단에 맡긴다. 실장비 성공·담당 배정·성능 수치를 새로 만들지 않았다. 중요한 상태 변경은 08에서 관리하고 다른 문서에서 참조한다.

작업공간 원본은 보존하고, 전달 사본에는 참고용 안내·오타 교정·경로 정리를 적용했다. 중복 개별안과 채용·강의·과거 코드 분석 보고서 6개는 전달 대상에서 제외했다. 오래된 표현은 08과 대조한다. 수정·제외와 점검 범위는 [링크 점검](research/LINK_AUDIT.md), 출처·해시는 [원본 목록](research/SOURCES.md)에서 확인한다.
