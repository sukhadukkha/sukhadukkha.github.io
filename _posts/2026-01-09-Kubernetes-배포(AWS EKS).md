---
layout: single
title:  "Kubernetes 배포(AWS EKS)"
categories: [Kubernetes]
tags: [Kubernetes]
toc: true
author_profile: true
---


## Kubernetes 배포

- 쿠버네티스는 가상 인스턴스를 생성하거나, 로드 밸런서를 생성하거나, 리모트 머신을 생성하거나 하지 않는다.
- 쿠버네티스가 실행될 인프라를 설정하는 것은 사용자의 몫이다.
- 쿠버네티스는 컨테이너와 Pod관리, 트래픽 밸런싱 등을 해주는 도구이다.
- Cloud Provider를 통해 가상 인스턴스, 클러스터를 설정할 수 있다.
- EC2를 이용하여 SSH로 연결한 후, 쿠버네티스에 필요한 소프트웨어를 설치하고, 네트워크를 만들고 이를 배포할 수 있다.
- 혹은 AWS EKS를 활용할 수 있다.


### AWS ECS(Elastic Container Service) vs AWS EKS(Elastic Kubernetes Service)

- EKS는 쿠버네티스 배포를 위한 서비스
- ECS는 쿠버네티스에 대해 아무것도 모름


## AWS EKS 사용해보기

- 강의 내용에서 어떻게 설정하고 배포하는지를 정리해서 올린다. 실제 AWS EKS 사용은 이번 학기 프로젝트에서 사용해볼 예정이다.
- 초기 설정 파일들
- auth.yaml

```yaml
apiVersion: v1
kind: Service
metadata:
  name: auth-service
spec:
  selector:
    app: auth
  type: ClusterIP
  ports:
    - protocol: TCP
      port: 3000
      targetPort: 3000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: auth
  template:
    metadata:
      labels:
        app: auth
    spec:
      containers:
        - name: auth-api
          image: sukhadukkha/kub-dep-auth:latest
          env:
            - name: TOKEN_KEY
              value: 'shouldbeverysecure'
```


- users.yaml
```yaml
apiVersion: v1
kind: Service
metadata:
  name: users-service
spec:
  selector:
    app: users
  type: LoadBalancer
  ports:
    - protocol: TCP
      port: 80
      targetPort: 3000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: users-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: users
  template:
    metadata:
      labels:
        app: users
    spec:
      containers:
        - name: users-api
          image: sukhadukkha/kub-dep-users:latest
          env:
            - name: MONGODB_CONNECTION_URI
              value: 'mongodb+srv://maximilian:wk4nFupsbntPbB3l@cluster0.ntrwp.mongodb.net/users?retryWrites=true&w=majority' # MongoDB Atlas 클러스터 주소이다.
            - name: AUTH_API_ADDRESSS
              value: 'auth-service.default:3000'
```

- 이미지 빌드 후, Docker Hub에 Push하면 AWS EKS를 사용해볼 준비가 완료된다.

---

- 그 후, AWS EKS에 들어가서 클러스터를 생성한다.
- EKS 서비스에 대한 role을 만들고, 그 서비스에 권한을 부여한다.
  - IAM(Identity and Access Management)역할 생성
  - **EKS는 사용자를 대신해서 다른 AWS 자원(EC2, LoadBalancer 등)을 관리해야한다. 이를 위해 EKS 서비스 자체가 AWS 자원에 접근할 수 있도록 허용하는 IAM Role을 만들어서 EKS에게 부여해야한다.
- 클러스터를 위한 네트워크를 구성한다.
  - 강의에서는 CloudFormation을 통해 강의 템플릿으로 VPC를 구성하고 설정했다.(이름: eksVpc)
- 이렇게 클러스터를 생성했다.


---

