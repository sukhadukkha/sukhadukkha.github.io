# Kubernetes Worker Join 이후 kube-proxy / Cilium 트러블슈팅 정리

작성 기준: `worker-us-1` 워커 노드 조인 이후 발생한 kube-proxy / Cilium API Server 접근 실패 문제

---

## 0. 상황 요약

워커 노드 `worker-us-1`을 Kubernetes 클러스터에 조인했다.

조인 명령:

```bash
sudo kubeadm join k8s-api.monithub.org:6443 \
  --token 0c1540.680d21eef8a6ca2e \
  --discovery-token-ca-cert-hash sha256:df20a1258756bd1584a68b49ea7855205d51756164a3313d8fbd821422be8d50
```

조인 결과:

```text
This node has joined the cluster
```

즉, `kubeadm join` 자체는 성공했다.

하지만 이후 워커 노드에서 확인해보니 `kube-proxy`, `Cilium` 관련 컨테이너가 API Server와 통신하지 못하는 문제가 발생했다.

---

## 1. 최종 원인 한 줄 요약

```text
kubelet은 public endpoint인 https://k8s-api.monithub.org:6443 를 보고 있었지만,
kube-proxy ConfigMap에서 내려온 kubeconfig는 아직 마스터 내부 IP인 https://10.0.0.48:6443 를 보고 있었다.
```

미국 워커 노드는 한국 OCI 마스터의 내부 IP `10.0.0.48`로 라우팅할 수 없기 때문에 `kube-proxy`가 API Server에 접속하지 못했다.

그 결과:

```text
kube-proxy API Server 접근 실패
↓
Service/Endpoint 정보 조회 실패
↓
10.96.0.1 Kubernetes Service NAT 규칙 생성 실패
↓
Cilium이 https://10.96.0.1:443 로 API Server 접근 실패
↓
Cilium config 컨테이너 재시작
```

---

## 2. 주요 구성 정보

```text
Master Public Endpoint: k8s-api.monithub.org:6443
Master Public IP: 150.230.248.235
Master Internal IP: 10.0.0.48
Worker Node: worker-us-1
Kubernetes Version: v1.29.15
CNI: Cilium VXLAN
```

---

## 3. 처음 확인한 것: join 성공 여부

### 명령어

```bash
sudo kubeadm join k8s-api.monithub.org:6443 \
  --token 0c1540.680d21eef8a6ca2e \
  --discovery-token-ca-cert-hash sha256:df20a1258756bd1584a68b49ea7855205d51756164a3313d8fbd821422be8d50
```

### 결과

```text
This node has joined the cluster:
* Certificate signing request was sent to apiserver and a response was received.
* The Kubelet was informed of the new secure connection details.
```

### 해석

`kubeadm join` 자체는 성공했다.

이 말은 최소한 다음이 정상이라는 뜻이다.

```text
워커 → k8s-api.monithub.org:6443 연결 가능
bootstrap token 정상
CA cert hash 정상
kubelet TLS bootstrap 성공
워커 노드가 클러스터에 등록됨
```

하지만 이것은 Kubernetes 네트워크 전체가 정상이라는 뜻은 아니다.

---

## 4. 워커에서 실행 중인 Kubernetes 컨테이너 확인

### 명령어

```bash
sudo crictl ps
```

### 명령 의미

`crictl`은 CRI(Container Runtime Interface)를 통해 containerd에 떠 있는 컨테이너를 조회하는 도구다.

Kubernetes가 Docker Engine 대신 containerd를 사용하므로, 워커 노드에서 실제 실행 중인 Kubernetes 컨테이너를 확인할 때 사용한다.

### 확인된 컨테이너

```text
cilium-envoy
kube-proxy
```

예시 출력:

```text
CONTAINER      IMAGE          CREATED        STATE     NAME           POD
ad2ccf73d4553  696d9bd24e518  3 minutes ago  Running   cilium-envoy   cilium-envoy-wmc9v
30326c4e094dc  9f93dc0efe80c  3 minutes ago  Running   kube-proxy     kube-proxy-74kzk
```

### 해석

워커 노드에 Kubernetes 시스템 컴포넌트가 내려온 것은 확인됐다.

```text
kube-proxy 컨테이너 Running
cilium-envoy 컨테이너 Running
```

