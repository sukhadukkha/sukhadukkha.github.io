---
layout: single
title:  "현장실습 테스트 장비 사용해서 On-premise에 배포해보기"
categories: [현장실습]
tags: [Linux]
toc: true
author_profile: true
---


# 실습 목표

- 현재 웹앱이 Oracle Cloud Free Tier Instance에 떠있다. VM에는 Docker Compose로 앱이 실행 가능하게 하기 위한 종속성들을 다 넣어놓았고, Object Storage도 사용중인 상태
- 클라우드에 있는 웹앱은 그대로 내버려두고, 회사 VPN 내부에서도 접속이 되도록 회사 물리 서버 (Dell R750)에서 웹앱 배포하고, 앱애 올린 사진 및 데이터들이 Unity 스토리지에 저장되게 만드는 것.
- 운영체제 : RHEL 8.10
- 아키텍쳐는 다음과 같다. 

```
현재 OCI
브라우저 → Nginx → Spring Boot → OCI Object Storage (사진·영상)
                         └────→ MySQL → Docker 볼륨

목표 온프레미스
브라우저 → VPN → R750의 Nginx → Spring Boot → 사진 및 영상은 Unity의 NFS File System
                                      └────→ MySQL → Unity의 Block Storage
```


```
서버 -> 스위치 -> Unity 
```

## VPN (192.168.1.xxx 대역) WireGuard

## 서버 및 스토리지 사양

### 물리 서버 사양

| 구분 | 사양 |
|---|---|
| 서버 | Dell PowerEdge R750 |
| 운영체제 | Red Hat Enterprise Linux 8.10 (Ootpa) |
| 커널 | `4.18.0-553.124.1.el8_10.x86_64` |
| 아키텍처 | `x86_64` |
| CPU | Intel Xeon Gold 6330 2.00GHz × 2 |
| CPU 코어 | 소켓당 28코어, 총 56 물리 코어 |
| 메모리 | 128GB, Multi-bit ECC |
| RAID 컨트롤러 | Dell PERC H745 Front |
| 부팅 장치 | Dell BOSS Virtual Disk 447.1GiB |
| 로컬 디스크 | PERC Virtual Disk 558.4GiB, 1.8TiB |
| 1GbE NIC | Broadcom NetXtreme BCM5720 |
| 고속 NIC | Broadcom BCM57504 4포트 25GbE SFP28 |
| FC HBA | QLogic QLE2562 Dual Channel 8Gb FC × 2 |

### 외장 스토리지 구성

| 구분 | 구성 |
|---|---|
| 스토리지 | Dell EMC Unity 380F |
| 연결 방식 | 8Gb Fibre Channel |
| FC 구성 | QLogic HBA 2개와 단일 FC 스위치 사용 |
| 조닝 | HBA 1 → Unity SPA0, HBA 2 → Unity SPB0 |
| 할당 LUN | 100GiB |
| Multipath | Device Mapper Multipath, ALUA |
| Multipath Alias | `story` |
| Volume Group | `vg_story` |
| MySQL LV | 20GiB XFS, `/srv/story/mysql` |
| Media LV | 60GiB XFS, `/srv/story/media` |

### 애플리케이션 실행 환경

| 구분 | 구성 |
|---|---|
| 컨테이너 런타임 | Podman 4.9.4 |
| 컨테이너 구성 | MySQL 8.0, Spring Boot, Nginx |
| Compose | Docker Compose v5.5.1을 Podman Provider로 사용 |
| 자동 실행 | systemd 서비스 |
| 데이터 저장 | Unity FC LUN 기반 XFS |
| 백업 | Dell NetWorker 19.10.0.4 |
| 백업 저장소 | Dell Data Domain |
| 복구 검증 | 파일 SHA-256 비교 및 MySQL 별도 DB 복원 |




- 스토리지 사양

```
Dell EMC Unity 380F All-Flash Storage
실습 스토리지는 2U DPE 기반의 Dell EMC Unity 380F All-Flash Array로, 25개의 2.5인치 드라이브 슬롯 중 12개의 SAS Flash SSD가 장착되어 있었다. 각 SSD의 표시 용량은 733.5GiB로 전체 Raw 용량은 약 8.60TiB였다.
Pool0는 SSD 12개를 이용한 RAID 5, 8+1 Stripe Width로 구성되어 있었으며 실제 Pool 사용 가능 용량은 5.7TiB였다. 확인 시점 기준 2.6TiB가 사용 중이고 2.8TiB가 남아 있었다. R750 애플리케이션용 Thin LUN을 생성하고 FC SAN을 통해 RHEL에 제공하여 MySQL 및 사진·동영상의 영구 저장소로 활용하였다.
```

| 항목 | 구성 |
|---|---|
| Storage | Dell EMC Unity 380F |
| Storage Type | All-Flash Array |
| Enclosure | 2U, 25 × 2.5인치 DPE |
| Installed Drives | SAS Flash SSD 12개 |
| Drive Capacity | 733.5GiB |
| Raw Capacity | 약 8.60TiB |
| Pool | Pool0 |
| RAID | RAID 5 |
| Stripe Width | 8+1 |
| Pool Usable Capacity | 5.7TiB |
| Pool Used | 2.6TiB |
| Pool Free | 2.8TiB |
| Pool Utilization | 약 46% |
| Hot Spare | Distributed Spare Capacity 1/32 |
| Storage Processor | Dual SP, SPA·SPB |
| Front-End Protocol | Fibre Channel |
| FC Port | SP당 4개, SPA0·SPB0 사용 |
| FC Link Speed | 8Gbps |
| Unity OE | 5.5.2.0.5.014 |

---

## Step 1. 실습 전 상황
- 스위치와 테스트 서버(R750) 연결 안되어있어서 IP 할당 못받고 있었음
  - `스위치에 꽂혀있는 케이블을 서버의 NIC 포트에 꼽으니 DHCP로 연결완료`
- MAC 터미널에서 SSH 접속 성공
- SAN Switch는 Brocade 6505 모델
- Storage는 Dell Unity (192.168.1.xxx)


![SSH 접속](/assets/images/SSHConnection.png)

```
[root@TK_TEST ~]# nmcli device status
DEVICE     TYPE      STATE          CONNECTION 
eno8303    ethernet  연결됨         eno8303    
virbr0     bridge    연결됨 (외부)  virbr0     
idrac      ethernet  연결됨         idrac      
eno12399   ethernet  연결 끊겼음    --         
eno12409   ethernet  연결 끊겼음    --         
eno12419   ethernet  연결 끊겼음    --         
eno12429   ethernet  연결 끊겼음    --         
eno8403    ethernet  연결 끊겼음    --         
ens7f0np0  ethernet  연결 끊겼음    --         
ens7f1np1  ethernet  연결 끊겼음    --         
ens7f2np2  ethernet  연결 끊겼음    --         
ens7f3np3  ethernet  연결 끊겼음    --         
lo         loopback  관리되지 않음  --
         
[root@TK_TEST ~]# ip -br addr
lo               UNKNOWN        127.0.0.1/8 
eno8303          UP             192.168.1.xxx/24 
ens7f0np0        DOWN           
ens7f1np1        DOWN           
ens7f2np2        DOWN           
ens7f3np3        DOWN           
eno8403          DOWN           
eno12399         DOWN           
eno12409         DOWN           
eno12419         DOWN           
eno12429         DOWN           
idrac            UNKNOWN        169.254.1.2/24 
virbr0           DOWN           192.168.122.1/24
 
[root@TK_TEST ~]# ip route
default via 192.168.1.xxx dev eno8303 proto dhcp src 192.168.1.xxx metric 101 
169.254.1.0/24 dev idrac proto kernel scope link src 169.254.1.2 metric 100 
192.168.1.0/24 dev eno8303 proto kernel scope link src 192.168.1.xxx metric 101 
192.168.122.0/24 dev virbr0 proto kernel scope link src 192.168.122.1 linkdown 
[root@TK_TEST ~]# 
```

![서버구조](/assets/images/OnpremServer.png)

- 이는 서버 뒷면 포트들 모습이다.
- 현재 IP는 DHCP로 192.168.1.xxx/24 로 할당받있고, Gateway는 192.168.1.xxx다.

- 현재 Oracle Cloud에 떠있는 웹 서버 아키텍처
  - 이걸 OnPrem에 맞게 코드를 수정한 뒤, 회사 Test Server에 배포해볼 것이다.






## 현재 서버 상태 및 해야 할 작업들 

```
[root@TK_TEST ~]# lsblk
NAME             MAJ:MIN RM   SIZE RO TYPE MOUNTPOINT
sda                8:0    0 558.4G  0 disk 
sdb                8:16   0   1.8T  0 disk 
sdc                8:32   0 447.1G  0 disk 
├─sdc1             8:33   0   600M  0 part /boot/efi
├─sdc2             8:34   0     1G  0 part /boot
└─sdc3             8:35   0 445.5G  0 part 
  ├─vg00-lv_root 253:0    0 429.5G  0 lvm  /
  └─vg00-lv_swap 253:1    0    16G  0 lvm  [SWAP]
  
[root@TK_TEST ~]# 
```

- sda, sdb가 어떤 디스크인지 , 로컬 Disk인지 Unity의 LUN인지 확인
  - `lsblk -d -o NAME,SIZE,VENDOR,MODEL,TRAN`

```
[root@TK_TEST ~]# lsblk -d -o NAME,SIZE,VENDOR,MODEL,TRAN
NAME   SIZE VENDOR   MODEL            TRAN
sda  558.4G DELL     PERC H745 Frnt   
sdb    1.8T DELL     PERC H745 Frnt   
sdc  447.1G ATA      DELLBOSS VD      sata
[root@TK_TEST ~]# 
```

- sda, sdb -> Dell PERC H745가 제공하는 서버 내부 디스크
- sdc -> BOSS 디스크 -> RHEL이 설치된 디스크 확인 가능

- LAN 연결 성공, IP 할당 확인 완료
- R750 FC 포트 -> FC 스위치 -> Unity 케이블 연결(x)
- 스토리지 설정 확인 -> FC 스위치 조닝 + Unity의 LUN 할당
  - 현재 FC 케이블 및 조닝 되어있지 않음. 상태 확인 후 조닝 필요


## Step 2. FC 케이블 경로 확인 및 연결

- 장비 및 포트 확인 
  1. R750의 FC 카드 포트, FC 스위치 빈 포트, Unity의 FC 포트 각각 확인 필요
  2. `FC 광케이블 연결 (R750 FC 포트 -> FC 스위치 -> Unity FC 포트)`
  3. 조닝 -> FC 스위치에서 R750과 Unity 서로 통신 허용
  4. Unity에서 전용 실습 LUN 할당
  5. RHEL에서 확인

## Step 3. FC 케이블 연결 구조 정리 및 조닝 및 cfg 변경

- 구조
- SAN 스위치 (192.168.1.xxx 접속)

![케이블연결구조](/assets/images/Onprem구조.png)

- 스위치 상태 확인 (포트, 조닝, cfgshow, switchshow)

```
TEST_SAN:admin> cfgshow
Defined configuration:
 cfg:	TEST_CFG	EXISTING_ZONE_1; EXISTING_ZONE_2; zone1; zone2; 
		zone3; zone4
 zone:	EXISTING_ZONE_1	
		EXISTING_HOST_P0; EXISTING_STORAGE_P1
 zone:	EXISTING_ZONE_2	
		EXISTING_HOST_P2; EXISTING_STORAGE_P1
 zone:	zone1	TEST_s3p2_P8; SPA
 zone:	zone2	TEST_s3p2_P8; SPB
 zone:	zone3	TEST_s6p2_P9; SPA
 zone:	zone4	TEST_s6p2_P9; SPB
 alias:	EXISTING_STORAGE_P1	
		1,1
 alias:	EXISTING_HOST_P0	
		1,0
 alias:	EXISTING_HOST_P2	
		1,2
 alias:	SPA	xx:xx:xx:xx:xx:xx:xx:03
 alias:	SPB	xx:xx:xx:xx:xx:xx:xx:04
 alias:	TEST_s3p2_P8	
		xx:xx:xx:xx:xx:xx:xx:01
 alias:	TEST_s6p2_P9	
		xx:xx:xx:xx:xx:xx:xx:02

Effective configuration:
 cfg:	TEST_CFG	
 zone:	EXISTING_ZONE_1	
		1,0
		1,1
 zone:	EXISTING_ZONE_2	
		1,2
		1,1
 zone:	zone1	xx:xx:xx:xx:xx:xx:xx:01
		xx:xx:xx:xx:xx:xx:xx:03
 zone:	zone2	xx:xx:xx:xx:xx:xx:xx:01
		xx:xx:xx:xx:xx:xx:xx:04
 zone:	zone3	xx:xx:xx:xx:xx:xx:xx:02
		xx:xx:xx:xx:xx:xx:xx:03
 zone:	zone4	xx:xx:xx:xx:xx:xx:xx:02
		xx:xx:xx:xx:xx:xx:xx:04
		
		
TEST_SAN:admin> switchshow
switchName:	TEST_SAN
switchType:	118.1
switchState:	Online   
switchMode:	Native
switchRole:	Principal
switchDomain:	1
switchId:	fffc01
switchWwn:	xx:xx:xx:xx:xx:xx:xx:05
zoning:		ON (TEST_CFG)
switchBeacon:	OFF

Index Port Address Media Speed       State   Proto
==================================================
   0   0   010000   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:06 
   1   1   010100   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:07 
   2   2   010200   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:08 
   3   3   010300   id    N8	   No_Light    FC  
   4   4   010400   id    N8	   No_Light    FC  
   5   5   010500   id    N8	   No_Light    FC  
   6   6   010600   id    N8	   No_Light    FC  
   7   7   010700   id    N8	   No_Light    FC  
   8   8   010800   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:01 
   9   9   010900   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:02 
  10  10   010a00   id    N8	   No_Light    FC  
  11  11   010b00   id    N8	   No_Light    FC  
  12  12   010c00   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:03 
  13  13   010d00   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:04 
  14  14   010e00   id    N8	   No_Light    FC  
  15  15   010f00   id    N8	   No_Light    FC  
  16  16   011000   id    N8	   No_Light    FC  
  17  17   011100   id    N8	   No_Light    FC  
  18  18   011200   id    N8	   No_Light    FC  
  19  19   011300   id    N8	   No_Light    FC  
  20  20   011400   id    N8	   No_Light    FC  
  21  21   011500   id    N8	   No_Light    FC  
  22  22   011600   id    N8	   No_Light    FC  
  23  23   011700   id    N8	   No_Light    FC 
```

