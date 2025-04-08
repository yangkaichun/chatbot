import os
import PyPDF2 # Library for reading PDFs
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS # Needed for requests from browser JS

# --- Configuration ---
# Load API key from environment variable
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    # If running directly in some IDEs, you might need to set it differently
    # or temporarily hardcode for testing (NOT RECOMMENDED for production)
    # API_KEY = "YOUR_API_KEY_HERE" # Replace with your actual key only for local testing
    print("Warning: GEMINI_API_KEY environment variable not found. Attempting to proceed without it or using a placeholder if set above.")
    # raise ValueError("GEMINI_API_KEY environment variable not set. Please set it before running.")
    # For now, we allow it to proceed but Gemini call will likely fail without a key.

if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
    except Exception as e:
        print(f"Error configuring Generative AI: {e}")
        # Handle cases where the key might be invalid format

# Make sure this path points to your PDF file
PDF_PATH = "推薦掛號Source.pdf"

# --- PDF Text Extraction ---
def extract_text_from_pdf(pdf_path):
    """Extracts text from all pages of a PDF file."""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            num_pages = len(reader.pages)
            print(f"Reading {num_pages} pages from {pdf_path}...")
            for page_num in range(num_pages):
                page = reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n" # Add newline between pages
            print(f"Finished reading PDF. Total characters: {len(text)}")
        return text
    except FileNotFoundError:
        print(f"Error: PDF file not found at '{pdf_path}'")
        return f"錯誤：無法找到 PDF 文件於 {pdf_path}"
    except Exception as e:
        print(f"Error reading PDF file '{pdf_path}': {e}")
        return f"錯誤：讀取 PDF 文件時發生問題: {e}"

# --- Generative AI Interaction ---
# Initialize the model (use a model suitable for free tier if necessary)
# Check Google AI documentation for available models
try:
    # Ensure API key is configured before creating the model
    if API_KEY and genai.API_KEY:
         model = genai.GenerativeModel('gemini-1.5-flash-latest') # Use a fast, potentially free-tier eligible model
         print("Gemini model initialized.")
    else:
         model = None
         print("Gemini model initialization skipped due to missing API key.")
except Exception as e:
    print(f"Error initializing Gemini model: {e}")
    model = None