하지만 컨테이너가 Running이라고 해서 내부 동작이 정상이라는 뜻은 아니다.  
그래서 로그 확인이 필요했다.

---

## 5. crictl endpoint 경고 처리

### 처음 출력된 경고

```text
runtime connect using default endpoints...
dockershim.sock: no such file or directory
```

### 의미

`crictl`이 기본 endpoint 후보들을 순서대로 찾다가 예전 Docker shim socket을 먼저 찾으면서 발생한 경고다.

현재 Kubernetes는 containerd를 사용하므로 `/run/containerd/containerd.sock`을 명시해주면 된다.

### 설정 명령어

```bash
sudo crictl config runtime-endpoint unix:///run/containerd/containerd.sock
sudo crictl config image-endpoint unix:///run/containerd/containerd.sock
```

### 효과

이후 `crictl`이 containerd socket을 바로 사용하므로 불필요한 dockershim 경고가 줄어든다.

---

## 6. Pod 단위로 확인

### 명령어

```bash
sudo crictl pods
```

### 명령 의미

현재 노드에서 containerd가 관리하는 Kubernetes Pod sandbox 목록을 보여준다.

### Cilium 관련 Pod 확인

```bash
sudo crictl pods | grep cilium
```

### 결과

```text
cilium-envoy-wmc9v   kube-system
cilium-t55qj         kube-system
```

### 해석

워커 노드에 Cilium 관련 Pod가 내려온 것은 확인됐다.

```text
cilium-envoy-wmc9v
cilium-t55qj
```

여기까지 보면 Cilium Pod 자체는 생성되었지만, 내부 컨테이너가 정상인지 추가 확인이 필요하다.

---

## 7. 특정 Pod 안의 컨테이너 확인

### 명령어

```bash
sudo crictl ps -a --pod 025c529ca70c8
```

### 명령 의미

특정 Pod ID 안에 있는 모든 컨테이너를 조회한다.

`-a` 옵션은 Running 컨테이너뿐 아니라 Exited 컨테이너도 보여준다.

### 결과 예시

```text
CONTAINER       IMAGE          CREATED          STATE     NAME     ATTEMPT   POD ID          POD
8b85e5f9fe61f   f2ebd8a25bd8d  11 seconds ago   Running   config   4         025c529ca70c8   cilium-t55qj
0f99454643ce0   f2ebd8a25bd8d  About a minute   Exited    config   3         025c529ca70c8   cilium-t55qj
```

### 해석

Cilium 관련 `config` 컨테이너가 반복 재시작되고 있었다.

중요한 단서:

```text
ATTEMPT 값 증가
Exited 컨테이너 존재
새 config 컨테이너가 다시 Running
```

즉 Cilium 초기 설정 또는 API Server 접속 과정에서 실패 후 재시작 중이라고 판단했다.

---

## 8. 사라진 컨테이너 로그 조회 실패

### 명령어

```bash
sudo crictl logs 0f99454643ce0
```

### 에러

```text
ContainerStatus from runtime service failed
container "0f99454643ce0": not found
```

### 원인

Cilium `config` 컨테이너가 계속 재시작되면서 이전 컨테이너 ID가 삭제된 상태였다.

### 이때 해야 할 것

최신 컨테이너 ID를 다시 조회해야 한다.

```bash
sudo crictl ps -a --pod 025c529ca70c8
```

그 다음 최신 `config` 컨테이너 ID로 로그를 다시 본다.

```bash
sudo crictl logs <최신_CONFIG_CONTAINER_ID>
```

### 트러블슈팅 포인트

Kubernetes 컨테이너는 재시작되면 컨테이너 ID가 바뀔 수 있다.  
따라서 예전 ID로 로그를 보면 `not found`가 날 수 있다.

---

## 9. Cilium config 컨테이너 로그 확인

### 명령어

```bash
sudo crictl logs <CILIUM_CONFIG_CONTAINER_ID>
```

### 주요 로그

```text
Establishing connection to apiserver
ipAddr=https://10.96.0.1:443
```

이후 에러:

```text
Unable to contact k8s api-server
Get "https://10.96.0.1:443/api/v1/namespaces/kube-system":
dial tcp 10.96.0.1:443: i/o timeout
```

