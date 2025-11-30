---
layout: single
title: "LinkedList"
categories: [java]
tags: [java]
toc: true
author_profile: true
---

# ☕ Java 공부 기록

## 📘 학습 날짜
- 2025-06-26

## 📅 오늘 배운 내용
- 이번 장에서는 배열리스트의 단점인 배열의 크기를 미리 확보해야 하는 문제와 <br> 배열의 앞이나 중간에 데이터를 추가한다면 기존 데이터를 오른쪽으로 모두 이동, 삭제하기 위해서는 왼쪽으로 이동해야 하는 성능상의 문제를 해결하기 위한 LinkedList를 구현해보았다.

### ✨ 1. LinkedList란 ? 
- 연결리스트는 배열 리스트의 단점인 메모리낭비, 중간 위치의 데이터 추가에 대한 성능 문제를 어느정도 극볼할 수 있다.
- 순서가 있고, 중복을 허용하는 자료 구조를 List라고 한다.
- 배열 리스트를 사용하든, 연결 리스트를 사용하든, 둘 다 리스트 자료구조이기 때문에 리스트를 사용하는 개발자 입장에서는 거의 비슷하게 느껴져야 한다.

### ✨ 2.  연결 리스트와 빅오
- 인덱스 조회 O(n)
- 검색 O(n)
- 앞에 추가(삭제) O(1)
- 뒤에 추가(삭제) O(n)
- 평균 추가(삭제) O(n)
- 배열 리스트는 인덱스를 통해 추가나 삭제할 위치를 O(1)로 빠르게 찾지만, 추가나 삭제 이후에 데이터를 한 칸씩 밀어야 할 때 O(n)이 걸린다.
- 반면 연결리스트는 인덱스를 통해 추가나 삭제할 위치를 O(n)으로 느리게 찾지만, 찾은 이후에 일부 노드의 참조값만 변경하면 되므로 이부분이 O(1)로 빠르다.
- 데이터를 조회할 일이 많고, 뒷 부분에 데이터를 추가한다면 배열 리스트가 더 좋은 성능을 제공한다. 
- 앞쪽의 데이터를 추가하거나, 삭제할 일이 만다면 연결리스트를 사용하는 것이 보통 더 좋은 성능을 제공한다.

### ✨ 3. 구현해본 코드

```java
package list;

public class MyLinkedListV3<E> {

    private Node<E> first;
    private int size = 0;


    public void add(E e) {
        Node<E> newNode = new Node<>(e);
        if (first == null) {
            first = newNode;
        } else {
            Node<E> lastNode = getLastNode();
            lastNode.next = newNode;
        }
        size++;

    }

    // 코드 추가
    public void add(int index, E e) {
        Node<E> newNode = new Node<>(e);
        if (index == 0) {
            newNode.next = first;
            first = newNode;
        } else {
            Node<E> prev = getNode(index - 1);
            newNode.next = prev.next;
            prev.next = newNode;
        }
        size++;
    }

    // 추가 코드
    public E remove(int index) {
        Node<E> removeNode = getNode(index);
        E removedItem = removeNode.item;
        if (index == 0) {
            first = removeNode.next;
        } else {
            Node<E> prev = getNode(index - 1);
            prev.next = removeNode.next;

        }

        removeNode.item = null;
        removeNode.next = null;
        size--;
        return removedItem;
    }

    private Node<E> getLastNode() {
        Node<E> x = first;
       /* for (int i = 0; i < size; i++) {
            x = x.next;
        }*/
        while (x.next != null) {
            x = x.next;
        }
        return x;
    }

    public E set(int index, E element) {
        Node<E> x = getNode(index);
        E oldValue = x.item;
        x.item = element;
        return oldValue;
    }

    public E get(int index) {
        Node<E> node = getNode(index);
        return node.item;
    }

    private Node<E> getNode(int index) {
        Node<E> x = first;
        for (int i = 0; i < index; i++) {
            x = x.next;
        }
        return x;
    }

    public int indexOf(E o) {
        int index = 0;
        for (Node<E> x = first; x != null; x = x.next) {
            if (o.equals(x.item)){
                return index;
            }
            index++;
        }
        return -1;
    }

    public int size() {
        return size;
    }

    @Override
    public String toString() {
        return "MyLinkedListV1{" +
                "first=" + first +
                ", size=" + size +
                '}';
    }

    private static class Node<E> {

        E item;
        Node<E> next;

        public Node(E item) {
            this.item = item;
        }

        @Override
        public String toString() {
            StringBuilder sb = new StringBuilder();
            Node<E> x = this;
            sb.append("[");
            while (x != null) {
                sb.append(x.item);
                if (x.next != null) {
                    sb.append("->");
                }
                x = x.next;
            }
            sb.append("]");
            return sb.toString();
        }
    }
}

```

- 다음에는 자바에서 제공하는 List를 배워볼 것이다.