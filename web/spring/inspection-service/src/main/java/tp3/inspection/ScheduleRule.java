package tp3.inspection;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.Set;

/**
 * 예약 점검의 실행 규칙과 다음 실행 시각 계산. 시각은 모두 zone(기본 Asia/Seoul) 기준으로 해석한다.
 * <ul>
 *   <li>MANUAL: 정해 둔 시각 없음 — 실행 버튼으로만 돌린다</li>
 *   <li>ONCE: runAt 에 한 번</li>
 *   <li>INTERVAL: intervalMinutes 마다. runAt 이 있으면 그 시각부터. days·window 가 있으면 그 요일·시간대 안에서만</li>
 *   <li>DAILY: 매일 timeOfDay</li>
 *   <li>WEEKLY: days 요일의 timeOfDay</li>
 * </ul>
 * 서버가 꺼져 있던 동안 놓친 회차는 몰아서 실행하지 않는다: 다음 시각은 항상 "지금 이후 첫 회차"다.
 */
record ScheduleRule(String kind, Instant runAt, Integer intervalMinutes, LocalTime timeOfDay, Set<Integer> days,
                    LocalTime windowStart, LocalTime windowEnd) {

    /** 새로 만들거나 고치거나 다시 켰을 때의 첫 실행 시각. 없으면 null. */
    Instant first(Instant now, ZoneId zone) {
        return switch (kind) {
            case "MANUAL" -> null;
            case "ONCE" -> runAt != null && runAt.isAfter(now) ? runAt : null;
            case "INTERVAL" -> fit(runAt != null && runAt.isAfter(now) ? runAt : now.plus(interval()), zone);
            default -> nextTimeOfDay(now, zone);
        };
    }

    /** planned 회차를 처리한 뒤의 다음 실행 시각. 없으면 null. */
    Instant after(Instant planned, Instant now, ZoneId zone) {
        return switch (kind) {
            case "MANUAL", "ONCE" -> null;
            case "INTERVAL" -> {
                long step = interval().toSeconds();
                long k = Math.max(0, Duration.between(planned, now).toSeconds()) / step + 1;
                yield fit(planned.plusSeconds(k * step), zone);
            }
            default -> nextTimeOfDay(now, zone);
        };
    }

    private Duration interval() {
        return Duration.ofMinutes(intervalMinutes);
    }

    private boolean dayOk(LocalDate d) {
        return days == null || days.isEmpty() || days.contains(d.getDayOfWeek().getValue());
    }

    private boolean inWindow(LocalTime t) {
        if (windowStart == null || windowEnd == null) {
            return true;
        }
        return windowStart.isBefore(windowEnd)
                ? !t.isBefore(windowStart) && t.isBefore(windowEnd)
                : !t.isBefore(windowStart) || t.isBefore(windowEnd); // 자정을 넘는 시간대(예: 22:00~06:00)
    }

    /** DAILY·WEEKLY: now 이후 첫 (허용 요일, timeOfDay). */
    private Instant nextTimeOfDay(Instant now, ZoneId zone) {
        LocalDate today = now.atZone(zone).toLocalDate();
        for (int i = 0; i <= 7; i++) {
            LocalDate d = today.plusDays(i);
            if (dayOk(d)) {
                Instant t = d.atTime(timeOfDay).atZone(zone).toInstant();
                if (t.isAfter(now)) {
                    return t;
                }
            }
        }
        return null;
    }

    /** INTERVAL: 후보 시각이 허용 요일·시간대 밖이면 다음 시간대 시작으로 민다. */
    private Instant fit(Instant candidate, ZoneId zone) {
        LocalTime start = windowStart == null || windowEnd == null ? LocalTime.MIDNIGHT : windowStart;
        Instant c = candidate;
        for (int i = 0; i < 20; i++) {
            ZonedDateTime z = c.atZone(zone);
            if (dayOk(z.toLocalDate()) && inWindow(z.toLocalTime())) {
                return c;
            }
            LocalDate d = z.toLocalTime().isBefore(start) ? z.toLocalDate() : z.toLocalDate().plusDays(1);
            c = d.atTime(start).atZone(zone).toInstant();
        }
        return null;
    }
}
