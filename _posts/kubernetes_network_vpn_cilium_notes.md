# Kubernetes 워커 노드 네트워크/VPN/Cilium 개념 정리

작성 기준: 한국 OCI Master(Control Plane) + 미국 Worker Node 구성 문서

---

## 0. 전체 목표

현재 목표 구성은 다음과 같다.

```text
한국 OCI 인스턴스
- Kubernetes Master / Control Plane
- Public IP: 150.230.248.235
- Internal IP: 10.0.0.48
- API endpoint: k8s-api.monithub.org:6443

미국 서버
- Kubernetes Worker Node
- Public IP: 129.159.177.124
```

최종 목표는 미국 서버를 Kubernetes Worker Node로 붙여서, Kubernetes 클러스터에서 Monithub 관련 Pod를 실행할 수 있게 하는 것이다.

---

## 1. Kubernetes에서 Master와 Worker 역할

### Master / Control Plane

Master는 Kubernetes 클러스터의 관리자 역할을 한다.

주요 역할:

```text
클러스터 상태 관리
Pod 스케줄링
Worker Node 관리
Kubernetes API 제공
클러스터 설정 저장
```

Master 안에는 다음과 같은 핵심 컴포넌트가 있다.

```text
kube-apiserver
etcd
kube-controller-manager
kube-scheduler
```

---

### Worker Node

Worker Node는 실제 애플리케이션 Pod가 실행되는 서버다.

주요 역할:

```text
Pod 실행
컨테이너 실행
Pod 상태 보고
네트워크 통신 처리
```

Worker Node 안에는 다음과 같은 구성요소가 있다.

```text
kubelet
containerd
CNI plugin, 예: Cilium
```

---

## 2. kubeadm join은 무엇인가?

워커 서버를 Kubernetes 클러스터에 등록하는 작업이다.

예시:

```bash
sudo kubeadm join k8s-api.monithub.org:6443   --token <token>   --discovery-token-ca-cert-hash sha256:<hash>
```

이 명령을 실행하면 워커 노드가 마스터 API 서버에 접속해서 클러스터에 가입한다.

흐름:

```text
Worker Node
↓
k8s-api.monithub.org:6443
↓
Kubernetes API Server
↓
Node 등록
↓
kubelet 설정 생성
```

---

## 3. `k8s-api.monithub.org:6443`의 의미

### `k8s-api.monithub.org`

Kubernetes API Server에 접근하기 위한 도메인이다.

### `6443`

Kubernetes API Server가 사용하는 기본 HTTPS 포트다.

즉 아래 주소는 Kubernetes API Server를 의미한다.

```text
https://k8s-api.monithub.org:6443
```

---

## 4. `curl -k https://k8s-api.monithub.org:6443/version`이 하는 일

### 명령어

```bash
curl -k https://k8s-api.monithub.org:6443/version
```

### 의미

워커 서버에서 마스터 Kubernetes API Server에 접근 가능한지 확인한다.

정상 응답 예시:

```json
{
  "major": "1",
  "minor": "29",
  "gitVersion": "v1.29.15"
}
```

### `-k` 옵션 의미

`-k`는 HTTPS 인증서 검증을 무시하라는 뜻이다.

정식 의미:

```text
-k = insecure
```

Kubernetes API Server는 자체 서명 인증서나 내부 인증서를 사용할 수 있다.  
이 경우 일반 curl은 인증서를 신뢰하지 못해서 실패할 수 있다.

그래서 네트워크 연결 확인 목적일 때는 `-k`를 붙인다.

---

## 5. 6443 연결이 성공하면 무엇이 확인되는가?

워커 서버에서 아래 명령이 성공하면:

```bash
curl -k https://k8s-api.monithub.org:6443/version
```

다음이 확인된다.

```text
워커 → k8s-api.monithub.org DNS 조회 가능
워커 → 마스터 Public IP 접근 가능
워커 → 마스터 TCP 6443 포트 접근 가능
마스터 API Server가 응답 중
마스터 쪽 OCI Security List / NSG / OS 방화벽에서 6443 허용됨
```

하지만 이것만으로 Kubernetes 전체 네트워크가 정상이라는 뜻은 아니다.

6443은 join과 API 통신용이다.  
조인 이후에는 노드 간 통신, Pod 간 통신, Cilium VXLAN 통신도 필요하다.

---

## 6. 왜 6443만 열고 나머지 control-plane 포트는 열지 않는가?

문서에서 다음 포트는 외부에 열지 말라고 되어 있다.

