from mistralai.client import MistralClient
import os

client = MistralClient(api_key=os.environ["MISTRAL_API_KEY"])

resp = client.chat(
    model="mistral-small-latest",
    messages=[
        {"role": "user", "content": "Zeg hallo"}
    ]
)

print(resp.choices[0].message.content)