- `현재 물리 포트 기준 조닝 상태`
  - zone1 : 서버 포트 8  ↔ Unity SPA 포트 12
  - zone2 : 서버 포트 8  ↔ Unity SPB 포트 13
  - zone3 : 서버 포트 9  ↔ Unity SPA 포트 12
  - zone4 : 서버 포트 9  ↔ Unity SPB 포트 13

| 스위치 포트 | 연결 장비 | WWPN | 상태 |
|---|---|---|---|
| 8 | R750 HBA 포트 1 | `xx:xx:xx:xx:xx:xx:xx:01` | Online, F-Port, 8Gb |
| 9 | R750 HBA 포트 2 | `xx:xx:xx:xx:xx:xx:xx:02` | Online, F-Port, 8Gb |
| 12 | Unity SPA 포트 0 | `xx:xx:xx:xx:xx:xx:xx:03` | Online, F-Port, 8Gb |
| 13 | Unity SPB 포트 0 | `xx:xx:xx:xx:xx:xx:xx:04` | Online, F-Port, 8Gb |

- 현재 상태는 HBA와 Storage의 1:2 WWN 조닝 관계다.
- 이걸 우선 1:1 WWN 조닝으로 변경
- HBA 포트별 접근 Target을 하나로 제한하기 위해 1:1 WWN 조닝으로 변경해보기
- 왜?
  - HBA1 -> SPA
  - HBA2 -> SPB

- 스위치 명령어

```

1. config에서 zone1~4 삭제 (cfgremove "TEST_CFG", "zone1;zone2;zone3;zone4")

TEST_SAN:admin> cfgremove "TEST_CFG", "zone1;zone2;zone3;zone4"
TEST_SAN:admin> cfgshow
Defined configuration:
 cfg:	TEST_CFG	EXISTING_ZONE_1; EXISTING_ZONE_2
 
-> zone1~4 cfg에서 빠진 것 확인 가능

2. 기존 Zone 삭제 (zonedelete)

TEST_SAN:admin> zonedelete "zone1"
TEST_SAN:admin> zonedelete "zone2"
TEST_SAN:admin> zonedelete "zone3"
TEST_SAN:admin> zonedelete "zone4"
TEST_SAN:admin> cfgshow
Defined configuration:
 cfg:	TEST_CFG	EXISTING_ZONE_1; EXISTING_ZONE_2
 zone:	EXISTING_ZONE_1	
		EXISTING_HOST_P0; EXISTING_STORAGE_P1
 zone:	EXISTING_ZONE_2	
		EXISTING_HOST_P2; EXISTING_STORAGE_P1
 alias:	EXISTING_STORAGE_P1	
		1,1
 alias:	EXISTING_HOST_P0	
		1,0
 alias:	EXISTING_HOST_P2	
		1,2
 alias:	SPA	xx:xx:xx:xx:xx:xx:xx:03
 alias:	SPB	xx:xx:xx:xx:xx:xx:xx:04
 alias:	TEST_s3p2_P8	
		xx:xx:xx:xx:xx:xx:xx:01
 alias:	TEST_s6p2_P9	
		xx:xx:xx:xx:xx:xx:xx:02

Effective configuration:
 cfg:	TEST_CFG	
 zone:	EXISTING_ZONE_1	
		1,0
		1,1
 zone:	EXISTING_ZONE_2	
		1,2
		1,1
 zone:	zone1	xx:xx:xx:xx:xx:xx:xx:01
		xx:xx:xx:xx:xx:xx:xx:03
 zone:	zone2	xx:xx:xx:xx:xx:xx:xx:01
		xx:xx:xx:xx:xx:xx:xx:04
 zone:	zone3	xx:xx:xx:xx:xx:xx:xx:02
		xx:xx:xx:xx:xx:xx:xx:03
 zone:	zone4	xx:xx:xx:xx:xx:xx:xx:02
		xx:xx:xx:xx:xx:xx:xx:04 
		
-> zone 1~4 삭제 확인 가능

3. Alias 삭제 (alidelete)

TEST_SAN:admin> alidelete "TEST_s3p2_P8"
TEST_SAN:admin> alidelete "TEST_s6p2_P9"
TEST_SAN:admin> alidelete "SPA"
TEST_SAN:admin> alidelete "SPB"
TEST_SAN:admin> cfgshow
Defined configuration:
 cfg:	TEST_CFG	EXISTING_ZONE_1; EXISTING_ZONE_2
 zone:	EXISTING_ZONE_1	
		EXISTING_HOST_P0; EXISTING_STORAGE_P1
 zone:	EXISTING_ZONE_2	
		EXISTING_HOST_P2; EXISTING_STORAGE_P1
 alias:	EXISTING_STORAGE_P1	
		1,1
 alias:	EXISTING_HOST_P0	
		1,0
 alias:	EXISTING_HOST_P2	
		1,2

Effective configuration:
 cfg:	TEST_CFG	
 zone:	EXISTING_ZONE_1	
		1,0
		1,1
 zone:	EXISTING_ZONE_2	
		1,2
		1,1
 zone:	zone1	xx:xx:xx:xx:xx:xx:xx:01
		xx:xx:xx:xx:xx:xx:xx:03
 zone:	zone2	xx:xx:xx:xx:xx:xx:xx:01
		xx:xx:xx:xx:xx:xx:xx:04
 zone:	zone3	xx:xx:xx:xx:xx:xx:xx:02
		xx:xx:xx:xx:xx:xx:xx:03
 zone:	zone4	xx:xx:xx:xx:xx:xx:xx:02
		xx:xx:xx:xx:xx:xx:xx:04

-> alias 삭제 확인 가능

4. 새 Alias 생성

TEST_SAN:admin> alicreate "TEST_HBA1", "xx:xx:xx:xx:xx:xx:xx:01"
TEST_SAN:admin> alicreate "TEST_HBA2", "xx:xx:xx:xx:xx:xx:xx:02"
TEST_SAN:admin> alicreate "UNITY_SPA0", "xx:xx:xx:xx:xx:xx:xx:03"
TEST_SAN:admin> alicreate "UNITY_SPB0", "xx:xx:xx:xx:xx:xx:xx:04"
TEST_SAN:admin> alishow
Defined configuration:
 cfg:	TEST_CFG	EXISTING_ZONE_1; EXISTING_ZONE_2
 zone:	EXISTING_ZONE_1	
		EXISTING_HOST_P0; EXISTING_STORAGE_P1
 zone:	EXISTING_ZONE_2	
		EXISTING_HOST_P2; EXISTING_STORAGE_P1
 alias:	EXISTING_STORAGE_P1	
		1,1
 alias:	EXISTING_HOST_P0	
		1,0
 alias:	EXISTING_HOST_P2	
		1,2
 alias:	TEST_HBA1	
		xx:xx:xx:xx:xx:xx:xx:01
 alias:	TEST_HBA2	
		xx:xx:xx:xx:xx:xx:xx:02
 alias:	UNITY_SPA0	
		xx:xx:xx:xx:xx:xx:xx:03
 alias:	UNITY_SPB0	
		xx:xx:xx:xx:xx:xx:xx:04

Effective configuration:
 cfg:	TEST_CFG	
 zone:	EXISTING_ZONE_1	
		1,0
		1,1
 zone:	EXISTING_ZONE_2	
		1,2
		1,1
 zone:	zone1	xx:xx:xx:xx:xx:xx:xx:01
		xx:xx:xx:xx:xx:xx:xx:03
 zone:	zone2	xx:xx:xx:xx:xx:xx:xx:01
		xx:xx:xx:xx:xx:xx:xx:04
 zone:	zone3	xx:xx:xx:xx:xx:xx:xx:02
		xx:xx:xx:xx:xx:xx:xx:03
 zone:	zone4	xx:xx:xx:xx:xx:xx:xx:02
		xx:xx:xx:xx:xx:xx:xx:04
		
-> 새 alias 생성 확인 가능(TEST_HBA1, TEST_HBA2, UNITY_SPA0, UNITY_SPB0)

5. 1:1 Zone 2개 생성 (zone create)

TEST_SAN:admin> zonecreate "Z_TEST_HBA1_UNITY_SPA0", "TEST_HBA1;UNITY_SPA0"
TEST_SAN:admin> zonecreate "Z_TEST_HBA2_UNITY_SPB0", "TEST_HBA2;UNITY_SPB0"
TEST_SAN:admin> zoneshow
Defined configuration:
 cfg:	TEST_CFG	EXISTING_ZONE_1; EXISTING_ZONE_2
 zone:	EXISTING_ZONE_1	
		EXISTING_HOST_P0; EXISTING_STORAGE_P1
 zone:	EXISTING_ZONE_2	
		EXISTING_HOST_P2; EXISTING_STORAGE_P1
 zone:	Z_TEST_HBA1_UNITY_SPA0	
		TEST_HBA1; UNITY_SPA0
 zone:	Z_TEST_HBA2_UNITY_SPB0	
		TEST_HBA2; UNITY_SPB0
 alias:	EXISTING_STORAGE_P1	
		1,1
 alias:	EXISTING_HOST_P0	
		1,0
 alias:	EXISTING_HOST_P2	
		1,2
 alias:	TEST_HBA1	
		xx:xx:xx:xx:xx:xx:xx:01
 alias:	TEST_HBA2	
		xx:xx:xx:xx:xx:xx:xx:02
 alias:	UNITY_SPA0	
		xx:xx:xx:xx:xx:xx:xx:03
 alias:	UNITY_SPB0	
		xx:xx:xx:xx:xx:xx:xx:04

Effective configuration:
 cfg:	TEST_CFG	
 zone:	EXISTING_ZONE_1	
		1,0
		1,1
 zone:	EXISTING_ZONE_2	
		1,2
		1,1
 zone:	zone1	xx:xx:xx:xx:xx:xx:xx:01
		xx:xx:xx:xx:xx:xx:xx:03
 zone:	zone2	xx:xx:xx:xx:xx:xx:xx:01
		xx:xx:xx:xx:xx:xx:xx:04
 zone:	zone3	xx:xx:xx:xx:xx:xx:xx:02
		xx:xx:xx:xx:xx:xx:xx:03
 zone:	zone4	xx:xx:xx:xx:xx:xx:xx:02
		xx:xx:xx:xx:xx:xx:xx:04
		
-> zone 생성 확인 가능

6. 기존 TEST_CFG Config에 새 Zone 추가 (cfgadd)

TEST_SAN:admin> cfgadd "TEST_CFG", "Z_TEST_HBA1_UNITY_SPA0;Z_TEST_HBA2_UNITY_SPB0"
TEST_SAN:admin> cfgshow
Defined configuration:
 cfg:	TEST_CFG	EXISTING_ZONE_1; EXISTING_ZONE_2; 
		Z_TEST_HBA1_UNITY_SPA0; Z_TEST_HBA2_UNITY_SPB0
 zone:	EXISTING_ZONE_1	
		EXISTING_HOST_P0; EXISTING_STORAGE_P1
 zone:	EXISTING_ZONE_2	
		EXISTING_HOST_P2; EXISTING_STORAGE_P1
 zone:	Z_TEST_HBA1_UNITY_SPA0	
		TEST_HBA1; UNITY_SPA0
 zone:	Z_TEST_HBA2_UNITY_SPB0	
		TEST_HBA2; UNITY_SPB0
 alias:	EXISTING_STORAGE_P1	
		1,1
 alias:	EXISTING_HOST_P0	
		1,0
 alias:	EXISTING_HOST_P2	
		1,2
 alias:	TEST_HBA1	
		xx:xx:xx:xx:xx:xx:xx:01
 alias:	TEST_HBA2	
		xx:xx:xx:xx:xx:xx:xx:02
 alias:	UNITY_SPA0	
		xx:xx:xx:xx:xx:xx:xx:03
 alias:	UNITY_SPB0	
		xx:xx:xx:xx:xx:xx:xx:04

Effective configuration:
 cfg:	TEST_CFG	
 zone:	EXISTING_ZONE_1	
		1,0
		1,1
 zone:	EXISTING_ZONE_2	
		1,2
		1,1
 zone:	zone1	xx:xx:xx:xx:xx:xx:xx:01
		xx:xx:xx:xx:xx:xx:xx:03
 zone:	zone2	xx:xx:xx:xx:xx:xx:xx:01
		xx:xx:xx:xx:xx:xx:xx:04
 zone:	zone3	xx:xx:xx:xx:xx:xx:xx:02
		xx:xx:xx:xx:xx:xx:xx:03
 zone:	zone4	xx:xx:xx:xx:xx:xx:xx:02
		xx:xx:xx:xx:xx:xx:xx:04
		
-> TEST_CFG cfg에 새로 만든 zone 추가된 것 확인 가능

7. 새 cfg 활성화 및 저장

cfgenable
cfgsave
```

