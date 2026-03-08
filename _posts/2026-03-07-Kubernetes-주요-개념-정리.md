---
layout: single
title:  "Kubernetes 주요 개념 정리(복습)"
categories: [Kubernetes]
tags: [Kubernetes]
toc: true
author_profile: true
---


## Docker와 Kubernetes의 관계

- `Docker가 컨테이너를 만들고 실행하기 위한 도구였다면, Kubernetes는 컨테이너를 자동으로 배포·관리·확장하는 도구이다.`
- Docker는 애플리케이션과 그 실행에 필요한 모든 환경(코드, 라이브러리, 설정 등)을 하나의 컨테이너라는 단위로 패키징한다.
- 실제 서비스에서는 수백, 수천개의 컨테이너가 돌아가기 때문에 이를 관리할 수 있어야 한다.(컨테이너가 죽으면? 트래픽이 몰리면?)
  - 이 컨테이너들을 오케스트레이션 하기 위해 Kubernetes를 사용한다.
- `Kubernetes는 여러대의 서버(Node)를 하나의 클러스터로 묶어 컨테이너의 배포,확장,네트워크,복구 등을 자동화한다.`


## Kubernetes 전체 구조

- `Kubernetes는 클러스터 구조로 동작한다.`

```
Cluster
 ├ Control Plane
 ├ Worker Node 1
 ├ Worker Node 2
 └ Worker Node 3
```

- `Control Plane(Master Node) -> 클러스터 관리`
- `Worker Node -> Pod 실행`

```
Node1 → Pod 3개
Node2 → Pod 2개
Node3 → Pod 5개
```

- 이런 식으로 여러 서버에서 컨테이너를 실행한다.

### Control Plane(Master Node)

- 구성 요소
  - API Server
  - Scheduler
  - Controller Manager
  - etcd
- 각 역할 설명
  - `API Server`: 모든 요청은 여기로 들어온다.(kubectl 명령 등) / 사용자 -> kubectl -> API Server
  - `Scheduler`: Pod를 어느 Node에 배치할지 결정한다. / Node1 -> CPU 부족, Node2 -> 여유 -> Pod는 Node2에 배치
    - 고려하는 것: CPU, Memory, Node 상태, Resource 사용량
  - `Controller Manager`: 사용자가 원하는 상태를 유지하는 역할을 한다. 
    - replicas = 3이고, 현재 상태가 Pod 2개가 실행중이라면 Controller가 Pod 1개를 추가 생성한다.
    - 대표적인 Controller: Replica Controller, Node Controller, Endpoint Controller
  - `etcd`: Kubernetes의 DB이다. 모든 상태 정보가 저장된다.
    - Pod 정보, Service 정보, Node 정보, ConfigMap, Secret
    - Key-Value Store, 분산 저장, 강한 일관성

### Worker Node

- `실제 컨테이너가 실행되는 서버이다.`
- 구성 요소
  - kubelet
  - kube-proxy
  - Container Runtime
- 각 역할 설명
  - `kubelet`: Node의 관리자, Control Plane과 통신한다.
  - `kube-proxy`: 네트워크 관리 / Service를 통해 Pod 연결을 관리한다.
  - `Container Runtime`: 컨테이너를 실행하는 엔진 / Docker, containerd, CRI-O 등이 있다.
    - 컨테이너 실행, 이미지 다운로드, 컨테이너 관리

### Pod 생성 흐름

- kubectl apply deployment.yaml로 Deployment 생성 
1. API Server가 사용자의 요청을 받고 Pod 정보를 etcd에 기록
2. Scheduler는 etcd를 계속 모니터링 -> Node 미할당 Pod 발견 -> 어느 Worker Node에 Pod를 배치하는게 적합할 지 결정 후 할당 -> API Server에 결과 전달
3. API Server가 `Pod.spec.nodeName = node1` 이런 식으로 etcd에 업데이트 및 저장
4. kubelet이 변경 감지 / kubelet이 `pull 방식으로 API Server를 지속적으로 감지한다.` 즉 Worker Node에 있는 kubelet이 내 Node에 할당된 Pod가 있는지를 계속 확인한다.
5. kubelet 명령(이미지 다운로드, 컨테이너 생성, 컨테이너 실행) -> Container Runtime 실행


