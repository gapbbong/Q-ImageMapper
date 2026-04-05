import json
import os
import glob
from pathlib import Path

# 설정 (경로에 맞게 수정)
SOURCE_DIR = r"E:\DugiGo\client\src\data"
OUTPUT_FILE = r"e:\3D studies\Dukigo+\supabase\all_exams_data.sql"

def escape_sql(text):
    if text is None:
        return 'NULL'
    if not isinstance(text, str):
        text = str(text)
    # SQL에서 '는 ''로 치환
    return text.replace("'", "''")

def main():
    # 모든 JSON 파일 찾기 (questions.json으로 끝나는 파일들)
    json_files = glob.glob(os.path.join(SOURCE_DIR, "*_questions.json"))
    
    print(f"발견된 파일 수: {len(json_files)}")
    
    sql_statements = []
    
    # 1. 기존 데이터 초기화 (선택 사항 - 필요시 주석 해제)
    sql_statements.append("-- [주의] 기존 가짜 데이터를 포함한 모든 기출문제 데이터를 초기화합니다.")
    sql_statements.append("TRUNCATE TABLE public.dukigo_exam_questions;")
    sql_statements.append("")

    total_count = 0

    for file_path in json_files:
        filename = os.path.basename(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if not isinstance(data, list):
                print(f"[Warn] {filename} is not a list. Skipping.")
                continue

            print(f"처리 중: {filename} ({len(data)} 문항)")
            
            for item in data:
                # 필수 필드 추출
                year = item.get('year', 0)
                # round가 문자열 "01" 등으로 올 수 있으므로 정수화 시도
                round_val = str(item.get('round', '1'))
                try:
                    round_int = int(round_val)
                except:
                    round_int = 1
                
                question_num = item.get('question_num', 0)
                question_text = escape_sql(item.get('question', ''))
                options = item.get('options', [])
                correct_answer = str(item.get('answer', '1'))
                explanation = escape_sql(item.get('explanation', ''))
                
                # options를 JSON 문자열로 변환 (ensure_ascii=False로 한글/특수문자 보존)
                options_json = escape_sql(json.dumps(options, ensure_ascii=False))
                
                # INSERT 문 생성 (id는 gen_random_uuid() 자동 생성)
                sql = (
                    f"INSERT INTO public.dukigo_exam_questions (category, year, round, question_number, question_text, options, correct_answer, explanation) "
                    f"VALUES ('ELECTRICITY', {year}, {round_int}, {question_num}, '{question_text}', '{options_json}'::jsonb, '{correct_answer}', '{explanation}');"
                )
                sql_statements.append(sql)
                total_count += 1
                
        except Exception as e:
            print(f"[Error] {filename} 처리 중 오류 발생: {e}")

    # 파일 저장
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(sql_statements))
    
    print("-" * 30)
    print(f"성공! 총 {total_count}개 문항이 통합되었습니다.")
    print(f"출력 파일: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