- 구성 완료 화면

![cfgshow](/assets/images/cfgshow.png)
![switchshow](/assets/images/switchshow.png)


| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| 서버 HBA | 2개 | 2개 |
| Unity Target | SPA0, SPB0 | SPA0, SPB0 |
| 테스트 Zone | 4개 | 2개 |
| HBA1 접근 Target | SPA0, SPB0 | SPA0 |
| HBA2 접근 Target | SPA0, SPB0 | SPB0 |
| Zone 구성 | Initiator 1 + Target 1 | Initiator 1 + Target 1 |
| 예상 LUN 경로 | 최대 4개 | 최대 2개 |
| 물리 Fabric | 단일 스위치 | 단일 스위치 |

## Step 4. Unity에서 Host 생성 + Initiator 등록 + LUN 생성 및 할당 

- Unity 상태 사진들

![프론트사진](/assets/images/EnclosuresFront.png)

![Pool](/assets/images/Pool0.png)

![raid 구성](/assets/images/Raid구성.png)


- FC 스위치 조닝 적용 뒤 서버의 HBA initiator 두개 검색 확인

![initiator](/assets/images/initiator.png)

- Host 생성 시 Initiator 설정

![HostInitiator 설정](/assets/images/HostInitiator설정.png)

- Host 생성 완료

```
R750 서버의 운영체제를 Linux로 지정하고, FC HBA 포트 두 개의 WWPN을 단일 Unity Host 객체에 등록하여 다중 경로 구성을 준비했다.
```

![Host 생성완료](/assets/images/Host생성완료.png)

- LUN 생성

![LUN 생성1](/assets/images/LUNcreate.png)

![LUN 생성2](/assets/images/LUN생성2.png)

![LUN 생성3](/assets/images/LUN생성3.png)

![LUN 생성4](/assets/images/LUN생성4.png)

```
Unity에서 100 GiB Thin LUN을 생성하고 Linux Host에 HLU 0으로 매핑했다. LUN에 부여된 고유 WWID를 기준으로 RHEL Multipath가 서로 다른 FC 경로를 동일한 논리 디스크로 식별하도록 구성했다.
```


## Step 5. RHEL LUN 재검색 + Multipath 확인

- 서버 접속 및 multipath 설치 확인
  - rpm -q device-mapper-multipath

- 설치 확인 완료 및 활성화
  - mpathconf --enable
  - systemctl enable --now multipathd

- 이미 존재하고 있었던 /etc/multipath.conf 있었다.
- LUN까지 할당했으니 rescan-scsi-bus.sh -a 명령으로 scsi 장비 리스캔
  - 문제 발생
    - FC 조닝은 완료됐지만, 당시 HOST에 실제 LUN이 할당되지 않아 Unity가 LUNZ라는 임시 장치 제공 중
    - 이후 HLU 0으로 실제 LUN 할당했지만, RHEL 커널에는 기존 LUNZ 장치 정보가 남아있었음. 
  - 해결
    - Dell에서도 LUNZ를 실제 HLU 0 LUN으로 교체할 때 제거를 포함한 재검색 필요할 수 있다고 설명한다.
    - `rescan-scsi-bus.sh -a -r`
      - -a : 기존 대상뿐 아닌 모든 SCSI Target과 LUN 검색
      - -r : 사라지거나 변경된 SCSI 장치를 제거
    - `udevadm settle`
      - 커널이 발견한 장치를 udev가 처리한다. /dev/sdd, /dev/sde 같은 장치 파일을 생성할 때 까지 기다린다.
    - `multipath -r` 
      - multipath 설정과 장치 지도를 다시 읽는다. 

### Unity FC LUN 인식 문제 해결

FC 조닝 및 Unity Host/LUN 매핑 후 RHEL에서 LUN을 재검색했으나, 실제 블록 장치와 Multipath 장치가 생성되지 않는 문제가 발생했다.

재검색 결과 Unity의 실제 LUN 대신, Host에 사용할 수 있는 LUN이 없을 때 제공되는 임시 장치인 `DGC LUNZ` 정보가 RHEL에 남아 있음을 확인했다. Unity에서는 실제 LUN을 HLU 0으로 정상 매핑했지만 기존 LUNZ 장치가 커널에 유지되고 있었다.

`rescan-scsi-bus.sh -a -r`을 사용해 기존 LUNZ 경로를 제거하고 SCSI Bus 전체를 다시 검색했다. 이후 udev 장치 처리를 완료하고 Multipath 구성을 다시 읽어 실제 `DGC VRAID` 장치를 인식시켰다.

검증 결과 동일한 WWID를 가진 두 개의 FC 경로가 발견됐으며, DM Multipath가 두 경로를 하나의 100G 논리 장치로 통합했다. ALUA 우선순위에 따라 최적 경로는 prio 50, 비최적 경로는 prio 10으로 구성됐으며 두 경로 모두 `active ready running` 상태임을 확인했다.


```
[root@TK_TEST ~]# rescan-scsi-bus.sh -a
Scanning SCSI subsystem for new devices
Scanning host 0 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
 Scanning for device 0 2 0 0 ... 
OLD: Host: scsi0 Channel: 02 Id: 00 Lun: 00
      Vendor: DELL     Model: PERC H745 Frnt   Rev: 5.16
      Type:   Direct-Access                    ANSI SCSI revision: 05
 Scanning for device 0 2 1 0 ... 
OLD: Host: scsi0 Channel: 02 Id: 01 Lun: 00
      Vendor: DELL     Model: PERC H745 Frnt   Rev: 5.16
      Type:   Direct-Access                    ANSI SCSI revision: 05
Scanning host 1 for  all SCSI target IDs, all LUNs
sg6 changed:  device 1 0 1 0 ... 
from:scsi1 Channel: 00 Id: 01 Lun: 00un: 00
  Vendor: DGC      Model: LUNZ             Rev: 54005400
  Type:   Direct-Access                    ANSI SCSI revision: 06  06
to:   Vendor: DGC      Model: VRAID            Rev: 5400  



Scanning host 2 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 3 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 4 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 5 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 6 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 7 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 8 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 9 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 10 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 11 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 12 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
 Scanning for device 12 0 0 0 ... 
OLD: Host: scsi12 Channel: 00 Id: 00 Lun: 00
      Vendor: ATA      Model: DELLBOSS VD      Rev: 00-0
      Type:   Direct-Access                    ANSI SCSI revision: 05
Scanning host 13 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 14 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
 Scanning for device 14 0 0 0 ... 
OLD: Host: scsi14 Channel: 00 Id: 00 Lun: 00
      Vendor: Marvell  Model: Console          Rev: 1.01
      Type:   Processor                        ANSI SCSI revision: 05
Scanning host 15 for  all SCSI target IDs, all LUNs
Scanning host 16 for  all SCSI target IDs, all LUNs
Scanning host 17 for  all SCSI target IDs, all LUNs
sg4 changed:  device 17 0 1 0 ... 
from:scsi17 Channel: 00 Id: 01 Lun: 00un: 00
  Vendor: DGC      Model: LUNZ             Rev: 54005400
  Type:   Direct-Access                    ANSI SCSI revision: 06  06
to:   Vendor: DGC      Model: VRAID            Rev: 5400  



0 new or changed device(s) found.          
0 remapped or resized device(s) found.
0 device(s) removed.                 
[root@TK_TEST ~]# lsblk
NAME             MAJ:MIN RM   SIZE RO TYPE MOUNTPOINT
sda                8:0    0 558.4G  0 disk 
sdb                8:16   0   1.8T  0 disk 
sdc                8:32   0 447.1G  0 disk 
├─sdc1             8:33   0   600M  0 part /boot/efi
├─sdc2             8:34   0     1G  0 part /boot
└─sdc3             8:35   0 445.5G  0 part 
  ├─vg00-lv_root 253:0    0 429.5G  0 lvm  /
  └─vg00-lv_swap 253:1    0    16G  0 lvm  [SWAP]
[root@TK_TEST ~]# multipath -ll
[root@TK_TEST ~]# systemctl is-active multi
multi-user.target   multipathd.service  multipathd.socket   
[root@TK_TEST ~]# systemctl is-active multi
multi-user.target   multipathd.service  multipathd.socket   
[root@TK_TEST ~]# systemctl is-active multi
multi-user.target   multipathd.service  multipathd.socket   
[root@TK_TEST ~]# systemctl is-active multipathd.
inactive
[root@TK_TEST ~]# systemctl is-active multipathd
active
[root@TK_TEST ~]# udevadm settle
[root@TK_TEST ~]# multipath -r
[root@TK_TEST ~]# multipath -ll
```


```
[root@TK_TEST ~]# rescan-scsi-bus.sh -a -r
Syncing file systems
Scanning SCSI subsystem for new devices and remove devices that have disappeared
Scanning host 0 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
 Scanning for device 0 2 0 0 ... 
OLD: Host: scsi0 Channel: 02 Id: 00 Lun: 00
      Vendor: DELL     Model: PERC H745 Frnt   Rev: 5.16
      Type:   Direct-Access                    ANSI SCSI revision: 05
 Scanning for device 0 2 1 0 ... 
OLD: Host: scsi0 Channel: 02 Id: 01 Lun: 00
      Vendor: DELL     Model: PERC H745 Frnt   Rev: 5.16
      Type:   Direct-Access                    ANSI SCSI revision: 05
Scanning host 1 for  all SCSI target IDs, all LUNs
sg6 changed:  device 1 0 1 0 ... 
from:scsi1 Channel: 00 Id: 01 Lun: 00un: 00
  Vendor: DGC      Model: LUNZ             Rev: 54005400
  Type:   Direct-Access                    ANSI SCSI revision: 06  06
to:   Vendor: DGC      Model: VRAID            Rev: 5400  
REM: Host: scsi1 Channel: 00 Id: 01 Lun: 00
NEW: Host: scsi1 Channel: 00 Id: 01 Lun: 00
      Vendor: DGC      Model: VRAID            Rev: 5400
      Type:   Direct-Access                    ANSI SCSI revision: 06
Scanning host 2 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 3 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 4 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 5 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 6 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 7 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 8 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 9 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 10 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 11 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 12 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
 Scanning for device 12 0 0 0 ... 
OLD: Host: scsi12 Channel: 00 Id: 00 Lun: 00
      Vendor: ATA      Model: DELLBOSS VD      Rev: 00-0
      Type:   Direct-Access                    ANSI SCSI revision: 05
Scanning host 13 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
Scanning host 14 for  SCSI target IDs  0 1 2 3 4 5 6 7, all LUNs
 Scanning for device 14 0 0 0 ... 
OLD: Host: scsi14 Channel: 00 Id: 00 Lun: 00
      Vendor: Marvell  Model: Console          Rev: 1.01
      Type:   Processor                        ANSI SCSI revision: 05
Scanning host 15 for  all SCSI target IDs, all LUNs
Scanning host 16 for  all SCSI target IDs, all LUNs
Scanning host 17 for  all SCSI target IDs, all LUNs
sg4 changed:  device 17 0 1 0 ... 
from:scsi17 Channel: 00 Id: 01 Lun: 00un: 00
  Vendor: DGC      Model: LUNZ             Rev: 54005400
  Type:   Direct-Access                    ANSI SCSI revision: 06  06
to:   Vendor: DGC      Model: VRAID            Rev: 5400  
REM: Host: scsi17 Channel: 00 Id: 01 Lun: 00
NEW: Host: scsi17 Channel: 00 Id: 01 Lun: 00
      Vendor: DGC      Model: VRAID            Rev: 5400
      Type:   Direct-Access                    ANSI SCSI revision: 06
2 new or changed device(s) found.          
	[1:0:1:0]
	[17:0:1:0]
0 remapped or resized device(s) found.
2 device(s) removed.                 
	[1:0:1:0]
	[17:0:1:0]
[root@TK_TEST ~]# udevadm settle
[root@TK_TEST ~]# multipath -r
[root@TK_TEST ~]# lsscsi | egrep -i 'DGC|LUNZ|VRAID'
[1:0:1:0]    disk    DGC      VRAID            5400  /dev/sde 
[17:0:1:0]   disk    DGC      VRAID            5400  /dev/sdd 
[root@TK_TEST ~]# lsblk -o NAME,SIZE,TYPE,VENDOR,MODEL,WWN
NAME               SIZE TYPE  VENDOR   MODEL            WWN
sda              558.4G disk  DELL     PERC H745 Frnt   0x6b07b250f79ca1003232466af87afb40
sdb                1.8T disk  DELL     PERC H745 Frnt   0x6b07b250f79ca1003232469a415166d4
sdc              447.1G disk  ATA      DELLBOSS VD      
├─sdc1             600M part                            
├─sdc2               1G part                            
└─sdc3           445.5G part                            
  ├─vg00-lv_root 429.5G lvm                             
  └─vg00-lv_swap    16G lvm                             
sdd                100G disk  DGC      VRAID            0x60060160b4505400c425b16a208f09e9
└─mpathab          100G mpath                           
sde                100G disk  DGC      VRAID            0x60060160b4505400c425b16a208f09e9
└─mpathab          100G mpath                           
[root@TK_TEST ~]# multipath -ll
mpathab (360060160b4505400c425b16a208f09e9) dm-2 DGC,VRAID
size=100G features='1 queue_if_no_path' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| `- 17:0:1:0 sdd 8:48 active ready running
`-+- policy='service-time 0' prio=10 status=enabled
  `- 1:0:1:0  sde 8:64 active ready running
