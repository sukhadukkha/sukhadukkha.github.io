---
layout: single
title:  "[RHEL 시리즈 09] 로그·tuned·SELinux·부팅·Podman"
categories: [Linux]
tags: [Linux]
toc: true
author_profile: true
---

마지막 글에서는 장애 분석과 운영에 필요한 로그, 시간 동기화, 성능 프로파일, SELinux, 부팅 과정과 Podman 컨테이너를 정리한다.

## 1. systemd-journald와 rsyslog

`systemd-journald`는 Kernel과 systemd 서비스 등의 로그를 Journal 형식으로 수집한다. `rsyslog`는 로그를 규칙에 따라 텍스트 파일이나 원격 로그 서버로 전달할 수 있다.

```bash
journalctl
journalctl -b
journalctl -b -1
journalctl -u sshd
journalctl -p err
journalctl --since '2026-09-28 09:00:00'
journalctl -f
```

- `-b`: 현재 부팅의 로그
- `-b -1`: 이전 부팅의 로그
- `-u`: 특정 systemd Unit 로그
- `-p`: 우선순위별 필터
- `-f`: 새 로그를 실시간으로 표시

전통적인 텍스트 로그는 `/var/log/messages`, `/var/log/secure`, `/var/log/cron` 등에서 확인한다. RHEL 버전과 서비스 설정에 따라 실제 위치는 다를 수 있다.

장애 시간을 기준으로 애플리케이션, OS, 네트워크와 스토리지 로그를 같은 시간대에서 비교하려면 시간 동기화가 중요하다.

## 2. chronyd와 시간 동기화

```bash
timedatectl
chronyc tracking
chronyc sources -v
systemctl status chronyd
```

`chronyc tracking`은 현재 시스템 시간의 동기화 상태, `sources -v`는 사용 중인 시간 서버와 후보 서버 상태를 보여준다. 애플리케이션 서버와 스토리지의 시간이 다르면 파일 생성 시각이나 장애 순서를 잘못 해석할 수 있다.

## 3. tuned와 프로세스 우선순위

`tuned`는 서버 용도에 맞춰 CPU, 전원, 디스크와 Kernel 관련 설정을 프로파일로 적용한다.

```bash
tuned-adm list
tuned-adm active
tuned-adm recommend
tuned-adm profile throughput-performance
```

권장 프로파일을 그대로 적용하기 전에 워크로드 특성과 전력·지연시간 요구사항을 확인하고 변경 전후 지표를 비교한다.

`nice` 값은 프로세스의 CPU 스케줄링 우선순위에 영향을 준다. 범위는 보통 -20부터 19까지며 값이 낮을수록 우선순위가 높다.

```bash
nice -n 10 작업명
renice 5 -p PID
```

우선순위 변경은 CPU 자원 경쟁에 영향을 주지만 I/O나 애플리케이션 자체 문제를 해결하는 만능 설정은 아니다.

## 4. SELinux

SELinux는 일반적인 사용자·그룹 권한에 추가로 정책을 검사하는 Mandatory Access Control이다. 파일과 프로세스에 붙은 context와 정책 규칙을 기준으로 접근을 허용하거나 거부한다.

```bash
getenforce
sestatus
ls -Z /var/www/html
ps -eZ | grep httpd
```

### 동작 모드

- **Enforcing**: 정책을 적용하고 위반을 차단한다.
- **Permissive**: 차단하지 않고 위반 로그만 남긴다.
- **Disabled**: SELinux 기능을 사용하지 않는다.

접근이 거부됐다고 SELinux를 바로 끄지 않는다. 먼저 일반 권한과 로그, context, Boolean과 정책을 확인한다.

```bash
ausearch -m AVC -ts recent
restorecon -Rv /var/www/html
semanage fcontext -a -t httpd_sys_content_t '/web(/.*)?'
restorecon -Rv /web
getsebool -a | grep httpd
```

`chcon`은 임시 변경이 될 수 있다. 영구적인 파일 context 규칙은 `semanage fcontext`로 등록하고 `restorecon`으로 적용한다.

## 5. Linux 부팅 흐름

```text
Firmware(BIOS/UEFI)
  → Boot Loader(GRUB2)
  → Kernel과 initramfs
  → systemd(PID 1)
  → target과 서비스 시작
```

```bash
systemctl get-default
systemctl set-default multi-user.target
systemctl isolate multi-user.target
systemctl list-dependencies default.target
```

`set-default`는 다음 부팅의 기본 target을 바꾸고, `isolate`는 현재 실행 상태를 전환한다. 원격 서버에서 target을 바꾸면 네트워크나 그래픽 세션이 종료될 수 있으므로 영향 범위를 먼저 확인한다.

부팅 문제는 이전 부팅 Journal, `fstab`, 파일시스템 상태, Kernel 명령줄과 실패한 Unit을 확인한다.

```bash
systemctl --failed
journalctl -b -p err
journalctl -b -1 -p err
```

root 암호 재설정이나 응급 모드 작업은 콘솔 접근과 시스템 정책이 필요한 관리 절차다. 작업 후에는 SELinux relabel 필요 여부와 계정 보안 기록을 확인한다.

## 6. 컨테이너와 Podman

컨테이너는 애플리케이션과 필요한 파일을 격리된 실행 환경으로 묶는다. 가상머신처럼 별도 Guest Kernel을 실행하는 방식이 아니라 Host Kernel을 공유한다.

RHEL에서는 daemonless 구조와 rootless 실행을 지원하는 Podman을 기본 컨테이너 도구로 사용한다.

```bash
podman search nginx
podman pull docker.io/library/nginx
podman images
podman run -d --name web -p 8080:80 nginx
podman ps
podman logs web
podman exec -it web /bin/sh
podman inspect web
podman stop web
podman rm web
```

### 데이터와 네트워크

```bash
podman volume create app-data
podman network create app-net
podman run -d --name app \
  --network app-net \
  -v app-data:/data:Z \
  image-name
```

SELinux가 Enforcing인 Host에서 bind mount나 volume을 사용할 때 `:Z` 또는 환경에 맞는 label 처리가 필요할 수 있다. 의미를 확인하지 않고 권한을 과도하게 열거나 SELinux를 끄는 방식은 피한다.

컨테이너 실행 후에는 상태만 `Up`인지 보는 데 그치지 않고 포트, 로그, 저장 경로, 재시작 정책과 Host 재부팅 후 동작도 확인해야 한다. 장기 서비스는 systemd와 연계해 자동 시작과 종료 순서를 관리할 수 있다.

## 7. 운영 확인 흐름

```text
현상과 발생 시각 확인
  → 서비스·프로세스 상태 확인
  → Journal과 애플리케이션 로그 확인
  → CPU·메모리·디스크·네트워크 상태 확인
  → 권한·SELinux·방화벽 확인
  → 조치 후 같은 방법으로 재검증
```

로그와 시간, 보안 정책, 부팅, 컨테이너는 서로 분리된 주제가 아니다. 실제 장애에서는 같은 서비스의 동작 조건으로 연결되므로 변경 전후 상태와 로그를 함께 남기는 습관이 중요하다.
