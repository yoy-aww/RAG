# 排障记录

> 真实踩坑，不是臆测。以后再搭环境按这个避坑。

## 1. PYTHONPATH 污染（反复炸）
Hermes agent 的 venv 被自动插进 PYTHONPATH，导致 venv 的 pip 装到了 Hermes 的 site-packages，import 也走错地方。
解法：所有 venv 内命令前加 `PYTHONPATH=""`。

## 2. venv pyvenv.cfg 损坏
手写 pyvenv.cfg 时用了 msys 路径 /c/Program Files/Python，Windows 原生解释器不认 -> venv python 启动报 failed to locate pyvenv.cfg。
解法：uv 建的 venv 别手写改 cfg；home 必须写 Windows 路径 C:\Program Files\Python。

## 3. 依赖装进了全局而非 venv（假成功）
pip install 看起来成功，实际装到了 AppData\Roaming\Python\Python313，venv 是空的。
解法：永远用 .venv/Scripts/python.exe -m pip install，不用裸 pip；装完用 venv python -c import xxx 验。

## 4. torch 默认 CPU 版
pip install torch 装的永远是 CPU 版（2.13.0+cpu），3060 显卡闲置。
解法：pip install torch==2.6.0+cu124 --index-url https://download.pytorch.org/whl/cu124
注意：官方源对我这网络约 250KB/s，2.5GB wheel 要 ~3 小时；可考虑用清华镜像。

## 5. Ollama MSYS 路径 bug
从 yoyac-work 目录调 ollama，临时路径被转成 C:\c\yoyac-work\...\hermes-tmp（不存在） -> runner 启动失败。
解法：从用户家目录调，或把 PATH 指向 Ollama 后用原生路径。

## 6. huggingface-hub 版本冲突
ST 旧版要求 hf-hub<1.0，装成 1.25.1 就炸。
解法：装 sentence-transformers>=2.2 自动拉兼容 hf-hub（当前 5.6 -> hf-hub 1.28 兼容）。

## 7. 内联 python 脚本里的反引号
在 bash 里用 python -c 写含反引号的字符串，反引号被 bash 当命令替换执行 -> 炸。
解法：长文本写文档用 write_file 或写 .py 脚本文件再执行，别把反引号放内联 -c 里。
