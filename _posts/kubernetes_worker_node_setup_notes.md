# Kubernetes Worker Node 사전 준비 정리

작성 기준: `worker-us-1` 워커 노드를 Kubernetes 클러스터에 조인하기 전까지 진행한 작업

## 0. 전체 목표

이 문서의 작업들은 미국 워커 서버를 Kubernetes 클러스터에 조인할 수 있는 상태로 준비하기 위한 과정이다.

현재 구조는 다음과 같다.

```text
한국 OCI 서버 = Kubernetes Master / Control Plane
미국 서버 = Kubernetes Worker Node
```

워커 노드는 실제 애플리케이션 Pod가 실행되는 서버다.  
따라서 워커 노드에는 컨테이너 실행 환경과 Kubernetes 노드 구성요소가 설치되어 있어야 한다.

---

## 1. hostname 설정

### 명령어

```bash
hostnamectl
sudo hostnamectl set-hostname worker-us-1
hostname
```

### 각 명령 의미

```bash
hostnamectl
```

현재 서버의 hostname과 OS 정보를 확인한다.

```bash
sudo hostnamectl set-hostname worker-us-1
```

서버의 hostname을 `worker-us-1`로 변경한다.

```bash
hostname
```

현재 적용된 hostname을 확인한다.

### 왜 필요한가?

Kubernetes는 각 노드를 이름으로 구분한다.  
일반적으로 `hostname`이 Kubernetes Node 이름으로 사용된다.

따라서 클러스터 안에서 hostname은 유일해야 한다.

예시:

```text
master-kr-1
worker-us-1
worker-us-2
```

hostname이 중복되면 Kubernetes가 노드를 구분하기 어려워지고, 조인 과정이나 노드 관리에서 문제가 생길 수 있다.

---

## 2. swap 비활성화

### 명령어

```bash
sudo swapoff -a
sudo sed -i.bak '/ swap / s/^/#/' /etc/fstab
free -h
```

### 각 명령 의미

```bash
sudo swapoff -a
```

현재 켜져 있는 모든 swap을 즉시 비활성화한다.

```bash
sudo sed -i.bak '/ swap / s/^/#/' /etc/fstab
```

`/etc/fstab` 파일에서 swap 설정 줄을 주석 처리한다.  
이렇게 해야 서버를 재부팅해도 swap이 다시 켜지지 않는다.

```bash
free -h
```

메모리와 swap 상태를 확인한다.

정상 예시:

```text
Swap: 0B
```

또는

```text
Swap: 0.0
```

### 왜 필요한가?

Swap은 RAM이 부족할 때 디스크 일부를 메모리처럼 사용하는 기능이다.

일반 서버에서는 유용할 수 있지만, Kubernetes에서는 문제가 될 수 있다.

Kubernetes의 `kubelet`은 Pod의 메모리 사용량을 기준으로 노드 상태를 판단하고, Pod를 재시작하거나 스케줄링한다.  
그런데 swap이 켜져 있으면 메모리 부족 상황이 디스크 swap으로 숨겨질 수 있다.

결과적으로:

```text
Pod가 메모리를 많이 사용
↓
원래는 Kubernetes가 OOM 처리 또는 재배치 판단
↓
Swap이 켜져 있으면 디스크로 밀림
↓
서버가 매우 느려짐
↓
Kubernetes가 상태를 정확히 판단하기 어려움
```

그래서 Kubernetes 워커 노드는 보통 swap을 꺼둔다.

---

## 3. 커널 모듈 설정

### 명령어

```bash
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

sudo modprobe overlay
sudo modprobe br_netfilter

lsmod | grep overlay
lsmod | grep br_netfilter
```

### 각 명령 의미

```bash
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF
```

`/etc/modules-load.d/k8s.conf` 파일을 생성하고 아래 내용을 저장한다.

```text
overlay
br_netfilter
```

