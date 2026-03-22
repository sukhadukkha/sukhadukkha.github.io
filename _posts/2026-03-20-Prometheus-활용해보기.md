---
layout: single
title:  "Prometheus 연습해보기"
categories: [Prometheus & Grafana]
tags: [Prometheus]
toc: true
author_profile: true
---


## Prometheus 쿼리를 통해 API의 동작 과정 이해하기

- export PROM="http://localhost:9090"으로 설정

- [✅] Prometheus 서버 health 확인하기 /-/healthy, /-/ready)

- [✅] Prometheus scrape target 목록 조회해보기 /api/v1/targets)

- [✅] 현재 수집 중인 job 목록 조회해보기 /api/v1/label/job/values)

- [✅] 현재 수집 중인 instance 목록 조회해보기 /api/v1/label/instance/values)

- [✅] 전체 metric 이름 목록 조회해보기 /api/v1/label/__name__/values)

- [✅] up 메트릭 instant query 해보기 /api/v1/query?query=up)

- [✅] 특정 job만 필터링해서 up 조회해보기
  - `curl -s -G "$PROM/api/v1/query" --data-urlencode 'query=up{job="node-exporter"}' | jq .`
  - `-s(silent)`: 불필요한 출력을 숨김 But 에러도 숨기기에 -sS 사용
  - `-S`: 에러는 출력
  - `-G(GET)`: GET 방식 요청
  - `--data-urlencode`: 쿼리를 URL 인코딩해서 안전하게 전달

- [✅] jq로 Prometheus API 응답 JSON 구조 보기 좋게 출력해보기

- [✅] range query로 최근 1시간 시계열 데이터 조회해보기 /api/v1/query_range)
  
```
export NOW=(data +%s)
export START=((NOW - 3600))
  curl -s -G "$PROM/api/v1/query_range" \
  --data-urlencode "query=up" \                     
  --data-urlencode "start=$START" \                                        
  --data-urlencode "end=$NOW" \                          
  --data-urlencode "step=1m" | jq . 
```

- [✅] step=30s, 1m, 5m로 바꿔가며 응답 차이 확인해보기

- [✅] CPU 사용률 PromQL 실행해보기

- [✅] 메모리 사용률 PromQL 실행해보기

- [✅] 디스크 사용률 PromQL 실행해보기

- [✅] up == 0 쿼리로 down 상태 target 찾아보기
  - `docker compose stop node-exporter`
  - `curl -s "$PROM/api/v1/query?query=up==0 | jq .`
  - node-exporter down 상태 확인 가능

- [✅] /api/v1/targets 응답에서 lastError, health 필드 확인해보기
  - `curl -s "$PROM/api/v1/targets" | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}'`

```
curl -s "$PROM/api/v1/targets"
│
└─ | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}'
        │                  │       │
        │                  │       └─ 각 target에서 3개 필드만 추출해서 새 객체 만들기
        │                  └─ 배열의 각 요소를 하나씩 꺼냄 (for문처럼)
        └─ API 응답 JSON에서 이 경로로 접근
```

```
{                                    // .
  "data": {                          // .data
    "activeTargets": [               // .data.activeTargets
      {                              // .data.activeTargets[]  ← [] 가 이걸 순회
        "labels": {
          "job": "node-exporter"     // .labels.job
        },
        "health": "up",              // .health
        "lastError": ""              // .lastError
      },
      { ... },  // 두번째 target
      { ... }   // 세번째 target
    ]
  }
}
```

- [✅] 각 API와 PromQL 결과를 보고 의미를 짧게 정리해보기

- [✅] Grafana 패널이 어떤 Prometheus query를 사용할지 추측해보기

- [✅] Prometheus API 호출 결과를 바탕으로 간단한 학습 보고서 작성해보기


## Prometheus를 활용해 데이터 분석해보기

- [✅] system_cpu_utilization_ratio 메트릭이 실제로 존재하는지 확인해보기
  - 존재하지 않아서 OTel의 config.yml 파일에 내용 추가

```yaml
receivers:
  hostmetrics:
    collection_interval: 10s
    scrapers:
      cpu:                       # 추가
        metrics:
          system.cpu.utilization:
            enabled: true   
      memory: {}
      disk: {}
      load: {}
      filesystem: {}
      network: {}

```

- [✅] metric 이름 목록에서 system_cpu_utilization_ratio 검색해보기
  - `curl -s "$PROM/api/v1/label/__name__/values | jq . | grep system_cpu_`

- [✅] system_cpu_utilization_ratio의 label 구조 확인해보기

- [✅] system_cpu_utilization_ratio instant query 실행해보기

```
curl -s -G "$PROM/api/v1/query" \
--data-urlencode 'query=system_cpu_utilization_ratio' | jq .
```

- [✅] 응답 JSON에서 metric label과 value를 분리해서 읽어보기

```
# metric label과 value 분리해서 출력

curl -s -G "$PROM/api/v1/query" \
  --data-urlencode 'query=system_cpu_utilization_ratio' | \
  jq '.data.result[] | {cpu: .metric.cpu, state: .metric.state, value: .value[1]}'
```

