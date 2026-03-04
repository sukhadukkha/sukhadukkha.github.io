---
layout: single
title:  "Grafana dashboard 만들어보기 (CPU 사용률 + 메모리 사용률 + 디스크 사용률 + 마운트란?)"
categories: [Prometheus & Grafana]
tags: [Prometheus]
toc: true
author_profile: true
---



## CPU 패널 만들어보기

- PromQL
  - `100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)`
- 패널 제목 변경 (Title)
- 단위 설정 
  - Unit -> Percent(0-100)
- Y축 범위 고정 
  - stadard options -> Min=0, Max=100
- Save Dashboard

## Memory 패널 만들어보기

- PromQL
  - `(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100`
- 패널 제목 변경
- 단위설정
  - Unit -> Percent(0~100)
- ... 

## Disk 패널 만들어보기

- PromQL
  - `(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100`
  - mountpoint가 /가 아니어서 화면에 아무것도 출력되지 않는 문제 발생
  - Prometheus에서 `node_filesystem_avail_bytes` 쿼리를 통해 mountpoint 확인
  - 이 쿼리는 Node Exporter가 수집한 파일시스템 메트릭이다.
  - 이 쿼리를 통해 mountpoint /etc/hostname, /etc/hosts, /etc/resolv.conf 확인 가능
- 왜 이 문제 발생했을까
  - Node Exporter는 컨테이너 안에서 실행되고있음 -> Mac의 실제 디스크가 아닌 컨테이너 내부 파일 시스템을 보는 중
- `(1 - (node_filesystem_avail_bytes{mountpoint="/etc/hostname"} / node_filesystem_size_bytes{mountpoint="/etc/hostname"})) * 100`
- 뒤의 과정은 동일

## 마운트란? 

- `어떤 저장 공간을 특정 경로에 연결하는 것`
- USB를 꽂으면 `/Volumes/USB` 이런 경로로 접근 가능 -> USB 라는 저장 공간을 /Volumes/USB 경로에 연결한 것
- `컨테이너에서 마운트가 왜 필요할까?`
  - 컨테이너는 완전히 독립된 공간, 호스트(Mac)랑 파일 공유 X
  - Docker가 컨테이너 시작할 때, 호스트의 /etc/hostname, 호스트의 /etc/resolv.conf 를 자동으로 넣어준다.
- 왜 이 3개일까?
  - /etc/hostname → 컨테이너 이름 (container_name)
  - /etc/hosts → 컨테이너끼리 이름으로 통신하려면 필요 (아까 prometheus:9090 같은 것)
  - /etc/resolv.conf → DNS 설정, 컨테이너 안에서 인터넷 되려면 필요
- **컨테이너는 VM 위에서 돌고, VM의 저 파일들이 컨테이너에 마운트된다.**

## 실습 화면

![구조](/assets/images/GrafanaDashboard2.png)