## Pod(가장 작은 실행 단위)

- `Pod는 컨테이너를 실행하는 최소 단위이다.` 
- Pod에 단일 컨테이너가 실행 되거나 다중 컨테이너가 실행된다.
- Pod 내부 컨테이너는 같은 IP를 공유한다.
- 같은 네트워크, 같은 스토리지도 공유한다.
- `Pod는 일시적 객체이고, 죽으면 다시 생성된다. (죽고 다시 살아나면 IP가 변경된다.)`

## Deployment(Pod 관리)

- `Pod를 관리하는 컨트롤러이다.`
- 역할
  - Pod 생성
  - Pod 복제
  - Pod 업데이트
  - Pod 자동 복구
- replicas: 3 (Pod 3개 유지), 만약 Pod가 하나 죽으면 자동으로 새 Pod 생성

## Service 

- Pod는 IP가 계속 바뀌기 때문에 고정 IP를 할당시켜줄 수 있는 Service가 필요하다.

```
Client
  │
Service
  │
Pod1
Pod2
Pod3
```

- 역할
  - Pod 접근 주소 제공
  - 로드 밸런싱
  - 서비스 연결

## Ingress(외부 접근)

- `Ingress는 외부 트래픽을 Service로 라우팅하는 규칙이다.`
- `Ingress는 왜 필요할까?`
    - 만약 Ingress가 없다면, MSA 구조에서 각 서비스마다 Service가 존재한다.
        - Service가 3개라면 3개의 LoadBalancer가 필요해진다.(과금)
- Ingress는 `하나의 진입점`(API Gateway 역할)을 제공한다. / 경로 기반 라우팅

```
Internet
   │
Ingress
   │
Service
   │
Pods
```

- example.com/api -> api-service
- example.com/web -> web-service
- test.com/api -> api-service

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
spec:
  rules:
  - host: test.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
```

## ConfigMap / Secret

- `DB 주소나 API 키 같은 값들을 코드와 분리해서 관리하기 위해 사용한다.`
- **ConfigMap**
  - 기밀 유지가 필요 없는 일반적인 설정 데이터를 저장하는 저장소
  - 저장 데이터: 환경 변수, 설정 파일(JSON, XML, .properties 등), 호스트 이름 등.
  - 활용 예시: 개발(Dev) 환경과 운영(Prod) 환경에서 서로 다른 데이터베이스 엔드포인트를 사용할 때, 각각의 ConfigMap을 만들어두고 Pod에 주입한다.
  - 주입 방식: Pod의 환경 변수로 넣거나, 파일 형태로 볼륨 마운트해서 사용할 수 있다.

- **Secret**
  - 암호,토큰,키 등 외부에 노출하면 안되는 민감한 데이터를 저장한다.
  - 저장 데이터: DB 비밀번호, SSH 키, OAuth 토큰, SSL 인증서 등.
  - 보안 팁: 실무에서는 더욱 강력한 보안을 위해 AWS Secrets Manager나 HashiCorp Vault와 연동하여 사용하기도 한다.
- `ConfigMap이나 Secret의 내용을 수정하면 이를 참조하는 Pod는 재시작 없이도 바뀐 값을 읽어오고, 동적 설정 변경을 가능하게 할 수 있다.`

## Volume / Persistent Volume / Persistent Volume Claim

- 컨테이너는 기본적으로 stateless기 때문에 상태를 유지하기 위해 저장소가 필요하다.
- Pod 실행 → 데이터 생성 → Pod 삭제 → 데이터 사라짐
- **Persistent Volume(PV)**
  - `PV는 클러스터에서 사용할 수 있는 실제 저장소 리소스이다.`
  - AWS EBS, NFS, Local Disk 등을 Kubernetes에 등록한다.


```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: my-pv
spec:
  capacity:
    storage: 10Gi
