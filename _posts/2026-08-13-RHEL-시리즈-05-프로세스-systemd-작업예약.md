---
layout: single
title:  "[RHEL 시리즈 05] 프로세스·systemd 서비스·작업 예약"
categories: [Linux]
tags: [Linux]
toc: true
author_profile: true
---

서버 운영에서는 현재 실행 중인 작업을 확인하고, 서비스를 제어하며, 반복 작업을 정해진 시각에 실행할 수 있어야 한다.

## 1. 프로세스란?

프로그램은 디스크에 저장된 실행 파일이고, 프로세스는 메모리에 올라와 실행 중인 프로그램의 인스턴스다. 각 프로세스는 PID를 가지며 부모 프로세스의 PID인 PPID도 가진다.

```bash
ps aux
ps -ef
ps -eo pid,ppid,user,stat,%cpu,%mem,cmd --sort=-%cpu
```

`ps aux`는 BSD 형식으로 CPU와 메모리 사용률을 보기 편하고, `ps -ef`는 부모·자식 관계와 전체 명령을 확인하기 좋다.

### 주요 프로세스 상태

| 상태 | 의미 |
|---|---|
| `R` | 실행 중이거나 실행 대기 |
| `S` | 인터럽트 가능한 대기 |
| `D` | 주로 I/O를 기다리는 인터럽트 불가능 대기 |
| `T` | 정지됨 |
| `Z` | 종료됐지만 부모가 상태를 회수하지 않은 좀비 |

`D`나 `Z` 상태가 보인다고 즉시 장애는 아니다. 오래 지속되는지, 어떤 자원을 기다리는지와 부모 프로세스 상태를 함께 확인한다.

## 2. 프로세스 모니터링

```bash
top
uptime
free -h
vmstat 1 5
```

`top`은 CPU, 메모리, 프로세스 상태를 실시간으로 보여준다. `uptime`의 Load Average는 1분, 5분, 15분 동안 실행 중이거나 실행·I/O를 기다린 작업 수의 평균이다.

Load Average는 CPU 코어 수와 함께 본다. 값이 높더라도 CPU 사용률, I/O 대기, 메모리와 스왑, 지속 시간을 함께 확인해야 원인을 판단할 수 있다.

## 3. Signal과 프로세스 종료

Signal은 프로세스에 특정 동작을 요청하는 방식이다.

```bash
kill -TERM 1234
kill -KILL 1234
pgrep -a httpd
pkill -TERM httpd
```

- `SIGTERM(15)`: 프로세스가 정리 작업을 수행하고 정상 종료할 기회를 준다.
- `SIGKILL(9)`: Kernel이 즉시 종료하며 프로세스가 처리할 수 없다.
- `SIGHUP(1)`: 일부 데몬에서 설정 재읽기에 사용한다.

먼저 `TERM`으로 정상 종료를 요청하고, 응답하지 않을 때 원인을 확인한 후 `KILL`을 마지막 수단으로 사용한다.

## 4. systemd와 Unit

RHEL은 systemd를 PID 1의 초기화 시스템으로 사용한다. systemd는 서비스 시작 순서와 의존성을 관리하고 시스템 상태를 Unit으로 표현한다.

주요 Unit 유형은 `service`, `socket`, `target`, `mount`, `timer` 등이 있다.

```bash
systemctl status sshd
systemctl start sshd
systemctl stop sshd
systemctl restart sshd
systemctl reload sshd
systemctl enable sshd
systemctl disable sshd
systemctl enable --now sshd
systemctl is-active sshd
systemctl is-enabled sshd
```

`start`는 현재 실행, `enable`은 부팅 시 자동 시작 설정이다. 두 동작은 별개다. `enable --now`는 둘을 함께 수행한다.

설정 파일을 수정했다면 서비스가 설정 재읽기를 지원하는지 확인한 뒤 `reload` 또는 `restart`를 선택한다.

### Unit 파일 확인

```bash
systemctl cat sshd
systemctl list-dependencies sshd
systemctl list-unit-files --type=service
```

배포판이 제공한 Unit 파일을 직접 고치기보다 다음 명령으로 override를 만들어 변경하는 방식이 안전하다.

```bash
systemctl edit 서비스명
systemctl daemon-reload
```

## 5. 일회성 작업 예약: at

```bash
echo '/usr/local/bin/report.sh' | at 23:00
atq
atrm 작업번호
```

`at`은 한 번만 실행할 작업에 사용한다. `atd` 서비스가 실행 중이어야 한다.

## 6. 반복 작업 예약: cron

```bash
crontab -e
crontab -l
```

```text
분 시 일 월 요일 명령
0 2 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1
```

cron은 사용자의 대화형 Shell보다 환경 변수가 적다. 명령과 파일은 절대 경로를 사용하고 출력과 오류를 로그로 남기는 것이 좋다.

시스템 단위 작업은 `/etc/crontab`, `/etc/cron.d/`, `/etc/cron.daily/` 등도 사용할 수 있다.

## 7. systemd timer

systemd timer는 서비스 Unit과 연결해 예약 작업을 실행한다. 의존성, 로그, 부팅 후 누락 작업 처리 등을 systemd 방식으로 관리할 수 있다.

```bash
systemctl list-timers
systemctl status logrotate.timer
```

프로세스 장애를 확인할 때는 무조건 종료부터 하지 않는다. 프로세스 상태, 로그, 자원 사용량과 연관 서비스를 먼저 확인하고, 조치 후 다시 상태와 로그를 확인해야 한다.
