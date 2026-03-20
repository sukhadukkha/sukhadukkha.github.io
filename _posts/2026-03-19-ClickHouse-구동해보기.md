---
layout: single
title:  "ClickHouse 구조 파악 및 직접 구동해보기"
categories: [소모임(discipline)]
tags: [소모임]
toc: true
author_profile: true
---


## ClickHouse란?

- MySQL 같은 일반 DB와 다르게 분석용으로 특화된 DB다.
- 최근 데이터 엔지니어링과 인프라 모니터링(로그 분석) 분야에서 각광받는 OLAP(Online Analytical Processing) DB다.
- `ClickHouse 특징`
  - 열 지향(Column-Oriented) DB
  - Row-oriented (MySQL 등): 이름, 나이, 주소를 한 줄로 묶어서 저장. (특정 사용자 정보를 찾을 때 빠름)
  - Column-oriented (ClickHouse): 모든 이름들만 따로, 모든 나이들만 따로 모아서 저장. (수백만 명의 평균 나이를 구할 때 압도적으로 빠름)
- 핵심 3요소
  - `MergeTree 엔진 (데이터 저장의 핵심)`
    - ClickHouse에서 가장 많이 쓰이는 엔진입니다. LSM Tree 구조와 유사하게 데이터를 일단 쌓아두고, 백그라운드에서 Merge(병합)하면서 정렬과 인덱싱을 수행합니다.
    - Sparse Index: 모든 행에 인덱스를 거는 게 아니라, 일정 간격마다 인덱스를 걸어 메모리 효율을 극대화합니다.
    - Partitions: 데이터를 날짜 등으로 나눠서 필요한 부분만 빠르게 읽습니다.
  - `벡터화 쿼리 실행 (Vectorized Query Execution)`
    - 데이터를 한 건씩 처리하는 게 아니라, CPU의 SIMD(Single Instruction, Multiple Data) 명령어를 활용해 수천 개의 데이터를 한 번에 처리합니다. "데이터를 통째로 넘겨서 한 번에 계산한다"고 이해하면 된다.
  - `분산 및 복제 (Sharding & Replication)`
    - Sharding: 데이터를 여러 서버에 쪼개서 저장하여 성능을 수평 확장(Scale-out)합니다.
    - Replication: 데이터 복사본을 만들어 서버 하나가 죽어도 서비스가 유지되게 합니다.
    - ClickHouse Keeper: 예전에는 ZooKeeper를 썼지만, 최근에는 자체 구현체인 ClickHouse Keeper를 써서 복제 서버 간의 상태를 동기화합니다.

```
일반 RDB (MySQL, PostgreSQL)
→ 행(Row) 단위 저장
→ 트랜잭션, CRUD에 강함

ClickHouse
→ 열(Column) 단위 저장
→ 대용량 데이터 집계/분석에 강함
→ "지난 1달간 CPU 평균" 같은 쿼리가 압도적으로 빠름
```

- `언제 사용할까?`
  - 쌓아둔 바대한 데이터를 순식간에 분석해서 결과를 뽑아내야 할 때 사용
  - 데이터를 넣는 것 보다 복잡하게 계산하는 것이 더 중요해지는 시점
- 주요 활용 사례
  - `대규모 로그 및 이벤트 분석`: 보통 로그 분석하면 ELK(Elasticsearch) 스택을 떠올리지만, 데이터 양이 많아지면 서버 비용이 감당 안 될 때가 있습니다. ClickHouse는 압축률이 매우 높고 검색 속도가 빨라서 수조 건의 로그를 분석하는 용도로 자주 쓰입니다.
  - `실시간 통계 대시보드`: 어드민 페이지나 서비스 분석 툴에서 "지난 한 달간 지역별/연령별 매출 추이" 같은 그래프를 보여줘야 할 때입니다.
  - `시계열 데이터 및 모니터링`: 아까 공부한 OpenTelemetry나 Prometheus의 데이터를 영구적으로 저장하고 분석할 때 씁니다. 특히 트레이싱(Tracing) 데이터처럼 양이 방대한 데이터를 저장하기에 아주 효율적입니다
  - `광고/핀테크 데이터 분석`: 초당 수만 건씩 쏟아지는 광고 클릭 데이터나 금융 거래 내역을 실시간으로 집계해서 사기 탐지(FDS)를 하거나 광고 효율을 계산할 때 사용합니다.
