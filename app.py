from flask import Flask, render_template, request, redirect, url_for
import os
from mistralai.client import MistralClient
from docx import Document
from pypdf import PdfReader
import markdown

AGENT_FILES_DIR = "agent_files"
MAX_CONTEXT_CHARS = 8000  # veilig voor mistral-small

# =========================
# Config & API key
# =========================

FALLBACK_API_KEY = "test"

API_KEY = os.environ.get("MISTRAL_API_KEY", FALLBACK_API_KEY)

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


@app.route("/search", methods=["GET"])
def search():
    q = request.args.get("q", "")
    answer = ""
    error = ""

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
            else:
                error = "Geen antwoord ontvangen van het model."

        except Exception as e:
            error = f"Fout bij Mistral API-call: {str(e)}"

    return render_template(
        "results.html",
        q=q,
        # answer=answer,
        html_answer=html_answer,
        error=error,
        )


if __name__ == "__main__":
    app.run(debug=True)
