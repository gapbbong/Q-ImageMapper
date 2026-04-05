# 28개 기출문제 JSON 통합 마이그레이션 최종 보정판 (PowerShell)
# DB 컬럼명 매칭: subject_id, exam_year, exam_round, question_no

$SourcePathPattern = "E:\DugiGo\client\src\data\*_questions.json"
$OutputFilePath = "e:\3D studies\Dukigo+\supabase\all_exams_data.sql"

# 파일 목록 확보
$Files = Get-ChildItem -Path $SourcePathPattern
Write-Output "Found Files: $($Files.Count)"

$SqlList = New-Object System.Collections.Generic.List[string]
$SqlList.Add("-- [FINAL] Integrated Exam Data (28 Files)")
$SqlList.Add("TRUNCATE TABLE public.dukigo_exam_questions;")

foreach ($File in $Files) {
    Write-Output "Processing: $($File.Name)"
    
    try {
        $Raw = Get-Content -Path $File.FullName -Raw -Encoding UTF8
        $Data = $Raw | ConvertFrom-Json
        
        foreach ($Item in $Data) {
            $year = if ($Item.year) { $Item.year } else { 0 }
            $roundRaw = if ($Item.round) { $Item.round.ToString() } else { "1" }
            $round = 1
            [int]::TryParse($roundRaw, [ref]$round) | Out-Null
            $qNum = if ($Item.question_num) { $Item.question_num } else { 0 }
            
            # SQL Escape
            $qText = if ($Item.question) { $Item.question.Replace("'", "''") } else { "" }
            $expl = if ($Item.explanation) { $Item.explanation.Replace("'", "''") } else { "" }
            $ans = if ($Item.answer) { $Item.answer.ToString() } else { "1" }
            $optsRaw = if ($Item.options) { ($Item.options | ConvertTo-Json -Compress) } else { "[]" }
            $optsJson = $optsRaw.Replace("'", "''")
            
            # 실제 DB 컬럼명 매칭: subject_id, exam_year, exam_round, question_no
            $sqlTemplate = "INSERT INTO public.dukigo_exam_questions (subject_id, exam_year, exam_round, question_no, question_text, options, correct_answer, explanation) VALUES ('ELECTRICITY', {0}, {1}, {2}, '{3}', '{4}'::jsonb, '{5}', '{6}');"
            $sql = $sqlTemplate -f $year, $round, $qNum, $qText, $optsJson, $ans, $expl
            
            $SqlList.Add($sql)
        }
    } catch {
        Write-Output "Error in $($File.Name): $($_.Exception.Message)"
    }
}

# UTF8 저장 (BOM 없이 확실하게 저장하기 위해 Set-Content 사용)
Set-Content -Path $OutputFilePath -Value $SqlList -Encoding UTF8

Write-Output "Success! Total Count: $($SqlList.Count - 2)"
Write-Output "Output: $OutputFilePath"