```text
etcd: 2379-2380
controller-manager: 10257
scheduler: 10259
```

이유는 이 포트들이 외부 접근용이 아니라 control-plane 내부 관리용이기 때문이다.

---

## 7. etcd 2379-2380을 외부에 열면 안 되는 이유

`etcd`는 Kubernetes 클러스터의 상태 저장 DB다.

저장되는 정보:

```text
Node 정보
Pod 정보
Service 정보
ConfigMap
Secret
클러스터 전체 상태
```

즉 etcd는 Kubernetes의 핵심 데이터베이스다.

포트 의미:

```text
2379 = etcd client 통신
2380 = etcd peer 통신
```

외부에 열면 위험한 이유:

```text
etcd 노출
↓
클러스터 상태 정보 유출
↓
Secret 유출 가능
↓
클러스터 전체 장악 가능
```

따라서 etcd는 외부에 열면 안 된다.

---

## 8. controller-manager 10257을 외부에 열면 안 되는 이유

`kube-controller-manager`는 Kubernetes 클러스터 상태를 계속 원하는 상태로 맞추는 컴포넌트다.

예:

```text
Deployment replicas=3인데 Pod가 2개뿐임
↓
Pod 하나 더 생성
```

```text
Node가 죽음
↓
Pod를 다른 노드로 재배치
```

이 컴포넌트는 control-plane 내부에서 API Server와 통신하면 된다.  
외부 워커나 사용자가 직접 접근할 필요가 없다.

---

## 9. scheduler 10259를 외부에 열면 안 되는 이유

`kube-scheduler`는 새 Pod를 어느 노드에 띄울지 결정한다.

예:

```text
새 Pod 생성 요청
↓
scheduler가 적절한 Worker Node 선택
↓
Pod 배치
```

scheduler도 외부에서 직접 접근할 필요가 없다.  
API Server를 통해 간접적으로 동작한다.

---

## 10. 왜 Kubernetes 외부 접근은 API Server 6443 중심인가?

Kubernetes는 외부 클라이언트와 노드가 대부분 API Server를 통해 통신하는 구조다.

```text
kubectl
OpenLens
kubeadm join
worker kubelet
CI/CD
↓
Kubernetes API Server 6443
↓
control-plane 내부 컴포넌트
```

따라서 외부에 공개해야 하는 대표 포트는 API Server의 6443이다.

비유:

```text
6443 = 회사 정문 / 안내데스크
2379-2380 = 금고
10257 = 운영팀 내부 시스템
10259 = 배치 담당 내부 시스템
```

외부 사용자는 정문으로만 들어오면 된다.  
금고나 내부 시스템 문을 밖에 열면 보안 사고가 난다.

---

## 11. Worker에서 추가로 필요한 포트

문서에서는 다음 포트들도 필요하다고 되어 있다.

```text
TCP 10250
UDP 8472
```

---

## 12. TCP 10250은 무엇인가?

`10250`은 kubelet API 포트다.

kubelet은 워커 노드에서 Pod를 관리하는 에이전트다.

Master는 kubelet과 통신하면서 다음 작업을 할 수 있다.

```text
Pod 상태 확인
로그 조회
exec 요청
노드 상태 확인
컨테이너 상태 확인
```

따라서 마스터와 워커 간에 TCP 10250 통신이 필요하다.

---

## 13. UDP 8472는 무엇인가?

`8472/UDP`는 Cilium VXLAN 터널 통신에 사용된다.

Cilium이 VXLAN overlay 모드로 동작할 때, 노드 간 Pod 트래픽을 UDP 8472로 캡슐화해서 보낸다.

즉:

```text
Pod A 패킷
↓
VXLAN으로 감쌈
↓
UDP 8472로 상대 노드에 전달
↓
상대 노드에서 VXLAN 해제
↓
Pod B로 전달
```

---

## 14. CNI란 무엇인가?

CNI는 Container Network Interface의 약자다.

Kubernetes에서 Pod 네트워크를 구성하는 플러그인 표준이다.

Kubernetes 자체는 Pod 네트워크를 직접 구현하지 않는다.  
CNI 플러그인이 Pod IP 할당, 라우팅, 네트워크 정책 등을 담당한다.

대표 CNI:

```text
Cilium
Calico
Flannel
Weave
```

이번 문서에서는 CNI로 Cilium을 사용한다.

---

## 15. Cilium이란 무엇인가?

Cilium은 Kubernetes용 CNI 플러그인이다.

