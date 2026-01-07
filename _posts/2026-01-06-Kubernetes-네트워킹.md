---
layout: single
title:  "Kubernetes 네트워킹"
categories: [Kubernetes]
tags: [Kubernetes]
toc: true
author_profile: true
---


## 예제 프로젝트 구조

- Pod와 컨테이너를 서로 연결하고, 외부 세계와 연결하는 방법

초기 구조
![구조](/assets/images/K8s-Network-Demo-Architecture.png)

---

## users-api의 deployment, service 생성하기

- Docker hub에 레포지토리 만들고, users-api 폴더에서 Docker build -t 를 통해 이미지를 빌드하고, 이미지를 push 
- kubernetes 폴더 만들고, 그 아래에 users-deployment.yaml 파일 생성
  - users 컨테이너에 대한 deployment 설정

```yaml
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
        - name: users
          image: sukhadukkha/kub-demo-users
```

- 그 뒤 변경되지 않는 안정적인 주소를 제공 할 수 있게 해주고, 외부 세계와 액세스를 할 수 있도록 해주는 service 생성하기
  - Users API에 요청을 보내기 위해서 생성
- users-service.yaml 파일 생성
- type: LoadBalancer을 통해 각 노드에 트래픽을 분산하고, 외부 세계에서 접근할 수 있는 변하지 않는 IP 주소를 제공 받을 수 있다.

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
      port: 8080                 # 이 포트는 다른 포트 사용해도 됨
      targetPort: 8080           # 이 포트 무조건 사용 필요, users-app.js는 내부 포트 8080을 열어두고 있기 때문
```
- kubectl apply -f=users-service.yaml로 서비스 생성
- minikube service users-service 를 통해 생성된 서비스 minikube에서 액세스

---

## Users 컨테이너와 Auth 컨테이너간 Pod 내부 통신 활성화 하기

- users-app.js 수정
- 도커 컴포즈는 서비스 이름으로 자동 연결해주지만, 쿠버네티스에서는 서비스(Service)라는 객체를 통해 통신해야 하며, 이 서비스의 이름을 환경 변수로 주입해주는 것이 MSA의 표준 패턴이기 때문에 수정해야한다.
```
const hashedPW = await axios.get('http://auth/hashed-password/' + password);
const hashedPW = await axios.get(`http://${process.env.AUTH_ADDRESS}/hashed-password/` + password);

```
```
const response = await axios.get(
    `http://${process.env.AUTH_ADDRESS}/token/` + hashedPassword + '/' + password
  );
  
const response = await axios.get(
    `http://${process.env.AUTH_ADDRESS}/token/` + hashedPassword + '/' + password
  );
```
- 변경 후 users-api 폴더에서 이미지 재 빌드 및 다시 푸쉬
- **docker compose 파일 수정(Docker compose로 실행 시, http://auth/hashed-password/...)**

```yaml
version: "3"
services:
  auth:
    build: ./auth-api
  users:
    build: ./users-api
    environment:          # 추가
      AUTH_ADDRESS: auth  # 추가
    ports: 
      - "8080:8080"
  tasks:
    build: ./tasks-api
    ports: 
      - "8000:8000"
    environment:
      TASKS_FOLDER: tasks
    
```

- Docker hub에서 kub-demo-auth 레포지토리 생성
- auth-api 폴더 이미지 빌드 및 push 
- 같은 포드 내에 Auth, Users 컨테이너 두개를 위치 시키기 위해 users-deployment.yaml 파일 수정

```yaml
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
        - name: users
          image: sukhadukkha/kub-demo-users:latest
        - name: auth      # 추가
          image: sukhadukkha/kub-demo-auth:latest
```

- users-service.yaml 파일에서 Auth API는 80번 포트에서 대기하고 있지만 이것을 추가하지는 않는다.
  - Users API는 외부에서 접근 가능해야하지만, Auth API는 외부에서 접근하지 못하게 할 것이기 때문이다.
- 같은 Pod에 있지만, 다른 컨테이너에 있는 Auth API와 통신할 수 있는 Users API의 올바른 주소는?

### Pod 내부 커뮤니케이션

- Pod 내부 통신의 경우 2개의 컨테이너가 동일한 Pod에서 실행된다면?
  - Pod 내의 Users 컨테이너와 Auth 컨테이너는 한 컴퓨터 안에 있는 것처럼 취급
  - Users API 에서 Auth API로 요청을 보낼 때, localhost를 통해 서로를 호출 가능
- users-deployment.yaml 파일 수정

```yaml
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
        - name: users
          image: sukhadukkha/kub-demo-users:latest
          env:  # 추가
            - name: AUTH_ADDRESS
              value: localhost
        - name: auth
          image: sukhadukkha/kub-demo-auth:latest
