---
layout: single
title:  "Prometheus & Grafana 개념 정리 및 실습"
categories: [Prometheus & Grafana]
tags: [Prometheus]
toc: true
author_profile: true
---


## Prometheus & Grafana의 기본 개념

- `Prometheus`
  - CPU 활용률
  - 남은 메모리
  - API 요청
  - 에러 횟수
  - ... 등을 주기적으로 가져와서 저장한다. (Pull 방식)
- `Grafana`
  - Prometheus가 모은 데이터를 그래프로 보여주는 화면
  - Prometheus는 숫자만 저장하기 때문에, Grafana를 통해 대시보드로 만든다.

---

## 활용 흐름

`서버/앱 -> (숫자 데이터 제공) -> Prometheus(수집 + 저장) -> Grafana(시각화) -> 대시보드로 확인 가능`

## prometheus.yml

- 왜 필요한가? 
  - Prometheus에게 어디에서 데이터를 가져올지 알려주는 설정파일이다.

- 예시

```yaml
global:
  scrape_interval:     15s # 15초마다 메트릭을 수집 (기본값 1분)
  evaluation_interval: 15s # 15초마다 규칙을 평가

# 규칙 파일을 불러오는 설정
rule_files:
  - "first_rules.yml"
  # - "second_rules.yml"

# 메트릭을 수집할 대상(Target) 설정
scrape_configs:
  # 작업 이름 (프로메테우스 자체 모니터링)
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # 추가적인 애플리케이션 모니터링 예시 (예: Node Exporter)
  - job_name: 'node_exporter'
    static_configs:
      - targets: ['localhost:9100']

```

## Prometheus & Grafana를 Docker compose로 띄워보기 실습 정리

- docker-compose.yml

```yaml
services:   # 실행할 컨테이너(서비스) 목록 정의

  prometheus:   # 서비스 이름 (docker-compose 내부 이름)
    image: prom/prometheus   # 사용할 도커 이미지 (Prometheus 공식 이미지)
    container_name: prometheus   # 생성될 컨테이너 이름
    ports:
      - "9090:9090"   # (호스트포트:컨테이너포트)
        # 내 PC 9090으로 접속하면 컨테이너 9090으로 연결
      # → http://localhost:9090 에서 Prometheus UI 접근 가능
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
        # 현재 디렉토리의 prometheus.yml 파일을
        # 컨테이너 내부 설정 경로로 마운트 (바인드 마운트)
      # → 설정 파일을 로컬에서 수정 가능

  grafana:   # Grafana 서비스 정의
    image: grafana/grafana   # Grafana 공식 이미지
    container_name: grafana   # 컨테이너 이름
    ports:
      - "3000:3000"   # http://localhost:3000 으로 Grafana 접속 가능
    depends_on:
      - prometheus
      # prometheus 컨테이너가 먼저 실행되도록 의존성 설정
```

- prometheus.yml

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

- localhost:3000 Grafana 접속 
- Grafana가 Prometheus 데이터를 보려면 Data Source로 Prometheus 등록
- URL 입력
  - http://prometheus:9090
  - **lcoalhost:9090이 아니라 prometheus:9090 인 이유?**
  - **docker compose로 띄우면 같은 네트워크로 묶임 -> 같은 네트워크의 컨테이너끼리는 서비스 이름이 곧 호스트 이름이 된다.**


- `localhost:9090 Prometheus에서 up 입력후 Execute -> PromQL 쿼리`
- 결과 : up{instance="localhost:9090", job="prometheus"} = 1
- up -> 서비스가 살아 있는지 묻는 메트릭
- instance="localhost:9090" -> Prometheus 자기 자신
- job="prometheus" -> prometheus.yml에서 설정한 job_name
- 값 1 -> 살아있음 (0이면 죽은 거)


- **Grafana 대시보드로 시각화 해보기**
  - Dashboards -> New Dashboard
  - up 쿼리 날려보기 -> 그래프에 표시됨 확인 완료


## 실습 흐름 정리 

- Docker Compose를 통해 Prometheus, Grafana 띄우기
- prometheus.yml 에서 localhost:9090(자기 자신) 에서 데이터 가져오게 설정
- Prometheus는 자기 자신 메트릭 수집 + 저장
- Grafana Datasource 설정을 통해 prometheus:9090의 데이터를 요청 받을 수 있게 설정
- 대시보드 -> up 쿼리 결과 그래프로 시각화 완료

## 실전 예시 

- 현재는 Prometheus가 자기 자신만 모니터링하고 있다.
- 실제 프로젝트에서는 다른 서비스들을 붙이는게 핵심이다.

```yaml
scrape_configs:
  - job_name: 'backend-api'
    static_configs:
      - targets: ['api-server:8080']
  - job_name: 'ai-service'
    static_configs:
      - targets: ['fastapi:8000']
```

## 더 나아가보기 

- Prometheus를 통해 CPU 활용률도 확인할 수 있다고 했다.
- 이것도 확인해보고 싶었지만 Prometheus는 자기 자신만 모니터링 하고 있다.
- Prometheus 자체는 CPU 메트릭을 안뽑는다고 하여 `Node Exporter`를 사용해보기로 했다.

## Node Exporter란?

- Prometheus에게 시스템 정보를 제공해주는 중간 다리 역할
- 예시 흐름
  - `Mac 시스템 (CPU/메모리/디스크) -> Node Exporter (시스템 메트릭을 HTTP로 노출) -> Prometheus (Node Exporter한테서 데이터 수집) -> Grafana (시각화)`

