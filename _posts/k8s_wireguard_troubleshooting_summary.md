# Kubernetes Worker Node 조인 + WireGuard 전환 트러블슈팅 정리

작성일: 2026-05-01  
대상 노드: `worker-us-1`  
최종 상태: WireGuard VPN 연결 성공, kube-proxy / Cilium / cilium-envoy / kubelet 정상화 확인 단계

---

## 1. 전체 배경

한국 OCI 인스턴스에 Kubernetes Control Plane/Master가 있고, 미국 OCI 서버를 Worker Node로 붙이는 작업을 진행했다.

초기 구성 정보:

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
- Node name: worker-us-1
- WireGuard IP: 10.200.0.2
```

초기 목표는 Public DNS인 `k8s-api.monithub.org:6443`로 워커를 조인하고, Cilium VXLAN 기반으로 Pod 네트워크를 구성하는 것이었다.

하지만 Public IP / NAT 기반 구성에서 여러 문제가 발생했고, 최종적으로 WireGuard VPN을 구축해 노드 간 직접 통신 가능한 Node IP를 구성하는 방향으로 전환했다.

---

## 2. 워커 노드 사전 준비

### 2.1 hostname 설정

```bash
sudo hostnamectl set-hostname worker-us-1
```

목적:

```text
Kubernetes 클러스터 안에서 노드 이름이 겹치지 않도록 설정
```

---

### 2.2 swap 비활성화

```bash
sudo swapoff -a
sudo sed -i.bak '/ swap / s/^/#/' /etc/fstab
```

목적:

```text
kubelet이 메모리 상태를 정확히 판단하도록 swap 비활성화
```

---

### 2.3 커널 모듈 설정

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
br_netfilter  → Pod/bridge 트래픽이 iptables 규칙을 타도록 하기 위해 필요
```

---

### 2.4 sysctl 설정

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

---

### 2.5 containerd 설치 및 설정

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
kubelet이 Pod/Container를 실행할 수 있도록 containerd 런타임 구성
```

구조:

```text
kubelet
↓
containerd
↓
Pod / Container
```

---

### 2.6 kubeadm / kubelet / kubectl 설치

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

하지만 이후 확인한 것처럼, API Server endpoint 접근 가능 여부와 Kubernetes Node IP 간 상호 통신 가능 여부는 별개다.

---

## 4. kubeadm join 1차 실패

초기 join 명령은 Public DNS를 사용했다.

```bash
sudo kubeadm join k8s-api.monithub.org:6443 \
  --token ... \
  --discovery-token-ca-cert-hash sha256:...
```

하지만 다음 에러가 발생했다.

```text
unable to fetch the kubeadm-config ConfigMap
Get "https://10.0.0.48:6443/api/v1/namespaces/kube-system/configmaps/kubeadm-config?timeout=10s":
dial tcp 10.0.0.48:6443: connect: no route to host
```

### 원인

명령은 Public DNS로 시작했지만, join 과정 중 클러스터 설정을 읽으면서 내부 IP인 `10.0.0.48:6443`로 접근하려 했다.

```text
처음 진입:
worker → k8s-api.monithub.org:6443

join 중간:
worker → 10.0.0.48:6443
```

미국 워커는 한국 OCI 내부 IP `10.0.0.48`에 라우팅할 수 없으므로 실패했다.

---

## 5. kubeadm join 성공

마스터 쪽 endpoint 관련 수정 후 다시 join을 수행했다.

```bash
sudo kubeadm join k8s-api.monithub.org:6443 \
  --token 0c1540.680d21eef8a6ca2e \
  --discovery-token-ca-cert-hash sha256:df20a1258756bd1584a68b49ea7855205d51756164a3313d8fbd821422be8d50
```

성공 메시지:

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

즉 kubelet은 Public DNS를 바라보고 있었다.

---

## 6. kubelet 상태 확인

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
kubelet은 컨테이너가 아니라 OS systemd 서비스
```

구조:

```text
worker-us-1
├── kubelet      → systemd 서비스
├── containerd   → systemd 서비스
└── Kubernetes Pod들
    ├── kube-proxy
    ├── cilium-agent
    ├── cilium-envoy
    └── opentelemetry-host
```

---

## 7. kubectl이 워커에서 바로 안 된 이유

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

