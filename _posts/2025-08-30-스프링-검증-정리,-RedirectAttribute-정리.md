---
layout: single
title: "스프링 검증 정리, RedirectAttribute 정리"
categories: [mvc2]
tags: [mvc2]
toc: true
author_profile: true
---

# ☕ Spring 공부 기록

## 📘 학습 날짜
- 2025-07

## 📅 오늘 배운 내용

### 1. 검증 개요

**컨트롤러의 중요한 역할 중 하나는 HTTP 요청이 정상인지 검증하는 것이다.**

---

- 클라이언트 검증은 조작할 수 있으므로 보안에 취약
- 서버만으로 검증하면, 고객의 사용성이 부족
- 적절히 섞어 사용하고, 최종 서버 검증은 필수
- API 방식 사용하면, API 스펙을 잘 정의해서 검증 오류를 API 응답 결과에 남겨주어야함

### 2. BindingResult

- 스프링이 제공하는 검증 오류를 보관하는 객체이다.
- BindingResult가 있으면 @ModelAttribute에 데이터 바인딩 시 오류 발생해도 컨트롤러 호출된다.
- BindingResult는 검증할 대상 바로 다음에 와야한다. (@ModelAttribute Item item, 바로 다음에 BindingResult bindingResult)
- BindingResult는 모델에 자동으로 포함

### 3. Bean Validation

- 검증 기능을 매번 코드로 작성하는 것은 상당히 번거롭다.
- 특정 필드에 대한 검증 로직은 대부분 빈 값인지 아닌지, 특정 크기를 넘는지 아닌지와 같은 매우 일반적인 로직임.
- 이런 검증 로직을 공통화하고 표준화 한 것이 바로 Bean Validation임.

--- 

- 사용하려면 의존관계 추가 필요
- implementation 'org.springframework.boot:spring-boot-starter-validation'
- @NotBlank - 빈 값 + 공백만 있는 경우 허용 안함
- @NotNull - null을 허용하지 않음
- @Range(min = 1000, max = 10000) - 범위 안의 값이어야함.
- @Max(9999) - 최대 9999까지만 허용
- 검증 시 @Valid 사용

---

**검증 순서**

- @ModelAttribute로 각각의 필드에 타입 변환 시도
    - 성공하면 다음으로, 실패하면 FieldError추가
- Validator 적용

- 바인딩에 성공한 필드만 Bean Validation이 적용된다. 
- ex) ItemName에 문자 "A" 입력 -> 타입 변환 성공 -> itemName 필드에 Bean Validation적용, price에 문자 "A" 입력 -> 타입 변환 실패 -> typeMismatch FieldError 추가 -> Bean Validation 적용 X

--- 

#### 3-1. Bean Validation 에러 메시지

Bean Validation이 기본으로 제공하는 오류 메시지를 좀 더 자세히 변경하고 싶다면? <br><br>

**에러 메시지 찾는 순서**

1. 생성된 메시지 코드 순서대로 messageSource에서 찾기
2. 애노테이션의 message 속성 -> @NotBlank(message = "공백X")
3. 라이브러리가 제공하는 기본 값 사용

---

**만약 등록과 수정 각각 다른 검증을 적용해야 한다면?**

- 폼 데이터 전달을 위한 별도의 객체 사용하여 검증 조건을 다르게 생성해 놓으면 된다.

```java
@Data
public class ItemSaveForm {
@NotBlank
private String itemName;
@NotNull
@Range(min = 1000, max = 1000000)
private Integer price;
@NotNull
@Max(value = 9999)
private Integer quantity;
}
// 저장용 폼이다
```

```java
@Data
public class ItemUpdateForm {
@NotNull
private Long id;
@NotBlank
private String itemName;
@NotNull
@Range(min = 1000, max = 1000000)
private Integer price;
//수정에서는 수량은 자유롭게 변경할 수 있다.
private Integer quantity;
}
// 수정용 폼이다.
```

```markdown
public String edit(@PathVariable Long itemId, @Validated
@ModelAttribute("item") ItemUpdateForm form, BindingResult bindingResult)

public String addItem(@Validated @ModelAttribute("item") ItemSaveForm form,
BindingResult bindingResult, RedirectAttributes redirectAttributes)

컨트롤러에서 이렇게 저장, 수정 각기 다른 폼 사용
```

--- 

# RedirectAttributes 정리

## 🔹 개념
- Spring MVC에서 **리다이렉트 시 데이터 전달**을 도와주는 클래스
- `Model`은 리다이렉트 시 사라지므로, 대신 사용

---

## 🔹 주요 메서드
### 1. `addAttribute(String name, Object value)`
- URL 쿼리 파라미터로 추가
- 예: `redirect:/items/{itemId}` → `/items/10?status=ok`

### 2. `addFlashAttribute(String name, Object value)`
- **세션에 임시 저장** → 다음 요청에서만 사용 가능
- 주로 1회성 메시지(등록 완료, 오류 알림 등)에 사용
- 요청이 끝나면 자동 삭제

---

## 🔹 사용 예시
```java
@PostMapping("/items/add")
public String addItem(
        @Validated @ModelAttribute("item") ItemSaveForm form,
        BindingResult bindingResult,
        RedirectAttributes redirectAttributes) {

    if (bindingResult.hasErrors()) {
        return "items/addForm";
    }

    Item item = itemService.save(form);

    redirectAttributes.addAttribute("itemId", item.getId());   // URL 파라미터
    redirectAttributes.addFlashAttribute("message", "상품이 등록되었습니다."); // 1회성 메시지

    return "redirect:/items/{itemId}";
}