# 10GB 저장소 제공
```

- **Persistent Volume Claim(PVC)**
  - `PVC는 사용자가 저장소를 요청하는 객체이다.`

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-pvc
spec:
  resources:
    requests:
      storage: 5Gi
# 5GB 스토리지 필요하다는 요청
```

- 사용 예시
  - PV 생성
  - PVC 생성
  - Pod에서 PVC 사용
- `PVC가 스토리지를 요청하고 조건이 맞으면 Kubernetes가 적당한 PV를 찾아 PVC에 바인딩한다.`
  - 바인딩 조건
  - Storage 크기, Access Mode, StorageClass

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: mysql-pv
spec:
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteOnce
```

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-pvc
spec:
  resources:
    requests:
      storage: 10Gi
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: mysql
spec:
  containers:
  - name: mysql
    image: mysql
    volumeMounts:
    - mountPath: "/var/lib/mysql"
      name: mysql-storage

  volumes:
  - name: mysql-storage
    persistentVolumeClaim:
      claimName: mysql-pvc
```

## 동적 프로비저닝(Dynamic Provisioning)

- `PV를 만들 필요 없이 PVC만 생성하면 자동으로 스토리지가 만들어지는 것`
- PVC 생성 -> StorageClass -> 자동 PV 생성
- 흐름
  - MySQL Pod가 10GB 스토리지를 요청(PVC 생성)
  - StorageClass 확인
  - Kubernetes가 PVC 요청을 보고 자동으로 PV 생성
  - Pod가 PVC를 mount해서 사용

```yaml
# PVC 샏성
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-pvc
spec:
  storageClassName: gp2
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

```yaml
# StorageClass 확인
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp2
provisioner: ebs.csi.aws.com
```

```yaml
# Pod가 PVC 사용
apiVersion: v1
kind: Pod
metadata:
  name: mysql
spec:
  containers:
  - name: mysql
    image: mysql
    volumeMounts:
    - mountPath: "/var/lib/mysql"
      name: mysql-storage

  volumes:
  - name: mysql-storage
    persistentVolumeClaim:
      claimName: mysql-pvc
```

```
1 PVC 생성
 ↓
2 StorageClass 확인
 ↓
3 AWS EBS 생성
 ↓
4 PV 자동 생성
 ↓
5 PVC와 PV Binding
 ↓
6 Pod mount
```

## StatefulSet

- `왜 필요할까?`
  - Deployment로 DB를 실행한다면 Pod 이름이 계속 바뀐다. 
  - Pod가 죽으면 새 Pod가 생성되면서 Pod Identity(고유성)가 유지되지 않는다.
- `StatefulSet 구조`
  - StatefulSet은 각 Pod에 고유한 ID와 스토리지를 부여한다.

```
StatefulSet
   │
   ├ mysql-0
   ├ mysql-1
   └ mysql-2
