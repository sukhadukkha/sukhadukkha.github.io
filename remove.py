import os

# ================= 사용자 설정 =================
target_folder = "./_posts"  # 포스트가 있는 폴더
# ===========================================

def clean_front_matter():
    if not os.path.exists(target_folder):
        print(f"❌ '{target_folder}' 폴더를 찾을 수 없습니다.")
        return

    count = 0
    
    # _posts 폴더 내의 모든 파일 순회
    for filename in os.listdir(target_folder):
        if filename.endswith(".md"):
            file_path = os.path.join(target_folder, filename)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            new_lines = []
            is_modified = False
            
            for line in lines:
                # 삭제할 문자열이 포함된 줄인지 확인
                # 공백을 제거한 후 비교하여 정확도 높임
                stripped_line = line.strip()
                
                if stripped_line == 'sidebar:' or stripped_line == 'nav: "docs"':
                    is_modified = True
                    continue # 이 줄은 리스트에 담지 않고 건너뜀 (삭제 효과)
                
                new_lines.append(line)
            
            # 변경된 내용이 있을 때만 파일 다시 쓰기
            if is_modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                print(f"✅ 수정됨: {filename}")
                count += 1
            else:
                # 이미 수정되었거나 해당 구문이 없는 경우
                pass

    print(f"\n🎉 총 {count}개의 파일에서 sidebar 설정을 제거했습니다!")

if __name__ == "__main__":
    clean_front_matter()
