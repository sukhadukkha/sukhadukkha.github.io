---
layout: single
title:  "Kubernetes로 데이터&볼륨 관리하기"
categories: [Kubernetes]
tags: [Kubernetes]
toc: true
author_profile: true
---


## Kubernetes & 볼륨 

- 볼륨
  - **컨테이너가 중지되고 제거된다고 해도, 중요한 데이터들이므로, 손실되지 않아야 할 때 사용**
- 쿠버네티스로 작업을 할 때, 컨테이너를 실행하는 것은 우리가 아니라, 쿠버네티스이다.
  - 클러스터와, deployment, service를 통해 쿠버네티스를 오케이스레이션하고, 쿠버네티스는 Pod를 생성하고, 컨테이너를 실행한다.
- 쿠버네티스에서 볼륨을 사용하려면 컨테이너에 볼륨을 추가하도록 쿠버네티스를 구성해야한다.
- deployment를 설정할 때, pod의 일부로 시작될 컨테이너에 볼륨을 탑재해야 한다는 것을 pod template에 추가할 수 있다.
- 볼륨은 쿠버네티스에 의해 시작되고 관리되는, pod의 일부이기 때문에 볼륨은 pod에 따라 다르다.
- 쿠버네티스 볼륨은 데이터가 저장되는 위치를 완벽하게 제어할 수 있다.
- 쿠버네티스 볼륨은 설정에 따라 영구적으로 혹은 pod 재시작(기존 pod 삭제하고, 새로운 pod 생성 의미)에는 살아남지 못하게(default) 설정할 수 있다.
  - 컨테이너 재시작에는 살아남는다.
- 쿠버네티스 볼륨은 도커 볼륨 시스템을 활용하지만, 더 많은 기능과 구성 옵션을 가지고 있다.

---

## deployment와 service 만들기

deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: story-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: story
  template:
    metadata:
      labels:
        app: story
    spec:
      containers:
        - name: story
          image: sukhadukkha/kub-data-demo

```

service.yaml
```yaml
apiVersion: v1
kind: Service
metadata:
  name: story-service
spec:
  selector:
    app: story
  type: LoadBalancer
  ports:
    - protocol: "TCP"
      port: 80
      targetPort: 3000
    
```

---

## Kubernetes Volumes (emptyDir)

- Kubernetes Volumes에 대한 정보 (https://kubernetes.io/docs/concepts/storage/volumes/)
- 여러가지의 볼륨들 확인 가능
- `볼륨은 Pod에 연결되고, Pod 별로 다르다.`
- Pod를 정의하고 구성하는 위치에 볼륨을 정의한다.
- 현재 상황: 컨테이너 재시작하면 데이터가 사라진다.
  - 해결 
  - emptyDir 볼륨 생성 : emptyDir을 Pod가 시작될 때 마다 빈 디렉토리를 생성하게 설정, Pod가 살아있는 한, 이 디렉토리를 데이터로 채운다. 하지만 Pod가 제거되면, 이 디렉토리도 제거된다.
  - 이를 통해 컨테이너 재시작되더라도 볼륨에 데이터가 저장된다.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: story-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: story
  template:
    metadata:
      labels:
        app: story
    spec:
      containers:
        - name: story
          image: sukhadukkha/kub-data-demo:1
          volumeMounts:
            - mountPath: /app/story           # 마운트될 컨테이너 내부의 경로이다. 컨테이너 내부의 /app/story 라는 경로를 이 볼륨과 연결한다.  
              name: story-volume 
      volumes:
        - name: story-volume      # 볼륨 이름
          emptyDir: {}     # 일시적인 빈 디렉토리
```

---

## Kubernetes Volumes (hostPath)

- emptyDir 볼륨의 단점
  - replicas가 2인 경우에 Pod의 인스턴스가 2개가 실행된다.
  - 이 경우에 트래픽이 다른 Pod로 전송되게된다면, 특정 Pod에서 저장한 데이터와 다른 Pod에서 저장한 데이터가 달라지게 된다.
- 해결은 hostPath 볼륨
  - 호스트 머신의 동일한 경로에서 하나의 볼륨을 공유한다.
  - 동일한 노드에서 모든 요청을 처리하는 경우에만 유용하다.
- 단점 
  - 여러 Pod, 다른 노드에서 실행되는 경우에는 동일한 데이터에 접근할 수 없다.
```yaml
   spec:
      containers:
        - name: story
          image: sukhadukkha/kub-data-demo:1
          volumeMounts:
            - mountPath: /app/story           
              name: story-volume
      volumes:
        - name: story-volume
          hostPath: 
            path: /data
            type: DirectoryOrCreate 
```

- /app/story 디렉토리를 호스트(Minikube 노드)의 실제 경로와 연결한다.
- Pod가 떠 있는 노드(컴퓨터)의 /data라는 폴더를 저장소로 사용한다.
- 노드에 /data 폴더가 없다면 쿠버네티스가 알아서 만들어준다.

---

## Kubernetes Volumes (CSI)

