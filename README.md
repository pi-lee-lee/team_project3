# team_project3

## 보유 하드웨어 제원

| 플랫폼 | 연산 보드 | 구동부 | 센서 |
|---|---|---|---|
| TurtleBot3 Waffle Pi | Raspberry Pi + OpenCR | DYNAMIXEL XM430-W210 ×2 (엔코더 내장) | LiDAR, 카메라(IMX219), IMU |
| Yahboom JetBot Mini | NVIDIA Jetson Nano 4GB | TT DC 기어모터 ×2 (엔코더 없음) | 카메라(IMX219) |

---

### TurtleBot3 Waffle Pi

출처: [ROBOTIS e-Manual – TurtleBot3 Features](https://emanual.robotis.com/docs/en/platform/turtlebot3/features/)

| 항목 | 제원 |
|---|---|
| 최대 병진 속도 | 0.26 m/s |
| 최대 회전 속도 | 1.82 rad/s (104.27 deg/s) |
| 최대 적재 하중 | 30 kg |
| 크기 (L × W × H) | 281 × 306 × 141 mm |
| 무게 (SBC·배터리·센서 포함) | 1.8 kg |
| 등판 가능 턱 높이 | 10 mm 이하 |
| 예상 동작 시간 | 약 2시간 |
| 예상 충전 시간 | 약 2시간 30분 |
| SBC | Raspberry Pi 4 (현행 기준, 구형 키트는 Raspberry Pi 3B+) |
| MCU (OpenCR) | 32-bit ARM Cortex-M7 (FPU 포함), 216 MHz, 462 DMIPS |
| 액추에이터 | DYNAMIXEL XM430-W210 ×2 |
| LiDAR | 360° Laser Distance Sensor LDS-02 (현행 기준, 구형 키트는 LDS-01) |
| 카메라 | Raspberry Pi Camera Module v2.1 (Sony IMX219, 8MP) |
| IMU | 3축 자이로 + 3축 가속도 |
| 배터리 | Li-Po 11.1 V, 1800 mAh / 19.98 Wh, 5C |
| 전원 출력 | 3.3 V / 800 mA, 5 V / 4 A, 12 V / 1 A |
| 확장 핀 | GPIO 18핀, Arduino 32핀 헤더 |
| 주변장치 인터페이스 | UART ×3, CAN ×1, SPI ×1, I2C ×1, ADC ×5, 5핀 OLLO ×4 |
| DYNAMIXEL 포트 | RS485 ×3, TTL ×3 |
| PC 연결 | USB |
| 펌웨어 업데이트 | USB 또는 JTAG |
| 충전 어댑터 | 입력 100–240 V AC 50/60 Hz, 출력 12 V DC 5 A |

> SBC와 LiDAR는 출고 시기에 따라 다르다. 보유 장비의 실제 모델은 기판·센서 라벨로 확인할 것.

---

### Yahboom JetBot Mini

출처: [Yahboom 제품 페이지](https://category.yahboom.net/products/jetbot-mini), [RobotShop](https://www.robotshop.com/products/yahboom-yahboom-jetbot-mini-ai-vision-robot-car-ros-starter-kit-w-jetson-nano-4gb-2gb-sub-board), [GitHub – YahboomTechnology/jetbot-mini](https://github.com/YahboomTechnology/jetbot-mini)

| 항목 | 제원 |
|---|---|
| 조립 크기 | 170.5 × 126.5 × 146.5 mm |
| 조립 무게 | 708 g |
| 연산 보드 | NVIDIA Jetson Nano 4GB |
| ├ CPU | Quad-core ARM Cortex-A57 @ 1.43 GHz |
| ├ GPU | 128-core NVIDIA Maxwell (472 GFLOPS) |
| ├ 메모리 | 4 GB 64-bit LPDDR4, 25.6 GB/s |
| └ 전력 모드 | 5 W / 10 W |
| 확장 보드 | Yahboom 전용 확장 보드 (듀얼 모터 드라이버, PWM 서보, OLED, 온보드 MCU) |
| 구동 모터 | TT DC 기어모터 ×2, 감속비 1:48, **엔코더 없음** (개루프 제어) |
| 바퀴 | 구동 바퀴 ×2 + 캐스터(유니버설 휠) ×1 |
| 카메라 | IMX219 CSI 카메라, 8MP (3280 × 2464), 1/4" CMOS, 초점거리 2.96 mm, 화각 77° |
| 카메라 마운트 | 틸트(pitch) 각도 수동 조정 |
| 배터리 | 18650 배터리 팩, 12.6 V 2200 mAh |
| 무선 | 1300 Mbps 무선 랜카드 (드라이버 설치 불필요) |
| 소프트웨어 | ROS, OpenCV, Python 3 |

> 엔코더가 없으므로 휠 오도메트리를 쓸 수 없다. 위치 추정은 카메라 기반으로 해야 한다.
