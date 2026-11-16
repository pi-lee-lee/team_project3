package tp3.common;

/**
 * 게이트웨이가 JWT를 검증한 뒤 내부 서비스로 넘기는 사용자 헤더.
 * 게이트웨이는 클라이언트가 보낸 같은 이름의 헤더를 먼저 지운다.
 * 내부 서비스는 외부에 노출되지 않으므로 이 헤더를 신뢰한다.
 */
public final class AuthHeaders {
    public static final String USER_ID = "X-User-Id";
    public static final String LOGIN = "X-User-Login";
    public static final String ROLE = "X-User-Role";
    public static final String COOKIE = "ACCESS_TOKEN";

    private AuthHeaders() {
    }
}
