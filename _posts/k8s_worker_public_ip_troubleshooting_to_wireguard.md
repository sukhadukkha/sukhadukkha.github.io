# Kubernetes Worker Node 조인 및 네트워크 트러블슈팅 종합 정리

작성일: 2026-05-01  
대상: `worker-us-1` 워커 노드  
최종 결정: Public IP 기반 구성을 포기하고 WireGuard VPN 기반 Node IP 통신망 구성 예정

---

## 1. 전체 상황 요약

한국 OCI 인스턴스에 Kubernetes Control Plane/Master가 있고, 미국 OCI 서버들을 Worker Node로 조인하는 작업을 진행했다.

```text
Master / Control Plane
- 위치: 한국 OCI
- Public IP: 150.230.248.235
- Internal IP: 10.0.0.48
- API Endpoint: k8s-api.monithub.org:6443
- Kubernetes Version: v1.29.15
- CNI: Cilium VXLAN

Worker
- 위치: 미국 OCI
- Node: worker-us-1
```

처음 목표는 Public DNS인 `k8s-api.monithub.org:6443`를 통해 Worker Node를 조인하고, Cilium VXLAN 기반으로 Pod 네트워크를 구성하는 것이었다.

하지만 진행 중 다음 문제가 연쇄적으로 발생했다.

```text
1. kubeadm join 중 마스터 내부 IP 10.0.0.48 접근 실패
2. kube-proxy가 10.0.0.48:6443을 바라보면서 API Server 접근 실패
3. kube-proxy가 Service NAT 규칙을 못 만들어 Cilium이 10.96.0.1:443 접근 실패
4. kube-proxy ConfigMap 수정 후 일부 정상화
5. 이후 API Server 6443 connection refused 간헐 발생
6. 마스터에서 워커 kubelet 10250 접근 실패
7. Cilium RBAC 오류 발생
8. 결국 Public IP/NAT 기반 Node 통신이 불안정하다고 판단
9. WireGuard VPN 기반으로 노드 간 직접 통신 가능한 Node IP를 만들기로 결정
```

---

## 2. 완료한 워커 노드 사전 준비

### hostname 설정

```bash
sudo hostnamectl set-hostname worker-us-1
```

목적:

```text
Kubernetes 클러스터 안에서 Node 이름을 유일하게 만들기 위해 설정
```

### swap 비활성화

```bash
sudo swapoff -a
sudo sed -i.bak '/ swap / s/^/#/' /etc/fstab
```

목적:

```text
kubelet이 메모리 상태를 정확히 판단하도록 swap 비활성화
```

### 커널 모듈 설정

```bash
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

sudo modprobe overlay
sudo modprobe br_netfilter
```

목적:

```text
overlay       → containerd가 컨테이너 이미지 레이어를 실행하는 데 필요
br_netfilter  → Pod/bridge 트래픽이 iptables 규칙을 타게 하기 위해 필요
```

### sysctl 설정

```bash
cat <<EOF | sudo tee /etc/sysctl.d/99-kubernetes-cri.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF

sudo sysctl --system
```

확인:

```bash
sysctl net.ipv4.ip_forward
sysctl net.bridge.bridge-nf-call-iptables
```

정상 값:

```text
net.ipv4.ip_forward = 1
net.bridge.bridge-nf-call-iptables = 1
```

목적:

```text
Pod 트래픽 라우팅과 Kubernetes Service/Pod 네트워크 처리를 위해 필요
```

### containerd 설치 및 설정

```bash
sudo apt install -y containerd
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd
```

목적:

```text
Kubernetes Worker Node에서 실제 컨테이너를 실행할 런타임 구성
kubelet → containerd → Pod/Container 실행
```

### kubeadm / kubelet / kubectl 설치

```bash
sudo apt install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
```

확인:

```bash
kubeadm version
kubelet --version
kubectl version --client
```

설치 버전:

```text
kubeadm: v1.29.15
kubelet: v1.29.15
kubectl: v1.29.15
Platform: linux/arm64
```

---

## 3. API Server 접근 확인

워커에서 마스터 API Server 접근 확인:

```bash
curl -k https://k8s-api.monithub.org:6443/version
```

정상 응답:

```json
{
  "major": "1",
  "minor": "29",
  "gitVersion": "v1.29.15",
  "platform": "linux/arm64"
}
```