```

- multipath -ll 결과 해석
- mpathab: 현재 자동으로 부여된 Multipath 이름
- 360060...: Unity LUN의 고유 WWID
- dm-2: Device Mapper 내부 장치 번호
- DGC,VRAID: Unity Block LUN
- size=100G: LUN 용량
- hwhandler='1 alua': Unity가 ALUA 방식으로 최적 경로를 구분
- wp=rw: 읽기·쓰기 가능
- prio=50 status=active: 현재 최적화된 주 경로
- prio=10 status=enabled: 정상 연결된 비최적 경로
- active ready running: 두 경로 모두 통신 가능한 정상 상태


## Step 6. mpathab에 고정 alias 부여한 뒤, Multipath 장치에 LVM 및 XFS 파일 시스템 생성하기.

- 기존 /etc/multipath.conf 의 multipaths 안에 다음 항목 추가

```
multipath {
    wwid 360060160b4505400c425b16a208f09e9
    alias sweet_story
}

-> 설정 적용

[root@TK_TEST ~]# vi /etc/multipath.conf
[root@TK_TEST ~]# multipathd reconfigure
ok
[root@TK_TEST ~]# multipath -r
[root@TK_TEST ~]# multipath -ll
story (360060160b4505400c425b16a208f09e9) dm-2 DGC,VRAID
size=100G features='1 queue_if_no_path' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| `- 17:0:1:0 sdd 8:48 active ready running
`-+- policy='service-time 0' prio=10 status=enabled
  `- 1:0:1:0  sde 8:64 active ready running
[root@TK_TEST ~]# ls -l /dev/mapper/story
lrwxrwxrwx 1 root root 7  9월 21 22:18 /dev/mapper/story -> ../dm-2
[root@TK_TEST ~]# 
```

- LVM PV와 VG 생성
  - VG : vg_story
  - LV : lv_mysql (20G), lv_media (60G)
  - 여유공간은 나중에 부족한 LV 확장 위해.

![LVMCreate](/assets/images/LVMcreate.png)

- XFS 파일 시스템으로 LV 포맷
- 생성한 LV 마운트 및 fstab에 등록 및 마운트 확인

![마운트 확인](/assets/images/MountCheck.png)

## Step 7. 소스코드 변경 및 물리 서버 OS에 Podman으로 배포 환경 구성 및 배포


- 이미지는 Docker Hub에 올리면 현재 클라우드에 떠있는 본체 docker file과 충돌이 날 수 있기에 Github에서 Onprem branch를 Clone 하기로 결정


- 변경한 소스코드 아키텍처 및 nginx 설정

![온프레미스 아키텍처](/assets/images/OnpremArchitecture.png)

- github에서 클론하기
  - 에러발생
  - gnone-ssh-askpass -> 750에 그래픽 화면 없어서 비밀번호 창 못띄움
  - github가 계정 비밀번호로 git clone을 허용하지 않음

```
git clone --branch codex/onprem-unity-storage --single-branch \
  https://github.com/sukhadukkha/private-memory-app.git /opt/sweet-story
cd /opt/sweet-story


(gnome-ssh-askpass:14470): Gtk-WARNING **: 10:35:41.179: cannot open display: 
error: unable to read askpass response from '/usr/libexec/openssh/gnome-ssh-askpass'
Username for 'https://github.com': sukhadukkha
(gnome-ssh-askpass:14471): Gtk-WARNING **: 10:35:47.270: cannot open display: 
error: unable to read askpass response from '/usr/libexec/openssh/gnome-ssh-askpass'
Password for 'https://sukhadukkha@github.com': 
remote: Invalid username or token. Password authentication is not supported for Git operations.
fatal: Authentication failed for '
```

- 해결
  - R750이 Github에 접속할 때 자신을 증명하는 키 만들기
  - install -d -m 700 /root/.ssh 키를 보관할 폴더 준비
  - ssh-keygen -t ed25519 -f /root/.ssh/story_deploy -C "R750 story deploy"
    - -t : 키 종류 
    - -f : 저장할 파일 이름
  - 생성한 .pub키 복사 후 Github에 Add deploy key
  - Onpremise 브랜치 clone

```
GIT_SSH_COMMAND='ssh -i /root/.ssh/story_deploy -o IdentitiesOnly=yes' \
git clone --branch codex/onprem-unity-storage --single-branch \
git@github.com:sukhadukkha/private-memory-app.git /opt/story


[root@TK_TEST ~]# GIT_SSH_COMMAND='ssh -i /root/.ssh/story_deploy -o IdentitiesOnly=yes' \
> git clone --branch codex/onprem-unity-storage --single-branch \
> git@github.com:sukhadukkha/private-memory-app.git /opt/story
'/opt/story'에 복제합니다...
remote: Enumerating objects: 1994, done.
remote: Counting objects: 100% (63/63), done.
remote: Compressing objects: 100% (51/51), done.
remote: Total 1994 (delta 5), reused 43 (delta 4), pack-reused 1931 (from 1)
오브젝트를 받는 중: 100% (1994/1994), 695.24 KiB | 733.00 KiB/s, 완료.
델타를 알아내는 중: 100% (1094/1094), 완료.
[root@TK_TEST ~]# ls -l /opt/story
합계 20
-rw-r--r-- 1 root root 5573  9월 22 10:48 README.md
drwxr-xr-x 3 root root   32  9월 22 10:48 backend
drwxr-xr-x 3 root root   20  9월 22 10:48 deploy
-rw-r--r-- 1 root root 1876  9월 22 10:48 docker-compose.onprem.yml
-rw-r--r-- 1 root root 1734  9월 22 10:48 docker-compose.yml
drwxr-xr-x 4 root root 4096  9월 22 10:48 frontend
[root@TK_TEST ~]# 
```

- goole map key 넣어주기
  - env example cp 해서 실제 env 파일 만들기

- podman compose 실행 파일 받고, Podman이 사용할 수 있게 등록해주기

```
mkdir -p /tmp/story-compose-install
cd /tmp/story-compose-install

curl -fL https://github.com/docker/compose/releases/download/v5.5.1/docker-compose-linux-x86_64 -o docker-compose-linux-x86_64
curl -fL https://github.com/docker/compose/releases/download/v5.5.1/docker-compose-linux-x86_64.sha256 -o docker-compose-linux-x86_64.sha256
sha256sum -c docker-compose-linux-x86_64.sha256

install -D -m 0755 docker-compose-linux-x86_64 /usr/local/libexec/docker/cli-plugins/docker-compose
systemctl enable --now podman.socket
podman compose version
```

| 명령 | 하는 일 |
| --- | --- |
| `mkdir -p /tmp/story-compose-install` | 설치 파일을 잠시 보관할 폴더를 만든다. `-p`는 폴더가 이미 있어도 오류를 내지 않는다. |
| `cd /tmp/story-compose-install` | 그 폴더로 이동한다. |
| 첫 번째 `curl -fL ... -o docker-compose-linux-x86_64` | GitHub에서 Linux x86_64용 Compose 실행 파일을 받는다. `-f`는 다운로드 오류를 알리고, `-L`은 GitHub의 다운로드 주소 이동을 따라가며, `-o`는 저장할 파일 이름을 정한다. |
| 두 번째 `curl -fL ...sha256 -o ...sha256` | 실행 파일의 검사값이 담긴 파일을 받는다. |
| `sha256sum -c docker-compose-linux-x86_64.sha256` | 받은 실행 파일의 검사값을 비교한다. `OK`가 나와야 다음 단계로 진행한다. |
| `install -D -m 0755 ... /usr/local/libexec/docker/cli-plugins/docker-compose` | 검사한 파일을 Podman이 Compose provider로 찾는 경로에 복사한다. `-D`는 필요한 경로를 만들고, `0755`는 실행 권한을 준다. |
| `systemctl enable --now podman.socket` | Compose가 Podman과 통신할 소켓을 **지금 켜고**, 재부팅 후에도 켜지도록 등록한다. Docker Engine을 켜는 명령은 아니다. |
| `podman compose version` | Podman이 설치된 Compose provider를 찾는지 확인한다. **버전만 확인하며 앱은 아직 실행하지 않는다.** |


- 배포 스크립트 실행
  - 각 스크립트 역할

| 파일 | 역할                                                               |
| --- |------------------------------------------------------------------|
| [check-mounts.sh](/Users/jihopark/OCI/deploy/onprem/check-mounts.sh) | Unity의 MySQL·미디어 저장 경로가 실제로 마운트됐는지 확인. 빠져 있으면 배포를 중단.            |
| [podman-common.sh](/Users/jihopark/OCI/deploy/onprem/podman-common.sh) | 다른 스크립트가 공통으로 쓰는 경로, 사전 확인, Compose 실행 함수를 모아둔 파일.               |
| [deploy.sh](/Users/jihopark/OCI/deploy/onprem/deploy.sh) | **첫 배포·코드 업데이트용.** 설정을 검사하고 이미지를 빌드한 뒤 앱을 실행.                    |
| [start.sh](/Users/jihopark/OCI/deploy/onprem/start.sh) | **재부팅 후 시작용.** 기존 이미지를 사용해 앱을 켜며 다시 빌드하지 않는다.                    |
| [stop.sh](/Users/jihopark/OCI/deploy/onprem/stop.sh) | 앱 컨테이너들을 중지한다.                                                   |
| [sweet-story-onprem.service](/Users/jihopark/OCI/deploy/onprem/sweet-story-onprem.service) | systemd에 등록하는 파일이다. 재부팅할 때 `start.sh`, 서비스 중지 때 `stop.sh`를 호출한다. |


- deploy.sh 스크립트로 배포 실시

- 배포 된 것 확인 


![배포1](/assets/images/배포확인1.png)
![배포2](/assets/images/배포확인2.png)


- 기능들 동작 확인 및 LUN 매핑해둔 경로에 데이터 저장되는지 확인

![동작 확인1](/assets/images/동작확인1.png)

![LUN 마운트상태](/assets/images/LUN마운트상태.png)

![경로로 저장확인](/assets/images/경로로저장확인.png)

- MySQL에 데이터 저장되는지 확인 
  - podman exec -it sweet-story-onprem-mysql-1 \ mysql -u memoryuser -p memoryapp

```sql
SELECT id, title
FROM memories
ORDER BY id DESC
LIMIT 5;

SELECT id, file_key, thumbnail_file_key
FROM photos
ORDER BY id DESC
  LIMIT 5;
```

![MySQL 데이터 저장확인](/assets/images/MySQL데이터저장확인.png)


- Unisphere LUN 용량 차는지 테스트 (사진은 너무 용량 작아서 테스트 파일 생성 후 테스트 진행)

