import os
import shutil
import re
from datetime import datetime

# ================= 사용자 설정 (경로 확인 필수!) =================
source_folder = "/Users/jihopark/IdeaProjects/Today-I-Learn/til"
target_folder = "./_posts"
# ==========================================================

def clean_title(text):
    # 1. 윈도우 금지 문자 제거
    text = re.sub(r'[\\/:*?"<>|]', '', text)
    # 2. 공백, 언더바 -> 하이픈
    text = text.replace(" ", "-").replace("_", "-")
    # 3. 중복 하이픈 제거
    text = re.sub(r'-+', '-', text).strip('-')
    return text

def parse_date_and_title(filename, file_path):
    # 확장자 제거
    name_no_ext = os.path.splitext(filename)[0]

    # 정규표현식: "YYYY-MM-DD-" 패턴이 맨 앞에 있는지 검사
    match = re.match(r'^(\d{4}-\d{2}-\d{2})-(.*)', name_no_ext)

    if match:
        # A. 파일명에 날짜가 이미 있는 경우 (예: 2025-05-31-제목.md)
        date_str = match.group(1)   # 2025-05-31
        pure_title = match.group(2) # 제목만 추출
    else:
        # B. 날짜가 없는 경우 -> 파일 생성일 사용
        creation_time = os.path.getctime(file_path)
        date_str = datetime.fromtimestamp(creation_time).strftime('%Y-%m-%d')
        pure_title = name_no_ext

    return date_str, clean_title(pure_title)

def migrate_smart():
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    count = 0

    for root, dirs, files in os.walk(source_folder):
        for filename in files:
            if filename.endswith(".md"):
                if ".git" in root or ".idea" in root:
                    continue

                file_path = os.path.join(root, filename)
                category = os.path.basename(root)
                if category.lower() == "til":
                    category = "TIL"

                # ★ 날짜와 제목을 분리하는 똑똑한 함수 호출
                date_str, safe_title = parse_date_and_title(filename, file_path)

                # 최종 파일명: YYYY-MM-DD-제목.md
                new_filename = f"{date_str}-{safe_title}.md"
                target_path = os.path.join(target_folder, new_filename)

                # Front Matter 작성 (제목에 날짜가 중복되지 않게 safe_title 사용)
                front_matter = f"""---
layout: single
title: "{safe_title.replace('-', ' ')}"
categories: [{category}]
tags: [{category}, TIL]
toc: true
author_profile: true
sidebar:
  nav: "docs"
---

"""
                try:
                    with open(file_path, 'r', encoding='utf-8') as f_in:
                        content = f_in.read()

                    with open(target_path, 'w', encoding='utf-8') as f_out:
                        f_out.write(front_matter + content)

                    print(f"✅ {filename} -> {new_filename}")
                    count += 1
                except Exception as e:
                    print(f"❌ 실패 {filename}: {e}")

    print(f"\n🎉 총 {count}개 처리 완료!")

if __name__ == "__main__":
    migrate_smart()