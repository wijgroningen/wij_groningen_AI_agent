from flask import Flask, render_template, request, redirect, url_for
import os
from mistralai.client import MistralClient
from docx import Document
from pypdf import PdfReader
import markdown
from flask import send_file

# Database setup
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

class Interaction(Base):
    __tablename__ = 'interactions'
    id = Column(Integer, primary_key=True)
    user = Column(String(64), nullable=True)  # optioneel, voor toekomstige gebruikersauth
    input_text = Column(Text, nullable=False)
    output_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    privacy_flag = Column(Boolean, default=False)  # voor toekomstige privacy-detectie
    # Voeg hier eenvoudig extra velden toe in de toekomst

# SQLite database (later makkelijk te vervangen door Postgres)
engine = create_engine('sqlite:///interactions.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)


AGENT_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_files")
MAX_CONTEXT_CHARS = 8000  # veilig voor mistral-small

# =========================
# Config & API key
# =========================
FALLBACK_API_KEY = "test"

API_KEY = os.environ.get("MISTRAL_API_KEY", FALLBACK_API_KEY)
API_KEY = "AEi0xtldgbjZO7ceNndyv2Bi47bFAgdY" # LATER VERVANGEN!!!!!

if API_KEY == FALLBACK_API_KEY:
    print(
        "⚠️ Warning: using fallback API key. "
        "Set the MISTRAL_API_KEY environment variable in production."
    )

print("Using API key:", API_KEY[:6] + "..." if API_KEY != "test" else "FALLBACK (test)")
client = MistralClient(api_key=API_KEY)

# =========================
# Agent prompt
# lees het agent_prompt.md bestand
# =========================
def load_agent_prompt():
    try:
        with open("agent_prompt.md", "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return (
            "Het promptbestand kon niet worden gevonden. "
            "Breek de applicatie af en geef een melding terug aan de gebruiker."
        )

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


@app.route("/search", methods=["GET"])
def search():
    q = request.args.get("q", "")
    answer = ""
    error = ""

    # Voor nu: geen gebruikersauthenticatie, dus user=None
    user = None

    if q:
        try:
            context_text = load_agent_files_text()

            response = client.chat(
                model="mistral-small-latest",
                messages=[
                    {"role": "system", "content": AGENT_PROMPT},
                    {
                        "role": "user",
                        "content": f"""
            Gebruik onderstaande context bij het beantwoorden van de vraag.
            Als de context niet relevant is, negeer deze.

            CONTEXT:
            {context_text}

            VRAAG:
            {q}
            """
                    },
                ],
                temperature=0.2,  # temperature bepaalt hoe voorspelbaar of creatief het taalmodel antwoordt.
            )


            if response.choices:
                answer = response.choices[0].message.content
                html_answer = markdown.markdown(answer)
                # Sla interactie op in database
                db = SessionLocal()
                db.add(Interaction(
                    user=user,
                    input_text=q,
                    output_text=answer,
                    # privacy_flag kan later automatisch bepaald worden
                ))
                db.commit()
                db.close()
            else:
                error = "Geen antwoord ontvangen van het model."

        except Exception as e:
            error = f"Fout bij Mistral API-call: {str(e)}"

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