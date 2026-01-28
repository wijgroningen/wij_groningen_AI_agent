from flask import Flask, render_template, request, redirect, url_for
import os
import ollama
from docx import Document
from pypdf import PdfReader
import markdown
from flask import send_file
from config import MISTRAL_API_KEY
import chromadb
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# =========================
# Database setup
# =========================
Base = declarative_base()

class Interaction(Base):
    __tablename__ = 'interactions'
    id = Column(Integer, primary_key=True)
    user = Column(String(64), nullable=True)  # optioneel, voor toekomstige gebruikersauth
    input_text = Column(Text, nullable=False)
    output_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    privacy_flag = Column(Boolean, default=False)  # voor toekomstige privacy-detectie
    model_used = Column(String(50), nullable=True)  # bijv. "qwen2.5:7b"
    response_time_seconds = Column(Integer, nullable=True)  # wachttijd in seconden
    plan_type = Column(String(30), nullable=True)  # gezinsanalyse/evaluatie/aanvraag

# SQLite database (later makkelijk te vervangen door Postgres)
engine = create_engine('sqlite:///interactions.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)


AGENT_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_files")
MAX_CONTEXT_CHARS = 8000  # veilig voor mistral-small

# =========================
# Config & Ollama Setup
# =========================
print("\n🚀 Initializing Ollama client...")
print("   Make sure Ollama is running: ollama serve")
print("   Then in another terminal: ollama pull\n")

OLLAMA_MODEL = "qwen2.5:7b"  # Sneller model dan mistral, beter instruction-following
OLLAMA_BASE_URL = "http://localhost:11434"

try:
    # Test connection to Ollama
    client = ollama.Client(host=OLLAMA_BASE_URL)
    print("✅ Connected to Ollama!\n")
except Exception as e:
    print(f"⚠️ Could not connect to Ollama: {e}")
    print("   Please start Ollama: ollama serve")
    print("   And pull the model: ollama pull mistral\n")

# =========================
# Vector Database Setup (RAG)
# =========================
print("🔄 Initializing Vector Database...")
try:
    # Laad embedding model
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Initialiseer Chroma vector database met persistentie
    chroma_client = chromadb.PersistentClient(
        path="./chroma_db"
    )
    
    vector_collection = chroma_client.get_or_create_collection(
        name="agent_documents",
        metadata={"hnsw:space": "cosine"}
    )
    print("✅ Vector Database initialized!\n")
except Exception as e:
    print(f"❌ Fout bij vector database setup: {e}")
    raise

def chunk_text(text, chunk_size=300, overlap=50):
    """Split tekst in overlapping chunks"""
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i:i + chunk_size])
    return chunks

def load_documents_to_vector_db():
    """Laad alle documenten in vector database"""
    if not os.path.isdir(AGENT_FILES_DIR):
        return 0
    
    chunk_id = 0
    for filename in os.listdir(AGENT_FILES_DIR):
        path = os.path.join(AGENT_FILES_DIR, filename)
        
        try:
            text = ""
            if filename.lower().endswith(".docx"):
                text = read_docx(path)
            elif filename.lower().endswith(".pdf"):
                text = read_pdf(path)
            else:
                continue
            
            # Split in chunks
            chunks = chunk_text(text)
            
            # Add chunks to vector database
            for i, chunk in enumerate(chunks):
                chunk_id += 1
                embedding = embedding_model.encode(chunk, convert_to_numpy=True)
                vector_collection.add(
                    ids=[f"{filename}_chunk_{i}"],
                    embeddings=[embedding],
                    documents=[chunk],
                    metadatas=[{"source": filename, "chunk": i}]
                )
        
        except Exception as e:
            print(f"⚠️ Kon bestand niet laden ({filename}): {e}")
    
    print(f"📚 Loaded {chunk_id} chunks into vector database")
    return chunk_id

def retrieve_relevant_context(query, top_k=3):
    """Retrieve relevante chunks from vector database"""
    query_embedding = embedding_model.encode(query, convert_to_numpy=True)
    
    results = vector_collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    
    if results and results['documents']:
        context_chunks = results['documents'][0]
        return "\n\n".join(context_chunks)
    return ""

