#!/usr/bin/env python3
import os
import re
from pathlib import Path


def remove_til_from_tags(file_path):
    """
    마크다운 파일의 front matter에서 tags에 있는 TIL을 제거합니다.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Front matter의 tags 라인을 찾아서 TIL 제거
    # tags: [java, TIL] -> tags: [java]
    # tags: [TIL, java] -> tags: [java]
    # tags: [TIL] -> tags: []

    def replace_tags(match):
        tags_line = match.group(0)

        # TIL을 제거
        # 쉼표와 공백도 함께 처리
        tags_line = re.sub(r',\s*TIL', '', tags_line)  # , TIL 제거
        tags_line = re.sub(r'TIL\s*,\s*', '', tags_line)  # TIL, 제거
        tags_line = re.sub(r'\[TIL\]', '[]', tags_line)  # [TIL] -> []

        return tags_line

    # tags: [...] 패턴을 찾아서 치환
    new_content = re.sub(r'tags:\s*\[.*?\]', replace_tags, content)

    # 파일이 변경되었는지 확인
    if content != new_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False


def main():
    """
    _posts 디렉토리의 모든 마크다운 파일에서 TIL 태그를 제거합니다.
    """
    posts_dir = Path('_posts')

    if not posts_dir.exists():
        print(f"Error: {posts_dir} 디렉토리를 찾을 수 없습니다.")
        return

    modified_files = []

    # _posts 디렉토리의 모든 .md 파일 처리
    for md_file in posts_dir.glob('*.md'):
        if remove_til_from_tags(md_file):
            modified_files.append(md_file.name)
            print(f"✓ {md_file.name}")

    # 결과 출력
    print(f"\n총 {len(modified_files)}개 파일에서 TIL 태그를 제거했습니다.")

    if not modified_files:
        print("TIL 태그가 포함된 파일이 없습니다.")


if __name__ == '__main__':
    main()