### 의미

Cilium은 Kubernetes API Server에 접근하려고 했다.

그런데 Cilium은 직접 `k8s-api.monithub.org:6443`로 붙지 않고, 클러스터 내부 기본 Service 주소인 다음 주소로 접근하려고 했다.

```text
https://10.96.0.1:443
```

`10.96.0.1`은 보통 `kubernetes.default.svc` Service IP다.

즉 Cilium은 다음 경로를 기대했다.

```text
Cilium
↓
https://10.96.0.1:443
↓
Kubernetes Service NAT
↓
실제 API Server
```

하지만 timeout이 발생했다.

---

## 10. 10.96.0.1이 무엇인가?

`10.96.0.1`은 Kubernetes 내부에서 API Server를 가리키는 기본 Service IP다.

보통:

```text
kubernetes.default.svc = 10.96.0.1:443
```

이 Service IP는 실제 API Server IP가 아니다.  
kube-proxy가 iptables NAT 규칙을 만들어서 실제 API Server로 전달해야 한다.

정상 흐름:

```text
Pod 또는 시스템 컴포넌트
↓
10.96.0.1:443
↓
kube-proxy iptables NAT
↓
실제 API Server endpoint
```

---

## 11. 10.96.0.1 NAT 규칙 확인

### 명령어

```bash
sudo iptables -t nat -L -n | grep 10.96.0.1
```

### 명령 의미

iptables NAT 테이블에서 `10.96.0.1` 관련 규칙이 있는지 확인한다.

kube-proxy가 정상 동작하면 `10.96.0.1:443`을 실제 API Server endpoint로 보내는 규칙이 생성되어야 한다.

### 결과

```text
결과 없음
```

### 해석

`10.96.0.1` 관련 NAT 규칙이 없다는 것은 kube-proxy가 Service NAT 규칙을 만들지 못했다는 뜻이다.

즉 Cilium이 `10.96.0.1:443`로 API Server에 접근하려 해도 라우팅이 되지 않는다.

이 시점에서 원인을 다음과 같이 좁혔다.

```text
Cilium 자체 문제라기보다,
kube-proxy가 Service NAT 규칙을 못 만들고 있음
```

---

## 12. kube-proxy 로그 확인

### 명령어

```bash
sudo crictl logs 30326c4e094dc
```

### 명령 의미

`kube-proxy` 컨테이너 로그를 조회한다.

### 주요 로그

```text
Using iptables proxy
```

이는 kube-proxy가 iptables 모드로 실행 중이라는 뜻이다.

이후 에러:

```text
Failed to retrieve node info
Get "https://10.0.0.48:6443/api/v1/nodes/worker-us-1":
dial tcp 10.0.0.48:6443: connect: no route to host
```

또한 다음 리소스들을 계속 조회하지 못했다.

```text
Service
Node
EndpointSlice
Events
```

관련 로그:

```text
failed to list *v1.Service
failed to list *v1.Node
failed to list *v1.EndpointSlice
Unable to write event
```

모두 공통적으로 다음 주소를 보고 있었다.

```text
https://10.0.0.48:6443
```

### 해석

kube-proxy가 API Server에 접근해야 Service/Endpoint 정보를 가져오고 iptables 규칙을 생성할 수 있다.

그런데 kube-proxy가 마스터의 내부 IP인 `10.0.0.48:6443`으로 API Server에 접근하려 하고 있었다.

미국 워커 노드는 한국 OCI 내부 IP `10.0.0.48`로 라우팅할 수 없기 때문에 실패했다.

---

## 13. kube-proxy가 실패하면 왜 Cilium도 실패하는가?

kube-proxy 실패:

```text
kube-proxy가 API Server에 못 붙음
↓
Service / EndpointSlice 정보 조회 실패
↓
10.96.0.1:443 NAT 규칙 생성 실패
```

Cilium 실패:

```text
Cilium이 https://10.96.0.1:443 로 API Server 접근 시도
↓
10.96.0.1 NAT 규칙 없음
↓
i/o timeout
```

즉 Cilium의 직접 원인은 `10.96.0.1:443` timeout이지만, 그 앞단 원인은 kube-proxy가 API Server에 붙지 못해서 Service NAT 규칙을 만들지 못한 것이다.

---