주요 역할:

```text
Pod 네트워크 구성
Pod-to-Pod 통신 처리
Service routing
NetworkPolicy 처리
eBPF 기반 네트워크 처리
VXLAN/Geneve 같은 overlay 지원
```

이번 문서에서는 Cilium을 VXLAN tunnel 모드로 사용한다.

---

## 16. VXLAN이란 무엇인가?

VXLAN은 Virtual Extensible LAN의 약자다.

간단히 말하면:

```text
서로 다른 서버에 있는 Pod들이 같은 네트워크에 있는 것처럼 통신하게 해주는 overlay 기술
```

VXLAN은 개념적으로 L2, 즉 데이터링크 계층 네트워크를 가상화한다.

하지만 실제 전송은 UDP를 사용한다.

정리:

```text
VXLAN = 가상 Layer 2 overlay
UDP = 실제 전송 수단, Layer 4
```

---

## 17. OSI 7계층에서 VXLAN과 UDP 위치

OSI 7계층:

```text
7 응용 계층
6 표현 계층
5 세션 계층
4 전송 계층       → TCP / UDP
3 네트워크 계층   → IP
2 데이터링크 계층 → Ethernet / MAC
1 물리 계층
```

VXLAN은 L2 네트워크를 가상화하는 기술이지만, 실제 패킷은 UDP 위에 실려 간다.

패킷 구조:

```text
Outer Ethernet
Outer IP
UDP 8472
VXLAN Header
Inner Ethernet
Inner IP
TCP/UDP
Payload
```

즉:

```text
VXLAN = L2 overlay 개념
UDP 8472 = VXLAN 패킷을 실제로 운반하는 L4 통신
```

---

## 18. 왜 Pod 패킷을 VXLAN으로 감싸는가?

Kubernetes Pod IP는 일반 인터넷이나 외부 네트워크가 모르는 내부 주소다.

예:

```text
한국 노드의 Pod A = 10.244.1.5
미국 노드의 Pod B = 10.244.2.8
```

Pod A가 Pod B로 통신하려고 하면 원래 패킷은 다음과 같다.

```text
출발지: 10.244.1.5
목적지: 10.244.2.8
```

하지만 외부 네트워크나 일반 라우터는 `10.244.2.8`이 어디 있는지 모른다.

그래서 VXLAN이 이 Pod 패킷을 노드 IP 간 통신 패킷 안에 감싼다.

```text
겉 패킷:
출발지 = 한국 노드 IP
목적지 = 미국 노드 IP
UDP 8472

안쪽 패킷:
출발지 = Pod A IP
목적지 = Pod B IP
```

외부 네트워크 입장에서는 그냥:

```text
한국 노드 → 미국 노드 UDP 패킷
```

으로 보인다.

미국 노드에 도착하면 Cilium이 안쪽 Pod 패킷을 꺼내서 Pod B에게 전달한다.

---

## 19. VXLAN 비유

```text
Pod 패킷 = 편지
VXLAN = 택배 상자
Node IP = 물류센터 주소
Pod IP = 건물 안의 방 번호
```

인터넷은 Pod IP라는 방 번호를 모른다.  
그래서 먼저 Node IP라는 물류센터 주소로 보낸다.  
도착한 노드가 안쪽 Pod IP를 보고 실제 Pod로 전달한다.

---

## 20. VPN과 VXLAN은 같은 것인가?

아니다. 둘은 다른 개념이다.

### VPN

VPN은 서버와 서버 사이에 사설 네트워크를 만드는 기술이다.

```text
한국 Master ← VPN → 미국 Worker
```

예:

```text
Master VPN IP = 10.100.0.1
Worker VPN IP = 10.100.0.2
```

VPN의 목적:

```text
노드끼리 서로 도달 가능한 네트워크를 만든다
```

---

### VXLAN

VXLAN은 Kubernetes Pod 패킷을 노드 간 패킷 안에 감싸서 보내는 overlay 기술이다.

VXLAN의 목적:

```text
Pod끼리 같은 Kubernetes 내부 네트워크에 있는 것처럼 통신하게 한다
```

---

## 21. VPN과 VXLAN의 관계

둘의 관계는 다음과 같다.

```text
VPN = 노드끼리 서로 갈 수 있게 해주는 길
VXLAN = 그 길 위에 Pod 패킷을 포장해서 보내는 방식
```

흐름:

```text
Pod A
↓
Cilium이 VXLAN으로 감쌈
↓
VPN 네트워크를 통해 상대 노드로 이동
↓
상대 노드에서 VXLAN 해제
↓
Pod B
```

즉 VPN은 Node-to-Node 통신 기반이고, VXLAN은 Pod-to-Pod 통신을 위한 캡슐화 방식이다.

---

## 22. 왜 이번 구성에서 VPN/Peering이 문제가 되는가?

문서에서 가장 중요한 문제는 이 부분이다.

```text
마스터 Kubernetes INTERNAL-IP = 10.0.0.48
```

`10.0.0.48`은 보통 OCI 내부 사설 IP다.

한국 OCI 내부에서는 접근 가능하지만, 미국 워커 서버가 일반 인터넷으로는 이 IP에 접근할 수 없다.

문제:

```text
미국 Worker → 10.0.0.48
```

이 경로가 없으면 노드 간 통신이 깨질 수 있다.

---

## 23. kubeadm join은 성공해도 Pod 통신이 실패할 수 있는 이유

`kubeadm join`은 다음 주소로 API Server에 접근한다.

```text
k8s-api.monithub.org:6443
```

이건 Public DNS/Public IP 기반으로 가능할 수 있다.

그래서 join 자체는 성공할 수 있다.

하지만 조인 이후 Cilium/VXLAN/Pod 통신은 Kubernetes Node IP를 기준으로 동작한다.

예:

```text
Master Node IP = 10.0.0.48
Worker Node IP = 어떤 IP
```

미국 워커가 `10.0.0.48`에 접근할 수 없다면:

```text
조인 성공
↓
Node 간 VXLAN 통신 실패
↓
Pod-to-Pod 통신 실패
↓
CoreDNS 불안정
↓
Service routing 실패
```

이런 문제가 생길 수 있다.

---

## 24. Kubernetes Node IP가 중요한 이유

Kubernetes에서 각 노드는 Node IP를 가진다.

확인 명령:

```bash
kubectl get nodes -o wide
```

출력 예시:

```text
NAME          STATUS   ROLES           INTERNAL-IP
master-kr-1   Ready    control-plane   10.0.0.48
worker-us-1   Ready    <none>          10.x.x.x
```

CNI, kubelet, Pod 네트워크는 이 Node IP를 기준으로 통신한다.

중요한 조건:

```text
각 노드의 Kubernetes Node IP는 서로 직접 통신 가능해야 한다.
```

직접 통신 가능한 IP가 아니면 Kubernetes 네트워크가 깨질 수 있다.

---

## 25. OCI Public IP와 NAT 문제

문서에 다음 내용이 있다.

```text
OCI Public IP는 보통 호스트 인터페이스에 직접 붙은 IP가 아니라 NAT 형태라,
kubelet --node-ip=<public-ip>가 거부될 수 있다.
```

의미:

OCI 인스턴스에서 `ip addr`로 확인하면 보통 Public IP가 서버 네트워크 인터페이스에 직접 붙어 있지 않고, 내부 private IP만 보이는 경우가 많다.

예:

```text
서버 인터페이스 실제 IP = 10.0.0.48
외부 Public IP = 150.230.248.235
```

Public IP는 OCI NAT 구조를 통해 외부에서 연결되는 주소일 뿐, OS 내부 네트워크 인터페이스에는 존재하지 않을 수 있다.

그래서 kubelet에 다음처럼 설정하면:

```text
--node-ip=150.230.248.235
```

kubelet이 다음처럼 판단할 수 있다.

```text
이 IP는 내 인터페이스에 없는 IP인데?
```

그 결과 node-ip 설정이 거부되거나 네트워크가 꼬일 수 있다.

---

## 26. 그래서 필요한 해결책

문서에서 제시한 해결책:

```text
WireGuard
Tailscale
일반 VPN
OCI Remote Peering
```

목표는 모두 같다.

```text
마스터와 워커가 서로 직접 통신 가능한 Node IP를 갖게 만드는 것
```

즉, Kubernetes Node IP를 서로 라우팅 가능한 주소로 잡는 것이 핵심이다.

---

## 27. 해결책 1: OCI Remote VCN Peering

### 개념

OCI Remote VCN Peering은 서로 다른 리전의 OCI VCN을 연결해서, private IP끼리 통신할 수 있게 하는 방식이다.

예:

```text
한국 OCI VCN
Master: 10.0.0.48
        │
      Remote VCN Peering / DRG
        │
미국 OCI VCN
Worker: 10.x.x.x
```

목표:

```text
한국 Master private IP ↔ 미국 Worker private IP 통신 가능
```

### 장점

```text
OCI 네이티브 방식
Public Internet을 직접 타지 않음
private IP 기반 통신 가능
운영/보안/성능 면에서 정석적
```

### 단점

```text
양쪽 VCN/DRG/Route Table/Security List 설정 필요
OCI 네트워크 권한 필요
팀장님 쪽 마스터 VCN 설정도 필요
혼자서 완료하기 어려울 수 있음
```

---

## 28. Remote Peering은 내 워커만 설정하면 되는가?

아니다.

Remote VCN Peering은 양쪽 네트워크 설정이 필요하다.

필요한 것:

```text
한국 VCN 쪽
- DRG 연결
- Remote Peering Connection
- Route Table 설정
- Security List / NSG 허용

미국 VCN 쪽
- DRG 연결
- Remote Peering Connection
- Route Table 설정
- Security List / NSG 허용
```

즉 팀장님이 관리하는 마스터 쪽 VCN 설정도 필요하다.

---

## 29. 해결책 2: WireGuard

### 개념

WireGuard는 서버 간 VPN 터널을 직접 만드는 소프트웨어다.

예:

```text
Master wg0 IP = 10.100.0.1
Worker wg0 IP = 10.100.0.2
```

이렇게 하면 두 서버가 VPN IP로 서로 통신할 수 있다.

### 장점

```text
빠름
가벼움
클라우드 종류와 무관
직접 제어 가능
Kubernetes 노드 간 VPN 구성에 자주 사용
```

### 단점

```text
Master와 Worker 양쪽에 설치/설정 필요
키 관리 필요
방화벽 포트 허용 필요
운영자가 직접 관리해야 함
```

### Kubernetes와 연결

WireGuard를 쓰면 Kubernetes Node IP를 WireGuard IP로 잡는 방식이 가능하다.

예:

```text
Master Node IP = 10.100.0.1
Worker Node IP = 10.100.0.2
```

이렇게 하면 Cilium VXLAN도 해당 VPN IP를 통해 통신할 수 있다.

---

## 30. 해결책 3: Tailscale

### 개념

Tailscale은 WireGuard 기반의 mesh VPN 서비스다.

직접 WireGuard를 설정하는 것보다 훨씬 쉽게 서버 간 VPN을 구성할 수 있다.

### 장점

```text
설치가 쉬움
NAT 환경에 강함
관리 UI가 있음
빠르게 테스트하기 좋음
```

### 단점

```text
외부 SaaS 의존성
팀/회사 계정 관리 필요
장기 운영 정책 고려 필요
```

### 필요한 작업

Tailscale도 양쪽 서버에 설치해야 한다.

```text
Master에 Tailscale 설치/login
Worker에 Tailscale 설치/login
같은 tailnet에 등록
```

따라서 이것도 팀장님 쪽 마스터 서버 협조가 필요하다.

---

## 31. 해결책 4: 일반 VPN

OpenVPN 같은 일반 VPN도 사용할 수 있다.

목표는 WireGuard/Tailscale과 같다.

```text
Master와 Worker 사이에 서로 통신 가능한 사설 네트워크 생성
```

다만 Kubernetes 노드 간 VPN 용도로는 WireGuard가 더 가볍고 많이 쓰이는 편이다.

---

## 32. 어떤 것을 쓰는 게 좋은가?

### 둘 다 OCI 인스턴스이고 VCN 권한이 있다면

```text
1순위: OCI Remote VCN Peering / DRG
```

이유:

```text
OCI 네이티브 방식
private IP 통신 가능
운영/보안 면에서 정석
```

### OCI 네트워크 권한이 부족하거나 빨리 테스트해야 한다면

```text
2순위: WireGuard
```

이유:

```text
클라우드 네트워크 설정을 크게 건드리지 않고 서버 간 VPN 가능
성능 좋음
구성 자유도 높음
```

### 가장 쉽게 테스트하고 싶다면

```text
3순위: Tailscale
```

이유:

```text
설치 쉬움
NAT 환경에서도 잘 동작
```

단, 회사 인프라에서는 외부 SaaS 의존성을 고려해야 한다.

---

## 33. 네가 혼자 할 수 있는 작업과 협의가 필요한 작업

### 혼자 할 수 있는 작업

워커 노드 내부 준비:

```text
hostname 설정
swap off
커널 모듈 설정
sysctl 설정
containerd 설치/설정
kubeadm/kubelet/kubectl 설치
마스터 API 6443 연결 테스트
```

