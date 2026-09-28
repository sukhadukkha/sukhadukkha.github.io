---
layout: single
title:  "[RHEL 시리즈 08] 네트워크·SSH·firewalld 관리"
categories: [Linux]
tags: [Linux]
toc: true
author_profile: true
---

원격 서버를 운영하려면 IP 주소와 경로, 이름 해석, SSH 인증, 방화벽을 함께 이해해야 한다. RHEL의 NetworkManager와 firewalld를 중심으로 정리한다.

## 1. 네트워크 설정의 구성 요소

- **IP 주소와 Prefix**: 호스트와 같은 네트워크 범위를 식별한다.
- **Default Gateway**: 같은 네트워크 밖으로 나갈 때 전달할 라우터다.
- **DNS**: 도메인 이름을 IP 주소로 변환한다.
- **Route**: 목적지별로 어느 인터페이스와 Gateway를 사용할지 정한다.
- **Port**: 하나의 IP에서 어떤 서비스와 통신할지 구분한다.

```bash
ip -br addr
ip route
ss -lntup
resolvectl status
ping -c 4 192.168.1.1
```

문제 확인은 물리 링크, IP와 Prefix, Route, DNS, 서비스 포트 순서로 범위를 좁히면 이해하기 쉽다.

## 2. NetworkManager와 nmcli

RHEL은 NetworkManager로 네트워크 장치와 연결 프로파일을 관리한다. 장치는 실제 NIC이고, connection은 IP·DNS·Route 설정을 담은 프로파일이다.

```bash
nmcli device status
nmcli connection show
nmcli connection show --active
```

### 고정 IP 설정 예시

```bash
nmcli connection modify ens192 \
  ipv4.method manual \
  ipv4.addresses 192.168.1.50/24 \
  ipv4.gateway 192.168.1.1 \
  ipv4.dns '192.168.1.10 8.8.8.8'

nmcli connection up ens192
```

원격 접속 중 IP를 변경하면 연결이 끊길 수 있다. 콘솔 접속 방법과 복구 계획을 확보한 뒤 수행한다.

## 3. 네트워크 문제 확인 순서

```bash
ip link show
ip -br addr
ip route get 8.8.8.8
ping -c 3 게이트웨이주소
getent hosts example.com
ss -lntp
curl -I http://서버주소
```

IP로는 접속되지만 이름으로 접속되지 않으면 DNS 영역을 의심할 수 있다. 서버에서 프로세스가 포트를 열지 않았다면 방화벽을 열어도 서비스에 연결할 수 없다. 따라서 서비스 상태와 listening port를 먼저 확인한다.

## 4. SSH

SSH는 암호화된 원격 Shell과 파일 전송 기능을 제공하며 기본 포트는 TCP 22다.

```bash
ssh user01@server
scp file.txt user01@server:/tmp/
sftp user01@server
```

### Host Key와 User Key

- **Host Key**: 접속한 서버가 이전에 접속한 바로 그 서버인지 확인하는 서버의 신원 정보다. 처음 접속하면 fingerprint를 확인해 `known_hosts`에 저장한다.
- **User Key**: 사용자가 개인키를 소유했음을 증명해 로그인하는 인증 수단이다.

```bash
ssh-keygen -t ed25519
ssh-copy-id user01@server
ssh -i ~/.ssh/id_ed25519 user01@server
```

개인키는 외부에 공개하면 안 된다. 서버에는 공개키가 `~/.ssh/authorized_keys`에 저장된다.

### sshd 설정

주요 설정 파일은 `/etc/ssh/sshd_config`다.

```bash
sshd -t
systemctl reload sshd
```

설정 변경 후 `sshd -t`로 문법을 검사하고, 기존 SSH 세션을 유지한 채 새 세션 접속을 시험한 다음 기존 세션을 종료하는 것이 안전하다.

## 5. firewalld

firewalld는 Zone을 기준으로 네트워크 인터페이스와 소스에 정책을 적용한다. 서비스 이름 또는 포트를 허용할 수 있다.

```bash
firewall-cmd --get-active-zones
firewall-cmd --list-all
firewall-cmd --get-services
```

### Runtime과 Permanent

```bash
firewall-cmd --add-service=http
firewall-cmd --permanent --add-service=http
firewall-cmd --reload
```

- **Runtime**: 현재 실행 중인 설정이며 재시작하면 사라질 수 있다.
- **Permanent**: 저장된 설정이며 reload 후 Runtime에 반영된다.

특정 포트를 열 때는 프로토콜도 지정한다.

```bash
firewall-cmd --permanent --add-port=9100/tcp
firewall-cmd --reload
firewall-cmd --query-port=9100/tcp
```

가능하면 넓은 포트 범위보다 필요한 서비스와 포트만 허용한다. 서비스가 사용하는 포트, 접근해야 할 출발지, 적용 Zone을 확인한 뒤 설정한다.

## 6. 연결 문제를 볼 때 구분할 것

```text
프로세스 실행 여부 → systemctl, ps
포트 Listen 여부   → ss
로컬 접속 여부     → curl localhost:PORT
방화벽 허용 여부   → firewall-cmd
경로와 IP 설정     → ip addr, ip route
이름 해석 여부     → getent hosts
```

네트워크 문제는 한 번에 모든 설정을 바꾸기보다 각 계층의 상태를 차례로 확인해야 원인과 조치 결과를 분명하게 남길 수 있다.
