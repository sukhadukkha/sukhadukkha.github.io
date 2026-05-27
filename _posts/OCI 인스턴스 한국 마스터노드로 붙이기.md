# 워커 노드 설치/설정 필요 사항 및 OpenLens kubeconfig 가져오기

작성일: 2026-04-30

---

# 1. 목표 구성

마스터 control-plane은 한국 OCI 인스턴스에 있고, 워커 노드는 미국 서버에 둔다.

* API Endpoint: `k8s-api.monithub.org:6443`
* 마스터 Public IP: `150.230.248.235`
* 마스터 내부 IP: `10.0.0.48`
* 워커 Public IP: `129.159.177.124`
* Kubernetes 버전: `v1.29.15`
* CNI: `Cilium VXLAN tunnel`
* VXLAN 포트: `UDP 8472`

---

# 2. 워커 조인 전 핵심 네트워크 조건

워커에서 다음 접근이 가능해야 한다.

```bash
curl -k https://k8s-api.monithub.org:6443/version
```

또는 TCP 연결 확인:

```bash
timeout 5 bash -c '</dev/tcp/k8s-api.monithub.org/6443' && echo ok
```

## 마스터에서 허용해야 하는 포트

| 방향       | 포트        | 용도                           |
| -------- | --------- | ---------------------------- |
| 워커 → 마스터 | TCP 6443  | kubeadm join, Kubernetes API |
| 워커 ↔ 마스터 | TCP 10250 | kubelet API                  |
| 워커 ↔ 마스터 | UDP 8472  | Cilium VXLAN                 |

## 주의

다음 포트는 외부에 열지 않는다.

* etcd: `2379-2380`
* controller-manager: `10257`
* scheduler: `10259`

---

# 3. Node IP 설계 주의사항

API 서버는 Public DNS로 접근 가능하지만, Cilium VXLAN과 Pod-to-Pod 통신은 Kubernetes Node IP 기준으로 동작한다.

현재 마스터 노드 INTERNAL-IP:

```text
10.0.0.48
```

## 문제 가능성

* 미국 워커가 한국 마스터의 `10.0.0.48`에 직접 접근할 수 없다면 VXLAN 실패 가능
* 조인은 성공해도 Pod 통신/CoreDNS/service routing 실패 가능
* OCI Public IP는 NAT 구조일 수 있어 `kubelet --node-ip=<public-ip>`가 거부될 수 있음

## 권장 구성

* WireGuard 
* Tailscale
* VPN
* OCI Remote Peering

각 노드가 서로 직접 통신 가능한 Node IP를 갖는 것이 중요하다.

---

# 4. 워커 노드 사전 준비

Ubuntu 22.04 기준.

## 4.1 hostname 설정

```bash
hostnamectl
sudo hostnamectl set-hostname worker-us-1
```

## 4.2 swap 비활성화

```bash
sudo swapoff -a
sudo sed -i.bak '/ swap / s/^/#/' /etc/fstab
```

확인:

```bash
free -h
```

## 4.3 커널 모듈 및 sysctl

```bash
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

sudo modprobe overlay
sudo modprobe br_netfilter
```

```bash
cat <<EOF | sudo tee /etc/sysctl.d/99-kubernetes-cri.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF
```

```bash
sudo sysctl --system
```

---

# 5. containerd 설치 및 설정

```bash
sudo apt-get update
sudo apt-get install -y containerd
```

기본 설정 생성:

```bash
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
```

systemd cgroup 활성화:

```bash
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd
```

확인:

```bash
sudo systemctl status containerd --no-pager
```

---

# 6. kubeadm / kubelet / kubectl 설치

```bash
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gpg
```

```bash
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
```

```bash
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /' \
  | sudo tee /etc/apt/sources.list.d/kubernetes.list
```

```bash
sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
```

버전 확인:

```bash
kubeadm version
kubelet --version
kubectl version --client
```

---

# 7. 워커 OS 방화벽

## 인바운드

* TCP `10250` (kubelet)
* UDP `8472` (Cilium VXLAN)

## 아웃바운드

* 마스터 TCP `6443`
* 마스터 TCP `10250`
* 마스터 UDP `8472`
* HTTPS `443` (이미지 Pull)

---

# 8. kubeadm join

마스터에서 생성된 조인 명령:

```bash
kubeadm join k8s-api.monithub.org:6443 --token 7bwbdk.tlfnoibrbozrdb4y --discovery-token-ca-cert-hash sha256:df20a1258756bd1584a68b49ea7855205d51756164a3313d8fbd821422be8d50
```

워커에서 실행:

```bash
sudo kubeadm join k8s-api.monithub.org:6443 --token 7bwbdk.tlfnoibrbozrdb4y --discovery-token-ca-cert-hash sha256:df20a1258756bd1584a68b49ea7855205d51756164a3313d8fbd821422be8d50
```

토큰 만료 시:

```bash
kubeadm token create --print-join-command
```

---

# 9. 조인 후 검증

```bash
kubectl get nodes -o wide
kubectl -n kube-system get pods -o wide
kubectl -n kube-system get pods -l k8s-app=cilium -o wide
kubectl -n kube-system exec ds/cilium -- cilium status
```

## 확인 항목

* 워커 노드 Ready 여부
* 워커 INTERNAL-IP 접근 가능 여부
* cilium Pod Running 여부
* CoreDNS Running 여부
* cluster health reachable 여부

---

# 10. Pod-to-Pod 통신 테스트

```bash
kubectl create deployment nginx-test --image=nginx:1.27
kubectl expose deployment nginx-test --port=80 --target-port=80
kubectl get pods -o wide
```

```bash
kubectl run curl-test --image=curlimages/curl:8.11.1 --restart=Never -- sleep 300
kubectl wait --for=condition=Ready pod/curl-test --timeout=120s
kubectl exec curl-test -- curl -sS nginx-test.default.svc.cluster.local
```

테스트 후 정리:

```bash
kubectl delete pod curl-test --ignore-not-found=true
kubectl delete svc nginx-test --ignore-not-found=true
kubectl delete deploy nginx-test --ignore-not-found=true
```

---

# 11. OpenLens 연결용 kubeconfig 가져오기

## 11.1 마스터에서 kubeconfig 생성

```bash
sudo cp -f /etc/kubernetes/admin.conf /home/ubuntu/kubeconfig-openlens.yaml
sudo chown ubuntu:ubuntu /home/ubuntu/kubeconfig-openlens.yaml
chmod 600 /home/ubuntu/kubeconfig-openlens.yaml
```

server 주소 변경:

```bash
sed -i 's#server: https://10.0.0.48:6443#server: https://k8s-api.monithub.org:6443#' /home/ubuntu/kubeconfig-openlens.yaml
```

확인:

```bash
grep 'server:' /home/ubuntu/kubeconfig-openlens.yaml
```

결과:

```text
server: https://k8s-api.monithub.org:6443
```

---

## 11.2 로컬 PC로 가져오기

```bash
scp ubuntu@150.230.248.235:/home/ubuntu/kubeconfig-openlens.yaml ./kubeconfig-monithub.yaml
```

SSH Key 사용 시:

```bash
scp -i /path/to/private-key ubuntu@150.230.248.235:/home/ubuntu/kubeconfig-openlens.yaml ./kubeconfig-monithub.yaml
```

---

## 11.3 OpenLens에 추가

OpenLens에서:

1. Add Cluster
2. Browse kubeconfig
3. `kubeconfig-monithub.yaml` 선택
4. Cluster Context 선택

연결 확인:

```bash
curl -k https://k8s-api.monithub.org:6443/version
```

```bash
KUBECONFIG=./kubeconfig-monithub.yaml kubectl get nodes -o wide
```

---

## 11.4 보안 주의

* kubeconfig-openlens.yaml은 cluster-admin 권한 포함
* Git 저장소/메신저/공개 서버 업로드 금지
* 사용 후 삭제 권장

마스터에서 삭제:

```bash
rm -f /home/ubuntu/kubeconfig-openlens.yaml
```

로컬 PC에서 삭제:

```bash
rm -f ./kubeconfig-monithub.yaml
```


# 왜 그렇게 했나에 관한 질문


- 왜 Docker Hub 대신 private registry를 썼는가?
- 왜 SSL이 필요한가?
- 왜 Kubernetes Node IP가 중요한가?
- 왜 VXLAN만으로 부족하고 VPN이 필요할 수 있는가?
- 왜 6443, 10250, 8472 포트를 열어야 하는가?
- 왜 etcd 2379-2380은 외부에 열면 안 되는가?
- Docker Compose에서 Kubernetes로 가면 무엇이 바뀌는가?