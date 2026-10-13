"""
MAIN - Complete Flask API Server
ULTIMATE RAG CHATBOT with all features
- Document Q&A with Hallucination Detection
- Employee Analytics
- CSV Dataset Upload & Analysis
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL
from layer3_aro import retrieve_with_analysis
from layer4_hdp import check
from layer5_analytics import is_analytics_question, answer_analytics_question
from layer7_data_analyzer import load_dataset, is_data_question, answer_data_question
from layer6_csv_processor import csv_processor
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
CORS(app)

client = Groq(api_key=GROQ_API_KEY)

# File upload settings
UPLOAD_FOLDER = './uploaded_files'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

current_dataset = None


def build_prompt(question, chunks):
    """Build prompt with context from retrieved documents"""
    context = "\n\n".join([
        f"[{c['metadata']['department']}]\n{c['content']}"
        for c in chunks
    ])
    return f"""You are a helpful company assistant. Answer using ONLY the context provided.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:"""


def generate_answer(question, chunks):
    """Generate answer using Groq LLaMA"""
    prompt = build_prompt(question, chunks)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1024
    )
    return response.choices[0].message.content.strip()


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Ultimate RAG Chatbot",
        "current_dataset": current_dataset
    }), 200


@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload CSV/Excel dataset"""
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "message": "No file selected"}), 400
        
        if not any(file.filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            return jsonify({"status": "error", "message": "Only CSV, XLSX, XLS files allowed"}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        df, error = load_dataset(filepath, filename)
        if error:
            return jsonify({"status": "error", "message": error}), 400
        
        global current_dataset
        current_dataset = filename
        summary = csv_processor.get_file_summary(df)
        
        print(f"Loaded dataset: {filename}")
        print(f"  Rows: {summary['rows']}")
        print(f"  Columns: {summary['columns']}")
        
        return jsonify({
            "status": "success",
            "message": f"Dataset '{filename}' uploaded!",
            "filename": filename,
            "summary": summary
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/datasets', methods=['GET'])
def list_datasets():
    """List uploaded datasets"""
    try:
        files = []
        if os.path.exists(app.config['UPLOAD_FOLDER']):
            files = [f for f in os.listdir(app.config['UPLOAD_FOLDER'])
                    if f.endswith(('.csv', '.xlsx', '.xls'))]
        return jsonify({
            "status": "success",
            "datasets": files,
            "current": current_dataset
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/ask', methods=['POST'])
def ask():
    """Main Q&A endpoint with intelligent routing and hallucination detection"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({"status": "error", "message": "Empty question"}), 400
        
        print(f"\n{'='*60}")
        print(f"Q: {question}")
        print(f"Current Dataset: {current_dataset}")
        print(f"{'='*60}")
        
        # LAYER 7: DATASET ANALYSIS (if uploaded)
        if current_dataset and is_data_question(question):
            print("[LAYER 7] Analyzing uploaded dataset...")
            data_answer = answer_data_question(question, current_dataset)
            if data_answer and "Could not" not in data_answer and "I could not" not in data_answer:
                return jsonify({
                    "status": "success",
                    "question": question,
                    "answer": data_answer,
                    "confidence": 1.0,
                    "verification_status": "verified",
                    "query_type": "data_analysis",
                    "sources": [{"id": current_dataset}],
                    "metadata": {
                        "mode": "Dataset Analysis",
                        "dataset": current_dataset
                    }
                }), 200
        
        # LAYER 5: COMPANY ANALYTICS
        if is_analytics_question(question):
            print("[LAYER 5] Analyzing company data...")
            analytics_answer = answer_analytics_question(question)
            if analytics_answer:
                return jsonify({
                    "status": "success",
                    "question": question,
                    "answer": analytics_answer,
                    "confidence": 1.0,
                    "verification_status": "verified",
                    "query_type": "analytics",
                    "sources": [],
                    "metadata": {"mode": "Company Analytics"}
                }), 200
        
        # LAYER 3: DOCUMENT SEARCH
        print("[LAYER 3] Retrieving documents...")
        retrieval = retrieve_with_analysis(question)
        chunks = retrieval['results']
        
        if not chunks:
            return jsonify({
                "status": "success",
                "question": question,
                "answer": "I cannot find a reliable answer to this question in our company documents.",
                "confidence": 0.0,
                "verification_status": "refused",
                "sources": [],
                "metadata": {"mode": "Document Search"}
            }), 200
        
        # GENERATE ANSWER
        print("[LLaMA] Generating answer...")
        raw_answer = generate_answer(question, chunks)
        
        # VERIFY ANSWER (LAYER 4 - HALLUCINATION DETECTION)
        print("[LAYER 4] Verifying answer...")
        hdp_result = check(raw_answer, chunks)
        
        # Build clear answer based on verification status
        status = hdp_result.get('status')
        confidence = hdp_result.get('confidence', 0.0)
        
        if status == 'refused':
            final_answer = f"I cannot find a reliable answer to this question. The system has refused to answer to prevent potentially incorrect information. (Confidence: {confidence:.0%})"
        elif status == 'warning':
            answer_text = hdp_result.get('answer') or "No reliable answer available"
            final_answer = f"Low confidence answer (Confidence: {confidence:.0%}):\n\n{answer_text}"
        else:
            final_answer = hdp_result.get('answer') or "No answer available"
        
        # Format sources
        sources = []
        for chunk in chunks[:3]:
            sources.append({
                "id": chunk["id"].split("_")[0],
                "department": chunk["metadata"].get("department"),
                "type": chunk["metadata"].get("document_type"),
                "score": chunk["score"]
            })
        
        return jsonify({
            "status": "success",
            "question": question,
            "answer": final_answer,
            "confidence": confidence,
            "verification_status": status,
            "sources": sources,
            "metadata": {
                "mode": "Document Search",
                "documents_retrieved": retrieval['result_count']
            }
        }), 200
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    import webbrowser
    import threading
    import subprocess
    import sys
    import os
    import time
    
    # Start frontend server in background
    def start_frontend():
        time.sleep(2)
        frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')
        try:
            if sys.platform == 'win32':
                subprocess.Popen(
                    ['python', '-m', 'http.server', '3000'],
                    cwd=frontend_path,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                subprocess.Popen(
                    ['python', '-m', 'http.server', '3000'],
                    cwd=frontend_path
                )
            print("Frontend server started on port 3000")
        except Exception as e:
            print(f"Could not start frontend: {e}")
    
    # Open browser automatically
    def open_browser():
        time.sleep(4)
        webbrowser.open('http://localhost:3000')
        print("Browser opened automatically")
    
    # Start frontend and browser in background threads
    threading.Thread(target=start_frontend, daemon=True).start()
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("\n" + "="*60)
    print("ULTIMATE RAG CHATBOT API SERVER")
    print("="*60)
    print("Backend running on:  http://127.0.0.1:5000")
    print("Frontend opening on: http://localhost:3000")
    print("Browser will open automatically in 4 seconds...")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)