따라서 워커 내부의 실제 Pod/Container 상태 확인에는 `crictl`을 사용했다.

---

## 8. crictl로 워커 컨테이너 확인

### 실행 중인 컨테이너 조회

```bash
sudo crictl ps
```

### 전체 컨테이너 조회

```bash
sudo crictl ps -a
```

### Pod 목록 조회

```bash
sudo crictl pods
```

### 특정 Pod 안의 컨테이너 확인

```bash
sudo crictl ps -a --pod <POD_ID>
```

구조:

```text
Node
└── Pod
    └── Container
```

즉:

```text
crictl pods → Pod 목록 확인
crictl ps   → Container 목록 확인
```

---

## 9. kube-proxy 문제

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

또한 다음 리소스를 watch하지 못했다.

```text
Service
Node
EndpointSlice
Events
```

### 원인

kube-proxy가 아직 내부 IP를 보고 있었다.

```text
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

이 파일은 워커에 있는 파일이지만, 원본은 마스터의 Kubernetes ConfigMap이다.

```text
마스터 kube-system/kube-proxy ConfigMap
↓
워커 kube-proxy Pod에 volume으로 마운트
↓
/var/lib/kubelet/pods/.../kube-proxy/kubeconfig.conf
```

즉 워커에서 직접 수정하는 것이 아니라, 마스터에서 `kube-proxy` ConfigMap을 수정해야 했다.

---

## 10. kube-proxy가 하는 일

kube-proxy는 Kubernetes Service 네트워크를 동작하게 하는 컴포넌트다.

예:

```text
kubernetes.default.svc = 10.96.0.1:443
```

`10.96.0.1`은 실제 서버 IP가 아니라 Kubernetes Service IP다.  
kube-proxy가 iptables NAT 규칙을 만들어 실제 API Server로 전달한다.

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

## 11. Cilium이 같이 실패한 이유

Cilium 로그:

```text
Unable to contact k8s api-server
Get "https://10.96.0.1:443/api/v1/namespaces/kube-system":
dial tcp 10.96.0.1:443: i/o timeout
```

원인 흐름:

```text
kube-proxy가 API Server 접근 실패
↓
Service / EndpointSlice 정보 조회 실패
↓
10.96.0.1:443 NAT 규칙 생성 실패
↓
Cilium이 10.96.0.1:443로 API Server 접근 시도
↓
timeout
```

초기 확인:

```bash
sudo iptables -t nat -L -n | grep 10.96.0.1
```

결과:

```text
결과 없음
```

의미:

```text
kube-proxy가 Kubernetes API Service IP 10.96.0.1에 대한 iptables NAT 규칙을 만들지 못함
```

---

## 12. kube-proxy ConfigMap 수정으로 해결된 부분

마스터에서 `kube-proxy` ConfigMap을 수정했다.

수정 전:

```yaml
server: https://10.0.0.48:6443
```

수정 후:

```yaml
server: https://k8s-api.monithub.org:6443
```

이후 kube-proxy Pod가 재시작되었다.

워커에서 확인:

```bash
sudo crictl ps -a
```

정상 예:

```text
kube-proxy Running ATTEMPT 0
cilium-agent Running ATTEMPT 0
```

Cilium init container들은 `Exited` 상태였지만, 이는 정상이다.

```text
config                    Exited ATTEMPT 0
mount-cgroup              Exited ATTEMPT 0
apply-sysctl-overwrites   Exited ATTEMPT 0
mount-bpf-fs              Exited ATTEMPT 0
clean-cilium-state        Exited ATTEMPT 0
install-cni-binaries      Exited ATTEMPT 0
```

init container는 초기 작업을 마치면 종료된다.

---

## 13. iptables NAT 규칙 생성 확인

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

이 시점에서 해결된 것:

```text
kube-proxy ConfigMap 내부 IP 문제 해결
kube-proxy API Server 접근 가능
10.96.0.1 Service NAT 규칙 생성
Cilium agent Running 상태 확인
```

---

## 14. Public IP 기반 구성에서 계속 남은 문제

### 14.1 마스터 → 워커 kubelet 10250 접근 실패

팀장님이 본 에러:

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
```

마스터가 워커의 Node IP `10.0.0.10:10250`에 접근하지 못했다.

