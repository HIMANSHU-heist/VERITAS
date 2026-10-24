import os
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

for name in ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]:
    resp = client.chat.completions.create(
        model=name,
        messages=[{"role": "user", "content": "Reply with only the word: READY"}],
        temperature=0,
        max_completion_tokens=200,
    )
    print(name, "->", resp.choices[0].message.content)
