package tp3.user;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Repository
public class UserRepository {

    public record User(long userId, String loginId, String passwordHash, String name, int roleId, String roleCode,
                       String roleName, String status, int tokenVersion, OffsetDateTime createdAt,
                       OffsetDateTime lastLoginAt) {
    }

    public record Role(int roleId, String code, String name, String description) {
    }

    private static final String SELECT = """
            SELECT u.user_id, u.login_id, u.password_hash, u.name, u.role_id, r.code AS role_code,
                   r.name AS role_name, u.status, u.token_version, u.created_at, u.last_login_at
            FROM users u JOIN role r USING (role_id)
            """;

    private final JdbcClient jdbc;

    public UserRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<User> findByLogin(String loginId) {
        return jdbc.sql(SELECT + " WHERE u.login_id = ?").param(loginId).query(User.class).optional();
    }

    public Optional<User> findById(long id) {
        return jdbc.sql(SELECT + " WHERE u.user_id = ?").param(id).query(User.class).optional();
    }

    public List<User> findAll() {
        return jdbc.sql(SELECT + " ORDER BY u.role_id, u.login_id").query(User.class).list();
    }

    public List<Role> roles() {
        return jdbc.sql("SELECT role_id, code, name, description FROM role ORDER BY role_id").query(Role.class).list();
    }

    public boolean existsByRole(String roleCode) {
        return jdbc.sql("SELECT count(*) FROM users u JOIN role r USING (role_id) WHERE r.code = ?")
                .param(roleCode).query(Long.class).single() > 0;
    }

    public long insert(String loginId, String passwordHash, String name, int roleId) {
        return jdbc.sql("""
                        INSERT INTO users (login_id, password_hash, name, role_id)
                        VALUES (?, ?, ?, ?) RETURNING user_id""")
                .params(loginId, passwordHash, name, roleId).query(Long.class).single();
    }

    public void update(long id, String name, Integer roleId, String status) {
        jdbc.sql("""
                        UPDATE users SET name = COALESCE(?, name), role_id = COALESCE(?, role_id),
                               status = COALESCE(?, status), updated_at = now(),
                               token_version = token_version + ?
                        WHERE user_id = ?""")
                .params(name, roleId, status, (roleId != null || status != null) ? 1 : 0, id).update();
    }

    public void updatePassword(long id, String hash) {
        jdbc.sql("UPDATE users SET password_hash = ?, updated_at = now(), token_version = token_version + 1 WHERE user_id = ?")
                .params(hash, id).update();
    }

    public void revokeSessions(long id) {
        jdbc.sql("UPDATE users SET token_version = token_version + 1, updated_at = now() WHERE user_id = ?")
                .param(id).update();
    }

    public void touchLogin(long id) {
        jdbc.sql("UPDATE users SET last_login_at = now() WHERE user_id = ?").param(id).update();
    }

    public void audit(Long userId, String loginId, String roleCode, String action, String target, Integer status,
                      String detail) {
        jdbc.sql("""
                        INSERT INTO audit_log (user_id, login_id, role_code, action, target, status, detail)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""")
                .params(userId, loginId, roleCode, action, target, status, detail).update();
    }

    public List<Map<String, Object>> auditLog(int limit) {
        return jdbc.sql("""
                        SELECT audit_id, occurred_at, user_id, login_id, role_code, action, target, status, detail
                        FROM audit_log ORDER BY audit_id DESC LIMIT ?""")
                .param(limit).query().listOfRows();
    }
}
