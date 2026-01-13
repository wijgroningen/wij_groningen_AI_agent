from flask import Flask, render_template, request, redirect, url_for
import requests
from mistralai.client import MistralClient 
import os

# Use a simple REST call to Mistral's chat completions endpoint to avoid
# depending on a specific mistralai client API that may differ between versions.
# Read the API key from the environment variable `MISTRAL_API_KEY` in production.
FALLBACK_API_KEY = 'test'
API_KEY = os.environ.get('MISTRAL_API_KEY', FALLBACK_API_KEY)
if API_KEY == FALLBACK_API_KEY:
    print('Warning: using fallback API key. Set the MISTRAL_API_KEY environment variable in production.')

# MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_AGENT_ID = "d25078d5-a27d-4d30-be81-165785cb0908"
MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"

# Load the agent prompt from agent_prompt.md
def load_agent_prompt():
    try:
        with open('agent_prompt.md', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "Het promptbestand kon niet worden gevonden. Breek de applicatie af en geef een melding terug aan de gebruiker."

AGENT_PROMPT = load_agent_prompt()

app = Flask(__name__, static_folder='static', template_folder='templates')

@app.route('/', methods=['GET'])
def home():
    q = request.args.get('q', '')
    if q:
        return redirect(url_for('search', q=q))
    return render_template('index.html')

@app.route('/search', methods=['GET'])
def search():
    q = request.args.get('q', '')
    answer = ''
    error = ''

    if q:
        try:
            # Prepare request payload for the Mistral chat API
            payload = {
                "model": "mistral-small",
                "messages": [
                    # {"role": "system", "content": AGENT_PROMPT},
                    {"role": "user", "content": q}
                ],
            }

            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            }

            resp = requests.post(MISTRAL_CHAT_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # Parse standard chat completions response
            answer = ''
            if isinstance(data, dict):
                choices = data.get('choices') or []
                if choices:
                    first = choices[0]
                    # Standard shape: first['message']['content']
                    if isinstance(first.get('message'), dict) and first['message'].get('content'):
                        answer = first['message']['content']
                    # Fallback: first.get('content')
                    elif first.get('content'):
                        answer = first['content']
            
            if not answer:
                error = 'Kon geen antwoord uit API-response halen.'
        except Exception as e:
            error = f"Fout bij API-call: {str(e)}"

    return render_template('results.html', q=q, answer=answer, error=error)

if __name__ == '__main__':
    app.run(debug=True)