이 파일은 부팅 시 자동으로 로드할 커널 모듈 목록을 지정한다.

즉 이 설정은 영구 설정이다.

```bash
sudo modprobe overlay
sudo modprobe br_netfilter
```

현재 실행 중인 시스템에 `overlay`, `br_netfilter` 커널 모듈을 즉시 로드한다.

즉 이 설정은 즉시 적용이다.

```bash
lsmod | grep overlay
lsmod | grep br_netfilter
```

해당 커널 모듈이 현재 로드되어 있는지 확인한다.

### 왜 파일에도 쓰고 modprobe도 실행하는가?

역할이 다르다.

```text
/etc/modules-load.d/k8s.conf에 쓰기
→ 재부팅 후에도 자동 적용

modprobe
→ 지금 당장 적용
```

Kubernetes 설치를 계속 진행하려면 현재 세션에서도 바로 적용되어야 하므로 둘 다 수행한다.

---

## 4. overlay 모듈이 필요한 이유

`overlay`는 컨테이너 파일시스템을 위해 필요하다.

Docker나 containerd는 컨테이너 이미지를 여러 레이어로 관리한다.

예시:

```text
base image layer
+ dependency layer
+ app layer
+ writable layer
```

이 레이어들을 하나의 파일시스템처럼 합쳐서 컨테이너가 실행되도록 만드는 데 Linux의 OverlayFS 기능이 사용된다.

즉:

```text
overlay = 컨테이너 이미지 레이어를 합쳐서 실행 가능하게 해주는 커널 기능
```

---

## 5. br_netfilter 모듈이 필요한 이유

`br_netfilter`는 Linux bridge를 지나가는 패킷이 iptables 규칙을 타게 해주는 모듈이다.

Kubernetes에서는 Pod 네트워크, Service 네트워크, NAT, 라우팅 처리를 위해 네트워크 규칙이 필요하다.

Pod 트래픽 흐름 예시:

```text
Pod
↓
가상 네트워크 인터페이스
↓
Linux bridge / CNI 네트워크
↓
노드 네트워크
```

이때 bridge를 지나는 패킷도 iptables 규칙에 걸려야 Kubernetes 네트워크가 정상 동작한다.

즉:

```text
br_netfilter = Pod 네트워크 패킷을 Linux 방화벽/라우팅 규칙이 볼 수 있게 해주는 기능
```

---

## 6. sysctl 네트워크 설정

### 명령어

```bash
cat <<EOF | sudo tee /etc/sysctl.d/99-kubernetes-cri.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF

sudo sysctl --system

sysctl net.ipv4.ip_forward
sysctl net.bridge.bridge-nf-call-iptables
sysctl net.bridge.bridge-nf-call-ip6tables
```

### 각 명령 의미

```bash
cat <<EOF | sudo tee /etc/sysctl.d/99-kubernetes-cri.conf
...
EOF
```

Kubernetes 네트워크에 필요한 커널 파라미터를 `/etc/sysctl.d/99-kubernetes-cri.conf` 파일에 저장한다.

```bash
sudo sysctl --system
```

`/etc/sysctl.d/` 등에 있는 sysctl 설정 파일들을 읽어서 현재 시스템에 적용한다.

```bash
sysctl net.ipv4.ip_forward
sysctl net.bridge.bridge-nf-call-iptables
sysctl net.bridge.bridge-nf-call-ip6tables
```

설정이 실제로 적용되었는지 확인한다.

정상 예시:

```text
net.ipv4.ip_forward = 1
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
```

---

## 7. sysctl 설정값 의미

### `net.bridge.bridge-nf-call-iptables = 1`

Linux bridge를 지나가는 IPv4 패킷에도 iptables 규칙을 적용한다.

Kubernetes Service, Pod 통신, NAT 처리에 중요하다.

예:

```text
Pod → Service → 다른 Pod
```

이런 트래픽이 iptables/CNI 규칙을 거쳐야 정상적으로 라우팅된다.