```

[root@TK_TEST media]# df -h /srv/story/media/
Filesystem                     Size  Used Avail Use% Mounted on
/dev/mapper/vg_story-lv_media   60G  462M   60G   1% /srv/story/media

dd if=/dev/urandom \
  of=/srv/story/media/.unity-capacity-test.bin \
  bs=64M count=64 \
  status=progress conv=fsync
  
  
if=/dev/urandom: 임의 데이터를 생성합니다.
of=...: Unity LUN에 마운트된 미디어 경로에 저장합니다.
bs=64M: 한 번에 64MiB씩 씁니다.
count=64: 총 64번 써서 약 4GiB를 만듭니다.
status=progress: 진행 상황을 표시합니다.
conv=fsync: 명령이 끝나기 전에 디스크로 쓰기를 완료합니다.



[root@TK_TEST media]# dd if=/dev/urandom \
>   of=/srv/story/media/.unity-capacity-test.bin \
>   bs=64M count=64 \
>   status=progress conv=fsync
dd: warning: partial read (33554431 bytes); suggest iflag=fullblock
2080374722 bytes (2.1 GB, 1.9 GiB) copied, 9 s, 231 MB/s
0+64 records in
0+64 records out
2147483584 bytes (2.1 GB, 2.0 GiB) copied, 11.852 s, 181 MB/s
[root@TK_TEST media]# ls -lh /srv/story/media/.
./                        ../                       .unity-capacity-test.bin
[root@TK_TEST media]# ls -lh /srv/story/media/.
./                        ../                       .unity-capacity-test.bin
[root@TK_TEST media]# ls -lh /srv/story/media/.unity-capacity-test.bin 
-rw-r--r-- 1 root root 2.0G  9월 22 13:26 /srv/story/media/.unity-capacity-test.bin
[root@TK_TEST media]# df -h /srv/story/media/
Filesystem                     Size  Used Avail Use% Mounted on
/dev/mapper/vg_story-lv_media   60G  2.5G   58G   5% /srv/story/media
[root@TK_TEST media]# du -sh /srv/story/media/
2.1G	/srv/story/media/
[root@TK_TEST media]# sync
```

![LUN 공간 할당 확인](/assets/images/LUN공간%20할당%20확인.png)



### 재부팅 자동 실행 서비스 등록

- 저장소에 준비해 둔 서비스 설정 파일을 systemd에 등록

- `install -m 0644 /opt/story/deploy/onprem/sweet-story-onprem.service /etc/systemd/system/sweet-story-onprem.service`
  - install : 파일 지정 위치로 복사하면서 권한까지 설정
  - -m 0644 : 복사된 파일의 권한을 0644로 설정
- systemctl daemon-reload
- systemctl enable --now sweet-story-onprem.service


## 지금까지 완성 범위

```
지금까지 완성한 범위
현재 다음 항목을 모두 수행했습니다.
- Dell R750에 RHEL 8.10 구성
- FC HBA와 FC 스위치, Unity 연결
- WWPN 기반 1:1 조닝
- Unisphere에서 Host 및 Initiator 등록
- 100GiB LUN 생성 및 Host Access 설정
- RHEL에서 LUN 재검색
- 두 FC 경로를 하나의 Multipath 장치 story로 구성
- LVM으로 MySQL 20GiB, 미디어 60GiB 분리
- XFS 생성 및 영구 마운트
- Podman Compose로 MySQL, Spring Boot, Nginx 배포
- 글 데이터가 MySQL LUN에 저장되는 것 확인
- 사진·영상이 미디어 LUN에 저장되는 것 확인
- 2GiB 데이터를 기록하고 Unisphere 사용량 증가 확인
- systemd 자동 시작 구성
```

## Step 8. 백업 소프트웨어(networker) 통해서 백업 및 복구 해보기

- mysql은 mysqldump 파일을 Networker로 백업하기
- 사진, 영상 저장하는 /srv/story/media는 networker로 파일 백업하기

- 넷워커 클라이언트 설치 
- 미리 만들어놓은 백업 서버에서 필요한 클라이언트 파일 scp로 전달 및 설치

```
[root@node1 linux_x86_64]# scp \
> lgtoclnt-19.10.0.4-1.x86_64.rpm \
> lgtoxtdclnt-19.10.0.4-1.x86_64.rpm \
> root@192.168.1.xxx:/tmp/networker-client-19.10/
root@192.168.1.xxx's password: 
lgtoclnt-19.10.0.4-1.x86_64.rpm                                       100%   62MB  88.1MB/s   00:00    
lgtoxtdclnt-19.10.0.4-1.x86_64.rpm                                    100%   61MB  56.4MB/s   00:01    
[root@node1 linux_x86_64]# 

cd /tmp/networker-client-19.10

dnf install -y --nogpgcheck \
  ./lgtoclnt-19.10.0.4-1.x86_64.rpm \
  ./lgtoxtdclnt-19.10.0.4-1.x86_64.rpm
```


- networker client 서비스 실행
  - systemctl enable --now networker
  - systemctl status networker


```
[root@TK_TEST networker-client-19.10]# systemctl enable --now networker
Synchronizing state of networker.service with SysV service script with /usr/lib/systemd/systemd-sysv-install.
Executing: /usr/lib/systemd/systemd-sysv-install enable networker
[root@TK_TEST networker-client-19.10]# 
[root@TK_TEST networker-client-19.10]# 
[root@TK_TEST networker-client-19.10]# systemctl status networker.service 
● networker.service - EMC NetWorker. A backup and restoration software package.
   Loaded: loaded (/usr/lib/systemd/system/networker.service; enabled; vendor preset: disabled)
   Active: active (running) since Tue 2026-09-22 14:10:06 KST; 8s ago
  Process: 18990 ExecStart=/opt/nsr/admin/networker.sh start (code=exited, status=0/SUCCESS)
 Main PID: 19006 (nsrexecd)
    Tasks: 9
   Memory: 7.3M
   CGroup: /system.slice/networker.service
           └─19006 /usr/sbin/nsrexecd
[root@TK_TEST networker-client-19.10]# 
[root@TK_TEST networker-client-19.10]# ps -ef | grep nsr
root     19006     1  0 14:10 ?        00:00:00 /usr/sbin/nsrexecd
root     19124  9420  0 14:10 pts/0    00:00:00 grep --color=auto nsr
[root@TK_TEST networker-client-19.10]# 
```

- 서버에 nwui 설치하고, 스크립트 실행 후 https://192.168.1.xxx:9090/nwui 접속

- 단계별로 백업서버 nwui에서 확인

1. Client Resource 만들기
2. Protection Group 만들기
3. Policy 만들기
4. Workflow 만들기
5. Backup Action 만들기
6. 첫 백업 수동 실행
7. 백업 성공 확인
8. 백업 기반으로 복구 해보기

- Client 생성

![클라이언트 생성](/assets/images/Client만들기.png)

- Group 생성

![Group 생성](/assets/images/Group생성.png)

- Policy 생성

![Policy 생성](/assets/images/Policy생성.png)

- Workflow 생성

![Workflow 생성](/assets/images/Workflow%20생성.png)

- Action 생성 

![Action 생성](/assets/images/Action%20생성.png)

- 백업 수동 실행 및 확인 (버그때문에 nwui에서 완료된 workflow 확인 불가능했음)

```
[root@node1 linux_x86_64]# nsrpolicy monitor \
  -p STORY_ONPREM_POLICY \
  -w STORY_BACKUP_WORKFLOW \
  -d -n
  
-p: 확인할 정책
-w: 확인할 워크플로
-d: 상세 정보
-n: 읽기 편한 세로 형식으로 출력

Policy          Workflow        Action          Job Name   Job Id     Parent Job Id Job Type             Job Status     Completion Status Start Time         Duration   
--------------- --------------- --------------- ---------- ---------- ------------- -------------------- -------------- ----------------- ------------------ ---------- 
STORY_ONPREM_PO STORY_BACKUP_WO                 STORY_ONPR 204                      workflow job         COMPLETED      succeeded          9/22/26 15:12:01  00:00:25   
STORY_ONPREM_PO STORY_BACKUP_WO STORY_FILESYSTE savegrp    205        204           backup action job    COMPLETED      succeeded          9/22/26 15:12:01  00:00:25   
                                                /srv/story 207        205           save job             COMPLETED      succeeded          9/22/26 15:12:11  00:00:10   
                                                TK_TEST:sa 206        205           savefs job           COMPLETED      succeeded          9/22/26 15:12:06  00:00:00   
121432:nsrpolicy: Policy monitor operation was completed successfully

[root@node1 linux_x86_64]# mminfo \
  -q "client=TK_TEST,name=/srv/story/media" \
  -r "client,name,level,sscreate,totalsize,ssid,volume,ssflags"
 client    name                             lvl created       total ssid      volume         ssflags
TK_TEST    /srv/story/media                full 09/22/2026 2147686376 3736214406 BACKUPPJH.001 vF
TK_TEST    /srv/story/media                full 09/22/2026 2147612936 3719437374 BACKUPPJH.001 vF
[root@node1 linux_x86_64]# 
```

- 복구 작업 (백업된 SaveSet 확인)

![SaveSet 확인 및 복구](/assets/images/SaveSet%20확인%20및%20복구.png)

- 서버에서 만들어놓은 복구 테스트 폴더(restore-test에 복구해보기)

![Restore 요약](/assets/images/Restore요약.png)

- 복구 작업 성공

![복구 성공](/assets/images/복구성공.png)

- 복구 폴더 확인

![복구 폴더 확인](/assets/images/복구%20확인.png)

- 해시값 동일 확인

```
[root@TK_TEST media]# sha256sum /srv/story/media/.unity-capacity-test.bin
shea231c4c6debc0c015e080a7734bd68995407f3ab22bcf4481b5c36178a55343  /srv/story/media/.unity-capacity-test.bin
[root@TK_TEST media]# sha256sum /restore-test/media/.unity-capacity-test.bin 
ea231c4c6debc0c015e080a7734bd68995407f3ab22bcf4481b5c36178a55343  /restore-test/media/.unity-capacity-test.bin
[root@TK_TEST media]# 
```

## Step 9. MySQL 논리 백업 및 복구 해보기

1. /srv/story/mysql 디렉터리 그대로 복사하면 일관성 깨질 수 있음
2. mysqldump로 SQL 백업 파일 생성
3. 해당 SQL파일을 Networker로 백업
4. 별도 테스트 DB에 복구
5. 데이터 검증

- 덤프 저장 경로 생성 install -d -o root -g root -m 0700 /var/backups/story/mysql
- 현재 mysql에 들어있는 데이터 확인

```
[root@TK_TEST story]# podman compose \
>   --env-file .env.onprem \
>   -f docker-compose.onprem.yml \
>   exec -T mysql \
>   sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' <<'SQL'
> SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users
> UNION ALL
> SELECT 'memories', COUNT(*) FROM memories
> UNION ALL
> SELECT 'photos', COUNT(*) FROM photos
> UNION ALL
> SELECT 'memory_comments', COUNT(*) FROM memory_comments;
> SQL
>>>> Executing external compose provider "/usr/local/libexec/docker/cli-plugins/docker-compose". Please refer to the documentation for details. <<<<

mysql: [Warning] Using a password on the command line interface can be insecure.
table_name	row_count
users	1
memories	1
photos	2
memory_comments	0
```

- mysql 백업 생성

```
[root@TK_TEST story]# umask 077
[root@TK_TEST story]# 
[root@TK_TEST story]# backup_file="/var/backups/story/mysql/memoryapp_$(date +%Y%m%d_%H%M%S).sql"
[root@TK_TEST story]# podman compose \
>   --env-file .env.onprem \
>   -f docker-compose.onprem.yml \
>   exec -T mysql \
>   sh -c 'exec mysqldump \
>     -uroot \
>     -p"$MYSQL_ROOT_PASSWORD" \
>     --single-transaction \
>     --quick \
>     --routines \
>     --triggers \
>     --events \
>     --hex-blob \
>     --no-tablespaces \
>     --set-gtid-purged=OFF \
>     "$MYSQL_DATABASE"' \
>   > "$backup_file"
>>>> Executing external compose provider "/usr/local/libexec/docker/cli-plugins/docker-compose". Please refer to the documentation for details. <<<<

mysqldump: [Warning] Using a password on the command line interface can be insecure.
[root@TK_TEST story]# ls -lh "$backup_file"
-rw------- 1 root root 27K  9월 22 15:43 /var/backups/story/mysql/memoryapp_20260922_154346.sql
```

| 옵션 | 의미 |
|---|---|
| `--single-transaction` | 백업 시작 시점의 일관된 데이터를 읽음 |
| `--quick` | 큰 테이블을 한꺼번에 메모리에 올리지 않고 순차 처리 |
| `--routines` | 프로시저와 함수 포함 |
| `--triggers` | 트리거 포함 |
| `--events` | Event Scheduler 이벤트 포함 |
| `--hex-blob` | 바이너리 데이터를 안전한 16진수 형태로 기록 |
| `--no-tablespaces` | Tablespace 관련 권한 문제 방지 |
| `--set-gtid-purged=OFF` | 복구할 때 GTID 설정을 덤프에 포함하지 않음 |


- Networker Save Set 추가 (/var/backups/story/mysql)
  - Client 수정

![Client Save set 수정](/assets/images/Client수정.png)

- 수동 백업 시작 및 생성된 save set 확인

![수정된 Save Set](/assets/images/수정된SaveSet.png)


- mysql 덤프를 위한 새로운 복구 경로 만들기
  - restore_dir="/restore-test/mysql-$(date +%Y%m%d_%H%M%S)"
  - mkdir -p "$restore_dir"

- 복구 실행

![덤프 복구 실행](/assets/images/dump복구실행.png)

- 복구 완료

![dump 복구 완료](/assets/images/덤프복구완료.png)