TCP 연결 확인:

```bash
timeout 5 bash -c '</dev/tcp/k8s-api.monithub.org/6443' && echo ok
```

결과:

```text
ok
```

확인된 것:

```text
워커 → k8s-api.monithub.org:6443 접근 가능
DNS 해석 가능
마스터 API Server가 응답함
```

하지만 이후 문제를 통해, API Server endpoint 접근 가능 여부와 Node 간 통신 가능 여부는 별개라는 점이 확인되었다.

---

## 4. 워커 OS 방화벽 설정

초기에는 워커 UFW에서 다음 포트를 Anywhere로 열었다.

```text
10250/tcp  ALLOW IN Anywhere
8472/udp   ALLOW IN Anywhere
```

이후 보안을 위해 마스터 IP만 허용하도록 변경할 계획이 생겼다.

권장 형태:

```bash
sudo ufw allow from 150.230.248.235/32 to any port 10250 proto tcp
sudo ufw allow from 150.230.248.235/32 to any port 8472 proto udp
```

의미:

```text
10250/tcp → 마스터/API Server가 워커 kubelet에 접근하기 위한 포트
8472/udp  → Cilium VXLAN 노드 간 터널링 포트
```

주의:

```text
6443/tcp는 워커 인바운드 포트가 아니라 마스터 API Server 포트다.
워커는 마스터의 6443으로 outbound 접근한다.
```

---

## 5. 문제 1: kubeadm join 중 10.0.0.48 접근 실패

처음 `kubeadm join`을 실행했을 때 다음 에러가 발생했다.

```text
unable to fetch the kubeadm-config ConfigMap
Get "https://10.0.0.48:6443/api/v1/namespaces/kube-system/configmaps/kubeadm-config?timeout=10s":
dial tcp 10.0.0.48:6443: connect: no route to host
```

명령은 Public DNS로 시작했다.

```bash
sudo kubeadm join k8s-api.monithub.org:6443 ...
```

하지만 join 과정 중 클러스터 설정을 가져오면서 내부 IP인 `10.0.0.48:6443`로 접근하려 했다.

```text
처음 진입 주소:
worker → k8s-api.monithub.org:6443

join 중간:
worker → 10.0.0.48:6443
```

미국 워커는 한국 OCI 내부 IP `10.0.0.48`로 라우팅할 수 없기 때문에 실패했다.

---

## 6. join 성공

마스터 쪽 endpoint 설정 수정 후 새 join 명령을 실행했다.

```bash
sudo kubeadm join k8s-api.monithub.org:6443 \
  --token 0c1540.680d21eef8a6ca2e \
  --discovery-token-ca-cert-hash sha256:df20a1258756bd1584a68b49ea7855205d51756164a3313d8fbd821422be8d50
```

결과:

```text
This node has joined the cluster:
* Certificate signing request was sent to apiserver and a response was received.
* The Kubelet was informed of the new secure connection details.
```

의미:

```text
kubelet이 API Server에 붙어 TLS bootstrap 성공
worker-us-1 노드가 클러스터에 등록됨
```

kubelet 설정 확인:

```bash
sudo grep server /etc/kubernetes/kubelet.conf
```

결과:

```text
server: https://k8s-api.monithub.org:6443
```

---

## 7. kubelet 상태 확인

워커에서 kubelet 상태 확인:

```bash
sudo systemctl status kubelet --no-pager
```

결과:

```text
Active: active (running)
```

의미:

```text
kubelet은 워커 노드에서 정상 실행 중
kubelet은 컨테이너가 아니라 systemd 서비스
```

구조:

```text
worker-us-1
├── kubelet      → OS systemd 서비스
├── containerd   → OS systemd 서비스
└── Kubernetes Pod들
    ├── kube-proxy
    ├── cilium-agent
    ├── cilium-envoy
    └── cilium-operator
```

---

## 8. kubectl이 워커에서 바로 안 된 이유

워커에서 다음 명령을 실행했다.

```bash
sudo kubectl get pods
```

에러:

```text
The connection to the server localhost:8080 was refused
```

원인:

```text
kubectl이 사용할 kubeconfig가 워커 사용자 환경에 없었음
kubeconfig가 없으면 kubectl은 기본값 localhost:8080으로 접속 시도
```

정리:

```text
kubectl → Kubernetes API Server에 질의하는 도구, kubeconfig 필요
crictl  → 워커 로컬 containerd를 직접 조회하는 도구, kubeconfig 불필요
```

그래서 워커 내부 컨테이너 확인에는 `crictl`을 사용했다.

---

## 9. crictl로 워커의 Pod/컨테이너 확인

실행 중인 컨테이너 조회:

```bash
sudo crictl ps
```

Pod 목록 조회:

```bash
sudo crictl pods
```

특정 Pod 안의 컨테이너 확인:

```bash
sudo crictl ps -a --pod <POD_ID>
```

구조:

```text
Node
└── Pod
    └── Container
```

`crictl pods`는 Pod를 보고, `crictl ps`는 컨테이너를 본다.

---

## 10. 문제 2: kube-proxy는 Running이지만 API Server에 못 붙음

kube-proxy 컨테이너는 생성되어 Running 상태였다.

```text
kube-proxy Running
```

하지만 로그를 확인하니 다음 에러가 반복되었다.

```bash
sudo crictl logs <kube-proxy-container-id>
```

에러:

```text
Failed to retrieve node info
Get "https://10.0.0.48:6443/api/v1/nodes/worker-us-1":
dial tcp 10.0.0.48:6443: connect: no route to host
```

또한 Service, Node, EndpointSlice를 watch하지 못했다.

```text
failed to list *v1.Service
failed to list *v1.Node
failed to list *v1.EndpointSlice
```

원인:

```text
kube-proxy가 API Server 주소로 아직 내부 IP를 보고 있었음
server: https://10.0.0.48:6443
```

확인 명령:

```bash
sudo grep -R "10.0.0.48" /etc/kubernetes /var/lib/kubelet 2>/dev/null
```

결과:

```text
/var/lib/kubelet/pods/.../volumes/kubernetes.io~configmap/kube-proxy/kubeconfig.conf:
    server: https://10.0.0.48:6443
```

이 파일은 워커 로컬 파일처럼 보이지만, 원본은 마스터의 Kubernetes ConfigMap이다.

```text
마스터 kube-system/kube-proxy ConfigMap
↓
워커 kube-proxy Pod에 volume으로 마운트
↓
/var/lib/kubelet/pods/.../kube-proxy/kubeconfig.conf
```

---

## 11. kube-proxy가 하는 일

kube-proxy는 Kubernetes Service 네트워크를 동작하게 하는 컴포넌트다.

예를 들어 Service IP가 있으면:

```text
kubernetes.default.svc = 10.96.0.1:443
```

이 Service IP는 실제 서버 IP가 아니다. kube-proxy가 iptables NAT 규칙을 만들어 실제 API Server로 연결해야 한다.

정상 흐름:

```text
Pod 또는 시스템 컴포넌트
↓
10.96.0.1:443
↓
kube-proxy iptables NAT 규칙
↓
실제 API Server
```

kube-proxy가 API Server에 못 붙으면 Service/Endpoint 정보를 못 받아오고, NAT 규칙을 만들 수 없다.

---

## 12. kube-proxy 문제로 인해 Cilium도 실패

Cilium 로그에서 다음 에러가 발생했다.

```text
Unable to contact k8s api-server
Get "https://10.96.0.1:443/api/v1/namespaces/kube-system":
dial tcp 10.96.0.1:443: i/o timeout
```

`10.96.0.1`은 보통 Kubernetes 기본 API Server Service IP다.

```text
default/kubernetes Service
kubernetes.default.svc
10.96.0.1:443
```

Cilium은 API Server에 접근하기 위해 이 내부 Service IP를 사용하려고 했다.

하지만 kube-proxy가 `10.96.0.1`에 대한 NAT 규칙을 만들지 못했기 때문에 timeout이 발생했다.

확인 명령:

```bash
sudo iptables -t nat -L -n | grep 10.96.0.1
```

초기 결과:

```text
결과 없음
```

의미:

```text
kube-proxy가 Kubernetes API Service IP 10.96.0.1에 대한 iptables NAT 규칙을 만들지 못함
```

---

## 13. 해결 1: kube-proxy ConfigMap 수정

마스터에서 kube-proxy ConfigMap을 수정했다.

수정 전:

```yaml
server: https://10.0.0.48:6443
```

수정 후:

```yaml
server: https://k8s-api.monithub.org:6443
```

