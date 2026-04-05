import sys
import os
import json
from PIL import Image
import google.generativeai as genai
import pydantic
import typing

API_KEY = "AIzaSyBh0hjI2YNDaN2fKzMi1k5qU6J_PxfnPLI"
genai.configure(api_key=API_KEY)

class QuestionOutput(pydantic.BaseModel):
    question_no: int
    question_text: str
    has_question_image: bool
    question_image_bbox: typing.List[int]
    choices: dict[str, str]
    answer: int
    explanation: str
    level: str

model = genai.GenerativeModel(
    model_name="gemini-flash-latest",
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": list[QuestionOutput]
    }
)

img_path = r"d:\App\Q-ImageMapper\exam_extractor\output\images\ElectricExam2019_파트004\page_001_left.png"

try:
    img = Image.open(img_path)
    prompt = r"""당신은 고도로 정밀한 시험 문제 추출 전문가입니다. 
1. 그림 감지: 그림이 존재할 경우 해당 이미지(회로도/표 포함) 영역의 [상, 좌, 하, 우] 경계 상자(Bounding Box) 좌표를 0~1000 범위의 정규화된 좌표계로 판별하여 question_image_bbox에 반환하세요. 그림이 없으면 [0,0,0,0]을 반환합니다.
"""
    response = model.generate_content([img, prompt])
    print(response.text)
except Exception as e:
    print("Error:", e)
