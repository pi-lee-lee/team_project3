package tp3.inspection;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

/**
 * 분석이 아직 없는 사진을 analysis-service 에 맡긴다(5초마다).
 * 요청 후 60초 안에 결과가 없으면 다시 맡긴다. 분석 서비스가 잠시 멈춰도 결과가 빠지지 않는다.
 */
@Component
public class AnalysisTrigger {

    private static final Logger log = LoggerFactory.getLogger(AnalysisTrigger.class);

    private final Store store;
    private final RestClient analysis;

    public AnalysisTrigger(Store store, RestClient analysisClient) {
        this.store = store;
        this.analysis = analysisClient;
    }

    @Scheduled(fixedDelay = 5000, initialDelay = 10000)
    public void run() {
        for (Long id : store.observationsNeedingAnalysis()) {
            try {
                analysis.post().uri("/jobs").contentType(MediaType.APPLICATION_JSON)
                        .body(Map.of("observationId", id)).retrieve().toBodilessEntity();
                store.markAnalysisRequested(id);
            } catch (Exception e) {
                log.debug("analysis request failed for {}: {}", id, e.toString());
                return;
            }
        }
    }
}
