package tp3.gateway;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.http.server.PathContainer;
import org.springframework.web.util.pattern.PathPattern;
import org.springframework.web.util.pattern.PathPatternParser;

import java.util.List;
import java.util.Optional;
import java.util.Set;

/** application.yml 의 gateway.rules 표. 위에서부터 처음 맞는 규칙을 적용한다. */
@ConfigurationProperties(prefix = "gateway")
public class AccessPolicy {

    public record Rule(String pattern, Set<String> roles) {
    }

    private List<String> publicPaths = List.of();
    private List<Rule> rules = List.of();
    private List<PathPattern> compiled;

    public boolean isPublic(String path) {
        return publicPaths.contains(path);
    }

    /** 맞는 규칙이 없으면 empty → 거부. */
    public Optional<Boolean> allows(String path, String role) {
        if (compiled == null) {
            compiled = rules.stream().map(r -> PathPatternParser.defaultInstance.parse(r.pattern())).toList();
        }
        PathContainer pc = PathContainer.parsePath(path);
        for (int i = 0; i < rules.size(); i++) {
            if (compiled.get(i).matches(pc)) {
                return Optional.of(rules.get(i).roles().contains(role));
            }
        }
        return Optional.empty();
    }

    public List<String> getPublicPaths() {
        return publicPaths;
    }

    public void setPublicPaths(List<String> publicPaths) {
        this.publicPaths = publicPaths;
    }

    public List<Rule> getRules() {
        return rules;
    }

    public void setRules(List<Rule> rules) {
        this.rules = rules;
        this.compiled = null;
    }
}
