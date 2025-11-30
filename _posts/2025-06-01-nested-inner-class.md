---
layout: single
title: "nested inner class"
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

### ✨ 1. 자바 중급 1편 섹션 8 중첩클래스, 내부클래스1

#### 🔍 1-1. 중첩 클래스, 내부 클래스란?

중첩 클래스는 총 4가지가 있고,<br> 크게 2가지로 분류할 수 있다.

- 정적 중첩 클래스 - static이 붙는다. 바깥 클래스의 인스턴스에 소속되지 않는다.
- 내부 클래스 - static이 붙지 않는다. 바깥 클래스의 인스턴스에 소속된다.
- 내부 클래스의 종류 - 내부 클래스(inner class) : 바깥 클래스의 인스턴스의 멤버에 접근<br>지역 클래스(local class) : 내부 클래스의 특징 + 지역 변수에 접근<br>익명 클래스(anonymous class) : 지역 클래스의 특징 + 클래스의 이름이 없는 특별한 클래스
- 중첩 클래스를 사용하는 이유 1. 논리적 그룹화 2. 캡슐화

#### 🔍 1-2 정적 중첩 클래스 활용 코드

```java
package nested.nested.ex2;

public class Network {

    public void sendMessage(String text) {
        NetworkMessage networkMessage = new NetworkMessage(text);
        networkMessage.print();
    }

    private static class NetworkMessage {

        private String content;

        public NetworkMessage(String content) {
            this.content = content;
        }

        public void print() {
            System.out.println(content);
        }
    }
}
```
#### 🔍 1-3 내부 클래스 활용 코드

```java
package nested.inner.ex2;

public class Car {
    private String model;
    private int chargeLevel;
    private Engine engine;

    public Car(String model, int chargeLevel) {
        this.model = model;
        this.chargeLevel = chargeLevel;
        this.engine = new Engine();
    }

    public void start() {
        engine.start();
        System.out.println(model + " 시작 완료");
    }

    private class Engine {
        public void start() {
            System.out.println("충전 레벨 확인: " + chargeLevel);
            System.out.println(model + "의 엔진을 구동합니다.");
        }
    }

}
```

```java
package nested.inner.ex2;

public class CarMain {

    public static void main(String[] args) {
        Car myCar = new Car("Model Y", 100);
        myCar.start();
    }
}
```

### ✨ 배운 점 및 느낀 점
```markdown
작년 학교에서 객체지향언어 수업을 들을 때, 자바 swing 컴포넌트에서 뭣도 모르고 사용했었던 클래스들의 정의를
다시 배울 수 있어서 좋았고, 프로젝트를 해볼 때, 사용하면서 어느정도 익숙해졌었던 내용이라 듣기 수월했다. 
다음 강의는 지역 클래스, 익명 클래스와 그 활용과 연습문제 풀이 순서인데 이름만 들으면 뭔지 잘 모르기 때문에 
열심히 들어야겠다.