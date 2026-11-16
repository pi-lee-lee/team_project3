# 원본 사본 목록과 보존

원본 루트는 `project_ws`다. 아래 상대경로를 이어 붙인 파일을 `source/` 아래 같은 상대경로에 복사했다. 소스·설정·원래 README는 바이트 그대로 보존하여 줄 번호도 일치한다. 모델·서버·전체 실행 패키지는 [실행 범위](RUNNING.md)에서 확인한다.

| 원본 루트 아래 경로·사본 | 포함 이유 | SHA-256 |
| --- | --- | --- |
| [src/my_bot_fall/my_bot_fall/smooth_base.py](source/src/my_bot_fall/my_bot_fall/smooth_base.py) | AStarDriver와 지도·추종·속도 제어 원본 | `5c4bd3f36ecc06b1ea63ac29165e41e6dbbdcaf1015fc2cb4f82b01aae7f54de` |
| [src/my_bot_fall/my_bot_fall/fall_patrol.py](source/src/my_bot_fall/my_bot_fall/fall_patrol.py) | 실제로 실행되는 순찰·웹·사건 제어 원본 | `d39bb141da90add123d17fe433c994afc414343aa7a8c9782baae4006854023e` |
| [src/my_bot_fall/my_bot_fall/patrol_logic.py](source/src/my_bot_fall/my_bot_fall/patrol_logic.py) | 관찰·경고·해제 상태 전이. FallPatrol이 직접 import | `787d03c3aa4da8d620d015a6ec5494ce1d27c2e387baf461276755a299604f17` |
| [src/my_bot_fall/my_bot_fall/voice_link.py](source/src/my_bot_fall/my_bot_fall/voice_link.py) | 음성 요청·결과·사건 메모 연결. 음성 비활성화 시에도 import 필요 | `51346e840043a68e0e21f17732cc74390b549e4f51ab630562ee6b6a9ee87d2e` |
| [src/my_bot_fall/my_bot_fall/web_log.py](source/src/my_bot_fall/my_bot_fall/web_log.py) | 정지/경로 로그 집계와 비동기 HTTP 로그 전송. 직접 import | `38dd0fa3ebbca1a37260f69eced9c46f900ee71c0ad78cd15456ac2978881e6b` |
| [src/my_bot_fall/my_bot_fall/event_photo_overlay.py](source/src/my_bot_fall/my_bot_fall/event_photo_overlay.py) | 사건 사진 주석 함수. 직접 import | `d4cf86e09ce8055f54dc0a78293161b410da4f1c26f865d159465ca8b03975a5` |
| [src/my_bot_fall/my_bot_fall/__init__.py](source/src/my_bot_fall/my_bot_fall/__init__.py) | Python 패키지 배치 참고 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [src/my_bot_fall/setup.py](source/src/my_bot_fall/setup.py) | patrol 진입점·설치 파일·원래 패키지 구성 | `d8602664d1c63ab6268843731f9c913a2a6e4c5e06c0443b95d4ed815fa8b272` |
| [src/my_bot_fall/setup.cfg](source/src/my_bot_fall/setup.cfg) | ROS Python 실행 파일 설치 위치 | `28aec5ce561c9845236dfa489d40cfe1340048729d56ee560e6b57f0a62d4fb6` |
| [src/my_bot_fall/package.xml](source/src/my_bot_fall/package.xml) | ROS 의존성과 패키지 메타데이터 | `de4e7f09843d06ee3953469c74bc91547c57970225e7cd55f70e114006ed22c5` |
| [src/my_bot_fall/resource/my_bot_fall](source/src/my_bot_fall/resource/my_bot_fall) | ament 패키지 리소스 표식 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [src/my_bot_fall/README.md](source/src/my_bot_fall/README.md) | 원래 전체 환경의 실행·검증 범위 설명 | `6cf12c2f1cf0f8db13f91d42821847d8ac407028ab01b4ed9f6377ab77679001` |
| [src/my_bot_fall/config/params_robot.yaml](source/src/my_bot_fall/config/params_robot.yaml) | lying_detector의 영상·자세 설정 | `8ed50ba4a79887f4cca4ccb6ae0f65528d93bb6a690ec7186d6ab81c3d4f0ded` |
| [src/my_bot_fall/launch/tb3_localization_real.launch.py](source/src/my_bot_fall/launch/tb3_localization_real.launch.py) | 지도·AMCL·RViz와 외부 Nav2 설정 연결 | `a59ce92e42482809b4b30d98c15d16583c4355f6c6b9dd449adc3db739e6d9a7` |
| [src/maps/new_map.yaml](source/src/maps/new_map.yaml) | 지도 해상도·원점·이미지 참조 | `b97aee33fd639079ca17ccdafa1ff707e0cd5e5ca4436f0e96a71ad1ded4f34e` |
| [src/maps/new_map.pgm](source/src/maps/new_map.pgm) | 위 YAML이 참조하는 원래 지도 이미지 | `5e8d9e826f69748ac395c23f31d198612403d0a7150a99019ff1755dc4c75bbb` |
| [scripts/demo_launcher.py](source/scripts/demo_launcher.py) | 서버 PC/Pi 실행 배치와 실제 전달 인자 확인 | `49ddfb6e6f7bd6dadf67d19367610e2ce5bad7e7630a1932eb6536ee657fae18` |

## 문서 근거와 해석 범위

실기 결과의 근거인 docs/HANDOVER.md는 필요한 기록과 줄 번호를 EVIDENCE.md에 요약했다. 전체 인수인계·녹음·로그·사건 DB·개인 인증 파일은 이 묶음에 포함하지 않았다. 지도는 요청한 원본을 복사했다.

원문 README가 참조하는 전체 작업공간의 README·scripts/README·docs/HANDOVER 등은 원래 프로젝트에서 확인할 대상이다. 새 안내 문서의 링크는 이 묶음 안에서 탐색하도록 구성했다. setup.py의 모델·다른 엔트리포인트 참조도 원래 구성 그대로다.

원본 패키지 메타데이터에는 MIT가 기재되어 있다. 모델·외부 패키지·지도 등 자료별 재사용 조건은 채택할 때 별도로 확인한다. 저자별 기여나 상대 코드와의 성능 우열은 이번 조사에서 확정하지 않았다.
