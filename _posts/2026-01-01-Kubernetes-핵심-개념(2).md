---
layout: single
title:  "Kubernetes 선언적 접근 방식"
categories: [Kubernetes]
tags: [Kubernetes]
toc: true
author_profile: true
---


## 명령적 접근 방식의 문제점

- 명령을 다 외워야함.
- 명령을 계속 반복해야함.

## 선언적 접근 방식

- yaml 파일을 클러스터에 적용
- apply 명령을 통해 yaml 파일을 클러스터에 적용
- 배포에 대한 정보 포함
- config 파일을 사용하여 원하는 목표 상태 정의
- 쿠버네티스는 목표 상태로 만들기 위해 스스로 작업 실행

---

## 구성 파일(deployment) 선언해보기

- deployment.yml 파일 생성
  - 파일 이름은 상관 없음. yml 파일 생성 필요

```yaml
apiVersion: apps/v1
kind: Deployment       # 만들고자 하는 리소스의 종류
metadata:
  name: second-app-deployment           # 이 Deployment의 고유 이름. kubectl get deployments 했을 때 나타나는 이름
spec:          # Deployment가 Pod를 어떻게 다룰지 정의
  replicas: 1           # 항상 이 숫자만큼의 Pod가 떠있어야 한다는 선언
  selector:             # Deployment가 관리할 Pod를 찾는 설정
    matchLabels:        # 여기에 적힌 Label을 가진 Pod 들만 Deployment가 책임지고 관리함
      app: second-app
      tier: backend
  template:             # 실제 생성될 Pod의 설계도
    metadata:
      labels:           # 생성될 Pod들에게 붙이는 이름표 (이 경우 Labels에 app=second-app, tier=backend 달고 Pod 생성됨)
        app: second-app
        tier: backend
    spec:                # 생성될 pod의 spec 설정
      containers:        #
        - name: second-node    # 컨테이너의 이름
          image: sukhadukkha/kub-first-app          # 사용할 도커 이미지 주소
      #  - name: ...      한 Pod 안에 여러 컨테이너 생성 가능
      #    image: ...
```

- 

- kubectl apply -f deployment.yaml 실행하면 에러 발생
  - selector 필드 필요
- matchLabels에 지정된 것들만 deployment에 의해 제어된다.
  - deployment에 속한 pod를 deployment에 알려주는 역할


## Service 선언해보기

- service 객체는 pod를 클러스터나 외부 세계에 노출하는 역할
- service.yaml 파일 추가
  - 이 애플리케이션 배포를 위한 service 정의 
```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
spec: 
  selector: 
    app: second-app          # second-app 라벨 가진 Pod 관리
  ports:
    - protocol: 'TCP'
      port: 80
      targetPort: 8080
  # - protocol: 'TCP'
  #   port: 443
  #   targetPort: 443
  type: LoadBalancer
```

- kubectl apply -f service.yaml 실행하여 service 생성
- kubectl get service 명령으로 생성된 service 확인 가능
- minikube service backend로 서비스 실행 가능

## 리소스 업데이트 & 삭제

- 리소스 업데이트
  - yaml 파일에서 변경 후 파일을 다시 적용
    - kubectl apply -f deployment.yaml
- 리소스 삭제 
  - kubectl delete deployment second-app-deployment
  - kubectl delete -f=deployment.yaml -f=service.yaml

## 다중 vs 단일 config 파일

- master-deployment.yaml 파일 생성
```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
spec:
  selector:
    app: second-app
  ports:
    - protocol: 'TCP'
      port: 80
      targetPort: 8080
  # - protocol: 'TCP'
  #   port: 443
  #   targetPort: 443
  type: LoadBalancer

---

apiVersion: apps/v1
kind: Deployment
metadata:
  name: second-app-deployment
spec: 
  replicas: 1
  selector:
    matchLabels:
      app: second-app
      tier: backend
  template:                  
    metadata:
      labels:
        app: second-app
        tier: backend
    spec:
      containers:
        - name: second-node
          image: sukhadukkha/kub-first-app:2
     #  - name: ...
     #    image: ...
```

- service와 deployment를 하나에 결합하는 경우 service를 먼저 배치하는 것이 좋다.
- 객체는 한 번에 생성되고 분석되지 않는다. 지속적으로 모니터링하며 생성되고 분석된다.


## Label & Selector에 대한 추가

- matchExpression(보통은 matchLabels 사용)
  - 더 많은 구성 옵션을 가진 항목을 선택하는 방법
```yaml
spec: 
  replicas: 1
  selector:
  #  matchLabels:
  #    app: second-app
  #    tier: backend
    matchExpression:
      - {key: app, operator: In,values: [second-app, first-app]}  # In,NotIn,Exists,DoNotExist
```
- deployment.yaml, service.yaml 파일의 metadata에 labels.group 에 example 추가
- kubectl delete deployments,services -l group=example 명령을 통해 이러한 레이블이 있는 deployment와 service를 삭제 가능
- -l 플래그를 사용하거나, 선언적 정의에서 selector을 사용하는 경우 항상 metadata의 labels를 사용한다.


## 활성 프로브(Liveness Probes)

- 이는 쿠버네티스가 pod와 컨테이너가 정상인지 아닌지 여부를 확인하는 방법과 관련이 있음
  - 쿠버네티스가 컨테이너에게 주기적으로 던지는 "아직 살아있는지?" 에 대한 질문
  - httpGet: /, 8080 응답 오나?
  - initialDelaySeconds: 5 -> 컨테이너 생성 시 5초는 기다려준다.
  - periodSeconds: 10 -> 10초마다 계속 확인할것
- initialDelaySeconds를 너무 짧게 잡아 5초로 잡으면 앱이 실행되는데 10초가 걸린다고 가정했을 때, 쿠버네티스는 앱이 실행중인데도 응답 없는 것으로 파악하고, 계속 재시작을 시키는 무한 루프에 빠질 수 있다.
- periodSeconds를 너무 짧게 잡으면 그 자체가 서버에 부하를 줄 수 있다.

```yaml
 spec:
      containers:
        - name: second-node
          image: sukhadukkha/kub-first-app:2
          imagePullPolicy: Always
          livenessProbe: 
            httpGet:
              path: /
              port: 8080
            periodSeconds: 10
            initialDelaySeconds: 5
```

- 디폴드 값에 반응하지 않는 애플리케이션이 있거나, 단순히 '/' 대신 '/something' 에 요청을 전송하여 그 상태를 확인하려는 경우에 매우 유용하다.
- imagePullPolicy를 Always로 설정함으로써, 태그가 변하지 않았다면 이미지를 다시 가져오지 않았던 쿠버네티스 설정을 항상 이미지를 다시 가져오게 설정할 수 있다.
  - 이미지가 아주 클 경우 Pod가 뜰 때마다 네트워크를 통해 데이터를 받아와야 하므로 가동 속도가 느려질 수 있고, 네트워크 부하가 생길 수 있다.
  - 실무에서는 Production 환경에서보다는 개발이나 테스트 환경에서 자주 사용한다.