---
layout: single
title:  "OTel로 리소스 데이터 수집해보기"
categories: [소모임(discipline)]
tags: [소모임]
toc: true
author_profile: true
---


## OTel과 Prometheus

- `Observability`를 담당하는 핵심 오픈소스
- `OpenTelemetry`는 데이터 표준화 및 수집기 / `Prometheus`는 데이터 저장소 및 분석기(DB)


- `OpenTelemetry`의 특징
  - 표준화: 어떤 언어로 코드를 짜든 동일한 형식으로 데이터를 뽑아냄
  - 유연성: 수집한 데이터를 Prometheus뿐 아니라 Datadog, Jaeger, AWS CloudWatch 등 여러 곳으로 동시에 보낼 수 있다.
  - 자동 계측(Auto-instrumentation): 코드를 거의 수정하지 않고도 라이브러리만 설치하면 HTTP 요청 시간 등을 자동으로 측정한다.
- `Prometheus`의 특징
  - 강력한 쿼리(PromQL): "최근 5분간 CPU 사용률 평균" 같은 복잡한 수치 계산에 최적화되어 있습니다.
  - Pull 모델: 서버가 각 서비스에 접속해 데이터를 가져오므로, 서비스가 갑자기 늘어나도 서버의 부하를 관리하기 쉽다.

- 활용 예시
  - EKS 기반 쇼핑몰 서비스 모니터링
  - 데이터 발생: 사용자가 상품을 주문합니다. (TypeScript 백엔드 서비스)
  - 데이터 수집 (OTel): OpenTelemetry SDK가 주문 처리 시간(Metric)과 서비스 간 호출 경로(Trace)를 수집합니다.
  - 데이터 전송 (OTel Collector): 수집된 데이터를 가공하여 Prometheus와 Jaeger로 각각 쏴줍니다.데이터 전송 (OTel Collector): 수집된 데이터를 가공하여 Prometheus와 Jaeger로 각각 쏴줍니다.
  - 데이터 저장 및 분석 (Prometheus): Prometheus는 수치 데이터를 저장하고, 특정 수치(예: 에러율 5% 초과)가 넘으면 슬랙으로 알람을 보냅니다.
  - 시각화 (Grafana): 엔지니어는 Grafana 대시보드에서 Prometheus의 데이터를 예쁜 그래프로 확인합니다.

## OTel Collector

- 복잡한 인프라에서 발생하는 데이터를 한데 모아 배달해주는 데이터 허브 역할
- 애플리케이션이나 인프라(EC2, EKS 등)에서 생성되는 메트릭, 트레이스, 로그를 수신하여 가공한 뒤, 우리가 원하는 분석 도구(Prometheus, Jaeger, CloudWatch 등)로 보내주는 프록시다.
- `왜 Collector를 거쳐서 전달할까?`
  - 부하 분산: 애플리케이션이 직접 데이터를 보내면 리소스를 많이 쓰지만, Collector가 대신 처리해 줍니다.
  - 보안: API 키나 인증 정보를 애플리케이션마다 심을 필요 없이 Collector 한 곳에서만 관리하면 됩니다.
  - 유연성: 소스 코드 수정 없이 설정 파일(config.yaml)만 바꾸면 데이터 목적지를 마음대로 변경할 수 있습니다.
- `핵심 3요소`
  - `Receivers(입구)`
    - 데이터를 어떻게 받을지 결정합니다.
    - Push 방식: 애플리케이션이 OTLP 프로토콜로 직접 데이터를 보냄.
    - Pull 방식: Collector가 특정 대상(예: host-metrics)에서 데이터를 긁어옴.
  - `Processors(공장)`
    - 받은 데이터를 어떻게 가공할지 결정한다.
    - Batch: 데이터를 효율적으로 보내기 위해 묶어서 처리함.
    - Filter: 불필요한 로그나 민감한 정보를 삭제함.
    - Attribute 추가: "이 데이터는 production 환경에서 온 거야"라는 태그를 일괄적으로 붙임.
  - `Exporters(출구)`
    - 가공한 데이터를 어디로 보낼지 결정한다.
      - Prometheus, Jaeger, AWS X-Ray, Datadog 등 다양한 분석 도구로 데이터를 쏴줍니다.

- 배포 패턴
  - Agent 패턴 (Sidecar): 각 서비스(Pod) 바로 옆에 붙어서 해당 서비스의 데이터만 수집합니다. 장애 추적이 빠릅니다.
  - Gateway 패턴 (Central): 여러 에이전트가 보낸 데이터를 한곳으로 모아 외부 벤더로 전달하는 중앙 집중 방식입니다. 비용 절감과 관리에 유리합니다.

- 설정 예시(config.yml)

