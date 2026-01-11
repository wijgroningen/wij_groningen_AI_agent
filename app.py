from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Hallo, dit is mijn Flask-app!"

if __name__ == '__main__':
    app.run(debug=True)
o