핵심:

```text
Pod ↔ Pod 통신        → Cilium CNI
API Server ↔ kubelet → TCP 10250
```

즉 Cilium이 정상이어도, API Server가 워커 kubelet 10250에 접근하지 못하면 logs/exec/probe 문제가 발생한다.

---

### 14.2 kubelet lease/status 업데이트 중 connection refused

kubelet 로그:

```text
Failed to ensure lease exists, will retry
Get "https://k8s-api.monithub.org:6443/apis/coordination.k8s.io/v1/namespaces/kube-node-lease/leases/worker-us-1?timeout=10s":
dial tcp 150.230.248.235:6443: connect: connection refused
```

의미:

```text
kubelet이 API Server로 Node Lease / Node Status를 업데이트하려 했지만,
150.230.248.235:6443에서 연결이 거부됨
```

`connection refused`와 `no route to host`의 차이:

```text
no route to host     → 해당 IP로 가는 경로가 없음
connection refused   → IP까지는 갔지만 포트 연결이 거부됨
```

가능성:

```text
API Server 또는 앞단 프록시/LB 불안정
마스터 6443이 간헐적으로 닫힘
방화벽/NSG reject
Public endpoint 기반 연결이 안정적이지 않음
```

---

### 14.3 Cilium RBAC 오류

Cilium 로그:

```text
pods is forbidden:
User "system:serviceaccount:kube-system:cilium" cannot watch resource "pods"

ciliumcidrgroups.cilium.io is forbidden:
User "system:serviceaccount:kube-system:cilium" cannot watch resource "ciliumcidrgroups"
```

또한:

```text
clusterrole.rbac.authorization.k8s.io "cilium" not found
clusterrole.rbac.authorization.k8s.io "system:discovery" not found
clusterrole.rbac.authorization.k8s.io "system:basic-user" not found
clusterrole.rbac.authorization.k8s.io "system:public-info-viewer" not found
```

의미:

```text
Cilium ServiceAccount가 필요한 리소스를 watch할 권한이 없었음
Cilium ClusterRole/ClusterRoleBinding 또는 RBAC 리소스가 비정상일 가능성
```

---

## 15. WireGuard VPN으로 전환한 이유

Public IP 기반 구성에서는 다음 문제가 있었다.

```text
1. Node IP가 OCI private IP로 잡힘
2. 마스터가 워커 private Node IP로 접근 불가
3. 워커가 마스터 internal IP로 접근 불가
4. API Server ↔ kubelet 10250 통신 실패
5. Cilium VXLAN / Service routing 불안정
6. Public endpoint 6443 connection refused 간헐 발생
```

핵심 결론:

```text
Kubernetes에서 중요한 것은 Public IP가 있다는 사실이 아니라,
각 노드의 Kubernetes Node IP가 서로 직접 통신 가능한지 여부다.
```

WireGuard를 사용하면 각 노드에 VPN IP를 부여할 수 있다.

```text
Master wg0 IP: 10.200.0.1
Worker wg0 IP: 10.200.0.2
```

그리고 kubelet Node IP를 WireGuard IP로 지정한다.

```text
worker-us-1 Node IP = 10.200.0.2
```

---

## 16. WireGuard 설치

워커에서 WireGuard 설치:

```bash
sudo apt update
sudo apt install -y wireguard
```

설치 도중 서비스 재시작 선택 화면이 나왔을 때는, Kubernetes 노드에서 불필요한 서비스 재시작을 피하기 위해 `none of the above`를 선택했다.

---

## 17. WireGuard 설정 파일 배치

팀장님에게 받은 worker용 설정 파일:

```text
/home/ubuntu/storage/etc/WireGuard/worker/wg0.conf
```

WireGuard가 실제로 읽는 경로:

```text
/etc/wireguard/wg0.conf
```

복사 명령:

```bash
sudo install -m 600 ~/storage/etc/WireGuard/worker/wg0.conf /etc/wireguard/wg0.conf
```

의미:

```text
worker용 wg0.conf를 /etc/wireguard/wg0.conf로 복사
권한은 600으로 설정
```

권한 확인:

```bash
sudo ls -l /etc/wireguard/wg0.conf
```

정상:

```text
-rw------- 1 root root ... /etc/wireguard/wg0.conf
```

