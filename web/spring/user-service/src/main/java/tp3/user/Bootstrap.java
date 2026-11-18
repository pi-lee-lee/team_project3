package tp3.user;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Component;

/**
 * 첫 실행 시 계정 준비. 비밀번호는 SQL에 두지 않고 환경변수로 받는다.
 * - ADMIN 계정이 없으면 INITIAL_ADMIN_LOGIN / INITIAL_ADMIN_PASSWORD 로 만든다.
 * - DEMO_USERS_PASSWORD 가 있으면 역할 1·2·3 시험 계정(sup1, mgr1, user1)과
 *   관제 대시보드 전용 계정(dash1, 역할 4: 조회만)을 만든다.
 */
@Component
public class Bootstrap implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(Bootstrap.class);

    private final UserRepository users;
    private final BCryptPasswordEncoder encoder;
    private final String adminLogin;
    private final String adminPassword;
    private final String demoPassword;

    public Bootstrap(UserRepository users, BCryptPasswordEncoder encoder,
                     @Value("${app.initial-admin.login}") String adminLogin,
                     @Value("${app.initial-admin.password}") String adminPassword,
                     @Value("${app.demo-users-password}") String demoPassword) {
        this.users = users;
        this.encoder = encoder;
        this.adminLogin = adminLogin;
        this.adminPassword = adminPassword;
        this.demoPassword = demoPassword;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (!users.existsByRole("ADMIN")) {
            if (adminPassword.isBlank()) {
                log.warn("ADMIN 계정이 없고 INITIAL_ADMIN_PASSWORD 도 비어 있어 만들지 않았습니다");
            } else {
                users.insert(adminLogin, encoder.encode(adminPassword), "웹사이트 관리자", 0);
                log.info("초기 ADMIN 계정 생성: {}", adminLogin);
            }
        }
        if (!demoPassword.isBlank()) {
            createIfAbsent("sup1", "시험 관리자", 1);
            createIfAbsent("mgr1", "시험 매니저", 2);
            createIfAbsent("user1", "시험 사용자", 3);
            createIfAbsent("dash1", "관제 대시보드", 4);
        }
    }

    private void createIfAbsent(String login, String name, int roleId) {
        if (users.findByLogin(login).isEmpty()) {
            users.insert(login, encoder.encode(demoPassword), name, roleId);
            log.info("시험 계정 생성: {} (역할 {})", login, roleId);
        }
    }
}
