# 카메라 인식 모델 학습 (소화기 · 통로 적치물)

`OBJECT` 판독기의 `detector: 'model'` 자리에 넣을 YOLO 모델을 만든다.
압력계(`GAUGE` style `dial`)와 표시등(`LAMP`)은 영상 처리로 읽으므로 학습이 필요 없다.

```
① 사진 모으기 (WSL, capture.py)  →  ② 라벨링 (Roboflow)  →  ③ 학습 (Colab, train.py)  →  ④ 확인 (WSL, live_check.py)
        ↑                                                                                         │
        └──────────────────── 틀린 장면을 모아 다시 라벨링·재학습 ←─────────────────────────────┘
```

## 클래스

| 이름 | 뜻 | 쓰는 규칙 |
| --- | --- | --- |
| `fire_extinguisher` | 소화기 | 소화기 제자리(OBJECT, 있어야 함) |
| `obstacle` | 통로 적치물(상자 등) | 피난 통로 막힘(OBJECT `expect: ABSENT`) |

## 준비 (한 번만)

- 로봇: 라즈베리파이에서 카메라 노드 실행(`TurtleBot3_Jazzy_IMX219_카메라_설정_및_복구_기록.md` 2절)
- WSL `Ubuntu-24.04` (ROS 2 Jazzy, `ROS_DOMAIN_ID=99` 는 `.bashrc` 에 들어 있음)
- `live_check.py` 용 가상환경: `source ~/yolo_venv/bin/activate` (ultralytics CPU 판)

## ① 사진 모으기

노트북 화면에 소화기 사진을 띄워 로봇 카메라 앞에 둔다.

```bash
cd /mnt/c/Users/minsu/Documents/Academy/team_project3/web/python/analysis-service/training
python3 capture.py --tag 소화기A          # 스페이스=한 장, a=자동(0.5초마다), q=끝
python3 capture.py --tag 빈벽             # 대상이 없는 사진도 꼭 모은다(오탐 줄이기)
```

잘 모으는 법:
- **클래스마다 150~300장**. 소화기 사진을 여러 종류(빨강 분말, 하얀 CO2, 각도 다른 것) 바꿔 가며 찍는다.
- 로봇을 움직이거나 노트북을 옮겨 **거리(30cm~1.5m) · 각도(정면~45°) · 화면 안 위치**를 다양하게.
- 실제 시연 장소(미로 벽 앞)에서 찍는다. 조명도 시연 때와 같게.
- 노트북 화면 밝기는 최대, 반사(형광등 비침)가 덜한 각도로. 화면 줄무늬(모아레)가 보이면 거리를 조금 바꾼다.
- **대상 없는 사진(빈 벽, 노트북에 다른 그림)** 을 전체의 10~20% 넣는다.
- 적치물은 실제 상자를 통로에 놓고 찍어도 된다(노트북 화면보다 실물이 시연과 같다).

## ② 라벨링 (Roboflow, 무료)

1. roboflow.com 에서 프로젝트 만들기 → **Object Detection**
2. `~/dataset/raw` 사진 올리기 (Windows 에서는 `\\wsl$\Ubuntu-24.04\home\minsu\dataset\raw`)
3. 사진마다 상자를 그리고 클래스(`fire_extinguisher`, `obstacle`) 지정. 대상이 없는 사진은 **Null(빈 사진)** 로 표시
4. Generate → 나누기 Train 70 / Valid 20 / Test 10, 전처리 Resize 640 (늘리기 증강은 끄기: 학습 때 한다)
5. Export → 형식 **YOLOv8** → 받은 zip 또는 코드 조각(`rf.download`)

## ③ 학습 (Google Colab)

colab.research.google.com → 새 노트 → 런타임 유형 **T4 GPU** → 칸마다 실행:

```python
!pip install -q ultralytics roboflow
from roboflow import Roboflow                     # Roboflow Export 화면의 코드 조각을 그대로 붙여도 된다
rf = Roboflow(api_key="<내 키>")
ds = rf.workspace("<워크스페이스>").project("<프로젝트>").version(1).download("yolov8")
```
```python
# train.py 를 Colab 왼쪽 파일 창에 올린 뒤
!python train.py --data {ds.location}/data.yaml --epochs 60
```
```python
from google.colab import files
files.download('runs/detect/fire_check/weights/best.pt')
```

T4 에서 300장·60번 학습이 10분 안팎. 끝에 나오는 **mAP50 이 0.8 이상**이면 시연에 쓸 만하다.

## ④ 확인

받은 `best.pt` 를 WSL `~/models/` 에 둔다(`cp /mnt/c/Users/minsu/Downloads/best.pt ~/models/`).

```bash
source ~/yolo_venv/bin/activate
python live_check.py --model ~/models/best.pt
```

로봇 카메라 영상에 상자가 그려진다. **틀리게 잡거나 놓친 장면에서 스페이스** → `~/dataset/hard` 에 저장됨 →
② 로 올려 라벨링하고 버전 2로 다시 학습한다. 보통 이 과정을 2~3번 돌리면 안정된다.

## 다음 단계

`best.pt` 를 `analysis-service` 에 넣어 `OBJECT` `detector: 'model'` 이 이 모델로 판독하게 만든다
(서버 컨테이너 의존성 추가는 저장소 담당과 상의).