- 현재는 kubectl 명령이 minikube 클러스터로 전달된다. 이를 생성한 EKS 클러스터로 보내야한다.
  - 이를 교체하기 위해 .kube 폴더 안의 config 파일을 변경하는 방법이 있다.
  - 이를 쉽게하려면, AWS CLI(Command Line Interface)를 사용할 수 있다. (다운로드 필요)
  - AWS CLI는 터미널에서 AWS의 모든 서비스를 관리하고 제어할 수 있게 해주는 명령어 도구다.
  - 이를 사용하려면 AWS에서 Access Key 발급 필요
  - `aws configure` 명령을 통해 AWS CLI를 AWS 계정에 연결해야한다.
  - `aws eks update-kubeconfig --region [리전코드] --name [클러스터이름]` 명령을 통해 kubectl이 AWS 클러스터와 통신하는데 필요한 모든 데이터로 config 파일을 업데이트한다.
  - `kubectl config current-context` 명령은 현재 어떤 클러스터를 향하고 있는지를 확인할 수 있다.
- 여기까지 클러스터와 이 클러스터에 연결된 kubectl을 사용할 수 있다.

---

- 일반 클러스터 네트워크 등은 있지만, 구체적인 Worker Node가 존재하지 않는다.
- 이를 생성하려면, 클러스터의 Compute로 이동하여 Add Node Group을 해준다.
- IAM Role도 설정한다.
  - 강의에서는 IAM 설정에서 Common use cases에서 EC2 선택
  - 또한 policies에서 EKSWorkerNodePolicy, CNI, ec2ContainerRegistryReadOnly 설정 추가
  - 이 권한은 노드 즉 클러스터의 일부인 EC2 인스턴스가 이미지를 가져와 성공적으로 실행하기 위해 작업을 수행하는 것을 허용한다.
- 어떤 종류의 EC2 인스턴스를 구동할지 선택한다.(small 인스턴스를 최소값으로 사용해야함)
- 스케일링 정책 설정 가능
  - 강의에서는 2로 설정했고 노드가 2개 생성된다.(2개의 다른 컴퓨터를 갖는다)
  - Pod와 컨테이너는 쿠버네티스에 자동으로 배포된다.
- **이는 몇개의 EC2 인스턴스를 실행하고, 이를 클러스터에 추가하는 작업이다.**
- 더하여 EKS는 노드에 필요한 kubelet, kube-proxy에 필요한 모든 쿠버네티스 소프트웨어도 설치하고, 그것들도 클러스터에 추가한다.
- AWS EC2를 확인해보면 2개의 인스턴스가 EKS에 의해 자동으로 생성된 것을 확인할 수 있다.

---

- 이제 구성을 적용해보자
- kubectl apply -f=auth.yaml -f=users.yaml
- LoadBalancer로 설정한 덕분에 kubectl get service 명령을 사용하여 URL을 얻을 수 있다.
- 더하여 자동으로 AWS에서 생성된 LoadBalancer도 확인할 수 있다.
- Pod는 사용 가능한 노드에 적절하게 쿠버네티스가 배치한다. 만약 4개로 설정했고, 노드가 2개라면 적당한 노드로 알아서 쿠버네티스가 배포해준다.

---

## EFS를 볼륨으로 추가하기(CSI 사용)

- PV, PVC를 생성해야한다.
- EFS CSI Driver를 클러스터에 만들어주어야한다.
  - 쿠버네티스와 EFS가 통신할 수 있게 하기 위해
- AWS EFS CSI Driver 깃허브 이용
- `kubectl apply -k "github.com/kubernetes-sigs/aws-efs-csi-driver/deploy/kubernetes/overlays/stable/?ref=release-2.2"` 명령을 통해 클러스터에 설정 적용
- 보안 그룹 생성(VPC는 eksVpc)
  - NFS 인바운드 룰 추가, CIDR는 VPCs에서 eks-Vpc의 IPv4 CIDR 복사하여 넣었다.
- AWS EFS 생성
  - 이름, VPC(eks-Vpc)
  - 방금 생성한 보안그룹으로 설정
- users.yaml의 service위에 PV 설정

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: efs-pv
spec:
  capacity: 
    storage: 5Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteMany
  storageClassName: efs-sc
  csi:
    driver: efs.csi.aws.com
    volumeHandle: <생성된 EFS ID>
```

- `kubectl get sc` 명령을 통해 storageClass 목록을 확인 가능
  - 현재는 efs-sc 스토리지 클래스가 존재하지 않는다.
  - 이를 가져오기위해 github에서 aws-efs-csi-driver/example/kubernetes/static_provisioning/specs/storageclass.yaml 파일 복사해서 users.yaml에 붙여넣기

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: efs-sc
provisioner: efs.csi.aws.com
```