```
- **Kubernetes로 싱행 시 (http://localhost/hashed-password/...)**
- kubectl apply로 이 파일 재 적용
- kubectl get pods를 통해 users-deployment-5c9f6d4ccd-cg6tf   2/2     Running       0          16s 이렇게 컨테이너 2개 실행되는것 확인 가능

---

## 다중 Deployments로 발전시키기

- 아키텍처는 다음과 같다.
![시스템 구조](/assets/images/K8s-Network-Demo-Architecture2.png)

- **더 이상 동일한 Pod에서 auth, users 컨테이너 실행되지 않도록 Auth API deployment 만들기**

- auth-deployment.yaml

```yaml
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
        - name: auth
          image: sukhadukkha/kub-demo-auth:latest
```

- users-deployment.yaml 파일에서 auth 컨테이너 삭제

```yaml
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
        - name: users
          image: sukhadukkha/kub-demo-users:latest
          env: 
            - name: AUTH_ADDRESS
              value: localhost
```

- **auth deployment에 대한 service가 없다면 Pod의 IP 주소가 변경될 수 있기 때문에 auth-service 생성**
- type를 LoadBalancer로 지정한다면 외부에서도 접근이 가능해지기 때문에, 외부에서 이 Pod에는 접근할 수 없게 만들어야 한다. (ClusterIP)
- ClusterIP : 쿠버네티스에 의해 자동 로드 밸런싱 수행하지만, 외부 세계에 노출은 하지 않는다.

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
      port: 80
      targetPort: 80
```

- `외부에 노출하지 않는다면 우리는 어떻게 접근해야 할까? AUTH_ADDRESS는 무엇이어야 할까?`
- 이 auth-service를 위해 생성된 IP 주소를 알아야 한다.
- 하나의 service에는 자체 IP 주소가 있으며, 그 IP 주소는 변경되지 않고, 이를 통해 Pod에 접근할 수 있다.
- kubectl apply -f=auth-service.yaml -f=auth-deployment.yaml 실행
- kubectl get service를 실행하면 auth-service의 ClusterIP 확인 가능
- users-deployment.yaml 파일 변경 및 apply 통해 재 적용
    
```yaml
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
        - name: users
          image: sukhadukkha/kub-demo-users:latest
          env: 
            - name: AUTH_ADDRESS
              value: "10.106.23.46"  # Cluster IP로 변경 
```

- 잘 동작 하는 것을 확인할 수 있다.
- **하지만 이 IP 주소를 수동으로 가져오는 것은 약간 성가신 일이다.**
- 이를 해결하기 위해 쿠버네티스는 자동으로 생성되는 환경 변수를 제공한다,
  - 그것의 이름은 서비스 이름이고, '-'가 '_'로 대체된 대문자로 이루어진다.

```
  const response = await axios.get(
    `http://${process.env.AUTH_SERVICE_SERIVCE_HOST}/token/` + hashedPassword + '/' + password
  );
```

- 이렇게 변경 후, docker compose에서도 사용할 수 있게 하기 위해 
```yaml
environment:
      AUTH_ADDRESS: auth
      AUTH_SERVICE_SERVICE_HOST: auth  # 추가
```

- 이를 실행하기 위해 users-api 폴더의 이미지 재 빌드, 푸쉬
- kubectl delete -f=users-deployment.yaml 명령 통해 생성된 deployment 삭제 후 apply를 통해 재 적용
  - 이미지가 태그가 변경되지 않으면 쿠버네티스가 이미지를 다시 가져오지 않기 때문
  - deployment 강제 재시작, imagePullPolicy: Always 설정, 태그 관리 통해 해결 가능
- 애플리케이션에 요청을 보내보면 수동으로 가져온 IP, 자동으로 생성되는 환경 변수 모두 잘 작동하는 것을 확인할 수 있다.

---

## Pod간 통신에 DNS 사용하기(가장 일반적인 방법)

- **클러스터 내부에는 알려진 DNS 주소가 존재한다.**
  - CoreDNS라는 서비스는 클러스터에 설치되어 있고, 이 서비스는 클러스터 내부의 도메인을 자동으로 생성한다.
  - 이 주소는 클러스터 내부에서만 알 수 있다.
- **그 이름은 service + Namespace 이름이다.**
- users-deployment.yaml 변경 및 재 적용

```yaml
 env: 
            - name: AUTH_ADDRESS
            # value: "10.111.3.139"
              value: "auth-service.default" # 추가