def get_department_recommendation(symptoms, pdf_knowledge):
    """Uses Generative AI to get department recommendation based on symptoms and PDF text."""
    if not model:
        return {"department": "AI 模型錯誤", "reason": "無法初始化 AI 模型，請檢查 API 金鑰設定。"}
    if pdf_knowledge.startswith("錯誤："):
         return {"department": "系統錯誤", "reason": pdf_knowledge} # Return PDF loading error

    # --- Carefully Crafted Prompt ---
    prompt = f"""
    任務：您是一位協助分析症狀並根據提供的「醫院掛號指南」文字內容，推薦適合掛號科別的助理。

    可用資訊：
    1.  使用者描述的症狀： "{symptoms}"
    2.  醫院掛號指南文字內容（來源：PDF 文件）：
        --- 開始 指南文字 ---
        {pdf_knowledge[:10000]}
        --- 結束 指南文字 ---
        (注意：為了效率，可能只截取了部分指南內容)

    指示：
    1.  請**嚴格且僅**根據上方提供的「醫院掛號指南文字內容」進行分析。
    2.  找出與使用者症狀「{symptoms}」最相關、最適合掛號的**單一個**「科別」或「部門」。
    3.  簡要說明推薦此科別的原因，**必須**是基於指南中的資訊。
    4.  如果指南文字中**明確找不到**與症狀相關的科別資訊，請回答「根據提供的掛號指南，無法確定具體科別，建議諮詢醫院服務台或專業醫師。」
    5.  **禁止**使用任何外部知識、網路搜尋結果或個人醫療經驗。
    6.  **禁止**提供任何醫療建議、診斷或治療方案。僅提供科別建議及基於文件的理由。
    7.  回答必須使用繁體中文。
    8.  請使用以下格式回覆：
        建議掛號科別：[科別名稱]
        原因：[根據指南內容的簡短說明]

    範例回覆：
    建議掛號科別：心臟內科
    原因：指南中提到胸悶、心悸等症狀建議看心臟內科。

    或 (如果找不到)：
    建議掛號科別：無法確定
    原因：根據提供的掛號指南，無法確定具體科別，建議諮詢醫院服務台或專業醫師。

    請開始分析並回覆：
    """

    try:
        # Generate content with safety settings to reduce chances of harmful content
        response = model.generate_content(
            prompt,
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
            )

        # --- Response Parsing ---
        recommendation_text = response.text.strip()
        print(f"AI Raw Response:\n---\n{recommendation_text}\n---") # Log raw response for debugging

        department = "無法判斷"
        reason = "無法從 AI 回應中解析結果。" # Default error reason

        # Simple parsing based on the requested format
        lines = recommendation_text.split('\n', 1) # Split only on the first newline
        if len(lines) > 0 and lines[0].startswith("建議掛號科別："):
            department = lines[0].replace("建議掛號科別：", "").strip()
            if len(lines) > 1 and lines[1].startswith("原因："):
                reason = lines[1].replace("原因：", "").strip()
            elif "無法確定" in department: # Handle the "cannot determine" case
                 reason = recommendation_text # Use the full text as reason
            else:
                 # If reason is missing or format is slightly off, try to provide context
                 reason = f"AI 建議 '{department}'，但未提供明確原因或格式不符。請參考原始回應: {recommendation_text}"

        elif "無法確定具體科別" in recommendation_text:
             department = "無法確定"
             reason = recommendation_text # Use the full text for this specific message
        else:
            # If the format is completely different, return the raw text as reason
            department = "格式不符"
            reason = f"AI 回應格式不符合預期，原始回應：{recommendation_text}"
            print(f"Warning: AI response format unexpected: {recommendation_text}")


        # Add a disclaimer
        reason += "\n\n**免責聲明：此建議僅基於提供的文件內容分析，不能取代專業醫師的診斷。如有疑問，請務必諮詢醫師。**"

        return {"department": department, "reason": reason}

    except Exception as e:
        print(f"Error calling Generative AI API or processing response: {e}")
        # Check for specific API errors if possible (e.g., rate limits, auth)
        error_message = f"呼叫 AI 模型時發生錯誤: {e}"
        if "API key not valid" in str(e):
             error_message = "AI API 金鑰無效或未設定，請檢查環境變數。"
        elif " épuisé " in str(e) or "quota" in str(e).lower(): # French/English for quota
             error_message = "AI API 使用額度可能已達上限。"

        return {"department": "AI 錯誤", "reason": error_message + "\n\n**免責聲明：此建議僅基於提供的文件內容分析，不能取代專業醫師的診斷。如有疑問，請務必諮詢醫師。**"}

# --- Flask Application Setup ---
app = Flask(__name__)
# Enable CORS for requests from the frontend (running as file:// or different port)
# For production, restrict the origins allowed: CORS(app, origins=["your_frontend_domain"])

frontend_origin = "https://yangkaichun.github.io" # <--- 替換成你的 GitHub Pages URL (沒有結尾的 /)
CORS(app, origins=[frontend_origin], supports_credentials=True) # 只允許你的前端來源
# --- Load PDF content when the Flask app starts ---
print("Initializing backend...")
PDF_KNOWLEDGE_BASE = extract_text_from_pdf(PDF_PATH)
if len(PDF_KNOWLEDGE_BASE) < 100 and not PDF_KNOWLEDGE_BASE.startswith("錯誤："): # Arbitrary short length check
    print("Warning: Extracted PDF text seems very short. Check PDF content and extraction logic.")


# --- API Endpoint ---
@app.route('/recommend', methods=['POST'])
def recommend_department():
    """API endpoint to receive symptoms and return department recommendation."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    symptoms = data.get('symptoms')

    if not symptoms:
        return jsonify({"error": "Missing 'symptoms' in request body"}), 400

    if PDF_KNOWLEDGE_BASE.startswith("錯誤："):
         # Return error if PDF failed to load during startup
         return jsonify({"department": "系統設定錯誤", "reason": PDF_KNOWLEDGE_BASE}), 500

    print(f"Received symptoms: {symptoms}")
    recommendation = get_department_recommendation(symptoms, PDF_KNOWLEDGE_BASE)
    print(f"Sending recommendation: {recommendation}")

    return jsonify(recommendation)

# --- Run the Application ---
if __name__ == '__main__':
    # Use host='0.0.0.0' to make the server accessible on your network
    # Default port is 5000, change if needed (e.g., port=5001)
    print("Starting Flask server on http://127.0.0.1:5000")
    print("Ensure the frontend JavaScript points to this address.")
    app.run(debug=True, host='0.0.0.0', port=5000) # debug=True for development ONLY
