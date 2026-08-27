import urllib.request,json
def post(path,data=None,ct="application/json"):
    enc=json.dumps(data,ensure_ascii=False).encode() if data else b""
    req=urllib.request.Request("http://127.0.0.1:8000"+path,data=enc,headers={"Content-Type":ct})
    return json.load(urllib.request.urlopen(req,timeout=60))
import os
print("=== 1) info ===")
print(json.dumps(post("/info"),ensure_ascii=False))
print("=== 2) 重复入库目录会怎样(加还是覆盖) ===")
n1=post("/info")["chunks"]
print("chunks前:",n1)
from urllib.request import Request
import urllib.parse
# ingest dir needs form
req=urllib.request.Request("http://127.0.0.1:8000/ingest/dir",data=b"path=C:\yoyac-work\RAG\data",headers={"Content-Type":"application/x-www-form-urlencoded"})
r=urllib.request.urlopen(req,timeout=120)
print("ingest again:",json.load(r))
print("chunks后:",post("/info")["chunks"])
print("=== 3) clear 后再 ingest ===")
print("clear:",urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8000/clear",method="DELETE"),timeout=30).read().decode())
print("chunks clear后:",post("/info")["chunks"])
print("=== 4) 空库 ask ===")
print(json.dumps(post("/ask",{"question":"x"}),ensure_ascii=False))
print("=== 5) 重新入库恢复 ===")
req=urllib.request.Request("http://127.0.0.1:8000/ingest/dir",data=b"path=C:\yoyac-work\RAG\data",headers={"Content-Type":"application/x-www-form-urlencoded"})
print("re-ingest:",json.load(urllib.request.urlopen(req,timeout=120)))
print("=== 6) top_k=1 ===")
a=post("/ask",{"question":"功率质保多久","top_k":1})
print("answer:",a["answer"][:60],"| sources:",len(a["sources"]))