## 14. kubelet 설정은 정상인지 확인

### 명령어

```bash
sudo grep server /etc/kubernetes/kubelet.conf
sudo grep server /etc/kubernetes/bootstrap-kubelet.conf 2>/dev/null
```

### 결과

```text
server: https://k8s-api.monithub.org:6443
```

### 해석

워커의 kubelet은 정상적으로 public endpoint를 보고 있었다.

즉 kubelet은 문제가 아니다.

정리:

```text
kubelet → https://k8s-api.monithub.org:6443 ✅
```

그래서 `kubeadm join`이 성공할 수 있었다.

---

## 15. 10.0.0.48이 어디에 남아 있는지 전체 검색

### 명령어

```bash
sudo grep -R "10.0.0.48" /etc/kubernetes /var/lib/kubelet 2>/dev/null
```

### 명령 의미

워커 노드의 Kubernetes 설정 디렉터리에서 `10.0.0.48` 문자열이 남아 있는 파일을 재귀적으로 찾는다.

대상:

```text
/etc/kubernetes
/var/lib/kubelet
```

에러 출력은 숨겼다.

```bash
2>/dev/null
```

### 결과

```text
/var/lib/kubelet/pods/.../volumes/kubernetes.io~configmap/kube-proxy/.../kubeconfig.conf:
    server: https://10.0.0.48:6443
```

### 해석

문제 원인이 정확히 확인됐다.

`10.0.0.48`은 kubelet 설정이 아니라 kube-proxy Pod에 마운트된 ConfigMap 안에 있었다.

즉:

```text
/etc/kubernetes/kubelet.conf
→ public endpoint 정상

/var/lib/kubelet/pods/.../kube-proxy/kubeconfig.conf
→ internal IP 10.0.0.48 사용
```

---

## 16. 왜 /var/lib/kubelet/pods 아래 파일을 직접 수정하면 안 되는가?

검색 결과에 나온 파일은 다음 경로에 있었다.

```text
/var/lib/kubelet/pods/.../volumes/kubernetes.io~configmap/kube-proxy/kubeconfig.conf
```

이 파일은 워커 노드 로컬 설정 원본이 아니다.  
마스터의 Kubernetes ConfigMap이 Pod에 마운트된 결과물이다.

즉 원본은 마스터에 있는:

```text
kube-system namespace의 kube-proxy ConfigMap
```

이다.

워커에서 이 파일을 직접 수정해도:

```text
Pod 재시작
ConfigMap 재마운트
원래 내용으로 복구
```

될 수 있다.

따라서 근본 수정은 마스터에서 해야 한다.

---

## 17. 최종 원인 구조

```text
1. kubeadm join
   → k8s-api.monithub.org:6443 사용
   → 성공

2. kubelet
   → /etc/kubernetes/kubelet.conf
   → server: https://k8s-api.monithub.org:6443
   → 정상

3. kube-proxy
   → kube-proxy ConfigMap에서 kubeconfig.conf 마운트
   → server: https://10.0.0.48:6443
   → 실패

4. kube-proxy 실패
   → Service/Endpoint 정보 조회 못 함
   → iptables NAT 규칙 생성 못 함
   → 10.96.0.1 관련 규칙 없음

5. Cilium
   → https://10.96.0.1:443 로 API Server 접근 시도
   → NAT 규칙 없음
   → i/o timeout
   → config 컨테이너 재시작
```

---

## 18. 최종 원인

```text
마스터의 kube-proxy ConfigMap에 들어 있는 kubeconfig server 주소가
https://10.0.0.48:6443 으로 되어 있었다.
```

이 IP는 한국 OCI 내부 IP다.

미국 워커 노드는 이 IP에 접근할 수 없다.

그래서 kube-proxy가 API Server에 접근하지 못했고, Cilium도 연쇄적으로 실패했다.

---

## 19. 해결 방향

### 마스터에서 확인

```bash
kubectl -n kube-system get cm kube-proxy -o yaml | grep -n "10.0.0.48"
```

### 마스터에서 수정

```bash
kubectl -n kube-system edit cm kube-proxy
```

아래 값을 찾는다.

```yaml
server: https://10.0.0.48:6443
```

다음으로 변경한다.

```yaml
server: https://k8s-api.monithub.org:6443
```