- [✅] jq를 사용해 응답에서 data.result만 추출해보기

```
curl -s -G "$PROM/api/v1/query" \
--data-urlencode 'query=system_cpu_utilization_ratio' | jq '.data.result[]'
```

- [✅] 특정 host_name 기준으로 system_cpu_utilization_ratio 조회해보기

- [✅] 특정 job 기준으로 system_cpu_utilization_ratio 조회해보기

```
# job 기준으로 필터링
curl -s -G "$PROM/api/v1/query" \
  --data-urlencode 'query=system_cpu_utilization_ratio{job="otel-host-metrics"}' | \
  jq '.data.result[] | {cpu: .metric.cpu, state: .metric.state, value: .value[1]}'
```

- [✅] CPU utilization 값이 0~1 비율인지 확인해보기

- [✅] system_cpu_utilization_ratio * 100으로 퍼센트 형태로 변환해보기

- [✅] CPU utilization이 높은 instance를 찾아보기

```
curl -s -G "$PROM/api/v1/query" \
  --data-urlencode 'query=(
    avg by(instance)(rate(node_cpu_seconds_total{mode!="idle"}[5m])) * 100
    or
    avg by(instance)(system_cpu_utilization_ratio{state!="idle"}) * 100
  )' | \
  jq '.data.result[] | {instance: .metric.instance, cpu_percent: .value[1]}'
{
  "instance": "node-exporter:9100",
  "cpu_percent": "0.025012619091896535"
}
{
  "instance": "host.docker.internal:8889",
  "cpu_percent": "2.7114064221222187"
}
```

- [✅] CPU utilization이 낮은 instance를 찾아보기

- [✅] 동일 메트릭을 range query로 최근 1시간 조회해보기

```
 curl -s -G "$PROM/api/v1/query_range" \
  --data-urlencode "query=system_cpu_utilization_ratio{cpu=\"cpu0\",state=\"user\"}" \
  --data-urlencode "start=$START" \
  --data-urlencode "end=$NOW" \
  --data-urlencode "step=5m" | \
  jq '.data.result[0].values[] | {time: (.[0] | todate), value: .[1]}'
{
  "time": "2026-03-21T04:39:52Z",
  "value": "0.09788092835518797"
}
{
  "time": "2026-03-21T04:44:52Z",
  "value": "0.13925327951570496"
}
{
  "time": "2026-03-21T04:49:52Z",
  "value": "0.08971774193553267"
}
{
  "time": "2026-03-21T04:54:52Z",
  "value": "0.19797979797977255"
}
{
  "time": "2026-03-21T04:59:52Z",
  "value": "0.14949494949499328"
}
{
  "time": "2026-03-21T05:04:52Z",
  "value": "0.12903225806451318"
}
{
  "time": "2026-03-21T05:09:52Z",
  "value": "0.1703629032258878"
}
{
  "time": "2026-03-21T05:14:52Z",
  "value": "0.17979797979805978"
}
```

- [✅] start, end, step 파라미터 의미 이해하기

- [✅] step=30s, 1m, 5m로 바꿔가며 응답 차이 확인해보기

- [✅] range query 응답의 시계열 값 배열에서 timestamp와 value를 직접 읽어보기

- [✅] 최근 1시간 평균 CPU utilization 계산해보기

- [✅] 최근 1시간 최대 CPU utilization 계산해보기

- [✅] 최근 1시간 최소 CPU utilization 계산해보기

```
# 평균
curl -s -G "$PROM/api/v1/query" \
  --data-urlencode 'query=avg_over_time(system_cpu_utilization_ratio{state!="idle"}[1h]) * 100' | \
  jq '.data.result[] | {cpu: .metric.cpu, state: .metric.state, avg: .value[1]}'

# 최대
curl -s -G "$PROM/api/v1/query" \
  --data-urlencode 'query=max_over_time(system_cpu_utilization_ratio{state!="idle"}[1h]) * 100' | \
  jq '.data.result[] | {cpu: .metric.cpu, state: .metric.state, max: .value[1]}'

# 최소
curl -s -G "$PROM/api/v1/query" \
  --data-urlencode 'query=min_over_time(system_cpu_utilization_ratio{state!="idle"}[1h]) * 100' | \
  jq '.data.result[] | {cpu: .metric.cpu, state: .metric.state, min: .value[1]}'
```

- [✅] CPU utilization이 일정 기준 이상인 구간이 있는지 확인해보기

```
각 코어의 전체 사용률

curl -s -G "$PROM/api/v1/query_range" \
  --data-urlencode 'query=sum by(cpu)(system_cpu_utilization_ratio{state!="idle"}) * 100 > 10' \
  --data-urlencode "start=$START" \
  --data-urlencode "end=$NOW" \
  --data-urlencode "step=1m" | \
  jq '.data.result[] | {cpu: .metric.cpu, values: .values}'
```

- [✅] 특정 host_name의 CPU utilization 추세가 상승 중인지 하락 중인지 해석해보기

- [✅] 여러 host_name 중 평균적으로 가장 바쁜 대상을 찾아보기