```
[root@TK_TEST ~]# cd /restore-test/mysql-20260922_155257/
[root@TK_TEST mysql-20260922_155257]# ls -ltR
.:
합계 0
drwx------ 2 root root 43  9월 22 15:43 mysql

./mysql:
합계 28
-rw------- 1 root root 26987  9월 22 15:43 memoryapp_20260922_154346.sql
[root@TK_TEST mysql-20260922_155257]# 
```

- 별도 복구 검증용 테스트 DB 생성

```
[root@TK_TEST story]# podman compose \
>   --env-file .env.onprem \
>   -f docker-compose.onprem.yml \
>   exec -T mysql \
>   sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' <<'SQL'
> DROP DATABASE IF EXISTS memoryapp_restore_test;
> 
> CREATE DATABASE memoryapp_restore_test
>   CHARACTER SET utf8mb4
>   COLLATE utf8mb4_unicode_ci;
> SQL
>>>> Executing external compose provider "/usr/local/libexec/docker/cli-plugins/docker-compose". Please refer to the documentation for details. <<<<

mysql: [Warning] Using a password on the command line interface can be insecure.
[root@TK_TEST story]# 
```

- 복구된 SQL 파일 Import

```
[root@TK_TEST story]# podman compose \
>   --env-file .env.onprem \
>   -f docker-compose.onprem.yml \
>   exec -T mysql \
>   sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' <<'SQL'
> DROP DATABASE IF EXISTS memoryapp_restore_test;
> 
> CREATE DATABASE memoryapp_restore_test
>   CHARACTER SET utf8mb4
>   COLLATE utf8mb4_unicode_ci;
> SQL
>>>> Executing external compose provider "/usr/local/libexec/docker/cli-plugins/docker-compose". Please refer to the documentation for details. <<<<

mysql: [Warning] Using a password on the command line interface can be insecure.
[root@TK_TEST story]# 
[root@TK_TEST story]# 
[root@TK_TEST story]# podman compose \
>   --env-file .env.onprem \
>   -f docker-compose.onprem.yml \
>   exec -T mysql \
>   sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" memoryapp_restore_test' \
>   < "$restored_file"
>>>> Executing external compose provider "/usr/local/libexec/docker/cli-plugins/docker-compose". Please refer to the documentation for details. <<<<

mysql: [Warning] Using a password on the command line interface can be insecure.
[root@TK_TEST story]# echo $?
0
```

- 운영 DB와 복구 DB의 테이블 수 및 데이터 비교

```
[root@TK_TEST story]# podman compose \
>   --env-file .env.onprem \
>   -f docker-compose.onprem.yml \
>   exec -T mysql \
>   sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' <<'SQL'
> SELECT
>     table_schema,
>     COUNT(*) AS table_count
> FROM information_schema.tables
> WHERE table_schema IN ('memoryapp', 'memoryapp_restore_test')
> GROUP BY table_schema;
> SQL
>>>> Executing external compose provider "/usr/local/libexec/docker/cli-plugins/docker-compose". Please refer to the documentation for details. <<<<

mysql: [Warning] Using a password on the command line interface can be insecure.
TABLE_SCHEMA	table_count
memoryapp	18
memoryapp_restore_test	18


[root@TK_TEST story]# podman compose \
>   --env-file .env.onprem \
>   -f docker-compose.onprem.yml \
>   exec -T mysql \
>   sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' <<'SQL'
> SELECT
>     'users' AS table_name,
>     (SELECT COUNT(*) FROM memoryapp.users) AS source_count,
>     (SELECT COUNT(*) FROM memoryapp_restore_test.users) AS restored_count
> UNION ALL
> SELECT
>     'memories',
>     (SELECT COUNT(*) FROM memoryapp.memories),
>     (SELECT COUNT(*) FROM memoryapp_restore_test.memories)
> UNION ALL
> SELECT
>     'photos',
>     (SELECT COUNT(*) FROM memoryapp.photos),
>     (SELECT COUNT(*) FROM memoryapp_restore_test.photos)
> UNION ALL
> SELECT
>     'memory_comments',
>     (SELECT COUNT(*) FROM memoryapp.memory_comments),
>     (SELECT COUNT(*) FROM memoryapp_restore_test.memory_comments);
> SQL
>>>> Executing external compose provider "/usr/local/libexec/docker/cli-plugins/docker-compose". Please refer to the documentation for details. <<<<

mysql: [Warning] Using a password on the command line interface can be insecure.
table_name	source_count	restored_count
users	1	1
memories	1	1
photos	2	2
memory_comments	0	0

```

## Step 10. Multipath 단일 경로 장애 테스트 해보기

- 테스트 전 상태 기록

```
[root@TK_TEST story]# date
2026. 09. 22. (화) 16:13:02 KST
[root@TK_TEST story]# 
[root@TK_TEST story]# multipath -ll story
story (360060160b4505400c425b16a208f09e9) dm-2 DGC,VRAID
size=100G features='1 queue_if_no_path' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| `- 17:0:0:0 sdd 8:48 active ready running
`-+- policy='service-time 0' prio=10 status=enabled
  `- 14:0:0:0 sde 8:64 active ready running
[root@TK_TEST story]# 
[root@TK_TEST story]# mountpoint /srv/story/mysql
/srv/story/mysql is a mountpoint
[root@TK_TEST story]# mountpoint /srv/story/media
/srv/story/media is a mountpoint
[root@TK_TEST story]# df -h /srv/story/mysql/ /srv/story/media/
Filesystem                     Size  Used Avail Use% Mounted on
/dev/mapper/vg_story-lv_mysql   20G  380M   20G   2% /srv/story/mysql
/dev/mapper/vg_story-lv_media   60G  2.5G   58G   5% /srv/story/media
[root@TK_TEST story]# podman ps
CONTAINER ID  IMAGE                                                COMMAND               CREATED      STATUS                PORTS               NAMES
8e4dfb08e193  docker.io/library/mysql:8.0                          --character-set-s...  3 hours ago  Up 3 hours (healthy)                      sweet-story-onprem-mysql-1
775bb33ccc96  docker.io/library/sweet-story-onprem-backend:latest                        3 hours ago  Up 3 hours                                sweet-story-onprem-backend-1
7c19127e7dee  docker.io/library/sweet-story-onprem-nginx:latest    nginx -g daemon o...  3 hours ago  Up 3 hours            0.0.0.0:80->80/tcp  sweet-story-onprem-nginx-1



[root@TK_TEST story]# grep -H . /sys/class/fc_host/host*/port_name
/sys/class/fc_host/host14/port_name:0x21000024ff3f5f42
/sys/class/fc_host/host15/port_name:0x21000024ff3f5f43
/sys/class/fc_host/host16/port_name:0x21000024ff3f5f54
/sys/class/fc_host/host17/port_name:0x21000024ff3f5f55
[root@TK_TEST story]# multipath -ll story
story (360060160b4505400c425b16a208f09e9) dm-2 DGC,VRAID
size=100G features='1 queue_if_no_path' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| `- 17:0:0:0 sdd 8:48 active ready running
`-+- policy='service-time 0' prio=10 status=enabled
  `- 14:0:0:0 sde 8:64 active ready running
[root@TK_TEST story]# grep -H . /sys/class/fc_host/host*/port_state
/sys/class/fc_host/host14/port_state:Online
/sys/class/fc_host/host15/port_state:Linkdown
/sys/class/fc_host/host16/port_state:Linkdown
/sys/class/fc_host/host17/port_state:Online
```

- switch 상태 다 Online

```
TEST_SAN:admin> switch show
rbash: switch: command not found
TEST_SAN:admin> switchshow
switchName:	TEST_SAN
switchType:	118.1
switchState:	Online   
switchMode:	Native
switchRole:	Principal
switchDomain:	1
switchId:	fffc01
switchWwn:	xx:xx:xx:xx:xx:xx:xx:05
zoning:		ON (TEST_CFG)
switchBeacon:	OFF

Index Port Address Media Speed       State   Proto
==================================================
   0   0   010000   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:06 
   1   1   010100   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:07 
   2   2   010200   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:08 
   3   3   010300   id    N8	   No_Light    FC  
   4   4   010400   id    N8	   No_Light    FC  
   5   5   010500   id    N8	   No_Light    FC  
   6   6   010600   id    N8	   No_Light    FC  
   7   7   010700   id    N8	   No_Light    FC  
   8   8   010800   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:01 
   9   9   010900   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:02 
  10  10   010a00   id    N8	   No_Light    FC  
  11  11   010b00   id    N8	   No_Light    FC  
  12  12   010c00   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:03 
  13  13   010d00   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:04 
  14  14   010e00   id    N8	   No_Light    FC  
  15  15   010f00   id    N8	   No_Light    FC  
  16  16   011000   id    N8	   No_Light    FC  
  17  17   011100   id    N8	   No_Light    FC  
  18  18   011200   id    N8	   No_Light    FC  
  19  19   011300   id    N8	   No_Light    FC  
  20  20   011400   id    N8	   No_Light    FC  
  21  21   011500   id    N8	   No_Light    FC  
  22  22   011600   id    N8	   No_Light    FC  
  23  23   011700   id    N8	   No_Light    FC 
```


- 스크립트 통해 계속 LUN에 Write

```
test_dir="/srv/story/media/multipath-test-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$test_dir"

iteration=0

while true; do
    iteration=$((iteration + 1))

    if dd if=/dev/zero \
        of="$test_dir/io.bin" \
        bs=1M count=16 \
        conv=fsync status=none
    then
        printf '%s iteration=%d WRITE_OK\n' \
            "$(date '+%F %T')" \
            "$iteration" \
            | tee -a "$test_dir/continuity.log"
    else
        printf '%s iteration=%d WRITE_FAILED\n' \
            "$(date '+%F %T')" \
            "$iteration" \
            | tee -a "$test_dir/continuity.log"

        break
    fi

    sleep 1
done
```

- 정상 작동 확인 watch 
  - multipath -ll 에서도 둘다 active, enabled

![정상동작](/assets/images/정상동작.png)

```
watch -n 1 'date "+%F %T"; multipath -ll story'

Every 1.0s: date "+%F %T"; multipath -ll story                         TK_TEST: Tue Sep 22 16:31:31 2026

2026-09-22 16:31:31
story (360060160b4505400c425b16a208f09e9) dm-2 DGC,VRAID
size=100G features='1 queue_if_no_path' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| `- 17:0:0:0 sdd 8:48 active ready running
`-+- policy='service-time 0' prio=10 status=enabled
  `- 14:0:0:0 sde 8:64 active ready running
```

- 실제 FC 케이블 포트 9번 뽑기 
- 동작 확인 (switch) 
  - 9번 No_Light로 변경된 것 확인 가능

```
Index Port Address Media Speed       State   Proto
==================================================
   0   0   010000   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:06 
   1   1   010100   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:07 
   2   2   010200   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:08 
   3   3   010300   id    N8	   No_Light    FC  
   4   4   010400   id    N8	   No_Light    FC  
   5   5   010500   id    N8	   No_Light    FC  
   6   6   010600   id    N8	   No_Light    FC  
   7   7   010700   id    N8	   No_Light    FC  
   8   8   010800   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:01 
   9   9   010900   id    N8	   No_Light    FC  
  10  10   010a00   id    N8	   No_Light    FC  
  11  11   010b00   id    N8	   No_Light    FC  
  12  12   010c00   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:03 
  13  13   010d00   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:04 
  14  14   010e00   id    N8	   No_Light    FC  
  15  15   010f00   id    N8	   No_Light    FC  
  16  16   011000   id    N8	   No_Light    FC  
  17  17   011100   id    N8	   No_Light    FC  
  18  18   011200   id    N8	   No_Light    FC  
  19  19   011300   id    N8	   No_Light    FC  
  20  20   011400   id    N8	   No_Light    FC  
  21  21   011500   id    N8	   No_Light    FC  
  22  22   011600   id    N8	   No_Light    FC  
  23  23   011700   id    N8	   No_Light    FC  
```

- 실제 watch 명령 확인 (17번 호스트 나간 것 확인 가능)

```
Every 1.0s: date "+%F %T"; multipath -ll story                         TK_TEST: Tue Sep 22 16:45:03 2026

2026-09-22 16:45:03
story (360060160b4505400c425b16a208f09e9) dm-2 DGC,VRAID
size=100G features='1 queue_if_no_path' hwhandler='1 alua' wp=rw
`-+- policy='service-time 0' prio=50 status=active
  `- 14:0:0:0 sde 8:64 active ready running
