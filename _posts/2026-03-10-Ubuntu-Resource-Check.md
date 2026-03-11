---
layout: single
title:  "Linux 서버 리소스 관리 / 모니터링 / LVM 실습"
categories: [Linux]
tags: [Linux]
toc: true
author_profile: true
---

## 실습해보기

- 실습 과정
  - VMware에 ubuntu 24.04 설치
  - IP 확인하기(`ifconfig`)
  - ssh 설치 확인 및 설치하기 
    - `sudo systemctl status ssh` / `sudo apt install openssh-server -y`
  - 방화벽 허용하기 (SSH 22번 포트 열기) 
    - `sudo ufw allow ssh`
  - 맥 터미널에서 ubuntu SSH 접속 
    - `ssh [사용자계정명]@[가상머신_IP주소]`

- `리소스 모니터링 도구 익히기`
  - `top`: 가장 기본적인 리소스 확인 도구
  - `htop`: top보다 훨씬 보기 편한 인터페이스 (설치 필요: sudo apt install htop)
  - `df -h`: 디스크 용량 확인
  - `free -m`: 메모리 사용량 확인
- `내가 할당한 자원 파악하기`
  - CPU 정보 확인
    - `nproc`: CPU 코어 수 확인
    - `lscpu`: 상세 정보 확인 (CPU 모델명, 아키텍처, L1/L2 캐시 용량 등)
  - 메모리 용량 확인
    - `free -h`: 사람이 읽기 편한 단위로 확인
  - 디스크 용량 확인
    - `lsblk`
    - `df -h`
  - 전체 확인
    - `htop`: 상단에 0[], 1[] -> CPU 코어별 사용량, Mem -> 메모리 사용량
- `실제 부하(Stress) 줘보기`
  - `sudo apt install stress`: stress 도구 설치
  - `stress --cpu 2 --timeout 30`: (코어 2개에 30초간 풀부하)
  - CPU 2개 사용률 100% 확인 가능!

![stress](/assets/images/stressTest.png)

- `vmstat` -> 시스템 전반적인 상태 (CPU, 메모리, 스왑, I/O, 프로세스 한눈에)
- `iostat` -> 디스크 I/O 상태 (디스크 읽기/쓰기 속도, 디스크 병목 찾을 때 사용)
- `netstat` -> 네트워크 연결 상태 (어떤 포트 열려있는지, 어떤 IP와 연결되어있는지)

```
서버 느려짐
    ↓
top → CPU/메모리 확인
    ↓
iostat → 디스크 병목 확인
    ↓
netstat → 네트워크 연결 과부하 확인
    ↓
vmstat → 전체적인 흐름 확인
```

- vmstat
- r -> 실행 대기중인 프로세스
- b -> I/O 대기중인 프로세스
- memory
  - swpd -> 스왑 사용량
  - free -> 여유 메모리
  - buff -> 버퍼 캐시
  - cache -> 페이지 캐시
- cpu
  - us -> 유저 프로세스 CPU 사용률
  - sy -> 시스템(커널) CPU 사용률
  - id -> idle 비율
  - wa -> I/O 대기
- 장애 상황이면?
  - wa 높으면 -> 디스크 병목
  - r 높으면 -> CPU 과부화
  - swpd 높으면 -> 메모리 부족으로 스왑 사용

```
ubuntu@ubuntu:~$ vmstat 1 5
procs -----------memory---------- ---swap-- -----io---- -system-- -------cpu-------
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st gu
 1  0      0 3491144  23896 296032    0    0   111    36   75    0  0  0 100  0  0  0
 0  0      0 3491144  23896 296032    0    0     0     0  245  192  0  1 99  0  0  0
 0  0      0 3491144  23896 296032    0    0     0     0  241  152  0  1 99  0  0  0
 0  0      0 3491144  23896 296032    0    0     0     0  112  102  0  0 100  0  0  0
 0  0      0 3491144  23896 296032    0    0     0     0   47   61  0  0 100  0  0  0
```

- iostat
- avg-cpu (평균 CPU 상태)
- tps -> 초당 I/O 요청 수
- kB_read/s -> 초당 읽기 속도
- kB_write/s -> 초당 쓰기 속도
- `dm-0, dm-1 -> device mapper -> LV들이 dm으로 표현됨`
- 장애 상황이면? 
  - %iowait 높으면 -> 디스크 병목
  - tps 높으면 -> I/O 요청 과부화
  - kB_read/s 높으면 -> 디스크 읽기 집중

