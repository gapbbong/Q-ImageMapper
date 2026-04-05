import json
import re
import os

def clean_text(text):
    if not text:
        return ""
    # Remove [cite: ...] and [cite_start]
    text = re.sub(r'\[cite:.*?\]', '', text)
    text = re.sub(r'\[cite_start\]', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def add_image_tag(question_text):
    img_keywords = ["그림", "회로", "곡선", "다음과 같은", "그래프", "브리지", "어드미턴스", "리액턴스"]
    if any(kw in question_text for kw in img_keywords):
        if "[그림 참고]" not in question_text:
            return f"{question_text} [그림 참고]"
    return question_text

def parse_generic(content, q_pattern, opt_pattern, ans_pattern, exp_pattern, round_str, year=2015):
    questions_dict = {}
    
    # Pre-clean citations for easier matching
    content = re.sub(r'\[cite:.*?\]', '', content)
    content = re.sub(r'\[cite_start\]', '', content)
    
    matches = list(re.finditer(q_pattern, content, re.MULTILINE | re.DOTALL))
    
    for i, match in enumerate(matches):
        q_num = int(match.group(1))
        start_pos = match.end()
        end_pos = matches[i+1].start() if i + 1 < len(matches) else len(content)
        block = content[start_pos:end_pos]
        
        # Question text is often in the header match itself or right after
        q_text_raw = match.group(2) if len(match.groups()) >= 2 else ""
        if not q_text_raw:
             # Try to find question text in the block before options
             q_text_match = re.search(r'^(.*?)(?=\n\*|\n\s*①|\n\s*1\.|\Z)', block, re.DOTALL)
             q_text_raw = q_text_match.group(1) if q_text_match else ""
        
        question = clean_text(q_text_raw)
        
        # Options
        options = []
        opt_matches = re.findall(opt_pattern, block)
        if opt_matches:
            # Flatten if nested
            opts = []
            for m in opt_matches:
                if isinstance(m, tuple): opts.extend(m)
                else: opts.append(m)
            options = [clean_text(o) for o in opts if o.strip()][:4]
        
        # Answer
        ans_match = re.search(ans_pattern, block)
        answer = 0
        if ans_match:
            ans_str = ans_match.group(1)
            ans_map = {'①': 1, '②': 2, '③': 3, '④': 4, '1': 1, '2': 2, '3': 3, '4': 4}
            answer = ans_map.get(ans_str[0], 0)
            
        # Explanation
        exp_match = re.search(exp_pattern, block, re.DOTALL)
        explanation = clean_text(exp_match.group(1)) if exp_match else ""
        
        questions_dict[q_num] = {
            "id": f"{year}_{round_str}_{q_num}",
            "year": year,
            "round": round_str,
            "question_num": q_num,
            "question": add_image_tag(question),
            "options": options,
            "answer": answer,
            "explanation": explanation,
            "level": "하"
        }
    
    # Sort by number
    return [questions_dict[n] for n in sorted(questions_dict.keys())]

def main():
    data_dir = "e:/3D studies/Dukigo+/data"
    
    # Round 01: ## **(\d+)\. Title** and **문제:** ...
    with open(os.path.join(data_dir, "2015_01.txt"), 'r', encoding='utf-8') as f:
        content = f.read()
        questions = parse_generic(
            content,
            q_pattern=r'## \*\*(\d+)\. (.*?)\*\*',
            opt_pattern=r'^\s*\d\.\s*(.*?)(?=\n\s*\d\.|\n\*|\Z)',
            ans_pattern=r'\*\*정답:\*\* \*\*(.*?)\*\*',
            exp_pattern=r'\*\*해설.*?\*\* (.*?)(?=\n\* \*\*정답|\n---|\Z)',
            round_str="01"
        )
        with open(os.path.join(data_dir, "2015_01_questions.json"), 'w', encoding='utf-8') as out:
            json.dump(questions, out, ensure_ascii=False, indent=2)

    # Round 02: **(\d+)\s+Question Text**
    with open(os.path.join(data_dir, "2015_02.txt"), 'r', encoding='utf-8') as f:
        content = f.read()
        questions = parse_generic(
            content,
            q_pattern=r'\*\*(\d{2})\s+(.*?)\*\*',
            opt_pattern=r'[①-④]\s*(.*?)(?=[①-④]|\Z|\n\*)',
            ans_pattern=r'\*\*정답:\s*([①-④])',
            exp_pattern=r'\[해설\] (.*?)(?=\n\*\*정답|\Z)',
            round_str="02"
        )
        with open(os.path.join(data_dir, "2015_02_questions.json"), 'w', encoding='utf-8') as out:
            json.dump(questions, out, ensure_ascii=False, indent=2)

    # Round 04 (2015_03.txt): ### **(\d+) Question Text**
    with open(os.path.join(data_dir, "2015_03.txt"), 'r', encoding='utf-8') as f:
        content = f.read()
        questions = parse_generic(
            content,
            q_pattern=r'### \*\*(\d+)\s+(.*?)\*\*',
            opt_pattern=r'[①-④]\s*(.*?)(?=[①-④]|\Z|\n\*)',
            ans_pattern=r'\*\*정답:\*\* ([①-④])',
            exp_pattern=r'\*\*해설:\*\* (.*?)(?=\n\*|\n---|\Z)',
            round_str="04"
        )
        with open(os.path.join(data_dir, "2015_04_questions.json"), 'w', encoding='utf-8') as out:
            json.dump(questions, out, ensure_ascii=False, indent=2)

    # Round 05 (2015_04.txt): **(\d{2})\. Question Text**
    with open(os.path.join(data_dir, "2015_04.txt"), 'r', encoding='utf-8') as f:
        content = f.read()
        questions = parse_generic(
            content,
            q_pattern=r'\*\*(\d{2})\.\s+(.*?)\*\*',
            opt_pattern=r'[①-④]\s*(.*?)(?=[①-④]|\Z|\n\*)',
            ans_pattern=r'\*\*정답:\*\* ([①-④])',
            exp_pattern=r'\*\*해설:\*\* (.*?)(?=\n\*|\n---|\Z)',
            round_str="05"
        )
        with open(os.path.join(data_dir, "2015_05_questions.json"), 'w', encoding='utf-8') as out:
            json.dump(questions, out, ensure_ascii=False, indent=2)

    print("Re-conversion completed with improved patterns.")

if __name__ == "__main__":
    main()