# =========================
# Agent prompt
# lees het agent_prompt.md bestand
# =========================
def load_agent_prompt(filename="agent_prompts/agent_prompt_v2.md"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return (
            "Het promptbestand kon niet worden gevonden. "
            "Breek de applicatie af en geef een melding terug aan de gebruiker."
        )

def get_agent_prompt_for_type(plan_type):
    """Laad de juiste prompt op basis van plan type"""
    type_map = {
        "gezinsanalyse": "agent_prompts/agent_prompt_gezinsanalyse.md",
        "evaluatie": "agent_prompts/agent_prompt_evaluatie.md",
        "aanvraag": "agent_prompts/agent_prompt_aanvraag.md",
    }
    filename = type_map.get(plan_type, "agent_prompts/agent_prompt_v2.md")
    return load_agent_prompt(filename)

AGENT_PROMPT = load_agent_prompt()

# =========================
# Support files 
# Lees alle docx en pdf bestanden in de agent_files map
# =========================
def read_docx(path):
    '''Lees tekst van een .docx bestand'''
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

def read_pdf(path):
    '''Lees tekst van een .pdf bestand'''
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)

def load_agent_files_text():
    '''Laad en combineer tekst van alle ondersteunde bestanden in de agent_files map'''
    texts = []

    if not os.path.isdir(AGENT_FILES_DIR):
        return ""

    for filename in os.listdir(AGENT_FILES_DIR):
        path = os.path.join(AGENT_FILES_DIR, filename)

        try:
            if filename.lower().endswith(".docx"):
                texts.append(f"[BRON: {filename}]\n{read_docx(path)}")

            elif filename.lower().endswith(".pdf"):
                texts.append(f"[BRON: {filename}]\n{read_pdf(path)}")

        except Exception as e:
            print(f"⚠️ Kon bestand niet lezen ({filename}): {e}")

    full_text = "\n\n".join(texts)

    # Hard limiter (belangrijk!)
    return full_text[:MAX_CONTEXT_CHARS]

# =========================
# Flask app
# =========================
app = Flask(__name__, static_folder="static", template_folder="templates")

# Laad documenten in vector database bij startup (alleen eerste keer)
if vector_collection.count() == 0:
    print("📖 First run: building vector DB...")
    doc_count = load_documents_to_vector_db()
    print(f"✅ Vector database ready with {doc_count} chunks!\n")
else:
    print(f"⚡ Vector DB already exists with {vector_collection.count()} chunks, skipping build\n")


@app.route("/", methods=["GET"])
def home():
    q = request.args.get("q", "")
    if q:
        return redirect(url_for("search", q=q))
    return render_template("index.html")


@app.route("/algemene-informatie", methods=["GET"])
def algemene_informatie():
    return render_template("algemene_informatie.html")


@app.route("/prompt", methods=["GET"])
def prompt():
    try:
        with open("agent_prompt.md", "r", encoding="utf-8") as f:
            md_content = f.read()
        html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code', 'nl2br'])
        
        return render_template("prompt.html", html_content=html_content, error=False)
    except FileNotFoundError:
        return render_template("prompt.html", html_content="<p>Prompt niet gevonden.</p>", error=True)


@app.route("/handleiding", methods=["GET"])
def handleiding():
    return redirect(url_for("prompt"))


@app.route("/context-files", methods=["GET"])
def context_files():
    # Laad list van agent_files
    agent_files = []
    if os.path.isdir(AGENT_FILES_DIR):
        for filename in sorted(os.listdir(AGENT_FILES_DIR)):
            if filename.lower().endswith(('.docx', '.pdf')):
                agent_files.append(filename)
    
    return render_template("context_files.html", agent_files=agent_files)