```
ubuntu@ubuntu:~$ iostat
Linux 6.8.0-101-generic (ubuntu) 	03/11/2026 	_aarch64_	(2 CPU)

avg-cpu:  %user   %nice %system %iowait  %steal   %idle
           0.07    0.00    0.35    0.01    0.00   99.58

Device             tps    kB_read/s    kB_wrtn/s    kB_dscd/s    kB_read    kB_wrtn    kB_dscd
dm-0              3.11        78.30         8.05         0.00     257145      26452          0
dm-1              0.56         1.82        21.94         0.00       5986      72052          0
loop0             0.00         0.00         0.00         0.00         14          0          0
nvme0n1           2.30        84.77         8.09         0.00     278409      26569          0
nvme0n2           0.21         2.86         1.44         0.00       9378       4714          0
nvme0n3           0.22         3.84        20.80         0.00      12624      68306          0
sr0               0.02         0.64         0.00         0.00       2096          0          0
```

- netstat
  - netstat -tulnp
    - -t -> TCP
    - -u -> UDP 
    - -l -> 현재 listening 중인 포트만
    - -n -> 숫자로 표시 (도메인 대신 IP)
    - -p -> 프로세스 정보 표시 (PID, 프로그램 이름 / 어떤 프로세스가 이 포트 사용하는지)


```
ubuntu@ubuntu:~$ netstat -tuln
Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State      
tcp        0      0 127.0.0.53:53           0.0.0.0:*               LISTEN     
tcp        0      0 127.0.0.54:53           0.0.0.0:*               LISTEN     
tcp        0      0 0.0.0.0:22              0.0.0.0:*               LISTEN     
tcp6       0      0 :::22                   :::*                    LISTEN     
udp        0      0 127.0.0.54:53           0.0.0.0:*                          
udp        0      0 127.0.0.53:53           0.0.0.0:*                          
udp        0      0 192.168.29.141:68       0.0.0.0:*          
```

```
"이 서버 몇 번 포트 열려있어?"
→ netstat -tuln

"지금 어떤 IP랑 연결되어 있어?"
→ netstat -tn

"특정 포트 누가 쓰고 있어?"
→ netstat -tulnp | grep 8080
```

## LVM(Logical Volume Manager)이란? + 생성 / 확장 실습해보기

- `핵심 3단계 구조`
  - PV (Physical Volume): 실제 물리적인 하드디스크나 파티션이다. (/dev/sdb)
  - VG (Volume Group): PV들을 하나로 합친 커더란 자원 Pool이다.
  - LV (Logical Volume): VG에서 잘라낸 논리 디스크다.

```
물리 디스크 (PV)
    ↓
묶기 (VG)
    ↓
잘라쓰기 (LV)
    ↓
파일시스템 마운트
```


- `왜 사용할까?`
  - `유연한 용량 조절`: 서버를 끄지 않고도 디스크 용량을 늘릴 수 있다.
  - `여러 디스크 통합`: 10GB 디스크 2개를 합쳐서 하나의 20GB 디스크로(LV) 만들 . 있다.
  - `스냅샷`: 현재 디스크 상태를 그대로 복사해 저장할 수 있어 백업에 유리하다.

- 실습해보기
  - `서비스 중단 없는 확장을 위해`
  - 서버 용량이 꽉 차서 서비스 장애가 났을 때의 조치 -> LVM 구조 확인 후 여유 공간이 있다면 볼륨 확장하고, 없다면 EBS를 추가하여 VG를 확장한다.
  - 실습 순서 
  - 1.VMware에 가상 디스크 추가
  - 2.PV생성
  - 3.VG생성
  - 4.LV생성
  - 5.파일시스템 생성
  - 6.마운트
 
- `1. 가상 디스크 추가하기`
  - Virtual Machine -> Settings -> Add Device -> New Hard Disk Add(5GB)
  - `lsblk`로 디스크 추가 확인

