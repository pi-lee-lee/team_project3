package tp3.common;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.Optional;

/** HS256 JWT 발급(user-service)과 검증(gateway)에 같은 비밀키를 쓴다. */
public class JwtCodec {

    public record TokenClaims(long userId, String login, String role, int tokenVersion) {
    }

    private final SecretKey key;

    public JwtCodec(String secret) {
        byte[] bytes = secret.getBytes(StandardCharsets.UTF_8);
        if (bytes.length < 32) {
            throw new IllegalArgumentException("JWT_SECRET must be at least 32 bytes");
        }
        this.key = Keys.hmacShaKeyFor(bytes);
    }

    public String issue(TokenClaims c, Duration ttl) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(Long.toString(c.userId()))
                .claim("login", c.login())
                .claim("role", c.role())
                .claim("tv", c.tokenVersion())
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(ttl)))
                .signWith(key)
                .compact();
    }

    public Optional<TokenClaims> parse(String token) {
        try {
            Claims p = Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
            return Optional.of(new TokenClaims(
                    Long.parseLong(p.getSubject()),
                    p.get("login", String.class),
                    p.get("role", String.class),
                    p.get("tv", Integer.class)));
        } catch (JwtException | IllegalArgumentException e) {
            return Optional.empty();
        }
    }
}
