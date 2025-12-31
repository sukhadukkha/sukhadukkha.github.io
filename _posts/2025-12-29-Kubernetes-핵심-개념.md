---
layout: single
title:  "Kubernetes 핵심 개념들"
categories: [Kubernetes]
tags: [Kubernetes]
toc: true
author_profile: true
---


## K8s가 하는 작업과 그렇지 않은 작업

- 하는 작업들 
  - 포드 관리
  - 모니터링, 스케일링 등
- 하지 않는 작업들
  - 클러스터와 노드 생성
  - 인스턴스 생성
  - 리소스 생성
  - 이를 사용자가 직접 하려면 어려움에 부딪힌다.
  - 이렇게 애플리케이션에 필요한 리소스를 생성하려면 직접 수행하거나, Kubermatic, EKS 같은 서비스를 사용해야함. 
  - AWS EKS(Elastic Kubernetes Service) 같은 서비스 활용 가능

---

## 로컬에서 쿠버네티스 시작하는법

- 필요한 것들
  - 클러스터
  - 마스터 노드
  - 워커 노드
  - 하나 이상의 가상 인스턴스
  - API 서버, 스케줄러, Docker, kubelet
  - kubectl (deployment 생성, 삭제, 변경 같은 명령 클러스터에 보내는 도구)
    - 이를 사용하여 마스터 노드에 명령 보낼 수 있음
- minikube : 더미 클러스터를 로컬로 설정하기 위한 도구
  - k8s를 시작하고 로컬에서 테스트하기 위한 훌륭한 도구
- kubectl 설치하기
  - Homebrew를 통해 brew install kubectl
  - kubectl version --client 명령으로 작동 확인
  - 1. 자동완성 엔진 활성화 (오류 방지를 위해 맨 위에 추가)<br>
       autoload -Uz compinit
       compinit
  - 2. kubectl 자동완성 스크립트 로드<br>
       source <(kubectl completion zsh)
  - 3. .zshrc 파일에 별칭과 자동완성 연결 코드 추가<br>
       echo "alias k='kubectl'" >> ~/.zshrc
       echo "complete -F __start_kubectl k" >> ~/.zshrc
  - 4. k ge Tab -> k get으로 자동완성

- minikube 설치하기
  - brew install minikube
  - Apple Silicon을 사용하고 있다면 Minikube를 실행하기 위해 Hypervisor를 설치 할 필요가 없다.
  - Docker Desktop을 기반으로 실행하기 때문이다.
  - minikube start를 입력하면 자동으로 docker 드라이버가 선택되어 실행됨.
  - 이는 가상 머신 내부에 쿠버네티스 클러스터를 생성하는 작업이다. 클러스터는 마스터 노드를 생성하고, 마스터 노드에 필요한 모든 소프트웨어를 설치하고, 워커 노드 소프트웨어도 설치한다.
  - 이렇게 데모 로컬 클러스터가 생성되면 kubectl 명령으로 제어할 수 있는 클러스터가 생성되는 것이고, 이 안에서 컨테이너를 실행할 수 있다.
  - echo 'source <(minikube completion zsh)' >> ~/.zshrc (설정 파일에 스크립트 추가)
  - alias m ='minikube' (alias 추가)
  - m s Tab 누르면 사용 가능한 명령어들 출력됨
  
- minikube status를 실행하여 작동하는지 확인
- minikube dashboard를 실행하여 클러스터의 웹 대시보드 볼 수 있음

---

## Kubernetes 객체(리소스)들

- Pods, Deployments, Services, Volume 등
- 특정 명령을 통해 이런 객체 생성 가능
- 명령적 방식과 선언적 방식으로 객체 생성 가능

### Pod

- 쿠버네티스가 알고 있는 상호작용하는 가장 작은 유닛
- 쿠버네티스는 Pod를 생성하고, Pod는 컨테이너를 보유하고, 쿠버네티스는 이러한 Pod와 컨테이너를 관리한다.
- Pod에 하나 또는 여러 컨테이너를 가질 수 있다.
- Pod도 클러스터의 일부이므로, Pod나 외부와 통신이 가능하다. 
- Default로 Pod에는 클러스터 내부 IP 주소가 있다.
  - 변경 가능, 클러스터 외부에서도 Pod와 통신 가능
- Pod하나에 여러 컨테이너가 있는 경우 localhost 주소를 사용하여 서로 통신 가능
- AWS ECS의 Task는 쿠버네티스의 Pod와 매우 비슷하다.
- **Pod는 임시적이다.**
- 자체적으로 Pod를 만들어 클러스터의 특정 워커 노드에서 실행할 수 있지만, 일반적으로는 k8s에게 이러한 Pod의 관리를 맡긴다.