### 팀장님 협의가 필요한 작업

노드 간 네트워크 방식 결정:

```text
OCI Remote VCN Peering
WireGuard
Tailscale
VPN
Node IP 설계
마스터 쪽 방화벽/NSG/Security List
마스터 kubelet node-ip 설정
Cilium 설정
```

---

## 34. 왜 kubeadm join을 아직 보류하는가?

join 명령은 실행 가능할 수도 있다.

하지만 네트워크 방식이 확정되지 않은 상태에서 join하면 다음 문제가 생길 수 있다.

```text
Node는 등록됐지만 Ready가 안 됨
Cilium Pod가 Running이 안 됨
CoreDNS가 계속 Pending/CrashLoop
Service 통신 실패
Pod-to-Pod 통신 실패
```

따라서 다음이 확정된 후 join하는 것이 안전하다.

```text
Master Node IP와 Worker Node IP가 서로 통신 가능한가?
TCP 10250이 양방향 또는 필요한 방향으로 열려 있는가?
UDP 8472가 노드 간 열려 있는가?
Cilium VXLAN이 어떤 Node IP를 사용할 것인가?
VPN/Peering 방식은 무엇인가?
```

---

## 35. OpenLens란 무엇인가?

OpenLens는 Kubernetes 클러스터를 GUI로 관리하고 확인할 수 있는 도구다.

볼 수 있는 것:

```text
Nodes
Pods
Deployments
Services
ConfigMaps
Secrets
Logs
Events
```

kubectl 명령어를 계속 치지 않아도 클러스터 상태를 시각적으로 확인할 수 있다.

---

## 36. kubeconfig란 무엇인가?

kubeconfig는 kubectl이나 OpenLens가 Kubernetes 클러스터에 접속할 때 사용하는 설정 파일이다.

포함 정보:

```text
Kubernetes API Server 주소
클러스터 인증서 정보
사용자 인증 정보
context 정보
```

예:

```yaml
clusters:
- cluster:
    server: https://k8s-api.monithub.org:6443
```

---

## 37. admin.conf가 민감한 이유

문서에서는 마스터의 `/etc/kubernetes/admin.conf`를 OpenLens용으로 복사한다고 되어 있다.

```bash
sudo cp -f /etc/kubernetes/admin.conf /home/ubuntu/kubeconfig-openlens.yaml
```

이 파일은 보통 cluster-admin 권한을 가진다.

즉 이 파일을 가진 사람은 클러스터에서 거의 모든 작업을 할 수 있다.

위험:

```text
Pod 삭제
Secret 조회
Deployment 변경
Node 조작
클러스터 전체 장악
```

그래서 GitHub, Notion, 메신저, 공개 서버 등에 올리면 안 된다.

---

## 38. kubeconfig에서 server 주소를 바꾸는 이유

마스터 안의 admin.conf는 보통 내부 IP를 바라볼 수 있다.

예:

```yaml
server: https://10.0.0.48:6443
```

하지만 OpenLens는 로컬 PC에서 접속한다.  
로컬 PC는 `10.0.0.48`에 접근하지 못할 수 있다.

그래서 외부에서 접근 가능한 Public DNS로 바꾼다.

```yaml
server: https://k8s-api.monithub.org:6443
```

문서의 명령:

```bash
sed -i 's#server: https://10.0.0.48:6443#server: https://k8s-api.monithub.org:6443#' /home/ubuntu/kubeconfig-openlens.yaml
```

---

## 39. Pod-to-Pod 통신 테스트가 필요한 이유

조인 후 `kubectl get nodes`에서 Ready가 떠도 Pod 네트워크가 완전히 정상이라고 단정할 수 없다.

그래서 테스트 Pod를 띄우고 Service를 통해 통신을 확인한다.

예:

```bash
kubectl create deployment nginx-test --image=nginx:1.27
kubectl expose deployment nginx-test --port=80 --target-port=80
kubectl run curl-test --image=curlimages/curl:8.11.1 --restart=Never -- sleep 300
kubectl exec curl-test -- curl -sS nginx-test.default.svc.cluster.local
```

이 테스트가 성공하면 다음이 확인된다.

```text
Pod 생성 가능
Service 생성 가능
CoreDNS 동작
Pod → Service DNS 해석 가능
Pod-to-Pod/Service 통신 가능
CNI 네트워크 정상
```

---

## 40. CoreDNS가 중요한 이유

