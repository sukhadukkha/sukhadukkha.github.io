---
layout: single
title:  "[현장실습] Dell PowerEdge 서버·스토리지 하드웨어 교육 정리"
categories: [현장실습]
tags: [Dell, Server, Storage]
toc: true
author_profile: true
---

Dell PowerEdge 서버의 섀시를 분해·조립하며 확인한 구성 요소와 RAID, SAN·NAS, HBA, Ethernet·Fibre Channel 연결 방식을 정리했다. 모델과 세대마다 지원하는 CPU, DIMM, Backplane과 PCIe 구성은 다르므로 실제 작업에서는 Service Tag를 기준으로 해당 모델의 Installation and Service Manual을 확인해야 한다.

## 1. PowerEdge 제품군과 폼팩터

PowerEdge 모델 앞의 문자는 서버 형태를 나타낸다.

- `R`: Rack Server
- `T`: Tower Server
- `M`: Modular Server
- `XE`: 가속기·AI·고성능 워크로드 등에 특화된 Server 제품군

예를 들어 R660은 16세대(16G), R670은 17세대(17G) Rack Server다. 다만 모델 번호의 각 숫자가 의미하는 CPU Vendor, Socket 수와 섀시 높이는 세대가 바뀌면서 달라질 수 있다. 숫자만으로 사양을 단정하지 않고 [Dell 공식 Technical Guide와 Support 문서](https://www.dell.com/support/home/)를 확인한다.

Rack Server의 높이는 `U(Unit)`로 표현한다. 1U는 약 44.45mm이며 2U 장비는 더 많은 Drive Bay와 PCIe Card, Cooling 구성을 제공할 수 있지만 정확한 확장성은 모델별로 다르다.

## 2. 서버 전면과 후면에서 확인할 요소

### 전면

- Drive Bay와 Backplane 유형
- 전원·상태 LED
- System Identification Button과 LED
- LCD 또는 Quick Sync 지원 여부
- USB·iDRAC Direct Port

상태 LED의 색상과 점멸 패턴은 부품 장애나 식별 상태를 나타낼 수 있다. 패턴의 의미는 모델별 Owner's Manual과 iDRAC Lifecycle Log에서 함께 확인한다.

### 후면

- PSU(Power Supply Unit)
- iDRAC 전용 관리 Port
- OCP NIC 또는 내장 LOM Port
- PCIe Riser와 확장 Card
- Serial·USB·VGA Port

OCP NIC는 Open Compute Project 규격을 사용하는 교체형 Network Adapter다. 모델에 따라 내장 LOM과 OCP NIC 구성이 다르다.

## 3. 서버 내부 주요 부품

```text
Power Supply
   ↓
Main Board ─ CPU ─ DIMM
   ├─ OCP NIC
   ├─ PCIe Riser ─ NIC / HBA / GPU
   ├─ PERC 또는 HBA
   └─ Backplane ─ HDD / SSD / NVMe
```

### CPU와 Memory

서버 CPU에는 Memory Controller가 통합되어 있으며 CPU Socket별 Memory Channel과 DIMM Slot이 연결된다. 성능을 위해 DIMM을 아무 Slot에나 장착하지 않고 Dell이 제시하는 Population Rule을 따른다.

- CPU 수에 따라 사용할 수 있는 DIMM Slot과 PCIe Lane이 달라질 수 있다.
- DIMM 용량, Rank와 속도를 혼합하면 지원 속도가 낮아지거나 지원되지 않을 수 있다.
- 다중 Socket Server는 CPU 간 통신에 Intel UPI 또는 AMD Infinity Fabric 등 Platform에 맞는 Interconnect를 사용한다.

교육 중 들었던 `QPI(QuickPath Interconnect)`는 이전 Intel Platform에서 사용된 명칭이며, 최근 Intel Xeon Scalable Platform에서는 주로 UPI라는 용어를 사용한다.

### CMOS Battery와 RAID Cache 보호

- Main Board의 Coin Cell Battery는 RTC와 일부 Firmware 설정 유지에 사용된다.
- RAID Controller는 Write Cache 보호를 위해 별도의 Battery나 Supercapacitor, Flash 기반 보호 장치를 사용할 수 있다.

두 부품은 외형이나 위치가 비슷해 보일 수 있지만 역할이 다르다.

### Cooling과 전원

서버는 온도가 높아지면 부품 보호를 위해 Fan 속도를 높이거나 CPU 성능을 제한하는 Thermal Throttling이 발생할 수 있다. Fan, Heatsink, Air Shroud와 빈 Slot용 Filler도 Airflow 구성의 일부다.

PSU와 일부 주변 장치도 Firmware 관리 대상이다. Firmware Update는 iDRAC·BIOS·PERC·NIC·Drive 등 부품 간 호환성과 권장 Update 순서를 확인하고 수행한다.

## 4. iDRAC과 Lifecycle Controller

iDRAC은 운영체제와 독립적으로 서버 Hardware를 관리하는 BMC(Baseboard Management Controller)다.

- 전원 켜기·끄기와 Reset
- CPU·Memory·Fan·Power·Storage 상태 확인
- Hardware Inventory와 Lifecycle Log 확인
- Virtual Console과 Virtual Media 사용
- BIOS·Firmware Update
- RAID와 일부 배포 작업 지원

운영체제가 부팅되지 않거나 Network Service가 중단돼도 iDRAC 관리망이 정상이라면 원격으로 Hardware 상태와 Console을 확인할 수 있다. 관리 Interface는 업무망과 분리하고 접근 권한과 Firmware를 관리해야 한다.

## 5. PCIe와 Riser

PCIe는 CPU와 NIC, HBA, NVMe, GPU 같은 고속 장치를 연결하는 Bus 규격이다.

```text
CPU
 ├─ PCIe → NIC
 ├─ PCIe → HBA
 ├─ PCIe → NVMe
 └─ PCIe → GPU
```

Riser는 Main Board의 PCIe 연결을 섀시 방향에 맞게 확장해 Card를 장착하도록 만드는 Board다. 하나의 Riser에 여러 Slot이 있을 수 있다.

확장 Card를 고를 때는 다음을 함께 확인한다.

- PCIe Generation과 Lane 수
- Slot의 Electrical·Physical Lane 구성
- Full Height·Low Profile, Half Length·Full Length
- CPU와 Slot의 연결 관계
- 전력과 Cooling 요구사항

PCIe 대역폭은 Generation뿐 아니라 Lane 수와 전송 방향을 함께 표기해야 한다. 예를 들어 PCIe 4.0 x16의 이론상 대역폭은 단방향 약 31.5GB/s, PCIe 5.0 x16은 단방향 약 63GB/s 수준이다. 실제 성능은 Protocol Overhead와 장치 성능의 영향을 받는다.

## 6. Drive, Backplane, PERC와 HBA

### Drive와 Backplane

2.5인치와 3.5인치는 Drive의 물리적 폼팩터다. 더 작은 Drive를 Adapter Carrier로 장착할 수 있는 경우도 있지만 Backplane의 Interface, Carrier, Firmware와 모델 지원 여부를 확인해야 한다.

Backplane은 전면 Drive와 Storage Controller 또는 PCIe 경로를 연결한다. Backplane 유형에 따라 SAS·SATA·NVMe Drive 지원과 Cable 구성이 달라진다.

### PERC

PERC(PowerEdge RAID Controller)는 Dell PowerEdge용 RAID Controller 제품군이다.

```text
CPU·PCIe
   ↓
PERC
   ↓
Backplane
   ↓
SAS 또는 SATA Drive
```

PERC는 여러 Physical Drive를 Virtual Disk로 구성하고 RAID 연산과 Cache를 처리한다. Controller Model마다 지원 Interface, Cache와 RAID Level이 다르다.

### HBA

HBA(Host Bus Adapter)는 Host와 Storage Network 또는 Drive를 연결하는 Adapter다. 문맥에 따라 FC HBA와 SAS HBA를 구분해야 한다.

- **FC HBA**: Server를 Fibre Channel SAN에 연결한다.
- **SAS HBA**: SAS/SATA Drive나 외장 Enclosure에 연결하며 RAID 기능 없이 Pass-through 역할을 중심으로 사용할 수 있다.

```text
Server FC HBA
   ↓
FC Switch
   ↓
Storage Front-end Port
   ↓
LUN
```

NVMe Drive는 PCIe 기반으로 통신한다. NVMe 사용 가능 개수와 CPU 요구사항은 Server Model, Backplane과 PCIe Lane 구성에 따라 달라지며 무조건 2 Socket Server에서만 사용할 수 있는 것은 아니다.

## 7. RAID 기본 개념

RAID는 여러 Drive를 묶어 성능이나 장애 허용성을 제공하는 기술이다.

| RAID | 최소 Drive | 특징 |
|---|---:|---|
| RAID 0 | 2 | Striping, 성능과 용량 활용은 좋지만 장애 허용 없음 |
| RAID 1 | 2 | Mirroring, 한 Drive의 복제본 유지 |
| RAID 5 | 3 | 분산 Parity 1개, Drive 1개 장애 허용 |
| RAID 6 | 4 | 분산 Parity 2개, Drive 2개 장애 허용 |
| RAID 10 | 4 | Mirroring과 Striping 결합 |

RAID 5와 RAID 6은 Write 시 Parity 계산이 필요하며, 장애 후 Rebuild 중 성능 저하와 추가 장애 위험을 고려해야 한다. Drive 수와 용량이 크다면 Rebuild 시간과 워크로드에 맞춰 RAID Level을 선택한다.

**RAID는 Backup이 아니다.** Controller 장애, 사용자 삭제, 파일 손상, Ransomware와 재해에는 별도의 Backup과 복구 절차가 필요하다.

### Hot Spare

- **Dedicated Hot Spare**: 지정한 Virtual Disk나 Disk Group에 사용한다.
- **Global Hot Spare**: Controller가 관리하는 호환 가능한 여러 Disk Group의 장애에 사용할 수 있다.

장애 Drive를 Hot Spare가 대신해 Rebuild할 수 있지만, 실제 동작은 Drive Type·용량과 Controller 정책에 따라 달라진다.

## 8. DAS, NAS와 SAN

| 구분 | 제공 단위 | 대표 연결 | 서버에서 보이는 형태 |
|---|---|---|---|
| DAS | Block | SAS 등 직접 연결 | Local Block Device |
| NAS | File | Ethernet, NFS·SMB | 공유 Directory |
| SAN | Block | FC 또는 iSCSI | Remote Block Device·LUN |

- **DAS**: Storage가 특정 Server에 직접 연결된다.
- **NAS**: Storage가 File System을 관리하고 Client에 File Share를 제공한다.
- **SAN**: Storage가 Server에 Block Device인 LUN을 제공하며 Server가 File System이나 LVM을 구성한다.
- **Unified Storage**: 한 시스템에서 Block과 File Service를 함께 제공한다. Dell Unity와 PowerStore 등이 해당 기능을 제공할 수 있다.

```text
NAS
Client ─ Ethernet ─ NAS Server ─ File System

FC SAN
Server FC HBA ─ FC Switch ─ Storage ─ LUN

iSCSI SAN
Server NIC ─ Ethernet Switch ─ Storage ─ LUN
```

## 9. SCSI, iSCSI와 Fibre Channel

SCSI는 Server가 Storage에 `READ`, `WRITE` 등의 작업을 요청하는 Command Set이다. 특정 Cable 하나만을 뜻하지 않는다.

### iSCSI

iSCSI는 SCSI Command를 TCP/IP Network로 전달한다.

```text
SCSI Command
   ↓
iSCSI
   ↓
TCP/IP와 Ethernet
   ↓
Ethernet Switch
   ↓
Storage Target
```

일반 Ethernet Infrastructure를 활용할 수 있지만 Storage Traffic 분리, MTU, Multipath, Authentication과 Network 이중화를 고려해야 한다.

### Fibre Channel

Fibre Channel은 Storage Network를 위한 별도의 Protocol 체계다. FC HBA, FC Switch와 Storage FC Port를 사용하고 Zoning과 LUN Masking으로 접근 경로를 구성한다.

```text
Server HBA WWPN
   ↓
FC Switch Zoning
   ↓
Storage Port
   ↓
Host Mapping과 LUN
```

FC가 반드시 광케이블만을 의미하는 것은 아니며, Fibre Channel Protocol과 물리 Media는 구분해서 이해해야 한다.

## 10. Ethernet Cable과 Connector

Cable은 신호를 전달하는 물리 매체이고 Ethernet은 Frame을 주고받는 통신 기술이다.

### RJ45와 Category Cable

- RJ45로 흔히 부르는 8P8C Connector는 구리 Ethernet 연결에 널리 사용한다.
- Cat6는 Twisted-pair Cable Category 중 하나다.
- 지원 속도와 거리는 Cable Category, 설치 품질과 장비 규격에 따라 달라진다.

일반 RJ45 Port에 SFP Module이나 광케이블을 직접 꽂을 수는 없다.

### SFP 계열

SFP 계열은 Switch나 NIC Port에 장착하는 교체형 Module 또는 Form Factor다.

| 규격 | 대표적인 Ethernet 속도 |
|---|---:|
| SFP | 1GbE |
| SFP+ | 10GbE |
| SFP28 | 25GbE |
| QSFP+ | 40GbE |
| QSFP28 | 100GbE |
| QSFP56 | 200GbE |
| QSFP-DD | 400GbE 이상 세대 |

실제 Module은 Ethernet 외에 FC 등 다른 Protocol 용도로도 사용될 수 있다. **형태가 맞는다고 서로 호환되는 것은 아니며** 속도, 파장, Fiber Type, Protocol과 Vendor 지원 목록을 확인해야 한다.

### Transceiver와 DAC

```text
광 연결
Switch SFP Port ─ Optical Transceiver ─ Fiber ─ Optical Transceiver ─ Server

DAC 연결
Switch SFP Port ═════ Copper Cable ═════ Server SFP Port
```

DAC(Direct Attach Cable)은 양쪽 Connector와 Cable이 일체형이다. 짧은 거리의 Server-ToR Switch 연결에서 비용과 연결 단순성의 장점이 있다. 광 연결은 더 긴 거리와 전기적 절연이 필요한 환경 등에 사용한다.

SFP Port에 Copper RJ45 Transceiver를 사용할 수도 있지만 Module의 발열, 지원 속도와 Switch 호환성을 확인해야 한다.
