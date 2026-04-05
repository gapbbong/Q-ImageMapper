import google.generativeai as genai

API_KEY = "AIzaSyBh0hjI2YNDaN2fKzMi1k5qU6J_PxfnPLI"
genai.configure(api_key=API_KEY)

models_to_try = ["gemini-2.5-flash-lite", "gemini-3-flash-preview", "gemini-flash-latest"]

for m_name in models_to_try:
    print(f"Trying model: {m_name}")
    try:
        model = genai.GenerativeModel(m_name)
        response = model.generate_content("Hello")
        print(f"Success with {m_name}: {response.text[:20]}...")
        break
    except Exception as e:
        print(f"Failed with {m_name}: {e}")