CoreDNS는 Kubernetes 내부 DNS다.

예를 들어 Service 이름으로 통신할 수 있게 해준다.

```text
nginx-test.default.svc.cluster.local
```

이 이름을 실제 Service IP로 해석해준다.

CoreDNS가 깨지면 다음 문제가 생긴다.

```text
Service 이름으로 통신 불가
Pod 간 서비스 디스커버리 실패
애플리케이션 내부 통신 실패
```

CoreDNS 문제는 CNI, Pod 네트워크, Node 간 통신 문제와 연결되는 경우가 많다.

---

## 41. Service routing이란 무엇인가?

Kubernetes Service는 여러 Pod 앞에 붙는 가상 네트워크 엔드포인트다.

예:

```text
Service: nginx-test
↓
Pod A
Pod B
Pod C
```

Pod가 직접 Pod IP를 몰라도 Service 이름으로 접근할 수 있다.

```text
curl nginx-test.default.svc.cluster.local
```

Service routing이 정상이어야 트래픽이 실제 Pod로 전달된다.

CNI나 kube-proxy/eBPF 라우팅 문제가 있으면 Service 통신이 깨질 수 있다.

---

## 42. 왜 control-plane에는 일반 Pod가 안 뜰 수 있는가?

문서에 다음 내용이 있다.

```text
control-plane에는 taint가 있으므로 일반 Pod는 워커에 뜨는 것이 정상이다.
```

Kubernetes는 기본적으로 control-plane 노드에 일반 애플리케이션 Pod가 배치되지 않도록 taint를 설정하는 경우가 많다.

목적:

```text
마스터 노드는 클러스터 관리에 집중
일반 애플리케이션은 Worker Node에서 실행
```

따라서 테스트 Pod가 워커에 뜨는 것이 정상이다.

---

## 43. taint와 toleration 개념

### taint

노드에 붙이는 제한 조건이다.

예:

```text
이 노드에는 일반 Pod를 올리지 마라
```

### toleration

Pod가 특정 taint를 견딜 수 있게 하는 설정이다.

예:

```text
나는 control-plane taint를 허용하니 이 노드에 올라가도 된다
```

일반적으로 control-plane에는 taint가 있고, 일반 앱 Pod는 worker node에 배치된다.

---

## 44. Docker Registry와 Kubernetes의 관계

현재 Docker Registry는 Kubernetes 밖에서 Docker 컨테이너로 실행 중일 수 있다.

이것도 괜찮다.

Kubernetes는 외부 registry에서 이미지를 pull하면 된다.

흐름:

```text
docker build
↓
docker push registry.monithub.org/monithub:develop
↓
Kubernetes Deployment
↓
image: registry.monithub.org/monithub:develop
↓
Worker Node가 image pull
↓
Pod 실행
```

즉 registry가 반드시 Kubernetes 내부 Pod로 떠 있어야 하는 것은 아니다.

초기에는 registry를 Kubernetes 밖에 두는 것이 더 단순하고 안정적이다.

---

## 45. Kubernetes에서 private registry를 쓰려면 필요한 것

Private registry는 인증이 필요하다.

Kubernetes에서는 registry 로그인 정보를 `imagePullSecret`으로 저장한다.

예:

```bash
kubectl create secret docker-registry registry-secret   --docker-server=registry.monithub.org   --docker-username=<username>   --docker-password='<password>'   --docker-email='<email>'
```

Deployment에는 다음처럼 연결한다.

```yaml
imagePullSecrets:
  - name: registry-secret
containers:
  - name: monithub
    image: registry.monithub.org/monithub:develop
```

---

## 46. Registry를 Kubernetes 안으로 옮길 수도 있는가?

가능하다.

구조:

```text
Kubernetes
├── registry Pod
├── registry Service
├── registry PVC
└── Ingress registry.monithub.org
```

하지만 초기에는 권장하지 않을 수 있다.

이유:

```text
registry는 이미지 저장소라 데이터 보존이 중요함
PVC/PV 설정 필요
Ingress/TLS/auth 설정 필요
클러스터가 죽으면 registry 접근도 영향받을 수 있음
```

따라서 초기에는:

```text
Registry = Kubernetes 외부 Docker 컨테이너
Monithub App = Kubernetes Pod로 마이그레이션
```

구성이 단순하다.

---

## 47. 서브도메인 방식과 path 방식

서비스를 외부에 노출하는 방식은 크게 두 가지가 있다.

### Host 기반, 서브도메인 방식