```yaml
receivers:
  otlp: # 앱에서 보낸 데이터를 받는 입구
    protocols:
      grpc:
      http:

processors:
  batch: # 데이터를 묶어서 효율적으로 전송

exporters:
  awsxray: # AWS X-Ray로 트레이스 전송
  prometheus: # 프로메테우스로 메트릭 전송
    endpoint: "0.0.0.0:8889"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [awsxray]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

## 과제 

- OTel 프로젝트 바이너리 다운받아, 시스템 리소스 데이터 수집하기
- host-metrics receiver, prometheus exporter 사용
- 8889 엔드포인트에서 메트릭 노출시키기

- `host-metrics receiver`
  - 서버(Host) 자체의 건강 상태 측정 도구
  - 역할: 가상머신(EC2 등)이나 베어메탈 서버의 CPU 사용률, 메모리 점유율, 디스크 I/O, 네트워크 트래픽 같은 인프라 지표를 긁어옵니다
- `prometheus exporter`
  - 수집된 데이터를 Prometheus가 읽을 수 있는 형식으로 변환해서 내보내는 장치
  - 역할: OTel 표준 형식으로 들어온 데이터를 Prometheus 특유의 데이터 포맷(Text-based exposition format)으로 바뀐 뒤, 특정 포트(기본 9443 등)에 노출시킵다.
  - 동작 방식: Prometheus는 'Pull' 방식이므로, 이 익스포터가 데이터를 들고 있다가 Prometheus 서버가 데이터를 요청(Scrape)하면 그때 데이터를 넘겨준다.
  - 활용: 수집은 OTel로 했지만, 분석과 알람 설정은 익숙한 Prometheus + Grafana 조합으로 하고 싶을 때 사용합니다.

- `이렇게 복잡하게 사용하는 이유는?`
  - 유연성: 만약 내일 당장 회사에서 "프로메테우스 말고 AWS CloudWatch로 바꿔!"라고 해도, receivers는 그대로 두고 exporters에 awscloudwatch만 추가하면 끝납니다. 코드 수정이 전혀 필요 없죠.
  - 단일화: 예전에는 인프라용(Node Exporter), 앱용(SDK) 에이전트를 따로 깔았지만, 이제 OTel Collector 하나로 다 끝낼 수 있습니다.

- 흐름

```
[Host System]
    ↓ (CPU, Memory, Disk 등 수집)
[hostmetrics receiver]  ← otelcol이 내장한 수집기
    ↓
[prometheus exporter]   ← /metrics 엔드포인트로 노출
    ↓
localhost:8889/metrics  ← 브라우저나 curl로 확인
```

- 바이너리 파일 다운로드 -> 압축 풀기 -> config.ymal 생성 -> ls -al로 실행 권한 확인 없으면 chmod +x를 통해 권한 부여 -> 실행


```yaml
receivers:
  hostmetrics:
    collection_interval: 10s   # 10초마다 수집
    scrapers:
      cpu: {}        # CPU 사용률
      memory: {}     # 메모리
      disk: {}       # 디스크 I/O
      load: {}       # 시스템 부하
      filesystem: {} # 파일시스템 사용량
      network: {}    # 네트워크 I/O

exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"   # 이 포트로 메트릭 노출

service:
  pipelines:
    metrics:
      receivers: [hostmetrics]
      exporters: [prometheus]
```

- 문제 발생
  - macOS Gatekeeper 차단
  - 맥북에서 외부 바이너리 파일을 직접 실행할 때 발생하는 에러
- 해결 
  - `xattr -d com.apple.quarantine otelcol-contrib`
    - xattr: 확장 속성 관리 도구 실행
    - -d: Delete (삭제) 하겠다는 뜻입니다.
    - com.apple.quarantine: 삭제할 구체적인 속성 이름(격리 꼬리표)입니다.
  - 그 다음 다시 실행 (`./otelcol-contrib --config config.yaml`)

- Docker로 실행한다면?
  - `기본 모드(bridge)`: Docker 컨테이너 -> 격리된 가상 네트워크 -> 호스트 시스템 메트릭 못 읽음(컨테이너 자신의 리소스만 읽음)
  - `host 모드`: Docker 컨테이너 -> 호스트 네트워크 직접 사용 -> 호스트 메트릭 읽을 수 있음
  - Network 모드를 host로 설정 (--network host)
- 주의 사항 
  - Mac에서는 `--network host` 동작 X
  - 이유는?
    - `Docker Desktop이 내부적으로 Linux VM 위에서 돌기에 host가 Mac이 아니라 VM이다.`
    - Linux에서만 host 모드가 완전히 동작한다. (Linux는 VM 레이어 없음)
    - 그렇기에 실무 환경 (AWS EC2, 온프레미스 Linux 서버) 에서 otelcol을 Docker로 띄우면 그 서버 리소스를 정확하게 모니터링할 수 있다.

## 결과

- `localhost:8889/metrics` 접속

![images](/assets/images/OTelMetric.png)