```

- 특징
  - Pod 이름이 고정된다.
  - Pod가 재시작해도 그대로 유지된다.
- `StatefulSet + PVC 구조`
  - Pod 마다 PVC가 따로 생성된다.
  - Pod 1개 ↔ PVC 1개 ↔ PV 1개
- 실제 동작 예시
  - MySQL StatefulSet이 있다면?
  - Pod 생성: mysql-0, mysql-1, mysql-2
  - 동시에 PVC 생성: mysql-data-mysql-0, mysql-data-mysql-1, mysql-data-mysql-2
  - Kubernetes가 PVC -> PV 자동 생성(Dynamic provisioning)
- Pod 재시작 시 동작 흐름
  - mysql-1 Pod 삭제
  - 새 Pod 생성: mysql-1 다시 생성
  - PVC는 그대로 mysql-data-mysql-1

- `Deployment vs StatefulSet 차이`

|              | Deployment | StatefulSet |
| ------------ | ---------- | ----------- |
| Pod identity | 없음         | 고정          |
| 스토리지         | 공유 가능      | Pod별 고유     |
| 사용 용도        | stateless  | stateful    |
| 예            | 웹 서버       | DB          |


![img.png](/assets/images/StatefulSet.png)


## Headless Service

- `일반 Service(ClusterIP)`
  - Service가 하나의 IP를 가짐
  - 내부적으로 로드밸런싱
  - 요청을 랜덤 Pod로 전달
  - api-service:80 -> Pod1 or Pod2 or Pod3 랜덤으로 전달
- `하지만 이런 방식을 사용한다면 발생하는 문제점은?` 
  - mysql-0 -> Primary
  - mysql-1 -> Replica
  - mysql-2 -> Replica
  - `Replica로 write 요청한다면? or 특정 Pod에 직접 연결이 필요하다면?`
  - 그래서 Headless Service를 사용한다.
- `Headless Service는 ClusterIP가 없는 Service다.`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mysql
spec:
  clusterIP: None
```

- Headless Service는 `로드밸런싱을 하지 않는다.`
- StatefulSet과 같이 사용하면 각 Pod의 DNS가 생성된다.
  - `즉 각 Pod 마다 고유 주소를 갖는다.`


```
mysql-0.mysql.default.svc.cluster.local
mysql-1.mysql.default.svc.cluster.local
mysql-2.mysql.default.svc.cluster.local
```

|           | 일반 Service | Headless Service |
| --------- | ---------- | ---------------- |
| ClusterIP | 있음         | 없음               |
| 로드밸런싱     | 있음         | 없음               |
| DNS       | Service 하나 | Pod별             |
| 사용        | 웹 서버       | DB / Stateful    |


- 대표적으로 Headless Service가 사용되는 서비스들
  - MySQL Cluster
  - PostgreSQL Cluster
  - Kafka
  - Cassandra
  - Redis Cluster
  - Elasticsearch

```
일반 Service = Load Balancing
Headless Service = Pod 직접 접근
AND
StatefulSet + Headless Service -> 항상 같이 동작한다.
```


## NodePort vs LoadBalancer vs Ingress

| 구분 | NodePort | LoadBalancer | Ingress |
|---|---|---|---|
| 계층 | L4 (Transport) | L4 (Transport) | L7 (Application) |
| 비용 | 무료 | 비쌈 (개당 과금) | 저렴 (하나로 공유 가능) |
| 주소 형태 | IP:Port | IP 또는 DNS | 도메인/경로 |
| 주요 용도 | 개발/테스트 | 단일 서비스 노출 | 복수 서비스 / 운영 환경 |


- 동작 흐름
- 1.내부 통로 만들기(Service-ClusterIP): 가장 먼저 Pod들을 묶어 클러스터 내부에서만 통하는 주소를 만든다.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-service # Ingress가 이 이름을 보고 찾아옵니다.
spec:
  type: ClusterIP   # 클러스터 내부용 IP만 할당 (가장 일반적)
  selector:
    app: my-api     # 'app: my-api' 라벨이 붙은 Pod들을 묶음
  ports:
    - protocol: TCP
      port: 80      # 서비스가 노출할 포트
      targetPort: 8080 # 실제 컨테이너(Spring Boot 등)가 떠 있는 포트
```
- 2.외부 입구 만들기(Ingress): 위에서 만든 api-service를 외부 도메인과 연결해준다.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    # AWS SAA 실습 시 중요! ALB를 만들라고 명령하는 주석입니다.
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
spec:
  rules:
  - host: my-app.com       # 사용자가 접속할 도메인
    http:
      paths:
      - path: /api         # 'my-app.com/api'로 들어오면
        pathType: Prefix
        backend:
          service:
            name: api-service # 1번에서 만든 서비스 이름!
            port:
              number: 80
```