```
# instance별 평균 CPU 사용률 내림차순 정렬
curl -s -G "$PROM/api/v1/query" \
  --data-urlencode 'query=topk(3, avg by(instance)(system_cpu_utilization_ratio{state!="idle"}) * 100)' | \
  jq '.data.result[] | {instance: .metric.instance, cpu_percent: .value[1]}'
```

- [✅] 응답 결과가 비어 있을 때 어떻게 해석할지 정리해보기

- [✅] 잘못된 쿼리나 빈 결과를 보고 원인 추측해보기

- [✅] curl 결과를 파일로 저장해보기

```
curl -s -G "$PROM/api/v1/query_range" \
  --data-urlencode 'query=avg(system_cpu_utilization_ratio{state!="idle"}) * 100' \
  --data-urlencode "start=$START" \
  --data-urlencode "end=$NOW" \
  --data-urlencode "step=1m" > cpu_usage.json
```

- [✅] 저장한 JSON 응답을 jq로 후처리해보기

```
cat cpu_usage.json | jq '.data.result[0].values[] | {time: (.[0] | todate), cpu_percent: .[1]}'
```

- [✅] Python 또는 JavaScript로 Prometheus API 호출 코드 작성해보기

- [✅] JSON 파싱 후 system_cpu_utilization_ratio 값만 추출해보기

- [✅] 추출한 값을 표 형태로 정리해보기

- [✅] host_name별 CPU utilization을 정렬해보기

- [✅] 평균, 최대, 최소 값을 계산하는 간단한 분석 코드 작성해보기

- [✅] 분석 결과를 바탕으로 “현재 가장 바쁜 instance” 한 줄 요약 작성해보기

- [✅] 분석 결과를 바탕으로 “최근 1시간 CPU 사용 추세” 한 줄 요약 작성해보기

- [✅] up 메트릭 instant query 해보기 (/api/v1/query?query=up)

- [✅] 특정 job만 필터링해서 up 조회해보기

- [✅] up == 0 쿼리로 down 상태 target 찾아보기

- [✅] /api/v1/targets 응답에서 lastError, health 필드 확인해보기

- [✅] CPU 사용률 PromQL 실행해보기

- [✅] 메모리 사용률 PromQL 실행해보기

- [✅] 디스크 사용률 PromQL 실행해보기

- [✅] 각 API와 PromQL 결과를 보고 의미를 짧게 정리해보기

- [✅] Grafana 패널이 어떤 Prometheus query를 사용할지 추측해보기

- [✅] 현재 서버(Host) 의 CPU 사용량, 1시간 동안의 평균 CPU 사용량, 1시간 동안의 CPU 사용량 변화량 쿼리해보기

## 응용1 (호스트 리소스 모니터링 + VM 리소스 모니터링)

- node-exporter는 VM의 리소스를 모니터링한다.
- 현재 OTel은 Docker 환경이 아닌 바이너리 코드로 host에서 실행중
- 나는 내 Mac의 리소스를 모니터링 해보고싶다.
- Prometheus에 Job을 추가해보자 (OTel 추가)
- 그리고 OTel receiver(hostmetrics), exporter(prometheus)를 활용하여 host를 모니터링해보자

순서

- prometheus.yml 수정

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  # 추가
  - job_name: 'otel-host-metrics'
    static_configs:
      - targets: ['host.docker.internal:8889']
```

- targets: ['host.docker.internal:8889']의 의미
  - Prometheus는 Docker 컨테이너 안에 존재한다.
  - 컨테이너 밖을 나가서 host에 있는 OTel을 찾으려면 `host.docker.internal:8889` 경로가 필요하다.
- promQL로 조회해보기
  - `curl -s "$PROM/api/v1/label/__name__/values" | jq '.data[]' | grep system` 명령을 통해 OTel에서 어떤 메트릭으로 host의 리소스를 수집하고 있는지 확인
  - CPU: system_cpu_time_seconds_total
  - 메모리: system_memory_usage_bytes
  - 디스크: system_filesystem_usage_bytes

**이렇게 Node-exporter를 통해서 VM의 리소스도 모니터링 할 수 있고, OTel hostmetrics를 통해 host의 리소스도 모니터링 할 수 있다.**


## 응용2 Prometheus에 ClickHouse 추가해서 clickhouse 메트릭 수집해보기 

- ClickHouse Prometheus 설정 파일 생성 (config.xml)
- prometheus.yml에 clickhouse 스크랩 추가
- docker-compose.yml에 clickhouse 추가
- docker compose up -d 로 컨테이너들 실행
- up 쿼리로 컨테이너 다 잘 떠있는지 확인
- clickhouse에 테이블 생성 및 select 쿼리 날려보기
- `ClickHouseProfileEvents_SelectQuery` 메트릭 통해 실행된 SELECT 쿼리 수 확인해보기
- `(ClickHouseMetrics_MemoryTracking / ignoring(instance, job) node_memory_MemTotal_bytes) * 100` 쿼리 통해 clickhouse의 메모리 점유량 확인해보기
- 더하여 다양한 ClickHouse 메트릭을 Grafana 대시보드에 나타낼 수 있다.