이후 kube-proxy DaemonSet/Pod가 재시작되었다.

재시작 후 워커에서 상태 확인:

```bash
sudo crictl ps -a
```

결과 예시:

```text
kube-proxy Running ATTEMPT 0
cilium-agent Running ATTEMPT 0
```

Cilium init containers:

```text
config                    Exited ATTEMPT 0
mount-cgroup              Exited ATTEMPT 0
apply-sysctl-overwrites   Exited ATTEMPT 0
mount-bpf-fs              Exited ATTEMPT 0
clean-cilium-state        Exited ATTEMPT 0
install-cni-binaries      Exited ATTEMPT 0
```

이는 정상이다. init container는 필요한 초기 작업을 마치면 `Exited` 상태가 된다.

---

## 14. 해결 2: iptables NAT 규칙 생성 확인

다시 확인:

```bash
sudo iptables -t nat -L -n | grep 10.96.0.1
```

결과:

```text
KUBE-SVC-NPX46M4PTMTKRN6Y  tcp  --  0.0.0.0/0  10.96.0.1  /* default/kubernetes:https cluster IP */
KUBE-MARK-MASQ             tcp  -- !10.244.0.0/16 10.96.0.1 /* default/kubernetes:https cluster IP */
```

의미:

```text
kube-proxy가 10.96.0.1:443 Kubernetes API Service에 대한 iptables NAT 규칙을 생성함
```

이 시점에 해결된 것:

```text
kube-proxy ConfigMap 내부 IP 문제 해결
kube-proxy API Server 접근 가능해짐
10.96.0.1 Service NAT 규칙 생성됨
Cilium agent가 Running 상태로 올라옴
```

---

## 15. 문제 3: 마스터에서 워커 kubelet 10250 접근 실패

팀장님이 OpenLens/logs 확인 중 다음 에러를 확인했다.

```text
Failed to load logs:
Get "https://10.0.0.10:10250/containerLogs/kube-system/cilium-t55qj/cilium-agent?...":
dial tcp 10.0.0.10:10250: connect: no route to host
```

의미:

```text
OpenLens / kubectl logs
↓
Kubernetes API Server
↓
worker-us-1 Node IP:10250
↓
kubelet
↓
Pod logs
```

그런데 워커의 Node IP가 `10.0.0.10` 같은 미국 OCI 내부 IP로 잡혀 있고, 한국 마스터가 이 IP로 라우팅할 수 없기 때문에 실패했다.

이 문제는 Cilium Pod 네트워크 문제가 아니라, API Server가 kubelet에 접근하는 노드 관리 통신 문제다.

```text
Pod ↔ Pod 통신        → Cilium CNI
API Server ↔ kubelet → TCP 10250
```

즉 Cilium이 정상이어도, 마스터가 워커 Node IP:10250에 접근하지 못하면 logs/exec/probe 관련 문제가 발생할 수 있다.

---

## 16. 문제 4: kubelet lease/status 업데이트 중 connection refused

kubelet 로그에서 다음 에러가 발생했다.

```text
Failed to ensure lease exists, will retry
Get "https://k8s-api.monithub.org:6443/apis/coordination.k8s.io/v1/namespaces/kube-node-lease/leases/worker-us-1?timeout=10s":
dial tcp 150.230.248.235:6443: connect: connection refused
```

또는:

```text
Error updating node status
Get "https://k8s-api.monithub.org:6443/api/v1/nodes/worker-us-1":
dial tcp 150.230.248.235:6443: connect: connection refused
```

의미:

```text
kubelet이 API Server로 Node Lease 또는 Node Status를 업데이트하려 했지만,
150.230.248.235:6443에서 연결이 거부됨
```

`connection refused`의 의미:

```text
IP까지는 도달했지만 해당 포트에서 연결을 거부함
```

이는 `no route to host`와 다르다.

```text
no route to host     → 해당 IP로 가는 경로가 없음
connection refused   → IP까지는 갔지만 포트 연결이 거부됨
```

가능성:

```text
API Server 또는 앞단 프록시/LB가 순간적으로 불안정
마스터 6443이 간헐적으로 닫힘
방화벽/NSG가 reject
Public endpoint 기반 연결이 안정적이지 않음
```

---

## 17. 문제 5: Cilium RBAC 오류

Cilium 로그에서 다음 에러가 발생했다.