```text
registry.monithub.org  → Docker Registry
api.monithub.org       → API Server
grafana.monithub.org   → Grafana
```

### Path 기반, context 방식

```text
monithub.org/registry  → Docker Registry
monithub.org/api       → API Server
monithub.org/grafana   → Grafana
```

Kubernetes Ingress에서는 둘 다 가능하다.

---

## 48. Docker Registry는 왜 서브도메인 방식이 더 나은가?

Docker Registry API는 기본적으로 `/v2/` 경로를 사용한다.

Docker client가 registry와 통신할 때:

```text
https://registry.monithub.org/v2/
```

이런 형태를 기대한다.

따라서 다음 방식이 자연스럽다.

```text
registry.monithub.org
```

반면 아래처럼 path prefix를 쓰면:

```text
monithub.org/registry
```

Docker client의 `/v2/` 요청과 경로가 꼬일 수 있어서 rewrite 설정이 필요할 수 있다.

그래서 Docker Registry는 보통 host 기반, 즉 서브도메인 방식을 추천한다.

---

## 49. 전체 네트워크 흐름 요약

최종적으로 Kubernetes에서 Monithub Pod가 실행되는 흐름은 다음과 같다.

```text
CI/CD 또는 수동 docker build
↓
docker push registry.monithub.org/monithub:develop
↓
Kubernetes Deployment 생성/수정
↓
Worker Node가 registry에서 image pull
↓
containerd가 컨테이너 실행
↓
Pod 실행
↓
Cilium이 Pod 네트워크 처리
↓
Service/CoreDNS를 통해 내부 통신
```

마스터/워커 네트워크는 다음이 필요하다.

```text
Worker → Master TCP 6443
Master ↔ Worker TCP 10250
Master ↔ Worker UDP 8472
Node IP 간 직접 통신 가능
```

---

## 50. 가장 중요한 결론

이 문서의 핵심은 다음이다.

```text
kubeadm join은 API Server 6443만 열려 있어도 성공할 수 있다.
하지만 Kubernetes가 정상 동작하려면 Node IP 간 통신이 가능해야 한다.
Cilium VXLAN은 노드 간 UDP 8472 통신이 필요하다.
마스터의 INTERNAL-IP 10.0.0.48을 워커가 접근할 수 없다면 Pod 네트워크가 깨질 수 있다.
그래서 VPN, WireGuard, Tailscale, OCI Remote Peering 같은 노드 간 사설 통신망이 필요할 수 있다.
```

---

## 51. 팀장님과 확인해야 할 질문

```text
1. 노드 간 네트워크는 OCI Remote VCN Peering으로 구성할 예정인가?
2. 아니면 WireGuard/Tailscale로 VPN IP를 만들어 사용할 예정인가?
3. Kubernetes Node IP는 어떤 IP로 잡을 것인가?
4. Master와 Worker 간 TCP 10250, UDP 8472는 어느 방향으로 열 것인가?
5. Cilium VXLAN tunnel은 어떤 Node IP를 기준으로 통신하게 할 것인가?
6. kubeadm join은 네트워크 방식 확정 후 진행하면 되는가?
```

---

## 52. 면접/포트폴리오에서 설명할 수 있는 문장

이 작업은 단순히 Kubernetes 명령어를 실행한 것이 아니라, 멀티 리전 환경에서 Kubernetes 노드 간 네트워크를 설계하는 작업이다.

설명 예시:

```text
한국 OCI에 Kubernetes control-plane을 두고 미국 서버를 worker node로 조인하는 구성을 준비했습니다.
이 과정에서 kubeadm join은 Public API endpoint로 가능하지만, Cilium VXLAN 기반 Pod-to-Pod 통신은 Kubernetes Node IP 간 직접 통신이 필요하다는 점을 확인했습니다.
OCI private IP가 리전 간 직접 라우팅되지 않기 때문에 Remote VCN Peering 또는 WireGuard/Tailscale 같은 VPN 구성이 필요하다고 판단했습니다.
```

---

## 53. 핵심 키워드

```text
Kubernetes
Control Plane
Worker Node
kubeadm join
kubelet
containerd
CNI
Cilium
VXLAN
UDP 8472
TCP 6443
TCP 10250
Node IP
Internal IP
Public IP
NAT
VPN
WireGuard
Tailscale
OCI Remote VCN Peering
DRG
Security List
NSG
CoreDNS
Service Routing
OpenLens
kubeconfig
imagePullSecret
Private Docker Registry
```
