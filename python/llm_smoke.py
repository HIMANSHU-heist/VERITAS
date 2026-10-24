from python.llm import LLM
from python.schemas import CueOut

m = LLM()
system = ("You explain a pre-computed market signal in one or two sentences. Do not invent numbers. "
          "Fields: score (-1..1), confidence (0..1), top_drivers (list of strings), reason (string).")
user = ("Signal score=0.35. Drivers: SP500_ret1=+0.8%, CRUDE_ret1=-1.2%, USDINR_ret1=+0.1%. "
        "Copy the score, set confidence=0.4, fill the JSON.")
for i in range(2):
    out = m.call_json("fast", system, user, CueOut)
    print(i, out.model_dump(), m.stats)