@app.route("/rebuild-vector-db", methods=["POST"])
def rebuild_vector_db():
    """Reset en herbouw de vector database"""
    try:
        # Verwijder alle bestaande documenten
        vector_collection.delete(
            ids=vector_collection.get()['ids']
        )
        # Herbouw database
        doc_count = load_documents_to_vector_db()
        return {"success": True, "message": f"Vector database rebuilt with {doc_count} chunks"}
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


@app.route("/search", methods=["GET"])
def search():
    q = request.args.get("q", "")
    plan_type = request.args.get("type", "gezinsanalyse")  # default: gezinsanalyse
    answer = ""
    html_answer = ""
    error = ""

    # Voor nu: geen gebruikersauthenticatie, dus user=None
    user = None

    if q:
        try:
            # Retrieve relevant context using vector database (RAG)
            print(f"🔍 Searching for relevant context for: '{q}'")
            print(f"   Plan type: {plan_type}")
            context_text = retrieve_relevant_context(q, top_k=1)

            # Laad de juiste prompt voor dit type
            agent_prompt = get_agent_prompt_for_type(plan_type)
            
            # Maak prompt
            prompt = f"""{agent_prompt}
            
Gebruik onderstaande context bij het beantwoorden van de vraag.
Als de context niet relevant is, negeer deze.

CONTEXT:
{context_text}

VRAAG:
{q}"""

            print(f"📊 Generating response via Ollama...")
            print(f"   Prompt length: {len(prompt)} chars")
            print(f"   Model: {OLLAMA_MODEL}")
            print(f"   Status: waiting for response...")
            
            # Call Ollama API met timeout
            try:
                import time
                start_time = time.time()
                
                response = client.generate(
                    model=OLLAMA_MODEL,
                    prompt=prompt,
                    stream=False,
                    options={
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "num_predict": 600,
                        "num_ctx": 2048,
                    }
                )
                answer = response['response'].strip()
                
                elapsed = time.time() - start_time
                print(f"✅ Response received in {elapsed:.1f}s")
                print(f"   Response length: {len(answer)} chars")
            except Exception as e:
                print(f"❌ Ollama error: {e}")
                answer = f"Fout bij het genereren van antwoord: {str(e)}"
            
            print("✅ Response generated!")
            
            html_answer = markdown.markdown(answer)
            # Sla interactie op in database
            try:
                db = SessionLocal()
                db.add(Interaction(
                    user=user,
                    input_text=q,
                    output_text=answer,
                    model_used=OLLAMA_MODEL,
                    response_time_seconds=int(elapsed),
                    plan_type=plan_type,
                    # privacy_flag kan later automatisch bepaald worden
                ))
                db.commit()
                db.close()
                print("💾 Saved to database")
            except Exception as db_error:
                print(f"❌ Database error: {db_error}")

        except Exception as e:
            error = f"Fout bij Ollama inference: {str(e)}"
            print(f"❌ Outer error: {e}")
            html_answer = ""

    # Check if request wants JSON (AJAX)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {
            'q': q,
            'html_answer': html_answer,
            'error': error
        }
    
    return render_template(
        "results.html",
        q=q,
        # answer=answer,
        html_answer=html_answer,
        error=error,
        )


@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    """Download een bestand uit agent_files"""
    # Valideer filename - alleen letters, nummers, punten en underscores toegestaan
    if not all(c.isalnum() or c in '._-' for c in filename):
        return "Ongeldig bestandsnaam", 400
    
    filepath = os.path.join(AGENT_FILES_DIR, filename)
    
    # Zorg ervoor dat het bestand echt in agent_files zit
    if not os.path.abspath(filepath).startswith(os.path.abspath(AGENT_FILES_DIR)):
        return "Bestand niet gevonden", 404
    
    if not os.path.exists(filepath):
        return "Bestand niet gevonden", 404
    
    return send_file(filepath, as_attachment=True)


@app.route("/admin/interactions")
def admin_interactions():
    db = SessionLocal()
    rows = db.query(Interaction).order_by(Interaction.created_at.desc()).limit(100).all()
    db.close()
    return render_template("admin_interactions.html", rows=rows)

if __name__ == "__main__":
    app.run(debug=True)