- `언제 사용하면 안될까?`
  - 회원 정보 수정이 빈번한 서비스 DB로는 절대 쓰지 마세요. (열 기반이라 한 줄씩 수정하는 게 매우 비효율적입니다.)
  - 트랜잭션(Transaction)이 중요해서 하나라도 틀리면 안 되는 결제 로직 등에는 MySQL 같은 전통적인 RDBMS가 훨씬 낫습니다.

- `왜 빠를까?`

| 특징           | 효과                                                                 |
|----------------|----------------------------------------------------------------------|
| 높은 압축률     | 같은 열에는 비슷한 데이터가 많아 압축이 잘 되고, 디스크 I/O가 줄어듭니다. |
| 필요한 열만 읽기 | SELECT SUM(price)를 하면 'price' 열만 읽고 나머지는 무시합니다.        |
| 멀티코어 활용   | 하나의 쿼리를 처리할 때 서버의 모든 CPU 코어를 다 활용합니다.           |


- 궁금한 점
  - `필요한 열만 읽기 -> MySQL도 저런식으로 동작하지 않나?`
- 해결
  - MySQL 같은 일반적인 RDBMS는 데이터를 저장할 때 "한 줄(Row)"을 통째로 묶어서 디스크의 한 블록에 저장합니다.
  - 저장 구조: [ID, 이름, 나이, 가격], [ID, 이름, 나이, 가격] ... 이런 순서로 디스크에 붙어 있습니다.
  - SELECT SUM(price) 실행 시
    - 엔진은 price가 포함된 데이터 블록을 통째로 메모리에 올립니다. -> 이때 내가 원하지 않는 '이름', '나이', 'ID' 데이터까지 전부 메모리에 같이 올라옵니다. -> 메모리(또는 디스크 I/O) 입장에서 보면, 정작 필요한 건 price뿐인데 쓸데없는 데이터까지 다 읽어야 하므로 불필요한 리소스 낭비가 발생합니다.
  - ClickHouse는 데이터를 저장할 때 "열(Column)"끼리 따로 모아서 저장합니다. 아예 파일 자체가 다를 수도 있습니다.
  - 저장 구조: 
    - `ID 파일`: [1, 2, 3, ...]
    - `이름 파일`: [Kim, Lee, Park, ...]
    - `가격 파일`: [100, 200, 300, ...]
  - SELECT SUM(price) 실행 시
    - ClickHouse는 오직 가격 데이터가 들어있는 파일/블록만 찾아가서 읽습니다. -> '이름'이나 '나이' 데이터는 아예 건드리지도 않습니다. 쳐다보지도 않죠. -> 필요한 데이터만 딱 골라서 읽기 때문에 디스크 I/O가 획기적으로 줄어들고, 데이터 압축 효율도 압도적으로 높습니다. (숫자들만 모여 있으니까요!)


| 특징           | MySQL (OLTP)                              | ClickHouse (OLAP)                          |
|----------------|-------------------------------------------|--------------------------------------------|
| 주요 목적       | 데이터의 무결성 (주문, 결제, 회원가입)     | 데이터 분석 (통계, 집계, 로그 분석)        |
| 데이터 수정     | UPDATE, DELETE가 매우 잦음                | 거의 INSERT만 발생함 (수정/삭제는 느림)     |
| 쿼리 성격      | 특정 ID의 데이터 1건 조회                 | 수억 행의 특정 컬럼들을 합산/평균           |
| 데이터 양       | 수백만 ~ 수천만 건 (적당함)               | 수십억 ~ 수조 건 (빅데이터)                 |


## 구동시켜보기 + 실습해보기 

- docker-compose.yml 생성