`600` 권한을 주는 이유:

```text
wg0.conf 안에는 PrivateKey가 있으므로 root만 읽고 쓸 수 있게 제한해야 함
```

---

## 18. WireGuard 인터페이스 실행

```bash
sudo systemctl enable --now wg-quick@wg0
```

의미:

```text
enable → 재부팅 후 자동 실행
--now  → 지금 즉시 실행
wg0    → /etc/wireguard/wg0.conf 사용
```

상태 확인:

```bash
sudo systemctl status wg-quick@wg0 --no-pager
sudo wg
ip addr show wg0
```

초기 확인 결과:

```text
wg0 인터페이스 생성됨
worker wg0 IP = 10.200.0.2/24
peer endpoint = 150.230.248.235:51820
```

---

## 19. WireGuard 초기 실패

처음 `sudo wg` 상태:

```text
transfer: 0 B received, 4.62 KiB sent
latest handshake 없음
```

그리고:

```bash
ping -c 3 10.200.0.1
```

결과:

```text
3 packets transmitted, 0 received, 100% packet loss
```

의미:

```text
워커가 마스터로 WireGuard 패킷은 보내고 있음
하지만 마스터로부터 응답을 받지 못함
WireGuard handshake 실패
```

가능성:

```text
마스터 OCI NSG/Security List에서 UDP 51820 미허용
마스터 UFW에서 UDP 51820 미허용
마스터 wg0가 안 올라옴
마스터 peer에 워커 PublicKey 미등록
마스터 peer AllowedIPs에 10.200.0.2/32 없음
키 쌍 불일치
```

---

## 20. WireGuard 정상 연결 확인

이후 마스터 쪽 설정/방화벽/peer 등록이 맞춰진 뒤 `sudo wg` 결과:

```text
interface: wg0
  public key: CwVa688D6oxatWdZoo+N9RzJVWfvUJYtjVi59neV+lE=
  private key: (hidden)
  listening port: 51820

peer: SJ4USqKt/mF709YThCNc0WNOjg3UVIDqms9dZ2PbezE=
  endpoint: 150.230.248.235:51820
  allowed ips: 10.200.0.1/32, 10.0.0.48/32, 10.96.0.0/12, 10.244.0.0/16
  latest handshake: 22 seconds ago
  transfer: 4.29 MiB received, 1.48 MiB sent
  persistent keepalive: every 25 seconds
```

핵심:

```text
latest handshake: 22 seconds ago
transfer: received/sent 둘 다 증가
```

의미:

```text
WireGuard VPN 핸드셰이크 성공
워커 ↔ 마스터 VPN 터널 실제 통신 중
```

---

## 21. WireGuard AllowedIPs 의미

워커의 Peer 설정:

```text
AllowedIPs = 10.200.0.1/32, 10.0.0.48/32, 10.96.0.0/12, 10.244.0.0/16
```

의미:

```text
10.200.0.1/32   → 마스터 WireGuard IP
10.0.0.48/32    → 마스터 내부 IP
10.96.0.0/12    → Kubernetes Service CIDR
10.244.0.0/16   → Kubernetes Pod CIDR
```

즉 이 대역으로 가는 트래픽은 wg0 인터페이스를 통해 WireGuard 터널로 보낸다.

---

## 22. kubelet Node IP 변경

WireGuard 통신이 된 후 kubelet Node IP를 VPN IP로 변경했다.

먼저 백업:

```bash
sudo cp /var/lib/kubelet/kubeadm-flags.env /var/lib/kubelet/kubeadm-flags.env.bak.$(date +%Y%m%d%H%M%S)
```

의미:

```text
기존 kubelet 실행 옵션 파일 백업
문제 발생 시 원복 가능하게 하기 위함
```

수정:

```bash
sudo sed -i 's/--node-ip=[^ "]*//g; s/"$/ --node-ip=10.200.0.2"/' /var/lib/kubelet/kubeadm-flags.env
```

의미:

```text
기존 --node-ip=... 옵션이 있으면 제거
새로 --node-ip=10.200.0.2 추가
```

kubelet 재시작:

```bash
sudo systemctl restart kubelet
```

의미:

```text
kubelet이 worker-us-1의 Kubernetes Node IP를 10.200.0.2로 등록하게 함
```

