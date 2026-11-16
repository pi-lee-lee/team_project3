package tp3.inspection;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.web.client.RestClient;

@SpringBootApplication
@EnableScheduling
public class InspectionServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(InspectionServiceApplication.class, args);
    }

    private static RestClient client(String baseUrl) {
        SimpleClientHttpRequestFactory f = new SimpleClientHttpRequestFactory();
        f.setConnectTimeout(3000);
        f.setReadTimeout(10000);
        return RestClient.builder().baseUrl(baseUrl).requestFactory(f).build();
    }

    @Bean
    RestClient robotClient(@Value("${app.robot-url}") String url) {
        return client(url);
    }

    @Bean
    RestClient analysisClient(@Value("${app.analysis-url}") String url) {
        return client(url);
    }
}