```text
pods is forbidden:
User "system:serviceaccount:kube-system:cilium" cannot watch resource "pods"

ciliumcidrgroups.cilium.io is forbidden:
User "system:serviceaccount:kube-system:cilium" cannot watch resource "ciliumcidrgroups"
```

그리고 다음 메시지가 포함되었다.

```text
clusterrole.rbac.authorization.k8s.io "cilium" not found
clusterrole.rbac.authorization.k8s.io "system:discovery" not found
clusterrole.rbac.authorization.k8s.io "system:basic-user" not found
clusterrole.rbac.authorization.k8s.io "system:public-info-viewer" not found
clusterrole.rbac.authorization.k8s.io "system:service-account-issuer-discovery" not found
```

의미:

```text
Cilium ServiceAccount가 필요한 리소스를 watch할 권한이 없음
Cilium ClusterRole/ClusterRoleBinding이 누락되었거나 설치/RBAC 리소스가 꼬였을 가능성
```

마스터에서 확인할 명령:

```bash
kubectl get clusterrole | grep -E "cilium|system:discovery|system:basic-user|system:public-info-viewer"
kubectl get clusterrolebinding | grep cilium
kubectl get sa -n kube-system cilium
kubectl auth can-i watch pods --as=system:serviceaccount:kube-system:cilium --all-namespaces
```

---

## 18. cilium-envoy xds.sock 오류

cilium-envoy 로그에서 다음 에러가 발생했다.

```text
/var/run/cilium/envoy/sockets/xds.sock
No such file or directory
```

의미:

```text
cilium-envoy가 Cilium agent가 만들어줘야 하는 xDS socket에 접근하려 했지만 파일이 없음
```

정상 구조:

```text
cilium-agent
↓ xDS socket 제공
/var/run/cilium/envoy/sockets/xds.sock
↑
cilium-envoy
```

이 에러는 cilium-envoy 자체가 1차 원인이라기보다, Cilium agent/config 초기화가 정상적으로 완료되지 않았을 때 발생하는 후속 증상으로 판단했다.

---

## 19. DaemonSet / HTTP probe 관련 발언 해석

팀장님이 다음과 같이 말했다.

```text
kubelet이 안 간다
http 프로브 실패
왜 데몬셋이 안 뜨지
```

의미 가능성:

```text
1. API Server가 워커 kubelet 10250에 접근하지 못함
2. kubelet이 Pod readiness/liveness HTTP probe를 실패 처리함
3. DaemonSet으로 떠야 하는 Cilium/kube-proxy Pod가 Ready가 안 됨
```

DaemonSet이란:

```text
각 노드마다 하나씩 떠야 하는 Pod를 관리하는 Kubernetes 리소스
```

예시:

```text
kube-proxy      → DaemonSet
Cilium          → DaemonSet
Cilium Envoy    → DaemonSet
```

HTTP probe란:

```text
kubelet이 컨테이너의 특정 HTTP endpoint를 호출해서 정상 여부를 판단하는 health check
```

---

## 20. 해결된 것과 남은 문제

### 해결된 것

```text
워커 노드 OS/Kubernetes 사전 준비 완료
kubeadm/kubelet/kubectl v1.29.15 설치 완료
worker-us-1 join 성공
kubelet.conf가 public endpoint를 보도록 수정됨
kube-proxy ConfigMap의 10.0.0.48 문제 일부 해결
kube-proxy가 10.96.0.1 iptables NAT 규칙 생성
Cilium agent Running 상태 확인
```

### 남은 문제

```text
마스터가 워커 Node IP 10.0.0.10:10250에 접근하지 못함
워커가 마스터 public endpoint 150.230.248.235:6443에 간헐적으로 connection refused 발생
Cilium RBAC ClusterRole/ClusterRoleBinding 누락 또는 비정상
Public IP/NAT 기반 Node IP 구성이 불안정
```

---

## 21. 왜 Public IP 기반 구성이 어려웠는가

Public IP 기반으로 Kubernetes 멀티 리전 노드를 구성하려면 다음 조건이 맞아야 한다.

```text
1. 각 노드의 Kubernetes Node IP가 서로 접근 가능한 IP여야 함
2. API Server가 Worker kubelet 10250에 접근 가능해야 함
3. Cilium VXLAN UDP 8472가 노드 간 열려 있어야 함
4. kubelet/kube-proxy/Cilium이 모두 접근 가능한 API endpoint를 바라봐야 함
5. Public IP가 NAT 구조여도 kubelet --node-ip 설정이 정상 동작해야 함
```