주의:

```text
이 작업은 WireGuard ping/handshake가 성공한 뒤에만 해야 함
VPN 통신이 안 되는데 node-ip를 VPN IP로 바꾸면 노드가 NotReady가 될 수 있음
```

---

## 23. kubelet 10250 방화벽 허용

마스터 VPN IP에서 워커 kubelet 포트 10250으로 접근하도록 iptables 규칙을 추가했다.

```bash
sudo iptables -C INPUT -s 10.200.0.1/32 -p tcp --dport 10250 -j ACCEPT 2>/dev/null || \
sudo iptables -I INPUT 1 -s 10.200.0.1/32 -p tcp --dport 10250 -j ACCEPT

sudo netfilter-persistent save 2>/dev/null || true
```

의미:

```text
마스터 VPN IP 10.200.0.1에서
워커 kubelet 포트 10250/tcp로 들어오는 요청 허용
```

명령 구조:

```text
iptables -C → 규칙이 이미 있는지 확인
||          → 없으면 다음 명령 실행
iptables -I INPUT 1 → INPUT 체인 맨 위에 허용 규칙 추가
netfilter-persistent save → 가능하면 규칙 저장
```

확인:

```bash
sudo iptables -L INPUT -n --line-numbers | grep 10250
```

UFW를 사용하는 경우에는 UFW에도 추가하는 것이 관리상 좋다.

```bash
sudo ufw allow from 10.200.0.1/32 to any port 10250 proto tcp
```

---

## 24. iptables와 UFW 관계

정리:

```text
UFW = 사람이 쓰기 쉽게 만든 방화벽 관리 도구
iptables = 실제 리눅스 커널 netfilter 규칙을 다루는 도구
```

관계:

```text
ufw 명령
↓
iptables 규칙으로 변환/적용
↓
리눅스 커널 netfilter가 실제 패킷 처리
```

중요한 점:

```text
UFW에서 추가한 규칙은 iptables에 반영됨
iptables에 직접 추가한 규칙은 ufw status에 자동으로 보이지 않을 수 있음
```

따라서 UFW를 active로 사용 중이면 가능한 UFW로도 같이 관리하는 것이 좋다.

---

## 25. VPN 전환 후 컨테이너 상태

VPN 적용 후 워커에서 확인:

```bash
sudo crictl ps
```

결과:

```text
CONTAINER           IMAGE               CREATED             STATE     NAME                 ATTEMPT   POD ID         POD
bf04f22e8a4ef       696d9bd24e518       7 minutes ago       Running   cilium-envoy         0         90c43af342314 cilium-envoy-72m5d
a8f103b2465e1       f2ebd8a25bd8d       8 minutes ago       Running   cilium-agent         0         1b107d41787ef cilium-bqwvk
06a1103976df4       9f93dc0efe80c       8 minutes ago       Running   kube-proxy           0         823d4604e709e kube-proxy-749gz
50d7b8f65ac86       6e6baa0e1348d       8 minutes ago       Running   opentelemetry-host   0         6472d2eca9324 opentelemetry-host-xl4lg
```

의미:

```text
cilium-envoy Running ATTEMPT 0
cilium-agent Running ATTEMPT 0
kube-proxy Running ATTEMPT 0
opentelemetry-host Running ATTEMPT 0
```

`ATTEMPT 0`은 재시작 없이 정상 실행 중이라는 뜻이다.

이전에는 Cilium 관련 컨테이너가 `ATTEMPT 77`, `ATTEMPT 94`처럼 계속 재시작되었으나, VPN 적용 후 정상화되었다.

---

## 26. 최종 상태

WireGuard 확인:

```bash
sudo wg
```

정상 상태:

```text
latest handshake: 22 seconds ago
transfer: 4.29 MiB received, 1.48 MiB sent
```

핵심 컴포넌트:

```text
wg0 인터페이스 up
worker VPN IP = 10.200.0.2
마스터 VPN IP = 10.200.0.1
WireGuard peer handshake 성공
kube-proxy Running
cilium-agent Running
cilium-envoy Running
opentelemetry-host Running
```

현재 상태 요약:

```text
WireGuard VPN 연결 성공
워커 Node IP를 VPN IP로 전환
kube-proxy 정상 Running
Cilium agent 정상 Running
Cilium Envoy 정상 Running
```

---

## 27. 최종 확인해야 할 것

### 워커에서 확인

```bash
sudo wg
ip addr show wg0
curl -k https://10.200.0.1:6443/readyz
sudo systemctl status kubelet --no-pager
sudo crictl ps
```

정상 기대:

```text
latest handshake 있음
received/sent 증가
wg0에 10.200.0.2 존재
readyz = ok
kubelet active(running)
cilium-agent / cilium-envoy / kube-proxy Running
```

---

### 마스터에서 확인

```bash
kubectl get nodes -o wide
kubectl -n kube-system get pods -o wide | grep worker-us-1
kubectl -n kube-system get pods -l k8s-app=cilium -o wide
kubectl -n kube-system exec ds/cilium -- cilium status
```

특히 확인할 것:

```text
worker-us-1 STATUS = Ready
worker-us-1 INTERNAL-IP = 10.200.0.2
Cilium Pod Running / Ready
kube-proxy Running
Cilium status 정상
```

---

## 28. 이번 트러블슈팅에서 배운 핵심

### 핵심 1. join 성공과 네트워크 정상은 다르다

```text
kubeadm join 성공
= kubelet이 API Server에 붙어 노드 등록 성공

하지만
= kube-proxy, Cilium, API Server ↔ kubelet, Pod 네트워크가 모두 정상이라는 뜻은 아님
```

---

### 핵심 2. Kubernetes Node IP가 중요하다

Public IP가 있어도 Kubernetes가 Node IP를 private IP로 잡으면 문제가 생긴다.

```text
worker Node IP = 10.0.0.10
master가 10.0.0.10으로 접근 불가
↓
logs / exec / kubelet 10250 / Cilium VXLAN 문제 발생
```

---

### 핵심 3. kube-proxy는 Service NAT 규칙을 만든다

```text
10.96.0.1 = kubernetes.default.svc = API Server Service IP
```

kube-proxy가 정상이어야 다음이 가능하다.

```text
10.96.0.1:443
↓
iptables NAT
↓
실제 API Server
```

---

### 핵심 4. Cilium은 kube-proxy 문제의 영향을 받을 수 있다

Cilium이 API Server에 접근할 때 `10.96.0.1:443`를 사용하면, kube-proxy가 해당 Service NAT 규칙을 만들어야 한다.

```text
kube-proxy 실패
↓
10.96.0.1 NAT 없음
↓
Cilium API 접근 실패
```

---

### 핵심 5. WireGuard는 Node IP 문제를 해결한다

WireGuard로 노드마다 VPN IP를 만들고, kubelet Node IP를 VPN IP로 지정하면 노드 간 통신이 안정화된다.

```text
master      = 10.200.0.1
worker-us-1 = 10.200.0.2
```

이후 Kubernetes는 이 VPN IP를 기준으로 노드 간 통신할 수 있다.

---

## 29. 최종 결론

Public IP 기반으로도 `kubeadm join` 자체는 가능했지만, Kubernetes 운영에 필요한 노드 간 통신은 불안정했다.

발생한 문제:

```text
마스터 내부 IP 10.0.0.48 접근 실패
kube-proxy ConfigMap 내부 IP 문제
Cilium API 접근 실패
10.96.0.1 NAT 규칙 미생성
마스터 → 워커 kubelet 10250 접근 실패
kubelet lease/status connection refused
Cilium RBAC / xDS socket 관련 오류
```

WireGuard 적용 후:

```text
wg0 handshake 성공
10.200.0.2 VPN IP 생성
kubelet node-ip를 10.200.0.2로 변경
kube-proxy Running
cilium-agent Running
cilium-envoy Running
opentelemetry-host Running
```

따라서 최종적으로는 다음 구조가 안정적인 방향이다.

```text
Kubernetes Node IP = WireGuard VPN IP
Master = 10.200.0.1
Worker = 10.200.0.2
```

이 구조에서는 다음 통신이 안정적으로 가능해진다.

```text
worker → master API Server
master → worker kubelet 10250
node ↔ node Cilium VXLAN 8472
Pod-to-Pod 통신
Service routing
CoreDNS
kubectl logs / exec / probe
```
