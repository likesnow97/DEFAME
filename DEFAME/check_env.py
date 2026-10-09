#!/usr/bin/env python3
"""DEFAME 环境自检（只读，不修改任何东西）。

用法（必须在项目根目录）：
    uv run --no-project python check_env.py

退出码 0 = 无阻塞性问题；1 = 有必须处理的失败项。
"""
from __future__ import annotations

import importlib
import importlib.metadata as md
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)  # config/globals.py 依赖 cwd == 项目根
sys.path.insert(0, str(ROOT))

OK, WARN, FAIL = " OK ", "WARN", "FAIL"
rows: list[tuple[str, str, str]] = []


def probe(name: str, fn, optional: bool = False) -> None:
    try:
        rows.append((OK, name, fn() or ""))
    except Exception as exc:
        status = WARN if optional else FAIL
        rows.append((status, name, f"{type(exc).__name__}: {exc}"))


# --- 1) 解释器 ---------------------------------------------------------
def _python() -> str:
    v = sys.version_info
    assert v[:2] == (3, 10), f"Dockerfile 用的是 3.10，当前 {v.major}.{v.minor}"
    return f"{v.major}.{v.minor}.{v.micro}  ({sys.prefix})"


probe("Python 3.10", _python)


# --- 2) requirements.txt 逐条核对 ---------------------------------------
def _requirements() -> str:
    from packaging.requirements import Requirement

    lines = [
        line.strip()
        for line in Path("requirements.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    missing, mismatched = [], []
    for line in lines:
        req = Requirement(line)
        try:
            have = md.version(req.name)
        except md.PackageNotFoundError:
            missing.append(req.name)
            continue
        if req.specifier and not req.specifier.contains(have, prereleases=True):
            mismatched.append(f"{req.name}(要{req.specifier}, 实装{have})")
    assert not missing, f"缺 {len(missing)} 个: {', '.join(missing)}"
    assert not mismatched, f"版本不符: {', '.join(mismatched)}"
    return f"{len(lines)} 条全部满足"


probe("requirements.txt", _requirements)


# --- 3) 关键第三方包 import ---------------------------------------------
# 可选：缺了/报错不影响默认流程，只警告
OPTIONAL = {"wandb", "tweepy", "peft", "bert_score", "bitsandbytes"}

for mod in [
    "numpy", "pandas", "scipy", "sklearn", "PIL", "bs4", "yaml", "tqdm",
    "requests", "jinja2", "tiktoken", "torchvision", "transformers",
    "sentence_transformers", "huggingface_hub", "openai", "duckduckgo_search",
    "langdetect", "markdownify", "markdown_pdf", "sty", "orjsonl", "pyparsing",
    "nltk", "matplotlib", "einops", "timm", "av", "accelerate", "spacy",
    "bert_score", "rouge_score", "wandb", "tweepy",
    "google.cloud.vision", "bitsandbytes", "peft",
]:
    probe(
        f"import {mod}",
        lambda m=mod: importlib.import_module(m) and "",
        optional=mod in OPTIONAL,
    )


# --- 4) CUDA -----------------------------------------------------------
def _cuda() -> str:
    import torch

    if not torch.cuda.is_available():
        return f"torch {torch.__version__}，CUDA 不可用（纯 CPU 也能跑，见 README）"
    return (
        f"torch {torch.__version__}，{torch.cuda.device_count()}x"
        f"{torch.cuda.get_device_name(0)}"
    )


probe("CUDA", _cuda)


# --- 5) 曾经踩过的坑：回归检查 ------------------------------------------
def _pyarrow_datasets() -> str:
    import datasets
    import pyarrow

    assert hasattr(pyarrow, "PyExtensionType"), (
        f"pyarrow {pyarrow.__version__} 已删除 PyExtensionType，"
        f"datasets {datasets.__version__} 会 import 失败，"
        "进而拖垮 sentence_transformers / defame.common.embedding。"
        "修: uv pip install 'pyarrow==7.0.0'"
    )
    return f"pyarrow {pyarrow.__version__} + datasets {datasets.__version__} 兼容"


probe("pyarrow/datasets 兼容", _pyarrow_datasets)


def _pyreqwest() -> str:
    v = md.version("pyreqwest-impersonate")
    assert v < "0.5.1", (
        f"{v} 只有 sdist，uv 会去现场编译 Rust（即之前安装卡死的原因）。"
        "修: constraints.txt 里写 pyreqwest-impersonate==0.5.0"
    )
    return f"pyreqwest-impersonate {v}（有 wheel，不触发 Rust 编译）"


probe("duckduckgo 的 Rust 依赖", _pyreqwest)


# --- 6) 项目自身模块冒烟测试 --------------------------------------------
# 放在子进程里跑：config/globals.py 在 key 未配置时会进入交互式 input()
SMOKE = (
    "import defame.common.modeling, defame.common.report, defame.common.embedding;"
    "import defame.tools.search.searcher;"
    "print('ok')"
)


def _project() -> str:
    p = subprocess.run(
        [sys.executable, "-c", SMOKE],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if p.returncode == 0:
        return "core 模块 import 正常"
    if "EOFError" in p.stderr and "Please enter" in p.stderr:
        raise AssertionError(
            "API key 全空，config/globals.py 末尾会自动进入交互式提问；"
            "非交互环境必然 EOFError。跑一次 `python -m scripts.run` 按提示填 key"
        )
    tail = (p.stderr or "").strip().splitlines()
    raise AssertionError(tail[-1] if tail else "未知错误")


probe("项目模块冒烟测试", _project)


# --- 7) API key 配置状态（只读文件，不 import config）--------------------
def _keys() -> str:
    import yaml

    data = yaml.safe_load(Path("config/api_keys.yaml").read_text()) or {}
    configured = [k for k, v in data.items() if v]
    if not configured:
        raise AssertionError("api_keys.yaml 里一个 key 都没填（见 README 的 APIs 一节）")
    return f"已配置 {len(configured)}/{len(data)}: {', '.join(configured)}"


probe("API keys", _keys, optional=True)


# --- 输出 --------------------------------------------------------------
width = max(len(name) for _, name, _ in rows)
for status, name, detail in rows:
    print(f"[{status}] {name:<{width}}  {detail}")

fails = sum(1 for s, _, _ in rows if s == FAIL)
warns = sum(1 for s, _, _ in rows if s == WARN)
print(f"\n共 {len(rows)} 项：{len(rows) - fails - warns} 通过, {warns} 警告, {fails} 失败")
sys.exit(1 if fails else 0)