## Node Exporter로 시스템 메트릭 시각화 실습 해보기

- docker-compose.yml

```yaml
services:
  prometheus:
    image: prom/prometheus
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    container_name: grafana
    ports:
      - "3000:3000"
    depends_on:
      - prometheus

  node-exporter:
    image: prom/node-exporter
    container_name: node-exporter
    ports:
      - "9100:9100"
```

- prometheus.yml

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
```

- localhost:9090에서 up
  - up{instance="node-exporter:9100", job="node-exporter"}
  - up{instance="localhost:9090", job="prometheus"}
  - Node Exporter 확인 가능
- 목표였던 `CPU 메트릭 쿼리 날려보기`
  - node_cpu_seconds_total
  - 결과
```
node_cpu_seconds_total{cpu="0", instance="node-exporter:9100", job="node-exporter", mode="idle"}	6866.75
node_cpu_seconds_total{cpu="0", instance="node-exporter:9100", job="node-exporter", mode="iowait"}	1.43
node_cpu_seconds_total{cpu="0", instance="node-exporter:9100", job="node-exporter", mode="irq"}	0
node_cpu_seconds_total{cpu="0", instance="node-exporter:9100", job="node-exporter", mode="nice"}	0
node_cpu_seconds_total{cpu="0", instance="node-exporter:9100", job="node-exporter", mode="softirq"}	16.91
node_cpu_seconds_total{cpu="0", instance="node-exporter:9100", job="node-exporter", mode="steal"}	0
node_cpu_seconds_total{cpu="0", instance="node-exporter:9100", job="node-exporter", mode="system"}	2.75
node_cpu_seconds_total{cpu="0", instance="node-exporter:9100", job="node-exporter", mode="user"}	8.03
node_cpu_seconds_total{cpu="1", instance="node-exporter:9100", job="node-exporter", mode="idle"}	6878.31
node_cpu_seconds_total{cpu="1", instance="node-exporter:9100", job="node-exporter", mode="iowait"}	1.49
node_cpu_seconds_total{cpu="1", instance="node-exporter:9100", job="node-exporter", mode="irq"}	0
node_cpu_seconds_total{cpu="1", instance="node-exporter:9100", job="node-exporter", mode="nice"}	0
node_cpu_seconds_total{cpu="1", instance="node-exporter:9100", job="node-exporter", mode="softirq"}	4.84
node_cpu_seconds_total{cpu="1", instance="node-exporter:9100", job="node-exporter", mode="steal"}	0
node_cpu_seconds_total{cpu="1", instance="node-exporter:9100", job="node-exporter", mode="system"}	2.76
node_cpu_seconds_total{cpu="1", instance="node-exporter:9100", job="node-exporter", mode="user"}	8.18
```  

  - 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)
  - 결과

```
{instance="node-exporter:9100"}	0.16443348221248755
```

- CPU 사용률 늘리고 다시 확인해보기
  - docker run --rm -it alpine sh -c "apk add --no-cache stress-ng && stress-ng --cpu 4"
  - stress-ng 이미지 사용해서 부하 줘보기
- Grafana를 통해 그래프로 확인해보기
  - Code 모드로 100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[10s])) * 100) 쿼리 날려보기
  - 부하 안줬을때 0에서 줬을때 40으로 그래프 변동하는것 확인 완료


## Mac + Docker Desktop 구조 파헤치기

```

[ Mac OS ]
    ↓
[ Docker Desktop VM (Linux 가상머신) ]
    ↓
[ stress 컨테이너 ]
[ node-exporter 컨테이너 ]
[ prometheus 컨테이너 ]
[ grafana 컨테이너 ]

```

- stress 컨테이너는 Mac OS에 직접 부하를 주는게 아닌 Docker Desktop 안의 Linux VM에 부하를 주는 것이다.
- `그렇다면 node-exporter는 누구의 메트릭을 보내는걸까?`
  - node-exporter는 기본적으로 내가 실행되고 있는 OS의 /proc을 읽어서 메트릭을 만든다.
  - 그렇다면 현재 node-exproter는 Docker 컨테이너 안에서 실행중이다.
  - 이는 Docker VM의 OS 메트릭을 읽는다는 것을 의미한다.
  - `즉 stress 컨테이너가 CPU 사용 ↑ -> Docker VM CPU 사용 ↑ -> node-exporter가 VM의 CPU 상태 수집 -> Prometheus가 scrape -> Grafana가 시각화`
  - 이 흐름으로 전개된다.
- 정리
  - Mac OS 위에 Docker Desktop VM이 동작한다.
  - 이 VM 위에서 컨테이너들이 실행된다.
  - 실행되는 컨테이너가 부하를 받으면 VM에 할당된 자원을 사용한다.
  - node-exporter 컨테이너가 메트릭을 생성 + 노출하고 Prometheus 컨테이너가 메트릭을 주기적으로 요청(http://node-exporter:9100/metrics)하고 Pull 해와서 저장한다.


## 실습 화면

![실습화면](/assets/images/GrafanaDashBoard.png)
![실습화면](/assets/images/GrafanaImportDashboard.png)

- CPU 4개에 부하를 주는 컨테이너 실행
- Docker Desktop VM의 CPU limit = 10으로 설정되어있음 (Docker Desktop -> Setting -> Resources에서 확인 가능)
- 4개에 부하를 주기때문에 4/10 -> 40까지 사용률 올라가는 것 확인 가능
