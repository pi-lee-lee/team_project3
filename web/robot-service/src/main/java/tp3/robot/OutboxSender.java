package tp3.robot;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.web.client.RestClient;

/**
 * 결과 보관·재전송: report_outbox 의 미전송 보고를 순서대로 inspection-service 로 보낸다.
 * 실패하면 그 자리에서 멈추고 다음 주기에 다시 보낸다(순서 유지). 받는 쪽은 reportId 로 중복을 걸러 낸다.
 */
@Component
public class OutboxSender {

    private static final Logger log = LoggerFactory.getLogger(OutboxSender.class);

    private final RobotRepository repo;
    private final RestClient http;

    public OutboxSender(RobotRepository repo, @Value("${app.inspection-url}") String inspectionUrl) {
        this.repo = repo;
        SimpleClientHttpRequestFactory f = new SimpleClientHttpRequestFactory();
        f.setConnectTimeout(3000);
        f.setReadTimeout(10000);
        this.http = RestClient.builder().baseUrl(inspectionUrl).requestFactory(f).build();
    }

    @Scheduled(fixedDelay = 1000)
    public void flush() {
        for (var r : repo.pending(20)) {
            try {
                if ("EVENT".equals(r.kind())) {
                    http.post().uri("/internal/tasks/{id}/events", r.missionId())
                            .header("X-Report-Id", r.reportId().toString())
                            .contentType(MediaType.APPLICATION_JSON).body(r.payload())
                            .retrieve().toBodilessEntity();
                } else {
                    var form = new LinkedMultiValueMap<String, Object>();
                    HttpHeaders jh = new HttpHeaders();
                    jh.setContentType(MediaType.APPLICATION_JSON);
                    form.add("meta", new HttpEntity<>(r.payload(), jh));
                    if (r.image() != null) {
                        HttpHeaders ih = new HttpHeaders();
                        ih.setContentType(MediaType.IMAGE_JPEG);
                        form.add("image", new HttpEntity<>(new ByteArrayResource(r.image()) {
                            @Override
                            public String getFilename() {
                                return "photo.jpg";
                            }
                        }, ih));
                    }
                    http.post().uri("/internal/tasks/{id}/observations", r.missionId())
                            .header("X-Report-Id", r.reportId().toString())
                            .contentType(MediaType.MULTIPART_FORM_DATA).body(form)
                            .retrieve().toBodilessEntity();
                }
                repo.markSent(r.reportId());
            } catch (Exception e) {
                repo.markFailed(r.reportId(), e.getMessage());
                if (r.attempts() % 10 == 0) {
                    log.info("보고 전송 실패(다시 시도 예정) {}: {}", r.reportId(), e.getMessage());
                }
                return;
            }
        }
    }
}
