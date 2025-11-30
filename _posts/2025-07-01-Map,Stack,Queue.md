---
layout: single
title: "Map,Stack,Queue"
categories: [java]
tags: [java]
toc: true
author_profile: true
---

# ☕ Java 공부 기록

## 📘 학습 날짜
- 2025-07-01

## 📅 오늘 배운 내용

### ✨ 1. Map이란? 

- Map은 키-값의 쌍을 저장하는 자료구조
- 키는 맵 내에서 유일해야함.
- 키는 중복될 수 없지만, 값은 중복 가능함
- Map은 순서유지 X

#### ✨ 1-1. Map vs Set
- Map의 키가 바로 Set과 같은 구조
- Map의 Value는 키 옆에 따라 붙은 것, 키 옆에 Value 하나만 추가한다면 Map이 됨.
- Map과 Set은 거의 같지만, 단지 Value가 있느냐 없느냐의 차이

### 2-1. Stack 자료구조(LIFO), 큐 자료구조(FIFO), Deque 자료구조
- stack 자료구조 및 큐 자료구조 생략(학교에서 학습)
- Deque 자료구조 -> 큐와 스택의 기능 모두 포함하고 있는 자료 구조
- Deque 자료구조에는 ArrayDeque, LinkedList가 있고, 주로 ArrayDeque사용 (시간복잡도 LinkedList보다 좋음)
- offerFirst(), offerLast(), pollFirst(), pollLast() 메서드들로 유연하게 사용가능
- Deque는 스택과 큐의 역할 모두 수행가능 및 큐, 스택의 메서드 이름까지 제공(push,pop,offer,poll)