```

- 하지만 스크립트는 계속 Write 중

```
2026-09-22 16:44:46 iteration=134 WRITE_OK
2026-09-22 16:44:47 iteration=135 WRITE_OK
2026-09-22 16:44:48 iteration=136 WRITE_OK
2026-09-22 16:44:49 iteration=137 WRITE_OK
2026-09-22 16:44:50 iteration=138 WRITE_OK
2026-09-22 16:44:51 iteration=139 WRITE_OK
2026-09-22 16:44:52 iteration=140 WRITE_OK
2026-09-22 16:44:53 iteration=141 WRITE_OK
2026-09-22 16:44:54 iteration=142 WRITE_OK
2026-09-22 16:44:55 iteration=143 WRITE_OK
2026-09-22 16:44:56 iteration=144 WRITE_OK
2026-09-22 16:44:57 iteration=145 WRITE_OK
2026-09-22 16:44:58 iteration=146 WRITE_OK
2026-09-22 16:44:59 iteration=147 WRITE_OK
2026-09-22 16:45:01 iteration=148 WRITE_OK
2026-09-22 16:45:02 iteration=149 WRITE_OK
2026-09-22 16:45:03 iteration=150 WRITE_OK
2026-09-22 16:45:04 iteration=151 WRITE_OK
2026-09-22 16:45:05 iteration=152 WRITE_OK
2026-09-22 16:45:06 iteration=153 WRITE_OK
2026-09-22 16:45:07 iteration=154 WRITE_OK
2026-09-22 16:45:08 iteration=155 WRITE_OK
2026-09-22 16:45:09 iteration=156 WRITE_OK
2026-09-22 16:45:10 iteration=157 WRITE_OK
2026-09-22 16:45:11 iteration=158 WRITE_OK
2026-09-22 16:45:12 iteration=159 WRITE_OK
2026-09-22 16:45:13 iteration=160 WRITE_OK
2026-09-22 16:45:14 iteration=161 WRITE_OK
2026-09-22 16:45:15 iteration=162 WRITE_OK
2026-09-22 16:45:16 iteration=163 WRITE_OK
2026-09-22 16:45:17 iteration=164 WRITE_OK
2026-09-22 16:45:18 iteration=165 WRITE_OK
2026-09-22 16:45:19 iteration=166 WRITE_OK
2026-09-22 16:45:20 iteration=167 WRITE_OK
2026-09-22 16:45:21 iteration=168 WRITE_OK
2026-09-22 16:45:22 iteration=169 WRITE_OK
2026-09-22 16:45:23 iteration=170 WRITE_OK
2026-09-22 16:45:24 iteration=171 WRITE_OK
2026-09-22 16:45:25 iteration=172 WRITE_OK
2026-09-22 16:45:26 iteration=173 WRITE_OK
2026-09-22 16:45:27 iteration=174 WRITE_OK
2026-09-22 16:45:28 iteration=175 WRITE_OK
2026-09-22 16:45:29 iteration=176 WRITE_OK
2026-09-22 16:45:30 iteration=177 WRITE_OK
2026-09-22 16:45:32 iteration=178 WRITE_OK
2026-09-22 16:45:33 iteration=179 WRITE_OK
2026-09-22 16:45:34 iteration=180 WRITE_OK
2026-09-22 16:45:35 iteration=181 WRITE_OK
2026-09-22 16:45:36 iteration=182 WRITE_OK
```

- 다시 케이블 복구 
  - 정상적으로 multipath -ll 돌아오는 것 확인 가능

```
Every 1.0s: date "+%F %T"; multipath -ll story                         TK_TEST: Tue Sep 22 16:46:31 2026

2026-09-22 16:46:31
story (360060160b4505400c425b16a208f09e9) dm-2 DGC,VRAID
size=100G features='1 queue_if_no_path' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| `- 17:0:0:0 sdd 8:48 active ready running
`-+- policy='service-time 0' prio=10 status=enabled
  `- 14:0:0:0 sde 8:64 active ready running
```

- switch 9번 포트도 다시 Online 확인 가능

```
Index Port Address Media Speed       State   Proto
==================================================
   0   0   010000   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:06 
   1   1   010100   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:07 
   2   2   010200   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:08 
   3   3   010300   id    N8	   No_Light    FC  
   4   4   010400   id    N8	   No_Light    FC  
   5   5   010500   id    N8	   No_Light    FC  
   6   6   010600   id    N8	   No_Light    FC  
   7   7   010700   id    N8	   No_Light    FC  
   8   8   010800   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:01 
   9   9   010900   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:02 
  10  10   010a00   id    N8	   No_Light    FC  
  11  11   010b00   id    N8	   No_Light    FC  
  12  12   010c00   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:03 
  13  13   010d00   id    N8	   Online      FC  F-Port  xx:xx:xx:xx:xx:xx:xx:04 
  14  14   010e00   id    N8	   No_Light    FC  
  15  15   010f00   id    N8	   No_Light    FC  
  16  16   011000   id    N8	   No_Light    FC  
  17  17   011100   id    N8	   No_Light    FC  
  18  18   011200   id    N8	   No_Light    FC  
  19  19   011300   id    N8	   No_Light    FC  
  20  20   011400   id    N8	   No_Light    FC  
  21  21   011500   id    N8	   No_Light    FC  
  22  22   011600   id    N8	   No_Light    FC  
  23  23   011700   id    N8	   No_Light    FC 
```


## Unity에서 NAS 파일서버 만들고 서버에서 마운트 해보기

1. Unity에서 NFS server 생성
2. File Systems 생성
3. NAS 서버를 R750에서 마운트
4. 파일 생성 및 읽기


- NFS Server 생성

![NFS Server 생성](/assets/images/NFSServer.png)

- 생성된 NFS Server로 ping 확인

```
[root@TK_TEST ~]# ping -c 3 192.168.1.xxx
PING 192.168.1.xxx (192.168.1.xxx) 56(84) bytes of data.
64 bytes from 192.168.1.xxx: icmp_seq=1 ttl=64 time=0.239 ms
64 bytes from 192.168.1.xxx: icmp_seq=2 ttl=64 time=0.125 ms
^C
--- 192.168.1.xxx ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1054ms
rtt min/avg/max/mdev = 0.125/0.182/0.239/0.057 ms
```

- NFS File System, Share 생성 (Read/Write, <ip>:/pjh-nfs-test)

![Share 생성1](/assets/images/Share생성1.png)
![Share 생성2](/assets/images/Share생성2.png)

- 공유 목록 확인
  - nfs-utils 설치
  - 공유 목록 확인 (showmount -e 192.168.1.xxx)
  - 둘 다 같은 파일시스템 및 같은 데이터 가리킨다. 파일 시스템 이름이나 share export 경로 둘 다 나오는 것

```
[root@TK_TEST ~]# showmount -e 192.168.1.xxx
Export list for 192.168.1.xxx:
/PJH_FILE_TEST (everyone)
/pjh-nfs-test  (everyone)
```
  
- NFS Server 마운트

```
[root@TK_TEST ~]# mkdir -p /mnt/unity-nfs-test
[root@TK_TEST ~]# mount -t nfs \
> -o vers=3,rw \
> 192.168.1.xxx:/pjh-nfs-test \
> /mnt/unity-nfs-test/
[root@TK_TEST ~]# findmnt /mnt/unity-nfs-test
TARGET              SOURCE                      FSTYPE OPTIONS
/mnt/unity-nfs-test 192.168.1.xxx:/pjh-nfs-test nfs    rw,relatime,vers=3,rsize=131072,wsize=131072,naml
[root@TK_TEST ~]# df -h /mnt/unity-nfs-test/
Filesystem                   Size  Used Avail Use% Mounted on
192.168.1.xxx:/pjh-nfs-test   10G  1.6G  8.5G  16% /mnt/unity-nfs-test
```

- 파일 r,w 테스트 (허가 거부 문제 발생)
  - Host Access에서 Read/Write, allow Root로 설정 시 파일 rw가능


```
[root@TK_TEST ~]# cd /mnt/unity-nfs-test/
[root@TK_TEST unity-nfs-test]# echo "Unity NFS test $(date)" | tee /mnt/unity-nfs-test/test.txt
tee: /mnt/unity-nfs-test/test.txt: 허가 거부
Unity NFS test 2026. 09. 23. (수) 16:09:47 KST
[root@TK_TEST unity-nfs-test]# touch hello
touch: cannot touch 'hello': 허가 거부
[root@TK_TEST unity-nfs-test]# echo "Unity NFS test $(date)" | tee /mnt/unity-nfs-test/test.txt
Unity NFS test 2026. 09. 23. (수) 16:13:16 KST
[root@TK_TEST unity-nfs-test]# ls
```

- 호스트 제한해보기
  - host access에서 read/write, 192.168.1.xxx 클라이언트만 read/write, allow root로 추가
  - 설정한 호스트에서만 접근 가능

```
[root@TK_TEST unity-nfs-test]# showmount -e 192.168.1.xxx
Export list for 192.168.1.xxx:
/PJH_FILE_TEST 192.168.1.xxx/255.255.255.255
/pjh-nfs-test  192.168.1.xxx/255.255.255.255
[root@TK_TEST unity-nfs-test]# 
```

## vCenter 에서 VM 만들고, Prometheus + Grafana로 서버 모니터링 스택 구축하기

1. vCenter에서 VM 생성
2. Monitoring VM에서 prometheus, grafana image 파일 받기
3. R750에서 Node-Exporter 이미지 파일 설치 및 컨테이너 실행
3. Prometheus 설정 파일 생성
4. 


- VM 생성

![vCenterVM](/assets/images/vCenterVM생성.png)

- RHEL 9.0 설치 (ISO 파일 연결)

- 사용할 포트

| 서비스 | 위치 | 포트 |
|---|---|---:|
| Node Exporter | R750 | TCP 9100 |
| Prometheus | 모니터링 VM | TCP 9090 |
| Grafana | 모니터링 VM | TCP 3000 |

- Prometheus + Grafana 이미지 파일 Pull 받기

```
[root@VM ~]# podman pull quay.io/prometheus/prometheus
Trying to pull quay.io/prometheus/prometheus:latest...
Getting image source signatures
Copying blob 49c226752edd done  
Copying blob eb7a272b9937 done  
Copying blob 487858d29734 done  
Copying blob 0dc8fee0e5ee done  
Copying blob 8ee344dffb17 done  
Copying blob 7a5b1d5c3c45 done  
Copying blob e80cad428b4d done  
Copying blob da388505dad8 done  
Copying blob 200d6e325877 done  
Copying config 31c1e0aacb done  
Writing manifest to image destination
Storing signatures
31c1e0aacb3a1914563c4e9b1e8d0a55095bf433aa43c1b0fe695959742845bd
[root@VM ~]# podman pull docker.io/grafana/grafana-oss
Trying to pull docker.io/grafana/grafana-oss:latest...
Getting image source signatures
Copying blob 01af952bd5a9 done  
Copying blob 6a0ac1617861 done  
Copying blob 6513f998b3a1 done  
Copying blob 38e67c1f799c done  
Copying blob 74d8a3a79084 done  
Copying blob ae2bb398229f done  
Copying blob 413bf89f4b8e done  
Copying blob d4c060f3b932 done  
Copying blob a3e1ec1858e3 done  
Copying blob 4f4fb700ef54 done  
Copying blob b508b56b15dd done  
Copying config 072d3db010 done  
Writing manifest to image destination
Storing signatures
072d3db0101e9fa5776fa9c454d8221994aeedf43e9abebe6652f42bf19bdc59
[root@VM ~]# podman images
REPOSITORY                     TAG         IMAGE ID      CREATED       SIZE
quay.io/prometheus/prometheus  latest      31c1e0aacb3a  5 weeks ago   262 MB
docker.io/grafana/grafana-oss  latest      072d3db0101e  3 months ago  1.09 GB
```

- R750 OS에 Node Exporter 설치하기

```
[root@TK_TEST ~]# podman pull quey.io/prometheus/node-exporter
Trying to pull quey.io/prometheus/node-exporter:latest...
Error: initializing image from source docker://quey.io/prometheus/node-exporter:latest: invalid character '<' looking for beginning of value
[root@TK_TEST ~]# podman pull quay.io/prometheus/node-exporter
Trying to pull quay.io/prometheus/node-exporter:latest...
Getting image source signatures
Copying blob c93f261857c3 done   | 
Copying blob f5ee56b8245c done   | 
Copying blob bef5f3176279 done   | 
Copying config 9bbbca8f5c done   | 
Writing manifest to image destination
9bbbca8f5cb8e9bd1b835e8ec086b6df6d9a458d2d10ef1c97ea4a9a3ae7e54b
[root@TK_TEST ~]# podman run -d \
>   --name node-exporter \
>   --network host \
>   --pid host \
>   --restart always \
>   --security-opt label=disable \
>   -v /:/host:ro,rslave \
>   quay.io/prometheus/node-exporter:latest \
>   --path.rootfs=/host \
>   --web.listen-address=:9100
ae61e8f8b0100e091993490f1257207b452e15305d12d8e136f9659c3dae3235
[root@TK_TEST ~]# podman ps
CONTAINER ID  IMAGE                                                COMMAND               CREATED        STATUS                 PORTS               NAMES
8e4dfb08e193  docker.io/library/mysql:8.0                          --character-set-s...  28 hours ago   Up 28 hours (healthy)                      sweet-story-onprem-mysql-1
775bb33ccc96  docker.io/library/sweet-story-onprem-backend:latest                        28 hours ago   Up 28 hours                                sweet-story-onprem-backend-1
7c19127e7dee  docker.io/library/sweet-story-onprem-nginx:latest    nginx -g daemon o...  28 hours ago   Up 28 hours            0.0.0.0:80->80/tcp  sweet-story-onprem-nginx-1
ae61e8f8b010  quay.io/prometheus/node-exporter:latest              --path.rootfs=/ho...  6 seconds ago  Up 7 seconds                               node-exporter
[root@TK_TEST ~]# 
```