---

### `net.bridge.bridge-nf-call-ip6tables = 1`

IPv6 트래픽에 대해서도 bridge 패킷이 ip6tables 규칙을 타게 한다.

IPv6를 당장 사용하지 않더라도 Kubernetes 기본 설정으로 같이 넣는 경우가 많다.

---

### `net.ipv4.ip_forward = 1`

서버가 IP 패킷을 다른 네트워크로 전달할 수 있게 한다.

Kubernetes 워커 노드는 단순히 자기 자신의 트래픽만 처리하지 않는다.  
Pod들의 트래픽을 다른 Pod, 다른 노드, Service로 전달해야 한다.

예:

```text
Pod A
↓
Worker Node
↓
다른 Node의 Pod B
```

이때 Worker Node가 라우터처럼 패킷을 전달해야 하므로 `ip_forward=1`이 필요하다.

---

## 8. sysctl 적용 중 Invalid argument 메시지

`sudo sysctl --system` 실행 중 다음과 같은 메시지가 나올 수 있다.

```text
sysctl: setting key "net.ipv4.conf.all.accept_source_route": Invalid argument
sysctl: setting key "net.ipv4.conf.all.promote_secondaries": Invalid argument
```

이 메시지는 직접 만든 Kubernetes 설정 파일 때문이 아니라 Ubuntu 기본 sysctl 파일에서 일부 커널 파라미터를 적용하는 과정에서 나올 수 있다.

중요한 것은 Kubernetes용 설정이 정상 적용되었는지다.

확인해야 할 값:

```text
net.ipv4.ip_forward = 1
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
```

이 값들이 정상이라면 워커 노드 준비 관점에서는 진행 가능하다.

---

## 9. containerd 설치

### 명령어

```bash
sudo apt update
sudo apt install -y containerd
```

### 각 명령 의미

```bash
sudo apt update
```

Ubuntu 패키지 목록을 최신화한다.

```bash
sudo apt install -y containerd
```

컨테이너 런타임인 `containerd`를 설치한다.

`-y` 옵션은 설치 중 나오는 확인 질문에 자동으로 yes를 입력한다.

### containerd가 무엇인가?

`containerd`는 실제 컨테이너를 실행하는 컨테이너 런타임이다.

Kubernetes는 직접 컨테이너를 실행하지 않는다.  
`kubelet`이 containerd에게 컨테이너 실행을 요청한다.

구조:

```text
Kubernetes kubelet
↓
containerd
↓
실제 컨테이너 실행
```

즉, 워커 노드에서 Pod를 실행하려면 containerd 같은 컨테이너 런타임이 필요하다.

---

## 10. containerd 설정 파일 생성

### 명령어

```bash
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
```

### 각 명령 의미

```bash
sudo mkdir -p /etc/containerd
```

containerd 설정 파일을 저장할 디렉터리를 만든다.

```bash
containerd config default
```

containerd의 기본 설정을 출력한다.

```bash
sudo tee /etc/containerd/config.toml
```

출력된 기본 설정을 `/etc/containerd/config.toml` 파일에 저장한다.

```bash
>/dev/null
```

화면 출력은 숨긴다.

결과적으로 다음 파일이 생성된다.

```text
/etc/containerd/config.toml
```

---

## 11. containerd의 SystemdCgroup 설정

### 명령어

```bash
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
```

### 명령 의미

`/etc/containerd/config.toml` 파일 안에서 아래 값을 찾는다.

```text
SystemdCgroup = false
```

그리고 다음 값으로 변경한다.

```text
SystemdCgroup = true
```

### 왜 필요한가?

Kubernetes의 `kubelet`과 `containerd`가 같은 cgroup 관리 방식을 사용하게 하기 위해서다.

`cgroup`은 Linux에서 CPU, 메모리 같은 자원을 제한하고 관리하는 기능이다.

예:

```text
Pod A는 메모리 512MB까지만 사용
Pod B는 CPU 1개까지만 사용
```

요즘 Kubernetes 환경에서는 `systemd cgroup driver` 사용이 권장된다.

그래서 containerd도 systemd cgroup을 사용하도록 맞춰준다.

이 설정이 맞지 않으면 kubelet과 containerd 사이에서 자원 관리 방식이 달라져 문제가 생길 수 있다.

---

## 12. containerd 재시작 및 자동 실행 설정

### 명령어

```bash
sudo systemctl restart containerd
sudo systemctl enable containerd
sudo systemctl status containerd --no-pager
```

### 각 명령 의미

```bash
sudo systemctl restart containerd
```

containerd를 재시작한다.  
설정 파일을 변경했기 때문에 새 설정을 반영하려면 재시작이 필요하다.

```bash
sudo systemctl enable containerd
```

서버가 재부팅되어도 containerd가 자동으로 실행되도록 등록한다.

```bash
sudo systemctl status containerd --no-pager
```

containerd 서비스 상태를 확인한다.

정상 예시:

```text
active (running)
```

---

## 13. Kubernetes 설치를 위한 필수 패키지 설치

### 명령어

```bash
sudo apt update
sudo apt install -y apt-transport-https ca-certificates curl gpg
```

### 각 패키지 의미

#### `apt-transport-https`

APT가 HTTPS 주소의 저장소에서 패키지를 받을 수 있게 해준다.

Kubernetes 패키지 저장소는 HTTPS를 사용한다.

#### `ca-certificates`

HTTPS 인증서를 검증하기 위한 루트 인증서 모음이다.

`https://pkgs.k8s.io` 같은 저장소에 접속할 때 인증서 신뢰 여부를 확인하는 데 필요하다.

#### `curl`

URL에서 파일을 다운로드하거나 API 요청을 보낼 때 사용하는 도구다.

여기서는 Kubernetes 저장소의 GPG 키를 다운로드하는 데 사용한다.

#### `gpg`

패키지 저장소의 서명 키를 처리하는 도구다.

APT가 패키지를 설치할 때 해당 패키지가 신뢰할 수 있는 저장소에서 온 것인지 검증하는 데 필요하다.

---

## 14. APT keyring 디렉터리 생성

### 명령어

```bash
sudo mkdir -p /etc/apt/keyrings
```

### 의미

Kubernetes 저장소의 GPG 키를 저장할 디렉터리를 만든다.

경로:

```text
/etc/apt/keyrings
```

`-p` 옵션은 디렉터리가 이미 있어도 에러 없이 넘어가고, 없으면 생성한다.

---

## 15. Kubernetes 공식 저장소 GPG 키 추가

### 명령어

```bash
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key   | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
```

### 명령 의미

Kubernetes v1.29 공식 패키지 저장소의 Release key를 다운로드한 뒤, APT가 사용할 수 있는 `.gpg` 형식으로 변환해서 저장한다.

### curl 옵션 의미

```text
-f  = HTTP 에러가 발생하면 실패 처리
-s  = 진행 로그를 조용히 출력
-S  = 에러가 발생하면 에러 메시지는 출력
-L  = 리다이렉트가 있으면 따라감
```

### 저장 결과

```text
/etc/apt/keyrings/kubernetes-apt-keyring.gpg
```

### 왜 필요한가?

APT가 Kubernetes 패키지를 설치할 때 다음을 검증하기 위해 필요하다.

```text
이 패키지가 공식 Kubernetes 저장소에서 온 것이 맞는가?
패키지가 중간에서 변조되지 않았는가?
```

---

## 16. Kubernetes APT 저장소 등록

### 명령어

```bash
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /'   | sudo tee /etc/apt/sources.list.d/kubernetes.list
```

### 명령 의미

Ubuntu APT에게 Kubernetes 패키지를 어디서 받을지 알려준다.

결과 파일:

```text
/etc/apt/sources.list.d/kubernetes.list
```

파일 내용:

```text
deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /
```

### 왜 v1.29인가?

문서에서 마스터 Kubernetes 버전이 `v1.29.15` 계열이라고 했기 때문이다.

워커 노드는 마스터와 같은 minor 버전 계열을 맞추는 것이 좋다.

```text
Master = v1.29.x
Worker = v1.29.x
```

버전 계열이 크게 다르면 조인이나 kubelet 동작에서 문제가 생길 수 있다.

---

## 17. 패키지 목록 갱신

### 명령어

```bash
sudo apt update
```

### 의미

방금 Kubernetes 저장소를 추가했으므로, APT 패키지 목록을 다시 가져온다.

이 작업 이후 Ubuntu가 다음 패키지들을 찾을 수 있게 된다.

```text
kubelet
kubeadm
kubectl
```

---

## 18. kubelet / kubeadm / kubectl 설치

### 명령어

```bash
sudo apt install -y kubelet kubeadm kubectl
```

### 설치되는 것

```text
kubelet  = 워커 노드에서 Pod를 관리하는 에이전트
kubeadm  = 클러스터 init/join 도구
kubectl  = Kubernetes CLI
```

---

## 19. kubelet이 하는 일

`kubelet`은 워커 노드에서 계속 실행되는 핵심 프로세스다.

역할:

```text
마스터 API 서버와 통신
내 노드에 어떤 Pod를 띄워야 하는지 확인
containerd에게 컨테이너 실행 요청
Pod 상태를 마스터에게 보고
컨테이너가 죽으면 재시작 처리
```

비유:

```text
워커 노드의 현장 관리자
```

구조:

```text
Kubernetes API Server
↓
kubelet
↓
containerd
↓
Pod / Container
```

---

## 20. kubeadm이 하는 일

`kubeadm`은 Kubernetes 클러스터를 만들거나 노드를 조인할 때 사용하는 도구다.

마스터에서는:

```bash
kubeadm init
```

워커에서는:

```bash
kubeadm join ...
```

을 수행한다.

지금 워커 노드에서는 나중에 아래와 같은 명령을 실행하기 위해 필요하다.

```bash
sudo kubeadm join k8s-api.monithub.org:6443 ...
```

역할:

```text
마스터 클러스터에 워커 노드 가입
인증서/토큰 검증
kubelet 설정 생성
노드 등록
```

비유:

```text
Kubernetes 클러스터 가입 도구
```

---

## 21. kubectl이 하는 일

`kubectl`은 Kubernetes를 조작하는 CLI 도구다.

예시:

```bash
kubectl get nodes
kubectl get pods
kubectl describe pod
kubectl logs
```

워커 노드에서 반드시 필요한 것은 아니지만, 상태 확인과 디버깅에 유용하다.

비유:

```text
Kubernetes 리모컨
```

---

## 22. Kubernetes 패키지 버전 고정

### 명령어

```bash
sudo apt-mark hold kubelet kubeadm kubectl
```

### 의미

`kubelet`, `kubeadm`, `kubectl`이 자동으로 업그레이드되지 않게 고정한다.

### 왜 필요한가?

Kubernetes는 버전 호환성이 중요하다.

예를 들어 마스터가:

```text
v1.29.15
```

인데 워커가 실수로:

```text
v1.30.x
v1.31.x
```

로 올라가면 문제가 생길 수 있다.

그래서 설치한 버전을 고정한다.

---

## 23. 버전 확인

### 명령어

```bash
kubeadm version
kubelet --version
kubectl version --client
```

### 각 명령 의미

```bash
kubeadm version
```

`kubeadm` 설치 버전을 확인한다.

```bash
kubelet --version
```

`kubelet` 설치 버전을 확인한다.

```bash
kubectl version --client
```

`kubectl` 클라이언트 버전을 확인한다.

