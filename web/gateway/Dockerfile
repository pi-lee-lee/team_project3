# gateway 실행 환경 (코드는 넣지 않는다). compose 가 이 폴더를 /workspace 로 연결하면
# 시작할 때 빌드(mvn package)하고 jar 를 실행한다. 공유 라이브러리 tp3:common 은 common-build 가 m2 볼륨에 설치해 둔다.
FROM maven:3.9-eclipse-temurin-21
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
ENV APP=gateway \
    MAVEN_OPTS="-Xmx384m" \
    MVN_FLAGS="-q -B -DskipTests -Daether.syncContext.named.factory=file-lock -Daether.syncContext.named.nameMapper=file-gav"
CMD ["sh", "-c", "mvn $MVN_FLAGS package && exec java -XX:MaxRAMPercentage=60 -XX:+UseSerialGC -XX:TieredStopAtLevel=1 -Djava.awt.headless=true -jar target/$APP-0.1.0.jar"]