하지만 OCI Public IP는 보통 OS 인터페이스에 직접 붙은 IP가 아니라 NAT로 연결되는 구조일 수 있다.

예:

```text
서버 OS 실제 IP: 10.0.0.10
외부 Public IP: 129.xxx.xxx.xxx
```

이 경우 Kubernetes가 자동으로 잡는 Node IP는 보통 내부 IP가 된다.

```text
worker-us-1 INTERNAL-IP = 10.0.0.10
```

한국 마스터가 미국 워커의 `10.0.0.10`에 접근할 수 없으면 다음 문제가 생긴다.

```text
API Server → worker kubelet 10.0.0.10:10250 실패
Cilium VXLAN 노드 간 통신 불안정
Pod-to-Pod / Service routing 문제 가능
logs/exec/probe 문제 발생
```

---

## 22. WireGuard VPN을 쓰기로 한 이유

최종적으로 Public IP 기반을 포기하고 WireGuard를 쓰기로 한 이유는 다음과 같다.

```text
Kubernetes에서 중요한 것은 Public IP가 존재하는지가 아니라,
각 노드의 Kubernetes Node IP가 서로 직접 통신 가능한지 여부다.
```

WireGuard를 사용하면 각 노드에 VPN 인터페이스와 VPN IP를 부여할 수 있다.

예:

```text
Master wg0 IP: 10.100.0.1
Worker1 wg0 IP: 10.100.0.2
Worker2 wg0 IP: 10.100.0.3
Worker3 wg0 IP: 10.100.0.4
```

이후 Kubernetes Node IP를 WireGuard IP로 잡으면 된다.

```text
master Node IP  → 10.100.0.1
worker-us-1     → 10.100.0.2
worker-us-2     → 10.100.0.3
worker-us-3     → 10.100.0.4
```

그러면 다음 통신이 VPN 안에서 안정적으로 가능해진다.

```text
worker → master API Server
master → worker kubelet 10250
node ↔ node Cilium VXLAN UDP 8472
Pod-to-Pod 통신
Service routing
CoreDNS
logs/exec/probe
```

---

## 23. WireGuard 구성 후 기대 구조

Public IP/NAT 기반 구조:

```text
master public endpoint
worker private IP
NAT
라우팅 불일치
Node IP 접근 실패
```

WireGuard 기반 구조:

```text
한국 Master
wg0: 10.100.0.1
        │
        │ WireGuard VPN
        │
미국 Worker1
wg0: 10.100.0.2

미국 Worker2
wg0: 10.100.0.3

미국 Worker3
wg0: 10.100.0.4
```

Kubernetes 관점:

```text
kubectl get nodes -o wide

NAME          INTERNAL-IP
master        10.100.0.1
worker-us-1   10.100.0.2
worker-us-2   10.100.0.3
worker-us-3   10.100.0.4
```

이 구조가 되면 모든 Node IP가 서로 직접 통신 가능해진다.

---

## 24. WireGuard 이후 다시 확인해야 할 것

### 노드 간 VPN IP 통신

```bash
ping <상대 wg0 IP>
```

예:

```bash
ping 10.100.0.1
ping 10.100.0.2
```

### API Server 접근

워커에서:

```bash
curl -k https://k8s-api.monithub.org:6443/version
```

또는 API Server를 WireGuard IP로 노출한다면:

```bash
curl -k https://10.100.0.1:6443/version
```

### kubelet 포트 접근

마스터에서 워커 kubelet 접근 확인:

```bash
timeout 5 bash -c '</dev/tcp/10.100.0.2/10250' && echo ok
```

### Cilium VXLAN 포트

노드 간 UDP 8472 허용 필요.

```text
Source: WireGuard CIDR
Port: UDP 8472
```

### Node IP 확인

마스터에서:

```bash
kubectl get nodes -o wide
```

확인할 것:

```text
INTERNAL-IP가 WireGuard IP로 잡혔는지
```

### kube-proxy/Cilium 상태 확인

```bash
kubectl -n kube-system get pods -o wide
kubectl -n kube-system get pods -l k8s-app=cilium -o wide
kubectl -n kube-system exec ds/cilium -- cilium status
```

