import os
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])
for m in sorted(client.models.list().data, key=lambda x: x.id):
    print(m.id)
