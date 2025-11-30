---
layout: single
title: "Date and Time"
categories: [java]
tags: [java, TIL]
toc: true
author_profile: true
sidebar:
  nav: "docs"
---

# ☕ Java 공부 기록

## 📘 학습 날짜
- 2025-05-31

## 📅 오늘 배운 내용

### ✨ 1. 자바 중급 1편 섹션 7. 날짜와 시간

- `LocalDateTime`
- `ZonedDateTime`
- `Instant`
- `Duration`, `Period`
- 날짜와 시간의 핵심 인터페이스
- 날짜와 시간 조회하고 조작하기

---

### 🔍 1-1 문제와 풀이: 날짜 더하기

```java
package time.test;

import java.time.LocalDateTime;

public class TestPlus {
    public static void main(String[] args) {
        LocalDateTime lt = LocalDateTime.of(2024, 1, 1, 0, 0);

        LocalDateTime futureDateTime = lt
            .plusYears(1)
            .plusMonths(2)
            .plusDays(3)
            .plusHours(4);

        System.out.println("기준 시각: " + lt);
        System.out.println("1년 2개월 3일 4시간 후의 시각 = " + futureDateTime);
    }
}
```
### 🔍 1-2 날짜 간격 반복 출력하기

```java
package time.test;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;

public class TestLoopPlus {
    public static void main(String[] args) {

        LocalDate startDate = LocalDate.of(2024, 1, 1);

        for (int i = 0; i < 5; i++) {
            LocalDate nextDate = startDate.plus(2 * i, ChronoUnit.WEEKS);
            System.out.println("날짜 " + i + ": " + nextDate);
        }
    }
}
```

### 🔍 1-3 디데이 구하기

```java
package time.test;

import java.time.LocalDate;
import java.time.Period;
import java.time.temporal.ChronoUnit;

public class TestBetween {
    public static void main(String[] args) {

        LocalDate startDate = LocalDate.of(2024, 1, 1);
        LocalDate endDate = LocalDate.of(2024, 11, 21);

        Period period = Period.between(startDate, endDate);
        long daysBetween = ChronoUnit.DAYS.between(startDate, endDate);
        System.out.println("between = " + period);

        System.out.println("시작 날짜: " + startDate);
        System.out.println("목표 날짜: " + endDate);
        System.out.println("남은 기간: " + period.getYears() + "년 " + period.getMonths() + "개월 " + period.getDays() + "일");
        System.out.println("디데이: " + daysBetween + "일 남음");

    }
}
```
### 🔍 1-4 시작 요일, 마지막 요일 구하기

```java

package time.test;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.temporal.TemporalAdjusters;

public class TestAdjusters {
    public static void main(String[] args) {

        int year = 2024;
        int month = 1;

        LocalDate localDate = LocalDate.of(year, month, 1);
        DayOfWeek firstDayOfWeek = localDate.getDayOfWeek();
        DayOfWeek lastDayOfMonth = localDate.with(TemporalAdjusters.lastDayOfMonth()).getDayOfWeek();
        System.out.println("firstDayOfWeek = " + firstDayOfWeek);
        System.out.println("lastDayOfWeek = " + lastDayOfMonth);
    }
}
```

### 🔍 1-5 국제 회의 시간

```java
package time.test;

import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;

public class TestZone {

    public static void main(String[] args) {

        ZonedDateTime seoulTime = ZonedDateTime.of(LocalDate.of(2024, 1, 1), LocalTime.of(9, 0), ZoneId.of("Asia/Seoul"));
        ZonedDateTime londonTime = seoulTime.withZoneSameInstant(ZoneId.of("Europe/London"));
        ZonedDateTime nyTime = seoulTime.withZoneSameInstant(ZoneId.of("America/New_York"));

        System.out.println("서울의 회의 시간: " + seoulTime);
        System.out.println("런던의 회의 시간: " + londonTime);
        System.out.println("뉴욕의 회의 시간: " + nyTime);
    }
}
```

### 🔍 1-6 달력 출력하기

```java
package time.test;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.Scanner;

public class TestCalendarPrinter {
    public static void main(String[] args) {

        Scanner scanner = new Scanner(System.in);

        System.out.print("년도를 입력하세요: ");
        int year = scanner.nextInt();
        System.out.print("월을 입력하세요: ");
        int month = scanner.nextInt();

        printCalendar(year, month);

    }
    public static void printCalendar(int year, int month) {

        LocalDate firstDayOfMonth = LocalDate.of(year, month, 1);
        LocalDate firstDayOfnextMonth = firstDayOfMonth.plusMonths(1);

        int offsetWeekDays = firstDayOfMonth.getDayOfWeek().getValue() % 7;

        // 월요일 - 1 (1%7=1) ... 일요일 - 7 (7%7=0)
        System.out.println("Su Mo Tu We Th Fr Sa");
        for (int i = 0; i < offsetWeekDays; i++) {
            System.out.print("   "); // 만약 월요일이면 i=0; i<1; 공백 총 3번 후 날짜 숫자 출력
        }

        LocalDate dayIterator = firstDayOfMonth;
        while (dayIterator.isBefore(firstDayOfnextMonth)) {
            System.out.printf("%2d ", dayIterator.getDayOfMonth()); // %2d = 2칸만큼 차지
            if (dayIterator.getDayOfWeek() == DayOfWeek.SATURDAY) {
                System.out.println();
            }
            dayIterator = dayIterator.plusDays(1);
        }
    }
}
```

### ✨ 배운 점 및 느낀 점

```markdown
1-6 달력문제는 출력 칸을 맞추는 것을 이해하는데 어려움이 있었다. 강의를 보고
이해를 할 수 있게 되었고, 날짜와 시간을 다루는 인터페이스 및 메서드들이 어떻게 활용되고,
어떤 것들이 있는지 배울 수 있는 강의 목차였다. 
LocalDate의 getDayOfWeek() = Monday 처럼 문자열 반환 (toString 오버라이딩 되어있음)
getValue() = Monday : 1, Sunday = 0 처럼 int형 반환
getDayofMonth() = 1 ,2 처럼 int형 반환
```