```
NAME                      MAJ:MIN RM  SIZE RO TYPE MOUNTPOINTS
sr0                        11:0    1  2.8G  0 rom  
nvme0n1                   259:0    0   20G  0 disk 
├─nvme0n1p1               259:1    0  953M  0 part /boot/efi
├─nvme0n1p2               259:2    0  1.8G  0 part /boot
└─nvme0n1p3               259:3    0 17.3G  0 part 
  └─ubuntu--vg-ubuntu--lv 252:0    0   10G  0 lvm  /
nvme0n2                   259:4    0    5G  0 disk   --> 추가된 것 확인 가능
```

- `2. PV 생성`
  - `sudo pvcreate /dev/nvme0n2` -> 디스크를 LVM이 관리할 수 있는 PV로 초기화
  - `sudo pvs` -> 생성된 PV 확인

```
 sudo pvs
  PV             VG        Fmt  Attr PSize   PFree 
  /dev/nvme0n1p3 ubuntu-vg lvm2 a--  <17.32g <7.32g
  /dev/nvme0n2   my-vg     lvm2 a--   <5.00g <5.00g
```

- `3. VG 생성`
  - `sudo vgcreate my-vg /dev/nvme0n2` -> PV를 묶어서 Volume Group 생성
  - `sudo vgs` -> 생성된 VG 확인 (VFree: 남은 용량)

```
sudo vgs
  VG        #PV #LV #SN Attr   VSize   VFree 
  my-vg       1   0   0 wz--n-  <5.00g <5.00g
  ubuntu-vg   1   1   0 wz--n- <17.32g <7.32g

```

- `4. LV 생성`
  - `sudo lvcreate -L 4G -n my-lv my-vg` -> -L 4G (크기 4GB) / -n my-lv (이름 my-lv) / mv-vg (어떤 VG에서 LV 만들지)
  - `sudo lvs` -> 생성된 LV 확인

```
 sudo lvs
  LV        VG        Attr       LSize  Pool Origin Data%  Meta%  Move Log Cpy%Sync Convert
  my-lv     my-vg     -wi-a-----  4.00g                                                    
  ubuntu-lv ubuntu-vg -wi-ao---- 10.00g            
```

- `5. 파일 시스템 생성`
  - `sudo mkfs.ext4 /dev/my-vg/my-lv`
  - mkfs: make filesystem / .ext4: 파일 시스템 종류
  - LV를 파일을 저장할 수 있는 구조로 변경시키는 명령이다.(`LV 위에 파일 시스템을 구축`)

- `6. 마운트`
  - 만들어진 파일시스템에 접근할 수 있도록 경로를 설정해준다.
  - `sudo mkdir /mnt/mydata` 
  - /mnt: 마운트 전용 디렉터리
  - `ls /mnt` 를 통해 mydata 디렉터리 생성된 것 확인 가능
  - `mount /dev/my-vg/my-lv /mnt/mydata` -> 생성한 LV를 연결

- 리눅스 디렉터리 구조

```
/           → 루트
/home       → 사용자 홈 디렉토리 (ubuntu 같은 유저 파일)
/mnt        → 임시 마운트 용도 (외장 디스크, 추가 볼륨 등)
/media      → USB, CD 같은 이동식 미디어 마운트
/etc        → 설정 파일들
/var        → 로그, 데이터 파일들
```

- 확인해보기

```
df -h
Filesystem                         Size  Used Avail Use% Mounted on
tmpfs                              391M  1.3M  390M   1% /run
efivarfs                           256K   33K  224K  13% /sys/firmware/efi/efivars
/dev/mapper/ubuntu--vg-ubuntu--lv  9.8G  2.7G  6.7G  29% /
tmpfs                              2.0G     0  2.0G   0% /dev/shm
tmpfs                              5.0M     0  5.0M   0% /run/lock
/dev/nvme0n1p2                     1.7G  102M  1.5G   7% /boot
/dev/nvme0n1p1                     952M  6.4M  945M   1% /boot/efi
tmpfs                              391M   12K  391M   1% /run/user/1000
/dev/mapper/my--vg-my--lv          3.9G   24K  3.7G   1% /mnt/mydata  --> 마운트 성공 확인 가능
```

