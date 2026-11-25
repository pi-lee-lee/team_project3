"""실제 터틀봇용 Nav2 설정을 시뮬레이션 설정(ros/sim/src/config/nav2_params.yaml)에서 만든다.

설정 원본은 하나만 둔다(튜닝값 · 행동 트리 · 충돌 감시가 시뮬레이션과 같게). 실물에서 달라지는 것만 바꾼다:
  - use_sim_time: 모든 노드 False(실제 시간)
  - AMCL 오도메트리 오차 계수 alpha1~4: 0.05(시뮬레이션은 미끄러짐 없는 odom) → 실물 기본 0.15(바퀴가 미끄러진다)
  - 지도 · 행동 트리 파일 경로: 실물 로봇의 경로

사용(호스트나 로봇 어디서든, PyYAML 필요):
  python3 make_real_params.py --map ~/maps/site.yaml --bt ~/nav2/navigate_fixed_plan.xml -o ~/nav2/nav2_params_real.yaml
  → 행동 트리 파일(ros/sim/src/config/navigate_fixed_plan.xml)도 --bt 경로에 함께 복사해 둔다.
실행(로봇): ros2 launch nav2_bringup bringup_launch.py map:=<지도> params_file:=<만든 파일> use_sim_time:=False
목표 브리지 · 워치독(ros/robot/src)도 함께 띄워야 금지구역 · 가상 장애물 층(keepout_layer · virtual_layer)이 채워진다.
"""
import argparse
import pathlib

import yaml

HERE = pathlib.Path(__file__).resolve().parent
SIM_PARAMS = HERE.parents[1] / 'sim' / 'src' / 'config' / 'nav2_params.yaml'


def use_real_time(node):
    """설정 안의 모든 use_sim_time 을 False 로."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == 'use_sim_time':
                node[k] = False
            else:
                use_real_time(v)
    elif isinstance(node, list):
        for v in node:
            use_real_time(v)


def main():
    ap = argparse.ArgumentParser(description='실제 터틀봇용 Nav2 설정 만들기')
    ap.add_argument('--map', required=True, help='저장 지도 yaml 경로(로봇 기준)')
    ap.add_argument('--bt', required=True, help='행동 트리 navigate_fixed_plan.xml 경로(로봇 기준)')
    ap.add_argument('--alpha', type=float, default=0.15, help='AMCL alpha1~4 (기본 0.15, 실물에서 맞춘다)')
    ap.add_argument('-o', '--out', required=True, help='만들 파일')
    a = ap.parse_args()

    p = yaml.safe_load(SIM_PARAMS.read_text(encoding='utf-8'))
    use_real_time(p)
    amcl = p['amcl']['ros__parameters']
    for k in ('alpha1', 'alpha2', 'alpha3', 'alpha4'):
        amcl[k] = a.alpha
    p['map_server']['ros__parameters']['yaml_filename'] = a.map
    p['bt_navigator']['ros__parameters']['default_nav_to_pose_bt_xml'] = a.bt

    head = (f'# 실제 터틀봇용 Nav2 설정 — ros/robot/tools/make_real_params.py 로 {SIM_PARAMS.name} 에서 만들었다. 직접 고치지 말고\n'
            f'# 원본(ros/sim/src/config/nav2_params.yaml)을 고친 뒤 다시 만든다. 바꾼 것: use_sim_time False, AMCL alpha1~4 {a.alpha},\n'
            f'# 지도 {a.map}, 행동 트리 {a.bt}\n')
    pathlib.Path(a.out).expanduser().write_text(head + yaml.safe_dump(p, sort_keys=False, allow_unicode=True), encoding='utf-8')
    print(f'wrote {a.out}')


if __name__ == '__main__':
    main()
