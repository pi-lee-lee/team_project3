package tp3.inspection;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import tp3.common.CurrentUser;

import java.util.Map;

/** 시연 시나리오 실행(시뮬레이션 전용). 경로가 /api/admin/** 이라 게이트웨이가 ADMIN 으로 제한한다. */
@RestController
public class DemoController {

    private final DemoService demo;

    public DemoController(DemoService demo) {
        this.demo = demo;
    }

    /** 시나리오 목록과 지금(또는 마지막) 실행의 진행 기록 */
    @GetMapping("/api/admin/demo")
    public Map<String, Object> status() {
        return demo.status();
    }

    @PostMapping("/api/admin/demo/{key}/run")
    public Map<String, Object> run(@PathVariable String key, HttpServletRequest req) {
        return demo.start(key, CurrentUser.from(req));
    }

    @PostMapping("/api/admin/demo/stop")
    public Map<String, Object> stop() {
        return demo.stop();
    }
}
