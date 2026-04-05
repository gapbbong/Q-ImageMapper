import google.generativeai as genai
import os

API_KEY = "AIzaSyBh0hjI2YNDaN2fKzMi1k5qU6J_PxfnPLI"
genai.configure(api_key=API_KEY)

print("--- Available Models ---")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print("Error listing models:", e)