워커에서:

```bash
sudo crictl ps -a
sudo iptables -t nat -L -n | grep 10.96.0.1
```

---

## 25. 이번 트러블슈팅에서 사용한 주요 명령어

### API Server 접근 확인

```bash
curl -k https://k8s-api.monithub.org:6443/version
timeout 5 bash -c '</dev/tcp/k8s-api.monithub.org/6443' && echo ok
```

### kubelet 상태 확인

```bash
sudo systemctl status kubelet --no-pager
sudo journalctl -u kubelet -n 200 --no-pager
```

### containerd/Pod/Container 확인

```bash
sudo crictl ps
sudo crictl ps -a
sudo crictl pods
sudo crictl logs <container-id>
sudo crictl ps -a --pod <pod-id>
```

### kube-proxy/Cilium 문제 확인

```bash
sudo crictl ps -a | grep kube-proxy
sudo crictl ps -a | grep cilium
sudo crictl logs <kube-proxy-container-id>
sudo crictl logs <cilium-agent-container-id>
```

### 내부 IP 참조 검색

```bash
sudo grep -R "10.0.0.48" /etc/kubernetes /var/lib/kubelet 2>/dev/null
sudo grep -R "10.0.0.48" /var/lib/kubelet/pods 2>/dev/null
```

### kubelet kubeconfig 확인

```bash
sudo grep server /etc/kubernetes/kubelet.conf
sudo grep server /etc/kubernetes/bootstrap-kubelet.conf 2>/dev/null
```

### iptables NAT 확인

```bash
sudo iptables -t nat -L -n | grep 10.96.0.1
```

### 마스터에서 확인할 명령

```bash
kubectl get nodes -o wide
kubectl get pods -A -o wide
kubectl -n kube-system get pods -o wide
kubectl -n kube-system get ds
kubectl -n kube-system get cm kube-proxy -o yaml
kubectl get clusterrole | grep cilium
kubectl get clusterrolebinding | grep cilium
kubectl auth can-i watch pods --as=system:serviceaccount:kube-system:cilium --all-namespaces
```

---

## 26. 최종 결론

이번 작업을 통해 확인한 핵심은 다음이다.

```text
Kubernetes에서 멀티 리전 Worker Node를 붙일 때 중요한 것은
Public IP 접속 가능 여부가 아니라 Node IP 간 직접 통신 가능 여부다.
```

Public DNS `k8s-api.monithub.org:6443`로 join 자체는 가능했지만, 이후 다음 문제가 계속 발생했다.

```text
kube-proxy가 내부 IP를 참조
Cilium이 API Server Service IP에 접근 실패
API Server가 워커 kubelet 10250에 접근 실패
kubelet이 public endpoint 6443에 간헐적으로 connection refused
Node IP가 private IP로 잡혀 상호 라우팅 불가
```

따라서 최종적으로 WireGuard VPN을 구축하여 모든 노드가 서로 직접 통신 가능한 VPN IP를 갖도록 하는 방향이 타당하다.

최종 목표:

```text
각 노드의 Kubernetes INTERNAL-IP = WireGuard IP
노드 간 10250 / 8472 / 6443 통신 안정화
Cilium VXLAN 정상화
CoreDNS / Service routing 정상화
logs / exec / probe 정상화
```

---

## 27. 팀장님께 공유할 요약

```text
Public endpoint로 kubeadm join은 성공했지만,
이후 kube-proxy, Cilium, kubelet, API Server 간 통신에서 계속 내부 IP/Node IP 라우팅 문제가 발생했습니다.

특히 kube-proxy는 ConfigMap 수정 전까지 10.0.0.48:6443을 보고 있었고,
마스터는 워커의 10.0.0.10:10250에 접근하지 못했습니다.

kube-proxy ConfigMap 수정 후 10.96.0.1 NAT 규칙은 생성됐지만,
여전히 kubelet lease/status 업데이트에서 150.230.248.235:6443 connection refused가 발생했고,
Cilium RBAC/ClusterRole 문제도 확인됐습니다.

결국 Public IP/NAT 기반으로 노드 간 통신을 맞추는 것보다,
WireGuard로 각 노드가 서로 직접 통신 가능한 VPN IP를 만들고
그 IP를 Kubernetes Node IP로 사용하는 구성이 더 안정적일 것 같습니다.
```
