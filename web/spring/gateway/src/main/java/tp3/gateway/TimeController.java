package tp3.gateway;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 서버 시간. 화면 왼쪽 아래 "서버 시간" 단추가 부른다(로그인한 모든 역할).
 * 예약 점검은 서버 시계 + 예약 기준 시간대로 돌기 때문에, 사용자가 기기 시계와 서버 시계 차이를 확인할 수 있게 한다.
 */
@RestController
public class TimeController {

    private final ZoneId zone;

    public TimeController(@Value("${app.display-zone:${SCHEDULE_ZONE:Asia/Seoul}}") String zone) {
        this.zone = ZoneId.of(zone);
    }

    @GetMapping("/api/time")
    public Map<String, Object> time() {
        Instant now = Instant.now();
        ZonedDateTime z = now.atZone(zone);
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("epochMs", now.toEpochMilli());
        m.put("zone", zone.getId());
        m.put("offset", z.getOffset().getId());
        m.put("local", z.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        return m;
    }
}
