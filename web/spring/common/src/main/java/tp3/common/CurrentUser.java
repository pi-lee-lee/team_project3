package tp3.common;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

/** MVC 서비스에서 게이트웨이가 넣은 헤더로 현재 사용자를 읽는다. */
public record CurrentUser(long id, String login, String role) {

    public static CurrentUser from(HttpServletRequest req) {
        String id = req.getHeader(AuthHeaders.USER_ID);
        if (id == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "no user context");
        }
        return new CurrentUser(Long.parseLong(id), req.getHeader(AuthHeaders.LOGIN), req.getHeader(AuthHeaders.ROLE));
    }

    public boolean isAdmin() {
        return "ADMIN".equals(role);
    }
}