### kube-proxy 재시작

```bash
kubectl -n kube-system rollout restart ds kube-proxy
```

또는:

```bash
kubectl -n kube-system delete pod -l k8s-app=kube-proxy
```

DaemonSet이 kube-proxy Pod를 다시 생성하면서 수정된 ConfigMap을 마운트하게 된다.

---

## 20. 수정 후 워커에서 확인할 명령어

### kube-proxy 새 로그 확인

```bash
sudo crictl ps -a | grep kube-proxy
sudo crictl logs <새_KUBE_PROXY_CONTAINER_ID> | tail -50
```

확인할 것:

```text
10.0.0.48:6443 no route to host 에러가 사라졌는지
Service / EndpointSlice watch 실패가 사라졌는지
```

---

### kube-proxy ConfigMap 마운트 내용 재확인

```bash
sudo grep -R "10.0.0.48" /var/lib/kubelet/pods 2>/dev/null
```

결과가 없어야 한다.

또는:

```bash
sudo grep -R "k8s-api.monithub.org" /var/lib/kubelet/pods 2>/dev/null
```

kube-proxy kubeconfig에서 public endpoint가 보여야 한다.

---

### iptables NAT 규칙 확인

```bash
sudo iptables -t nat -L -n | grep 10.96.0.1
```

정상이라면 `10.96.0.1:443` 관련 규칙이 생겨야 한다.

---

### Cilium 상태 확인

```bash
sudo crictl ps -a | grep cilium
sudo crictl pods | grep cilium
```

Cilium config 컨테이너가 계속 재시작되지 않아야 한다.

---

## 21. 마스터에서 최종 확인할 명령어

### 노드 상태

```bash
kubectl get nodes -o wide
```

확인할 것:

```text
worker-us-1 STATUS = Ready
worker-us-1 INTERNAL-IP 확인
```

---

### kube-system Pod 상태

```bash
kubectl -n kube-system get pods -o wide
```

확인할 것:

```text
kube-proxy Running
cilium Running
coredns Running
```

---

### Cilium Pod 확인

```bash
kubectl -n kube-system get pods -l k8s-app=cilium -o wide
```

확인할 것:

```text
worker-us-1에 뜬 cilium Pod가 Running/Ready인지
```

---

### Cilium 상태

```bash
kubectl -n kube-system exec ds/cilium -- cilium status
```

확인할 것:

```text
Cluster health reachable
Node reachable
Cilium agent 정상
```

---

## 22. 원인을 좁혀간 순서

이번 트러블슈팅에서 원인을 좁혀간 순서는 다음과 같다.

```text
1. kubeadm join 성공 확인
   → 워커가 클러스터에 등록된 것은 확인

2. crictl ps 확인
   → kube-proxy, cilium-envoy 컨테이너가 워커에 내려온 것 확인

3. crictl pods 확인
   → cilium 관련 Pod가 존재하는 것 확인

4. crictl ps -a --pod 확인
   → cilium config 컨테이너가 반복 재시작되는 것 확인

5. Cilium config 로그 확인
   → Cilium이 10.96.0.1:443 API Service 접근 timeout 확인

6. iptables NAT에서 10.96.0.1 확인
   → Kubernetes Service NAT 규칙이 없는 것 확인

7. kube-proxy 로그 확인
   → kube-proxy가 10.0.0.48:6443 API Server 접근 실패 확인

8. kubelet.conf 확인
   → kubelet은 k8s-api.monithub.org:6443을 보고 있어서 정상 확인

9. grep -R "10.0.0.48" 검색
   → kube-proxy ConfigMap 마운트 파일에 10.0.0.48이 남아 있는 것 확인

10. 최종 결론
   → kube-proxy ConfigMap의 server 주소가 내부 IP라서 발생한 문제
```

---

## 23. 각 명령어 요약표

