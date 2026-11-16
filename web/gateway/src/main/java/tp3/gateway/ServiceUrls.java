package tp3.gateway;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.services")
public record ServiceUrls(String user, String inspection, String robot, String analysis) {
}