### deployment

- 일반적으로 수동으로 Pod를 직접 생성하여 특정 워커 노드로 이동하지는 않는다.
- 대신 deployment 객체를 생성하고, 생성하고 관리해야하는 Pod의 수와 컨테이너 수에 대한 가이드를 제공한다.
- deployment 객체는 하나 이상의 pod를 제어할 수 있다.
  - 이를 사용하여 한 번에 여러 pod를 생성하고, 원하는 목표 상태를 설정하는 컨트롤러 객체를 내부적으로 생성할 수 있다.
- deployment를 일시 중지하거나, 삭제하고, 롤백할 수 있다.
- deployment도 스케일링 될 수 있다.
  - 더 많은, 더 적은 pod가 필요하다고 쿠버네티스에게 알리거나, 특정 메트릭을 설정할 수 있는 오토 스케일링 기능을 사용할 수 있다.
  - 메트릭에 수신 트래픽과 CPU 사용률이 있다고 가정하고, 메트릭을 초과하면 쿠버네티스가 자동으로 더 많은 pod를 생성하고 줄어들면 다시 제거한다.
- **일반적으로 pod를 직접 생성하지 않으며 직접 관리하지 않고, deployment를 사용하여 객체를 생성하고, 클러스터에 전송하여 쿠버네티스가 이를 관리하도록 한다.**

---

## deployment 만들어보기(명령형 접근 방식)

- k8s를 사용하기 위해서는 여전히 이미지를 생성해야한다.
- minikube start로 클러스터 실행
- kubectl 명령으로 클러스터에 지침을 보낼 수 있음
- kubectl create deployment를 통해 새로운 deployment 객체를 만들고, 이 객체가 클러스터로 전송된다.
  - kubectl create deployment first-app --image=kub-first-app
  - kubectl get deployments로 생성된 deployment들 확인 가능
  - kubectl get pods를 통해 deployment에서 생성된 모든 것을 확인 가능
  - 문제점 발생
    - 현재 kub-first-app이라는 이미지는 로컬 머신에만 존재하고 있다.
    - create deployment 명령으로 deployment를 생성할 때, 지정한 이미지는 가상 머신에서도 존재해야한다.
    - 이 이미지는 가상 머신 클러스터에는 존재하지 않는다.
  - 해결은? 
    - 우선 다시 kubectl delete deployments first-app로 deployment 삭제
    - 이미지를 Docker Hub로 Push
    - docker tag kub-first-app sukhadukkha/kub-first-app로 로컬에 있는 이미지 이름 변경
    - docker push sukhadukkha/kub-first-app
    - kubectl create deployment first-app --image=sukhadukkha/kub-first-app 를 통해 원격 이미지 사용
    - kubectl get deployments 를 확인하면 READY 1/1확인 가능

### 작동하는 원리

- kubectl create deployment : deployment 객체 생성 및 쿠버네티스 클러스터에 있는 마스터노드, 컨트롤 플레인으로 전송
- 마스터 노드는 클러스터에 필요한 모든 것을 생성한다. 
  - ex) 워커 노드에 pod를 배포하는 일 
- 마스터 노드의 스케줄러가 pod를 분석하여 새로 생성된 pod에 가장 적합한 Node를 찾는다.
- 생성된 pod는 워커 노드 중 하나로 보내진다.
- 워커 노드에서 우리는 kubelet 서비스를 얻게된다.
  - 여기에서 pod 관리, pod에서 컨테이너 시작, pod 모니터링 하고 그 상태를 확인한다.

--- 

## Service

- pod와 pod에서 실행되는 컨테이너에 접근하려면 service 객체가 필요하다.
- 클러스터의 다른 pod에 pod를 노출하거나, 외부에게 pod를 노출한다.
  - pod에는 디폴트로 이미 내부 IP주소가 있다. (minikube dashboard로 확인 가능)
  - 이 내부 IP 주소는 외부에서 사용할 수 없다.
  - pod가 교체될때마다 변경된다.
  - 그렇기에 service가 없다면 pod를 찾는 것은 어렵다.
- **service는 pod를 그룹화하고, 공유 IP 주소를 제공한다. 이 주소는 변경되지 않는다.**
- 변경되지 않는 주소를 제공하고 외부에서도 접근할 수 있도록 service에게 지시할 수 있다.
  - 이 과정을 통해 클러스터 외부에서 pod에 접근할 수 있다.