```yaml
version: '3.7' # Docker Compose 파일 형식 버전

services:
  # [1] ClickHouse 서버: 실제 데이터 저장 및 고성능 연산 엔진
  ch-server:
    image: clickhouse/clickhouse-server:latest # 공식 최신 서버 이미지 사용
    container_name: clickhouse-server # 컨테이너 이름을 고정하여 네트워크 통신 시 호스트명으로 사용
    environment:
      # 컨테이너 실행 시 'practice'라는 이름의 데이터베이스를 자동으로 생성
      - CLICKHOUSE_DB=practice
      # 기본 유저(default)에게 SQL을 통한 사용자/권한 관리 기능을 부여 (학습 시 편의성 제공)
      - CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1
    ports:
      - "8123:8123" # HTTP 포트: 웹 GUI(Play UI, Tabix) 및 REST API 통신용
      - "9000:9000" # Native 포트: CLI 클라이언트 및 고성능 드라이버 전용
    ulimits:
      # ClickHouse는 컬럼 기반 저장 방식이라 한꺼번에 수많은 파일을 열어야 함
      # OS 기본 파일 열기 제한(보통 1024)을 초과해 서버가 멈추는 것을 방지하기 위한 필수 설정
      nofile:
        soft: 262144 # 부팅 시 기본 허용치
        hard: 262144 # 시스템 전체에서 허용하는 최대치

  # [2] ClickHouse 클라이언트: 서버에 명령을 내리고 결과를 확인하는 도구
  ch-client:
    image: clickhouse/clickhouse-client:latest # 서버와 동일한 버전의 공식 클라이언트 이미지
    container_name: clickhouse-client # 클라이언트 컨테이너 이름
    # 도커 컨테이너는 실행할 프로세스가 없으면 즉시 자동 종료됨
    # 'sleep infinity' 명령어를 통해 컨테이너가 꺼지지 않고 계속 살아있도록 유지 (언제든 접속 가능하게)
    entrypoint: ["/bin/sh", "-c", "sleep infinity"]
```

- ClickHouse는 기본적으로 Server, Client가 분리되어 있다.
  - `ch-server`: 실제 데이터를 저장하고 쿼리를 처리하는 엔진
  - `ch-client`: 사용자가 SQL문을 입력하면 서버로 전달하고 결과를 받아와서 화면에 뿌려주는 인터페이스
- `entrypoint` 설명
  - `/bin/sh`: 누가?
    - 의미: 유닉스/리눅스 시스템의 가장 기본적인 Shell 경로
    - 역할: 사용자가 입력한 명령어를 운영체제가 알아들을 수 있게 전달
    - 왜 쓸까?: 컨테이너 안에서 복합적인 명령어나 스크립트를 실행하기 위해
  - `-c`: 어떻게?
    - 의미: Command 약자
    - 역할: 지금 바로 뒤에 나오는 문자열을 명령어로 인식해서 실행해라
  - `sleep infinity`: 무엇을
    - sleep: 프로세스를 지정된 시간동안 아무것도 하지 않고 대기 상태로
    - infinity: 무한대로
    - 즉 영원히 대기해라
- `ch-client` 컨테이너는 원래 서버에 접속해서 쿼리를 날릴 때만 잠깐 켜지는 도구라 그냥 놔두면 바로 꺼져버린다.
- 이 컨테이너를 계속 켜두고 필요할 때마다 `docker exec` 명령으로 들어가서 사용하기 위해 `entrypoint`를 설정한다.


- `CLI로 Click House 실습해보기`
  - client 컨테이너 접속하기 : `docker exec -it clickhouse-client clickhouse-client --host clickhouse-server`
  - 나(-it)를 clickhouse-client라는 컨테이너 안으로 보내서, 그 안에 설치된 clickhouse-client 프로그램을 실행시키고, 옆집에 있는 clickhouse-server에 접속시켜라


```
1. 테이블 생성

CREATE TABLE users_activity (
    user_id UInt32,
    event_type String,
    event_time DateTime,
    amount Float32
) 
ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_type, event_time);

2. 1100만건 데이터 삽입해보기

INSERT INTO users_activity
SELECT
    number % 10000 AS user_id,
    concat('type_', toString(number % 5)) AS event_type,
    now() - rand() % 1000000 AS event_time,
    rand() % 1000 AS amount
FROM numbers(11000000);

3. 분석 및 성능 확인

-- 집계 쿼리
SELECT event_type, sum(amount) FROM users_activity GROUP BY event_type;

결과

┌─event_type─┬────────avg(amount)─┐
│ type_2     │ 499.20155454545454 │
│ type_0     │  499.5797090909091 │
│ type_4     │ 499.64886454545456 │
│ type_1     │ 499.62358363636366 │
│ type_3     │          499.59951 │
└────────────┴────────────────────┘

5 rows in set. Elapsed: 0.038 sec. Processed 11.00 million rows, 143.00 MB (288.62 million rows/s., 3.75 GB/
-> 집계 쿼리에도 엄청난 성능 확인 가능! 
```