| 옵션 | 의미 |
|---|---|
| `--network host` | R750의 TCP 9100에서 직접 서비스 |
| `--pid host` | 호스트 프로세스 관련 지표 접근 |
| `--restart always` | 컨테이너가 종료되면 다시 시작 |
| `label=disable` | SELinux로 인해 호스트 파일 접근이 막히는 것을 방지 |
| `/:/host:ro,rslave` | R750 전체 파일시스템을 읽기 전용으로 전달 |
| `--path.rootfs=/host` | 컨테이너가 자신의 파일시스템 대신 R750을 기준으로 수집 |
| `:9100` | Node Exporter의 기본 포트 |

- 모니터링 VM에서 연결 확인 
  - curl -s http://192.168.1.xxx:9100/metrics | head

- Prometheus 설정 파일 생성

```
[root@VM ~]# mkdir -p /opt/monitoring/prometheus
[root@VM ~]# cat > /opt/monitoring/prometheus/prometheus.yml <<'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "prometheus"
    static_configs:
      - targets:
          - "localhost:9090"

  - job_name: "r750-node"
    static_configs:
      - targets:
          - "192.168.1.xxx:9100"
        labels:
          server: "TK_TEST"
EOF
[root@VM ~]# 


- scrape_interval: 15s: 15초마다 지표 수집
- prometheus: Prometheus가 자기 상태를 수집
- r750-node: R750 Node Exporter 지표 수집
- server: TK_TEST: Grafana에서 서버를 구분할 때 사용할 라벨
```

- Podman 네트워크 및 데이터 볼륨 생성
  - Prometheus와 Grafana가 컨테이너 이름으로 통신할 수 있도록 전용 네트워크 생성 및 컨테이너 재생성 시에도 데이터 유지되도록 볼륨 생성
  - podman network create monitoring-net
  - podman volume create prometheus-data


- Prometheus 실행

```
podman run -d \
  --name prometheus \
  --network monitoring-net \
  --restart always \
  -p 9090:9090 \
  -v /opt/monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro,Z \
  -v prometheus-data:/prometheus \
  quay.io/prometheus/prometheus:latest \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --storage.tsdb.retention.time=15d \
  --web.enable-lifecycle
  
  
- 9090:9090: VM의 TCP 9090으로 Prometheus UI 제공
- prometheus-data: 시계열 데이터 영구 보관
- retention.time=15d: 데이터를 15일간 보관
- :ro,Z: 설정 파일은 읽기 전용으로 전달하고 SELinux Label 적용
```

- http://<모니터링_VM_IP>:9090/targets 접속해서 동작 확인

![Prometheus](/assets/images/Prometheus실행.png)

- Grafana 설정 및 대시보드가 컨테이너 재생성 후에도 유지되도록 볼륨 생성
  - podman volume create grafana-data
- Grafana 컨테이너 실행

```
podman run -d \
  --name grafana \
  --network monitoring-net \
  --restart always \
  -p 3000:3000 \
  -v grafana-data:/var/lib/grafana:Z \
  docker.io/grafana/grafana-oss:latest
  
[root@VM ~]# podman ps
CONTAINER ID  IMAGE                                 COMMAND               CREATED         STATUS             PORTS                   NAMES
3f0bf11a6773  quay.io/prometheus/prometheus:latest  --config.file=/et...  5 minutes ago   Up 5 minutes ago   0.0.0.0:9090->9090/tcp  prometheus
5f8f864a63fc  docker.io/grafana/grafana-oss:latest                        11 seconds ago  Up 11 seconds ago  0.0.0.0:3000->3000/tcp  grafana
[root@VM ~]# 
```

| 옵션 | 의미 |
|---|---|
| `--network monitoring-net` | Prometheus와 동일한 컨테이너 네트워크 사용 |
| `--restart always` | 비정상 종료 및 재부팅 후 재시작 |
| `-p 3000:3000` | VM의 TCP 3000으로 Grafana 제공 |
| `grafana-data` | 계정·데이터소스·대시보드 영구 저장 |
| `:Z` | SELinux 컨테이너 접근 레이블 적용 |

- Grafana 접속 및 DataSource 설정

![Grafana 접속](/assets/images/Grafana접속.png)
![DataSource 설정](/assets/images/DataSource설정.png)

```
Grafana–Prometheus 연결 오류 해결
문제
Grafana에서 Prometheus 데이터 소스를 연결할 때 다음 오류가 발생했다.
lookup prometheus on 168.126.63.1:53: no such host

원인
Grafana와 Prometheus는 동일한 monitoring-net에 연결되어 있었지만, Podman이 구형 CNI 네트워크 백엔드를 사용하고 있었고 podman-plugins가 설치되어 있지 않았다.
Network Backend: CNI
dns_enabled: false
podman-plugins: 미설치
이 때문에 컨테이너 이름을 IP로 변환하는 dnsname 플러그인이 동작하지 않았다. Grafana가 prometheus를 컨테이너 이름으로 해석하지 못하고 외부 DNS 서버에 질의하면서 연결에 실패했다.

해결
CNI의 컨테이너 이름 해석 기능을 제공하는 패키지를 설치했다.
dnf install -y podman-plugins
기존 네트워크에는 DNS 플러그인이 자동 적용되지 않기 때문에 컨테이너를 중지한 뒤 monitoring-net을 다시 생성했다.
podman stop grafana prometheus
podman rm grafana prometheus
podman network rm monitoring-net
podman network create monitoring-net
기존 Named Volume을 그대로 연결해 Prometheus와 Grafana 컨테이너를 재생성했다.

결과
dnsname 플러그인이 활성화되어 Grafana가 prometheus라는 컨테이너 이름을 내부 IP로 해석할 수 있게 됐다.
Grafana 데이터 소스는 다음 주소로 연결했다.
http://prometheus:9090
Prometheus 쿼리로 R750 Node Exporter 상태를 확인했다.

R750 Node Exporter
→ Prometheus
→ Grafana
```


- 대시보드 import (1860 대시보드)
  - Grafana에서 제공되는 Node Exporter Full 공개 대시보드

![DashBoardImport](/assets/images/DashBoard확인.png)


## NAS로 사진, 영상 저장 이관하기

1. NFS 연결 확인
2. 미디어 복사
3. 복사 결과 검증
4. /srv/stroy/media를 NFS로 전환
5. 애플리케이션 및 재부팅 검증

- 현재 상태 확인

```
[root@TK_TEST ~]# findmnt /srv/story/media 
TARGET           SOURCE                        FSTYPE OPTIONS
/srv/story/media /dev/mapper/vg_story-lv_media xfs    rw,relatime,attr2,inode64,
```

- NFS를 임시 경로에 마운트

```
[root@TK_TEST ~]# findmnt /mnt/story-media-nfs 
TARGET               SOURCE                      FSTYPE OPTIONS
/mnt/story-media-nfs 192.168.1.xxx:/pjh-nfs-test nfs    rw,relatime,vers=3,rsize=13107
[root@TK_TEST ~]# df -h /mnt/story-media-nfs/
Filesystem                   Size  Used Avail Use% Mounted on
192.168.1.xxx:/pjh-nfs-test   10G  1.6G  8.5G  16% /mnt/story-media-nfs
```

- 쓰기 권한 확인

```
[root@TK_TEST ~]# touch /mnt/story-media-nfs/.write-test
[root@TK_TEST ~]# ls -l /mnt/story-media-nfs/.write-test 
-rw-r--r-- 1 root root 0  9월 25 09:26 /mnt/story-media-nfs/.write-test
[root@TK_TEST ~]# rm -f /mnt/story-media-nfs/.write-test 
```

- 미디어 파일 복사

```
[root@TK_TEST ~]# rsync -aH \
> --numeric-ids \
> --info=progress2 \
> --exclude='.unity-capacity-test.bin' \
> /srv/story/media/ \
> /mnt/story-media-nfs/
     50,830,940 100%   74.07MB/s    0:00:00 (xfr#14, to-chk=0/34)
```

| 옵션 | 의미 |
|---|---|
| `rsync` | 원본과 대상의 파일을 비교하며 복사 |
| `-a` | 디렉터리 구조·소유자·권한·수정 시간을 최대한 유지 |
| `-H` | 하드링크 유지 |
| `--numeric-ids` | UID와 GID 숫자를 그대로 유지 |
| `--info=progress2` | 전체 복사 진행률 표시 |
| `--exclude` | 지정한 파일을 복사 대상에서 제외 |


- 복사 결과 검증

```
[root@TK_TEST ~]# rsync -rcn \
>   --delete \
>   --exclude='.unity-capacity-test.bin' \
>   /srv/story/media/ \
>   /mnt/story-media-nfs/
[root@TK_TEST ~]# 
```

| 옵션 | 의미 |
|---|---|
| `-r` | 하위 디렉터리까지 재귀적으로 검사 |
| `-c` | 파일 크기나 시간뿐 아니라 체크섬으로 내용 비교 |
| `-n` | Dry Run, 실제 변경 없이 결과만 미리 표시 |
| `--delete` | 대상에만 존재하는 파일을 표시 |

- /etc/fstab 변경

```
기존 /srv/story/media 주석 처리 후

192.168.1.xxx:/PJH_FILE_TEST /srv/story/media nfs rw,vers=3,proto=tcp,hard,_netdev,x-systemd.automount,x-systemd.mount-timeout=30 0 0
```

| 옵션 | 의미 |
|---|---|
| `rw` | 읽기와 쓰기 허용 |
| `vers=3` | NFSv3 사용 |
| `proto=tcp` | TCP 사용 |
| `hard` | NFS 장애 시 요청을 포기하지 않고 재시도하여 데이터 손상 방지 |
| `_netdev` | 네트워크가 필요한 파일시스템임을 systemd에 알림 |
| `x-systemd.automount` | 해당 경로에 접근할 때 자동 마운트 |
| `x-systemd.mount-timeout=30` | 최초 마운트를 최대 30초 기다림 |
| 마지막 `0 0` | dump 백업 및 부팅 시 fsck 대상에서 제외 |


- 기존 LV에서 NFS로 전환

```
[root@TK_TEST ~]# umount /mnt/story-media-nfs 
[root@TK_TEST ~]# 
[root@TK_TEST ~]# 
[root@TK_TEST ~]# umount /srv/story/media 
[root@TK_TEST ~]# 
[root@TK_TEST ~]# 
[root@TK_TEST ~]# systemctl daemon-reload 
[root@TK_TEST ~]# mount /srv/story/media/
[root@TK_TEST ~]# findmnt -T /srv/story/media 
TARGET           SOURCE                      FSTYPE OPTIONS
/srv/story/media 192.168.1.xxx:/pjh-nfs-test nfs    rw,relatime,vers=3,rsize=131072,ws
[root@TK_TEST ~]# ls -la /srv/story/media/
합계 24
drwxr-xr-x 10 root root 8192  9월 22 16:42 .
drwxr-xr-x  4 root root   32  9월 22 09:36 ..
dr-xr-xr-x  2 root bin   152  9월 23 15:50 .etc
drwxr-xr-x  4 root root  152  9월 22 11:43 gallery
drwxr-xr-x  2 root root 8192  9월 23 15:50 lost+found
drwxr-xr-x  6 root root  152  9월 24 14:06 memories
drwxr-xr-x  2 root root  152  9월 22 16:29 multipath-test-20260922_162938
drwxr-xr-x  2 root root  152  9월 22 16:30 multipath-test-20260922_163012
drwxr-xr-x  2 root root  152  9월 22 16:42 multipath-test-20260922_164222
-rw-r--r--  1 root root   48  9월 23 16:05 test.txt
[root@TK_TEST ~]# df -hT /srv/story/media/
Filesystem                  Type  Size  Used Avail Use% Mounted on
192.168.1.xxx:/pjh-nfs-test nfs    10G  1.6G  8.5G  16% /srv/story/media
```


- 사진 저장 

![사진 저장](/assets/images/사진%20저장.png)

![NFS Share](/assets/images/NFSSHare.png)

## 또 포트폴리오에 추가하면 좋을것들

- idrac에서 펌웨어 업데이트 해본 경험
- 실제 신한 데이터 센터 서버 납품 동행 및 랙 마운팅 경험

## 문제 해결 사례

- SCSI 재검색 후 LUN 인식 문제 해결
- 동일 WWID의 두 경로를 Multipath 장치로 통합
- FC 활성 경로 제거 중에도 연속 쓰기 유지
- NFS Root Squash로 인한 쓰기 거부 원인 확인
- Podman CNI DNS 플러그인 부재로 발생한 컨테이너 이름 해석 문제 해결
- NetWorker 복원 파일의 SHA-256 무결성 검증
- MySQL Dump 복구 후 테이블 건수 검증

> 본 실습은 테스트 환경에서 보안을 유지하며 진행했습니다.