### Service로 deployment 노출시키기

- kubectl expose deployment first-app type=LoadBalancer --port=8080  (service 생성 및 deployment에 의해 생성된 pod 노출)  
  - --type : 디폴트는 ClusterIP, 클러스터 내부에서만 연결할 수 있음. NodePort는 실행중인 워커 노드의 IP 주소를 통해 노출됨(실제로 외부에서 접근 가능), LoadBalancer는 클러스터가 실행되는 인프라에 존재해야하는 LoadBalancer를 활용한다. (이 service에 대한 고유한 주소 생성, 들어오는 트래픽 모든 pod에 골고루 분산)
  - kubectl get services 를 실행하여 생성되었는지 확인 가능
- minikube 에서는 service에 액세스하는 명령 가지고 있음
  - minikube service first-app

---

## 컨테이너 재시작 및 스케일링

- 실제 스케일링
- kubectl scale deployment/first-app --replicas=3
  - replica는 pod의 인스턴스다. 3 replicas는 동일한 pod/컨테이너가 3번 실행 중이란 의미
  - 이 명령을 실행하고 kubectl get pods를 실행해보면 3개의 pod확인 가능
  - 로드밸런서가 있기때문에 트래픽도 고르게 분산된다.
  - 애플리케이션의 /error로 들어가면 하나의 포드가 Error상태가 되고, /error 경로를 지우고 다시 실행하면 새로운 포드로 리다이렉트 된다. 
  - 컨테이너는 에러가 발생하면 재시작을 시도한다.
  - 쿠버네티스가 자동으로 서버를 다시 살려놓는다.

---

## Deployment 업데이트하기

- 코드를 변경하고, deployment 업데이트하고 원하는 경우 다른 deployment로 롤백하기
- 코드 변경하고 `docker build -t sukhadukkha/kub-first-app .` 명령으로 이미지 리빌드
- `docker push sukhadukkha/kub-first-app` 명령으로 새로운 이미지 Docker Hub에 Push
- kubectl set image deployment/first-app kub-first-app=sukhadukkha/kub-first-app
  - first-app이라는 deployment 안에 있는 kub-first-app 이라는 이름의 컨테이너를 찾고 그 컨테이너가 사용하는 이미지를 sukhadukkha/kub-first-app 으로 바꿔라
  - 이렇게 실행하고 m service first-app을 실행하고 방문해봐도 바뀐게 없다.
  - 그 이유는 새 이미지에 다른 태그가 있는 경우에만 다운로드 되기 때문이다.
  - 다시 `docker build -t sukhadukkha/kub-first-app:2 .` 명령으로 이미지에 새 버전을 지정하고 Docker Hub에 Push
  - docker push sukhadukkha/kub-first-app:2
  - kubectl set image deployment/first-app kub-first-app=sukhadukkha/kub-first-app:2 명령을 실행하고 애플리케이션에 접속해보면 변경사항이 적용된 것 확인 가능
  - `kubectl rollout status deployment/first-app`
    - rollout은 배포의 진행 과정 관리하는 도구, status는 그 과정이 잘 끝났는지 확인하는 명령어

---

## Deployment 롤백 & 히스토리

- 실패하는 명령 실행
  - kubectl set image deployment/first-app kub-first-app=sukhadukkha/kub-first-app:3
  - 이 명령을 입력하고 kubectl rollout status deployment/first-app 을 실행해보고, dashboard에 들어가보면 새로운 포드를 생성하는데 이미지 Pulling 에러가 발생했고, 쿠버네티스 전략에 따라 새 Pod가 성공적으로 시작되지 않기 때문에 기존의 pod를 종료하지 않는 것을 확인할 수 있다.
- 이것은 이 업데이트를 롤백해야 한다.
- `kubectl rollout undo deployment/first-app` 를 통해 최근의 deployment undo
- `kubectl rollout history deployment/first-app` 를 통해 deployment 히스토리 살펴볼 수 있다.
- `kubectl rollout history deployment/first-app --revision=6` 를 통해 history 번호를 revision에 입력하면 이미지를 볼 수 있다.
- `kubectl rollout undo  deployment/first-app --to-revision=3` 를 통해 특정 revision 이미지로 롤백할 수 있다.

---

## 명령형 접근 방식에서 선언적 접근 방식으로

- kubectl delete service first-app
- kubectl delete deployment first-app
- 이 명령들을 통하여 서비스와 deployment를 삭제하고 선언적 접근 방식으로 실행해보자