- CSI(Container Storage Interface)
- 쿠버네티스와 외부 저장소를 연결해주는 어댑터 역할의 드라이버다.
- 저장소는 클러스터 노드에 있지 않고, 클라우드 스토리지 서비스에 존재하게 된다.
- 등장 배경 : 예전에는 쿠버네티스 엔지니어들이 클라우드의 저장소를 연결하는 코드를 소스코드안에 다 집어넣었다.
  - AWS에서 기능 수정 시, 쿠버네티스 전체 업데이트 필요, 새로운 저장소 회사 나타나면 엔지니어들이 그 코드를 직접 짜줘야하는 문제 발생
- 해결 : 쿠버네티스는 규격을 제공하고, 저장소 회사들이 직접 연결 드라이버를 만들어라.
- 작동 방식
  - 엔지니어가 10GB 저장소가 필요해 라고 요청하면, 쿠버네티스가 CSI 드라이버에게 명령을 내린다. 드라이버는 클라우드에 가서 실제 디스크를 생성한다.
  - Pod가 노드 A 에서 실행되다가, 죽고 노드 B에서 다시 살아나면, CSI 드라이버가 노드 A에 붙어있던 디스크를 떼어네서 노드 B에 다시 꽂아준다.

---

## 영구 볼륨(PV)

- 현재까지 볼륨의 문제점 
  - Pod가 제거되면 볼륨도 파괴된다.
  - 이를 hostPath로 해결하였지만, 이는 minikube라는 단일 노드 환경에서만 유용하다. 모든 Pod는 항상 동일한 워커노드에서만 실행되기 때문이다. (minikube에는 워커노드가 1개)
  - AWS로 이동하면, 여러 노드가 존재하게 되고, hostPath도 더 이상 도움이 되지 않는다.
- 데이터베이스가 있는 컨테이너, Pod 교체 후 살아남아야 하는 파일을 저장하는 컨테이너가 있는 경우에는 Pod와 노드에 종속되지 않는 독립적인 볼륨이 필요하다.
- 영구볼륨은 Pod와 노드에 독립적이다.
- 영구 볼륨은 단순한 독립 스토리지 그 이상의 의미를 가진다.
  - 볼륨이 해당 Pod및 노드에서 분리된다는 것이 Key Idea이다.
  - 볼륨이 구성되는 방식에 대한 완전한 권한을 갖게 된다.
  - Pod와 독립적으로 한 번만 정의하고, 원하는 경우 여러 Pod에서 이를 시용할 수 있다.
  - 
- 전체적인 아키텍처
![구조](/assets/images/PV%20&%20PCV.png)

### 영구 볼륨 생성하기

- 단일 노드 테스트 환경에서만 작동하는 영구 볼륨 생성 후, 작동 원리 파악하기(hostPath)
- fileSystem vs Block
  - fileSystem : 데이터를 파일과 폴더 구조(계층형)로 저장하고, 이미 파일 시스템이 구축된 상태로 제공된다. 여러 명이 동시에 접속해서 파일을 올리고 내릴 수 있다. 관리하기 쉽고 검색이 용이하다. 공유 가능하다.(RWX), 여러개의 노드가 동시에 이 저장소에 붙어서 읽고 쓸 수 있다.(ReadWriteMany)
  - Block : 데이터를 일정한 크기의 조각으로 나누어 저장하고, 파일 시스템이 없는 상태로 제공된다. 성능이 매우 빠르다. DB처럼 입출력이 빈번한 곳에 최적이다. 접근 제한(RWX 불가), 한 번에 하나의 노드에만 꽂을 수 있다.(ReadWriteOnce)
  - 속도가 중요하다면 블록 (EBS), 여러 Pod가 동시에 한 폴더를 써야 한다면 파일 (EFS)
- ReadWriteOnce vs ReadWriteMany vs ReadOnlyMany
  - ReadWriteOnce(RWO) : 한 번에 하나의 노드만 읽고 쓸 수 있다. 볼륨이 특정 노드에 마운트 되면, 다른 노드는 이 볼륨에 접근할 수 없다. 단 하나의 "Pod"가 아닌 단 하나의 "노드" 기준. 같은 노드 안의 여러 Pod는 동시에 접근 가능
  - ReadWriteMany(RWX) : 여러 개의 노드가 동시에 읽고 쓸 수 있다. 여러 노드에 흩어져 있는 수 많은 Pod들이 동시에 같은 데이터를 읽고 수정해야 할 때 사용
  - ReadOnlyMany(ROX) : 여러 개의 노드가 동시에 읽기만 가능함. 데이터를 보호해야 하거나, 여러 노드에서 동일한 설정 파일이나, 정적 리소스를 참조만 해야 할 때 사용
- 영구 볼륨 생성(host-pv.yaml)
- 사용하려면 PVC(Persistence Volume Claim) 생성 필요

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: host-pv
spec:
  capacity:
    storage: 1Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteOnce       # hostPath의 경우 이 모드 사용 가능
  hostPath:
    path: /data
    type: DirectoryOrCreate
