---
layout: single
title: "ArrayList"
categories: [java]
tags: [java, TIL]
toc: true
author_profile: true
sidebar:
  nav: "docs"
---

# ☕ Java 공부 기록

## 📘 학습 날짜
- 2025-06-25

## 📅 오늘 배운 내용

### ✨ 1. 배열의 특징 
- 배열에서 자료를 찾을때 index를 사용하여 매우 빠르게 자료를 찾을 수 있음 O(1)
- 배열에서의 검색 연산은 최악의 경우 O(n)
- 배열에 첫번째 위치에 데이터 루가 -> 모든 데이터를 한 칸씩 이동해야 하기 때문에 O(n)
- 중간 위치에 추가 -> index의 오른쪽에 있는 데이터를 모두 한 칸씩 이동해야함 O(n)
- 마지막 위치에 추가 -> 이동하지 않고 마지막 인덱스에 바로 접근하여 추가하면 되므로 O(1)

### ✨ 1-1. 배열의 한계
- 배열은 배열을 생성하는 시점에 크기를 미리 정해야함. 
- 배열의 길이를 동적으로 변경할 수 없고, 데이터를 추가하기 불편한 문제를 해소할 수 있는 자료 구조를 List라고 한다.
- 배열 : 순서가 있고 중복을 허용하지만 크기가 정적으로 고정
- 리스트 : 순서가 있고 중복을 허용하지만 크기가 동적으로 변할 수 있음

### ✨ 2. 구현한 배열 리스트 코드 정리
- 동적 배열 크기 구현
- 원하는 위치에 데이터 추가하는 기능
- 원하는 위치의 데이터를 삭제하는 기능
- 배열 리스트의 빅오 : 데이터 추가(마지막) O(1), 앞 중간 O(n), 데이터 삭제(마지막) O(1), 앞 중간 O(n), 인덱스 조회 O(1), 데이터 검색 O(n)
- 제네릭을 통한 타입 안전성 확보하는 배열 리스트 코드 구현
```java
package collection.array;

import java.util.Arrays;

public class MyArrayListV4<E> {

    private static final int DEFAULT_CAPACITY = 5;

    private Object[] elementData;
    private int size = 0;

    public MyArrayListV4() {
        elementData = new Object[DEFAULT_CAPACITY];
    }

    public MyArrayListV4(int initialCapacity) {
        elementData = new Object[initialCapacity];
    }


    public int size() {
        return size;
    }

    public void add(E e) {

        if (size == elementData.length) {
            grow();
        }
        elementData[size] = e;
        size++;
    }

    // 코드 추가

    public void add(int index, E e) {
        if (size == elementData.length) {
            grow();
        }
        // 데이터 이동
        shiftRightFrom(index);
        elementData[index] = e;
        size++;
    }

    // 코드 추가, 요소의 마지막부터 index까지 오른쪽으로 밀기
    private void shiftRightFrom(int index) {
        for (int i = size; i > index; i--) {
            elementData[i] = elementData[i - 1];
        }
    }

    private void grow() {
        int oldCapacity = elementData.length;
        int newCapacity = oldCapacity * 2;
        // 배열을 새로 만들고 기존 배열을 새로운 배열에 복사

        /*
        Object[] newArr = new Object[newCapacity];
        for (int i = 0; i < elementData.length; i++) {
            newArr[i] = elementData[i];
        }*/

        elementData = Arrays.copyOf(elementData, newCapacity);
    }

    @SuppressWarnings("unchecked")
    public E get(int index) {
        return (E) elementData[index];
    }

    public E set(int index, E element) {
        E oldValue = get(index);
        elementData[index] = element;
        return oldValue;
    }

    // 코드 추가
    public E remove(int index) {
        E oldValue = get(index);
        // 데이터 이동
        shiftLeftFrom(index);

        size--;
        elementData[size] = null;
        return oldValue;
    }

    // 코드 추가 요소의 index부터 마지막까지 왼족으로 밀기
    private void shiftLeftFrom(int index) {
        for (int i = index; i < size - 1; i++) {
            elementData[i] = elementData[i + 1];
        }
    }

    public int indexOf(E o) {
        for (int i = 0; i < size; i++) {
            if (o.equals(elementData[i])) {
                return i;
            }
        }
        return -1;
    }

    public String toString() {
        //[1,2,3,null.null] // size 3
        // [1,2,3] size 3
        return Arrays.toString(Arrays.copyOf(elementData, size)) + " size = " + size + ", capacity = " + elementData.length;
    }

}

```

### ✨ 3. ArrayList의 단점 
- 정확한 크기를 알지 못하면 메모리가 낭비됨(배열 뒷부분 사용 안되는 경우)
- 데이터를 중간에 추가하거나 삭제할 때 비효율적 O(n)
- 배열 리스트는 순서대로 마지막에 데이터를 추가, 삭제할 때는 성능 Good, But 앞이나 중간에 추가하거나 삭제할 때는 성능 Bad
- 이런 단점을 해결한 자료 구조인 LinkedList를 다음 강의에 배운다.