- PVC 추가 

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: efs-pvc
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: efs-sc
  resources: 
    requests: 
      storage: 5Gi
```

- Pod에 pvc 적용한 최종 users.yaml

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: efs-sc
provisioner: efs.csi.aws.com
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: efs-pv
spec:
  capacity: 
    storage: 5Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteMany
  storageClassName: efs-sc
  csi:
    driver: efs.csi.aws.com
    volumeHandle: <생성된 EFS ID>
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: efs-pvc
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: efs-sc
  resources: 
    requests: 
      storage: 5Gi
---
apiVersion: v1
kind: Service
metadata:
  name: users-service
spec:
  selector:
    app: users
  type: LoadBalancer
  ports:
    - protocol: TCP
      port: 80
      targetPort: 3000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: users-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: users
  template:
    metadata:
      labels:
        app: users
    spec:
      containers:
        - name: users-api
          image: sukhadukkha/kub-dep-users:latest
          env:
            - name: MONGODB_CONNECTION_URI
              value: 'mongodb+srv://maximilian:wk4nFupsbntPbB3l@cluster0.ntrwp.mongodb.net/users?retryWrites=true&w=majority'
            - name: AUTH_API_ADDRESS
              value: 'auth-service.default:3000'
          volumeMounts:
            - name: efs-vol
              mountPath: /app/users
      volumes:
        - name: efs-vol
          persistentVolumeClaim:
            claimName: efs-pvc
```

- CSI EFS 드라이버를 deployment에 볼륨으로 추가하기 위해 필요한 구성
  - StorageClass 만들기
  - PV, PVC 만들기
  - Pod에 연결 후, 컨테이너에 연결

---

## 다른 방법

- AWS EKS Add-on 방식(AWS CLI통해 설정)
  - `aws eks create-addon --cluster-name 내클러스터이름 --addon-name aws-efs-csi-driver`
- Helm 차트 방식

## 내용 추가(LoadBalancer와 비용)

- **LoadBalancer를 서비스마다 만들면 비용이 점점 더 커지게 된다.**
- **이를 해결하기 위해 Nginx(Ingress Controller) 하나만 로드밸런서로 띄우고, 나머지는 ClusterIP로 내부 통신하는 방법을 사용한다.**
  - Ingress Controller 설치
  - Service의 kind를 Ingeress로 설정
  - Ingress yaml 파일 생성
  - 예시 파일

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app-ingress
spec:
  rules:
  - http:
      paths:
      - path: /users
        pathType: Prefix
        backend:
          service:
            name: users-service
            port:
              number: 80
      - path: /auth
        pathType: Prefix
        backend:
          service:
            name: auth-service
            port:
              number: 3000
```
- 스프링이나 노드 서버가 뜰 때까지 시간이 걸릴 수 있기 때문에, livenessProbe나 readinessProbe 설정을 추가한다면, 서비스가 준비되지 않은 파드로 트래픽을 보내는 에러를 방지할 수 있다.

---

## Kubernetes에서 포트 충돌이 안나는 이유

- **궁금한점: 만약 노드가 2개이고, 노드 A에 users, auth 파드가 생겼다고 가정해보자. 그리고 이 파드를 관리하는 서비스는 둘다 targetPort가 3000이다. 이 때 포트 충돌이 일어나지는 않을까?**
- 해결: 쿠버네티스는 노드 A(EC2) 내부에 users, auth 파드 생성되면 가상 랜카드를 하나씩 꽂는다.
  - 각 파드는 자신만의 네트워크 네임스페이스를 가진다.
  - 이 네임스페이스 안에 들어있는 가상 랜카드에 쿠버네티스가 가상 IP를 부여한다.
  - EC2 내부의 가상 Bridge를 통해 각 파드들이 이 Bridge에 연결되어 서로 통신한다.
  - 이를 통해 auth,users 파드가 각각 예를들어 10.1.1.5, 10.1.1.6 라는 가상 IP를 갖고있기 때문에, 10.1.1.5의 3000번포트, 10.1.1.6의 3000번 포트를 사용하여 충돌이 일어나지 않게 된다.
 