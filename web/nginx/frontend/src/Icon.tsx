/**
 * 아이콘: Google Material Symbols (Rounded, Apache 2.0) — 글꼴 파일을 프로젝트에 포함해 모든 OS 브라우저에서 같게 보인다.
 *
 * 화면 코드는 아이콘을 SF Symbols 식 이름(`camera.fill` 등)으로 부르고, 이 파일 한 곳에서 Material Symbols 이름에 연결한다.
 * (Apple SF Symbols 는 라이선스상 Apple 플랫폼 앱에서만 쓸 수 있어 웹에는 넣지 않았다.)
 * 이름이 `.fill` 로 끝나면 채움형으로 그린다. 굵기는 Apple 화면과 어울리게 400(Regular).
 */
import 'material-symbols/rounded.css';

const SYMBOLS: Record<string, string> = {
  // 내비게이션
  'person.2': 'group',
  'cpu': 'smart_toy',
  'mappin.and.ellipse': 'location_on',
  'slider.horizontal.3': 'tune',
  'list.bullet.clipboard': 'assignment',
  'server.rack': 'dns',
  'video': 'videocam',
  'plus.circle': 'add_circle',
  'checklist': 'checklist',
  'clock.arrow.circlepath': 'history',
  'calendar.badge.clock': 'event_repeat',
  'play.fill': 'play_arrow',
  'trash': 'delete',
  'rectangle.portrait.and.arrow.right': 'logout',
  // 관제
  'camera.fill': 'photo_camera',
  'map.fill': 'map',
  'arrow.up': 'arrow_upward',
  'arrow.down': 'arrow_downward',
  'arrow.counterclockwise': 'rotate_left',
  'arrow.clockwise': 'rotate_right',
  'stop.fill': 'stop',
  'exclamationmark.octagon.fill': 'report',
  'hand.raised.fill': 'back_hand',
  'location.fill': 'my_location',
  // 상태·동작
  'checkmark.circle.fill': 'check_circle',
  'xmark.circle.fill': 'cancel',
  'exclamationmark.triangle.fill': 'warning',
  'nosign': 'block',
  'clock': 'schedule',
  'photo': 'image',
  'plus': 'add',
  'pencil': 'edit',
  'xmark': 'close',
  'arrow.triangle.2.circlepath': 'refresh',
  'chevron.right': 'chevron_right',
  'arrow.up.right.square': 'open_in_new',
  'chevron.left': 'chevron_left',
  'chevron.up.chevron.down': 'unfold_more',
  'checkmark': 'check',
  'tray': 'inbox',
  'square.and.pencil': 'edit_square',
  'person.crop.circle': 'account_circle',
  'key': 'key',
  'gauge': 'speed',
  'doc.text.magnifyingglass': 'manage_search',
  'antenna': 'cell_tower',
  'list.bullet': 'list',
  'photo.on.rectangle': 'photo_library',
  'arrow.uturn.backward': 'undo',
  'ellipsis': 'more_horiz',
  'checkmark.shield.fill': 'verified_user',
  // 대시보드
  'bell.fill': 'notifications',
  'flame.fill': 'local_fire_department',
  'arrow.up.left.and.arrow.down.right': 'fullscreen',
  'wifi.slash': 'wifi_off',
  'battery': 'battery_5_bar',
  'bolt.fill': 'bolt',
  'hourglass': 'hourglass_top',
  'eye': 'visibility',
  // 시나리오: 규칙 · 경고 · 사건 · 설정
  'gearshape': 'settings',
  'ruler': 'rule',
  'door.left.hand.open': 'door_open',
  'target': 'adjust',
  'paperplane.fill': 'send',
  'checkmark.seal.fill': 'verified',
  'hand.thumbsup.fill': 'thumb_up',
  'bell.slash': 'notifications_off',
  'viewfinder': 'center_focus_strong',
  'flask': 'science',
  'gauge.needle': 'speed',
  'gamecontroller.fill': 'videogame_asset',
};

export function Icon({ name, size = 18, className = '', title }: { name: string; size?: number; className?: string; title?: string }) {
  const fill = name.endsWith('.fill') ? 1 : 0;
  return (
    <span
      className={`icon material-symbols-rounded ${className}`}
      style={{ fontSize: size, fontVariationSettings: `'FILL' ${fill}, 'wght' 400, 'GRAD' 0, 'opsz' ${Math.min(48, Math.max(20, size))}` }}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      {SYMBOLS[name] ?? 'help'}
    </span>
  );
}