- Ingress를 통해 생성된 ALB -> 경로애 따라 Service에 요청 -> Service는 가장 적합한 Pod에 전달

- 여기서 궁금증
  - `만약 Pod 하나가 응답을 안하거나 먹통이 되면 Service는 어떻게 판단해서 Pod에 전달할까?`

## Probe

- `Service가 어떤 Pod가 지금 일을 할 수 있는 상태인지를 판단하는 기준`
- `Readiness Probe(준비 완료 상태 확인)`
  - 역할: "지금 손님(트래픽)을 받을 준비가 됐니?"
  - 상황: 애플리케이션(예: Spring Boot)이 처음 뜰 때 DB 연결도 해야 하고, 설정 파일도 읽어야 한다. 그동안은 트래픽을 받으면 에러가 납니다.
  - 결과: 실패하면 해당 Pod을 서비스(Endpoints) 목록에서 일시적으로 제외합니다. 즉, 서비스가 이 Pod로는 트래픽을 보내지 않는다. (Pod가 죽지는 않음)
  
- Liveness Probe(생존 상태 확인)
  - 역할: "너 아직 살아있니? 혹시 먹통(Deadlock) 된 거 아니야?"
  - 상황: 앱이 실행 중인데 갑자기 무한 루프에 빠지거나 내부 오류로 응답을 못 하는 상태가 될 수 있다.
  - 결과: 실패하면 쿠버네티스가 해당 Pod을 강제로 죽이고 새로 하나를 띄운다.(Restart)

    
- Deployment 파일의 Pod 템플릿 부분 Probe 설정 예시


```yaml
spec:
  containers:
  - name: my-api
    image: my-api-image:v1
    # [Readiness: 준비될 때까지 트래픽 보내지 마!]
    readinessProbe:
      httpGet:
        path: /api/ready
        port: 8080
      initialDelaySeconds: 5 # 앱 실행 후 5초 뒤부터 확인 시작
      periodSeconds: 5       # 5초마다 확인
    
    # [Liveness: 응답 없으면 재시작시켜!]
    livenessProbe:
      httpGet:
        path: /api/live
        port: 8080
      initialDelaySeconds: 15 # 충분히 뜰 시간을 준 뒤 확인
      periodSeconds: 20
```

## HPA(Horizontal Pod Autoscaler)

- `Pod의 개수를 동적으로 조절할 때는 HorizontalPodAutoscaler라는 리소스를 정의한다.`

- hpa.yaml 예시

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: my-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-service-deployment # 어떤 Deployment를 늘릴지 지정
  minReplicas: 2  # 최소 Pod 개수
  maxReplicas: 10 # 최대 Pod 개수 (폭주 시 대비)
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70 # [임계점] CPU 사용량이 평균 70%를 넘으면 Pod 추가!
```

- 필수 조건: 이 설정을 하려면 Pod 설정 파일(Deployment)에 반드시 resources.requests (최소 필요한 자원량)가 적혀 있어야 한다. 그래야 70%라는 기준을 계산할 수 있다.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-deployment
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-api
  template:
    metadata:
      labels:
        app: my-api
    spec:
      containers:
      - name: my-api
        image: my-api-image:v1
        ports:
        - containerPort: 8080
        
        # [핵심] HPA가 계산을 하기 위한 기준점 설정
        resources:
          requests:
            memory: "256Mi"
            cpu: "500m"      # 500m은 0.5 코어를 의미합니다 (1000m = 1 CPU)
          limits:
            memory: "512Mi"  # 이 수치를 넘어가면 컨테이너가 종료될 수 있음 (OOM)
            cpu: "1000m"     # 이 수치를 넘지 못하도록 제한함 (Throttling)
```