| 명령어 | 목적 | 확인한 것 |
|---|---|---|
| `sudo kubeadm join ...` | 워커 노드를 클러스터에 조인 | join 자체는 성공 |
| `sudo crictl ps` | 실행 중인 컨테이너 조회 | kube-proxy, cilium-envoy Running |
| `sudo crictl pods` | Pod sandbox 조회 | cilium Pod 존재 |
| `sudo crictl ps -a --pod <POD_ID>` | 특정 Pod 내부 컨테이너 전체 조회 | Cilium config 컨테이너 재시작 확인 |
| `sudo crictl logs <CONTAINER_ID>` | 컨테이너 로그 확인 | Cilium API 접근 timeout, kube-proxy 내부 IP 접근 실패 |
| `sudo iptables -t nat -L -n \| grep 10.96.0.1` | Kubernetes Service NAT 규칙 확인 | 10.96.0.1 규칙 없음 |
| `sudo grep server /etc/kubernetes/kubelet.conf` | kubelet API Server 주소 확인 | kubelet은 public endpoint 사용 |
| `sudo grep -R "10.0.0.48" /etc/kubernetes /var/lib/kubelet` | 내부 IP 참조 위치 검색 | kube-proxy ConfigMap 마운트에서 발견 |

---

## 24. 핵심 개념 정리

### kubelet

워커 노드의 Kubernetes 에이전트다.  
Pod 실행, 노드 상태 보고, containerd 제어를 담당한다.

이번 문제에서는 kubelet은 정상적으로 public endpoint를 보고 있었다.

```text
server: https://k8s-api.monithub.org:6443
```

---

### kube-proxy

Kubernetes Service 네트워크를 처리한다.  
iptables 규칙을 만들어 Service IP를 실제 endpoint로 라우팅한다.

이번 문제에서는 kube-proxy가 API Server에 접근하지 못해 Service NAT 규칙을 만들지 못했다.

---

### 10.96.0.1

Kubernetes API Server를 가리키는 내부 Service IP다.

보통:

```text
kubernetes.default.svc = 10.96.0.1:443
```

Cilium 같은 컴포넌트가 이 주소로 API Server에 접근할 수 있어야 한다.

---

### Cilium

Kubernetes CNI 플러그인이다.  
Pod 네트워크, VXLAN, Service 통신 등을 처리한다.

이번 문제에서는 Cilium 자체가 근본 원인은 아니었다.  
Cilium이 API Server Service IP `10.96.0.1:443`로 접근하려 했지만, kube-proxy NAT 규칙이 없어서 timeout이 발생했다.

---

### ConfigMap

Kubernetes에서 설정 파일을 Pod에 주입하는 리소스다.

이번 문제에서 kube-proxy의 kubeconfig는 ConfigMap으로부터 Pod에 마운트되었다.

그래서 워커의 `/var/lib/kubelet/pods/...` 아래 파일을 직접 수정하는 것이 아니라, 마스터의 kube-proxy ConfigMap을 수정해야 한다.

---

## 25. 팀장님께 전달할 요약

```text
join 자체는 성공했고 kubelet은 public endpoint인 k8s-api.monithub.org:6443을 보고 있습니다.

하지만 kube-proxy ConfigMap에서 내려온 kubeconfig는 아직 server: https://10.0.0.48:6443 을 보고 있습니다.

그래서 kube-proxy가 API Server에 접근하지 못하고, Service/Endpoint 정보를 못 받아와서 10.96.0.1 Kubernetes Service NAT 규칙도 생성되지 않습니다.

그 결과 Cilium도 10.96.0.1:443로 API Server에 접근하다가 timeout이 발생합니다.

마스터에서 kube-system/kube-proxy ConfigMap의 server 주소를 https://k8s-api.monithub.org:6443 로 바꾸고 kube-proxy DaemonSet을 재시작해야 합니다.
```

---

## 26. 최종 구조 그림

### 현재 문제 구조

```text
kubelet
↓
https://k8s-api.monithub.org:6443
↓
정상

kube-proxy
↓
https://10.0.0.48:6443
↓
no route to host

Cilium
↓
https://10.96.0.1:443
↓
kube-proxy NAT 규칙 없음
↓
timeout
```

### 수정 후 기대 구조

```text
kubelet
↓
https://k8s-api.monithub.org:6443
↓
정상

kube-proxy
↓
https://k8s-api.monithub.org:6443
↓
Service/Endpoint 정보 조회 성공
↓
iptables NAT 규칙 생성
↓
10.96.0.1:443 동작

Cilium
↓
https://10.96.0.1:443
↓
API Server 접근 성공
↓
Cilium 정상화
```