`--client`를 붙이는 이유는 아직 클러스터 kubeconfig가 없을 수 있기 때문이다.  
즉, Kubernetes API 서버에 접속하지 않고 내 서버에 설치된 kubectl 버전만 확인한다.

---

## 24. 지금까지 완료된 상태

현재까지 완료한 작업은 다음과 같다.

```text
hostname 설정
swap 비활성화
커널 모듈 overlay / br_netfilter 설정
sysctl 네트워크 설정
containerd 설치
containerd systemd cgroup 설정
containerd 재시작 및 자동 실행 설정
Kubernetes v1.29 저장소 등록
kubelet / kubeadm / kubectl 설치
Kubernetes 패키지 버전 고정
```

이제 워커 노드는 Kubernetes 클러스터에 join하기 위한 기본 준비가 된 상태다.

---

## 25. 아직 보류해야 하는 작업

아직 바로 실행하지 않는 것이 좋은 작업:

```bash
sudo kubeadm join k8s-api.monithub.org:6443 ...
```

### 왜 보류하는가?

문서에서 강조한 것처럼, 마스터와 워커 간 Node IP 통신 방식이 아직 확정되지 않았기 때문이다.

특히 다음 문제가 남아 있다.

```text
마스터 INTERNAL-IP = 10.0.0.48
미국 워커가 10.0.0.48에 직접 접근 가능한지 불확실
Cilium VXLAN UDP 8472 통신 필요
kubelet TCP 10250 통신 필요
VPN / WireGuard / Tailscale / OCI Remote Peering 방식 결정 필요
```

`kubeadm join`은 `k8s-api.monithub.org:6443`로 성공할 수 있지만, 조인 후 Pod-to-Pod 통신, CoreDNS, Service routing, Cilium VXLAN이 깨질 수 있다.

따라서 네트워크 방식이 확정된 후 join하는 것이 안전하다.

---

## 26. 다음에 확인할 것

워커 서버에서 마스터 API 접근 확인:

```bash
curl -k https://k8s-api.monithub.org:6443/version
```

또는 TCP 연결 확인:

```bash
timeout 5 bash -c '</dev/tcp/k8s-api.monithub.org/6443' && echo ok
```

정상이라면 워커에서 마스터 API 서버 6443 포트까지 접근 가능한 것이다.

하지만 이것은 조인을 위한 API 접근 확인일 뿐, Pod 네트워크까지 정상이라는 의미는 아니다.

추가로 확인해야 할 것:

```text
마스터 ↔ 워커 Node IP 직접 통신 가능 여부
TCP 10250 kubelet 통신
UDP 8472 Cilium VXLAN 통신
VPN / Peering 방식 결정
```

---

## 27. 전체 흐름 요약

```text
1. hostname 설정
2. swap off
3. overlay / br_netfilter 커널 모듈 설정
4. sysctl 네트워크 설정
5. containerd 설치 및 설정
6. kubelet / kubeadm / kubectl 설치
7. Kubernetes 패키지 버전 고정
8. 마스터 API 6443 연결 테스트
9. VPN / Peering / Node IP 방식 확정
10. kubeadm join
```

---

## 28. 핵심 개념 요약

```text
containerd
→ 실제 컨테이너 실행 담당

kubelet
→ 워커 노드에서 Pod를 관리하는 Kubernetes 에이전트

kubeadm
→ 클러스터 init/join 도구

kubectl
→ Kubernetes CLI

overlay
→ 컨테이너 이미지 레이어 파일시스템 지원

br_netfilter
→ Pod/bridge 트래픽이 iptables 규칙을 타게 함

ip_forward
→ 워커 노드가 Pod 트래픽을 다른 네트워크로 전달할 수 있게 함

swap off
→ kubelet이 메모리 상태를 정확히 판단하도록 함

SystemdCgroup = true
→ kubelet과 containerd의 cgroup 관리 방식을 systemd로 맞춤
```
