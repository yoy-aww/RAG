import os,time
os.environ["HF_ENDPOINT"]="https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"]="1"
os.environ["SENTENCE_TRANSFORMERS_BACKEND"]="torch"
from sentence_transformers import SentenceTransformer
import torch
print("GPU:",torch.cuda.is_available(),torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none")
m_gpu=SentenceTransformer("BAAI/bge-large-zh-v1.5",device="cuda" if torch.cuda.is_available() else "cpu")
device=str(m_gpu.device)
print("loaded on",device)
import numpy as np
queries=["组件功率质保","开路电压","逆变器接线","热斑隐裂","功率下降排查"]*200
# warmup
m_gpu.encode(queries[:5])
for d,label in [(m_gpu.device,device)]:
    t=time.time()
    v=m_gpu.encode(queries,normalize_embeddings=True,batch_size=32)
    dt=time.time()-t
    print(f"GPU encode {len(queries)} queries -> {np.asarray(v).shape}, {dt:.2f}s, {len(queries)/dt:.1f} queries/s")