```

### Namespace란? 

- **하나의 클러스터를 여러 개의 논리적인 가상 클러스터로 나누는 단위이다.**
- 왜 사용하나? 
  - 리소스 격리 : 동일한 이름의 Deployment, Service의 충돌을 방지한다. 'dev' 폴더에도 auth-api, 'prod' 폴더에도 auth-api가 존재할 때, 이 충돌을 방지한다.
  - 보안 및 권한 제어: 특정 팀이나 프로젝트 그룹에 특정 네임스페이스에 대한 접근 권한만 부여 가능
  - 리소스 제한: 네임스페이스별로 사용 가능한 CPU, 메모리를 정해둘 수 있다. 

--- 

## Task Deployment, Service 만들기

- 위의 Auth API, User API와 비슷하게 구성

```
tasks-app.js파일 수정 (환경변수 사용)
const response = await axios.get(`http://${process.env.AUTH_ADDRESS}/verify-token/` + token);
```

- Docker compose 환경에서도 잘 동작하도록 docker-compose.yaml 파일에 환경변수 추가
- Docker 이미지 빌드, 이미지 푸쉬

```yaml
 tasks:
    build: ./tasks-api
    ports: 
      - "8000:8000"
    environment:
      TASKS_FOLDER: tasks
      AUTH_ADDRESS: auth  # 추가
```

- tasks-deployment.yaml, tasks-service.yaml 파일 생성

```yaml
apiVersion: v1
kind: Service
metadata:
  name: tasks-service
spec:
  selector:
    app: tasks
  type: LoadBalancer
  ports:
    - protocol: TCP
      port: 8000
      targetPort: 8000
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: task-deployment
spec: 
  replicas: 1
  selector:
    matchLabels:
      app: tasks
  template:
    metadata:
      labels:
        app: tasks
    spec:
      containers:
        - name: tasks
          image: sukhadukkha/kub-demo-tasks:latest
          env: 
            - name: AUTH_ADDRESS 
              value: "auth-service"
            - name: TASKS_FOLDER
              value: "tasks"
```

- deployment, service apply로 적용
- minikube service tasks-service 실행하여 /tasks 요청 잘 가는 것 확인

---

## 컨테이너화된 프론트엔드 추가하기

- frontend 폴더의 이미지를 빌드하고, docker run -p 80:80 --rm -d sukhadukkha/kub-demo-frontend를 실행하고 localhost에 접속해본다. (쿠버네티스 사용 X)
- 브라우저 검사에서 CORS 에러 발생하는 것을 확인할 수 있다.
  - 해결하기 위해 tasks-app.js에 코드 추가
```
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST,GET,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type,Authorization');
  next();
})
```

- tasks-api 이미지 재 빌드, 푸쉬
- 이미지 변경되었으므로 deployment 삭제 후 재 적용(최신 이미지 적용 안됨 이슈)

---

- 이제 이 프론트엔드를 쿠버네티스에 어떻게 배포할 수 있을까?
- 컨테이너를 쿠버네티스의 Pod로 옮기고 외부에서의 접근을 위해 frontend-deployment.yaml, frontend-service.yaml 생성
- frontend 폴더 이미지 빌드, 푸쉬
- apply로 생성한 deployment, service 적용
- minikube service frontend-service로 실행 및 접속

- `지금은 frontend와 task가 소스코드에 주소를 하드코딩해서 통신하고있다.`
```
fetch('http://127.0.0.1:51759/tasks' ...)
```

### 프론트엔드 리버스 프록시 사용하기 

- **리버스 프록시: 클라이언트와 백엔드 서버 사이에서 Nginx 등 리버스 프록시에게 요청을 보내면 프록시가 이를 가로채서 적절한 서버로 전달하고 응답을 대신 받아주는 구조**
- nginx.conf 파일에 내용 추가
```
server {
  listen 80;

  
  location /api/ {   # 추가: /api/ 으로 요청이 들어오면 이 구성 시작
    proxy_pass http://tasks-service.default:8000/;

  }
  
  location / { 
    root /usr/share/nginx/html;
    index index.html index.htm;
    try_files $uri $uri/ /index.html =404;
  }
  
  include /etc/nginx/extra-conf.d/*.conf;
}
```

- frontend의 app.js 파일 변경
```
 fetch('http://127.0.0.1:51759/tasks ... 
 fetch('/api/tasks  ... # 이렇게 변경
```

- 사용자가 브라우저를 통해 사이트에 접속하면 모든 요청은 Nginx에 도착한다.
- Nginx는 요청된 주소를 보고 어디로 보낼지 결정한다.
- /api/tasks 요청 -> /api/로 시작 -> tasks-service로 요청 넘김 -> 서버의 응답을 받고 Nginx는 응답을 브라우저에 전달
- `http://...:8000/ (뒤에 / 있음) 와 http://...:8000 (뒤에 / 없음)의 차이`
  - / 붙인 경우 : http://tasks-service.default:8000/tasks -> 즉 백엔드 서버는 /api/tasks가 아닌 /tasks 요청 받음
  - / 안 붙인 경우 : http://tasks-service.default:8000/api/tasks -> 백엔드 서버는 /api/tasks 요청을 받는다.
  - 즉 /가 있으면 location에 적힌 경로를 지우고 전달한다. (/api/ 지우고 전달)
  - /가 없으면 사용자가 요청한 주소를 그대로 전달한다. (/api/ 포함하여 전달)