```

### 영구 볼륨 클레임 생성하기 (PVC)

- 클레임은 이 볼륨을 사용하려는 Pod에서 만든다.
- 클레임 생성(host-pvc.yaml)

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: host-pvc
spec:
  volumeName: host-pv
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```
- Pod를 이 클레임에 연결하기
- Pod를 위해 생성된 볼륨이 아닌, 전체 클러스터용으로 생성된 볼륨
- deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: story-deployment
spec:
  replicas: 2
  selector:
    matchLabels:
      app: story
  template:
    metadata:
      labels:
        app: story
    spec:
      containers:
        - name: story
          image: sukhadukkha/kub-data-demo:1
          volumeMounts:
            - mountPath: /app/story           
              name: story-volume
      volumes:
        - name: story-volume
          persistentVolumeClaim: 
            claimName: host-pvc

```

--- 

## 영구 볼륨 사용하여 실행해보기

- 쿠버네티스에는 스토리지 클래스라는 개념 존재
  - `kubectl get sc` 를 통해 minikube에 디폴트 스토리지 클래스가 있음 확인 가능
  - 스토리지 클래스는 쿠버네티스에서 관리자에게 스토리지 관리 방법과 볼륨 구성 방법을 세부적으로 제어할 수 있게 해주는 개념
  - 이 볼륨이 어떤 종류의 저장 장치에 속하는가를 나타내는 라벨
  - PV에 적힌 경우: 나는 standard 그룹에 속하는 저장소다.
  - PVC에 적힌 경우: 나는 standard 그룹에 속하는 저장소만 만날거다.
- 쿠버네티스는 PV와 PVC를 연결할 때, 용량과 접근 모드 뿐 아니라 storageClassName이 일치하는지도 확인한다.

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: host-pv
spec:
  capacity:
    storage: 1Gi
  volumeMode: Filesystem
  storageClassName: standard   # 추가
  accessModes:
    - ReadWriteOnce
  hostPath:
    path: /data
    type: DirectoryOrCreate
```

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: host-pvc
spec:
  volumeName: host-pv
  accessModes:
    - ReadWriteOnce
  storageClassName: standard    # 추가
  resources:
    requests:
      storage: 1Gi
```

- `kubectl apply -f=host-pv.yaml` , `kubectl apply -f=host-pvc.yaml` 명령으로 파일 적용
- `kubectl apply -f=deployment.yaml` 로 deployment.yaml 파일 재 적용
- kubectl get pv, kubectl get pvc 명령을 통해 pv, pvc 확인 가능

### 정적 프로비저닝 vs 동적 프로비저닝

- 정적 프로비저닝 
  - 관리자가 PV를 미리 만들어둠
  - Class 역할 - PV와 PVC를 연결하는 매칭 키워드
- 동적 프로비저닝 
  - PVC를 만들면 PV가 자동으로 생성됨.
  - Class 역할 - 어떤 디스크를 만들지 결정하는 설계도

--- 

## 환경 변수 사용하기

```
const filePath = path.join(__dirname, 'story', 'text.txt'); 이 코드를
const filePath = path.join(__dirname, process.env.STORY_FOLDER, 'text.txt'); 로 변경
```


```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: story-deployment
spec:
  replicas: 2
  selector:
    matchLabels:
      app: story
  template:
    metadata:
      labels:
        app: story
    spec:
      containers:
        - name: story
          image: sukhadukkha/kub-data-demo:2   # Tag 변경 (1 -> 2)
          env:                  # 환경 변수 추가
            - name: STORY_FOLDER
              value: 'story'
          volumeMounts:
            - mountPath: /app/story           
              name: story-volume
      volumes:
        - name: story-volume
          persistentVolumeClaim: 
            claimName: host-pvc
```

- docker build -t sukhadukkha/kub-data-demo:2 . 로 이미지 재 빌드 (app.js 바뀌었기 때문) 및 Docker Hub에 Push
- kubectl apply -f=deployment.yaml 명령으로 바뀐 yaml 파일 적용

---

- yaml 파일의 spec에 환경 변수를 설정하지 않으려면?
- ConfigMap 활용
- environment.yaml 파일 추가
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: data-store-env
data:
  folder: 'story'
  # key: value ... (더 추가 가능))
```

- 이후 이 파일 적용 `kubectl apply -f=environment.yaml`
- kubectl get configmaps 명령으로 생성된 configmap 확인 가능

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: story-deployment
spec:
  replicas: 2
  selector:
    matchLabels:
      app: story
  template:
    metadata:
      labels:
        app: story
    spec:
      containers:
        - name: story
          image: sukhadukkha/kub-data-demo:2
          env:
            - name: STORY_FOLDER
              valueFrom:          # ConfigMap에서 값을 가져와 STORY_FOLDER 값으로 설정하게 된다.
                configMapKeyRef:  
                  name: data-store-env
                  key: folder
          volumeMounts:
            - mountPath: /app/story           
              name: story-volume
      volumes:
        - name: story-volume
          persistentVolumeClaim: 
            claimName: host-pvc
```

- kubectl apply -f=deployment.yaml 실행
- 애플리케이션 잘 작동하는 것을 확인