- 실습해보기
  - 서버 디스크가 꽉 차가고있음 -> LV 확장해서 용량 늘리기
  - `Case 1: VG에 여유 공간이 있을 때 추가 디스크 없이 바로 LV 확장 가능`
  - `Case 2: VG도 꽉 찼을 때 디스크 추가 -> PV 생성 -> VG 확장 -> LV 확장`

- `Case 1 실습`
  - `sudo vgs`명령으로 my-vg에 1GB 여유 공간 확인 완료
  - `sudo lvextend -L +900M /dev/my-vg/my-lv` (LV 확장)
  - `sudo resize2fs /dev/my-vg/my-lv` (파일 시스템 확장)
    - 파일 시스템 확장은 왜 필요할까?
    - LV -> 4.9GB But 파일 시스템 -> 3.9GB (예전 크기)
  

```
 sudo lvextend -L +1G /dev/my-vg/my-lv
  Insufficient free space: 256 extents needed, but only 255 available
  에러 발생 -> 900M로 줄여서 실행
```

```
sudo vgs
  VG        #PV #LV #SN Attr   VSize   VFree   
  my-vg       1   1   0 wz--n-  <5.00g 1020.00m
  ubuntu-vg   1   1   0 wz--n- <17.32g   <7.32g
-------------------------------------------------
sudo vgs
  VG        #PV #LV #SN Attr   VSize   VFree  
  my-vg       1   1   0 wz--n-  <5.00g 120.00m   -> 확인 가능
  ubuntu-vg   1   1   0 wz--n- <17.32g  <7.32g
  
-------------------------------------------------
df -h
Filesystem                         Size  Used Avail Use% Mounted on
tmpfs                              391M  1.3M  390M   1% /run
efivarfs                           256K   33K  224K  13% /sys/firmware/efi/efivars
/dev/mapper/ubuntu--vg-ubuntu--lv  9.8G  2.7G  6.7G  29% /
tmpfs                              2.0G     0  2.0G   0% /dev/shm
tmpfs                              5.0M     0  5.0M   0% /run/lock
/dev/nvme0n1p2                     1.7G  102M  1.5G   7% /boot
/dev/nvme0n1p1                     952M  6.4M  945M   1% /boot/efi
tmpfs                              391M   12K  391M   1% /run/user/1000
/dev/mapper/my--vg-my--lv          4.8G   24K  4.5G   1% /mnt/mydata          ----> 용량 늘어난 것 확인 가능
```


- **서버를 재부팅하면 마운트 사라진다** -> `/etc/fstab` 파일에 등록 -> 영구 마운트
  - `sudo nano /etc/fstab` -> 맨 아래줄에 추가 /dev

- `Case 2 실습`
  - 새 디스크 추가 -> PV 생성 -> VG 확장 -> LV 확장
  - `sudo pvcreate /dev/nvme0n3`
    - `sudo vgextend my-vg /dev/nvme0n3` (VG 확장)
    - `sudo lvextend +4G /dev/my-vg/my-lv` (LV 확장)
    - `sudo resize2fs /dev/my-vg/my-lv` (파일 시스템 확장)


```
sudo vgextend my-vg /dev/nvme0n3
  Volume group "my-vg" successfully extended
ubuntu@ubuntu:~$ sudo vgs
  VG        #PV #LV #SN Attr   VSize   VFree 
  my-vg       2   1   0 wz--n-   9.99g  5.11g   ---> 용량 확장 확인 가능
  ubuntu-vg   1   1   0 wz--n- <17.32g <7.32g
-----------------------------------------------
lsblk
NAME                      MAJ:MIN RM  SIZE RO TYPE MOUNTPOINTS
sr0                        11:0    1  2.8G  0 rom  
nvme0n1                   259:0    0   20G  0 disk 
├─nvme0n1p1               259:1    0  953M  0 part /boot/efi
├─nvme0n1p2               259:2    0  1.8G  0 part /boot
└─nvme0n1p3               259:3    0 17.3G  0 part 
  └─ubuntu--vg-ubuntu--lv 252:0    0   10G  0 lvm  /
nvme0n2                   259:4    0    5G  0 disk 
└─my--vg-my--lv           252:1    0  8.9G  0 lvm  /mnt/mydata
nvme0n3                   259:5    0    5G  0 disk 
└─my--vg-my--lv           252:1    0  8.9G  0 lvm  /mnt/mydata
```