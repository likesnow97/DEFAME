"""Minimal fact-check using the local Qwen3-VL API.

Start /data/snow/modlib/server/llm_server.py first. The default API URL is
http://127.0.0.1:8765/v1; override it with QWEN_BASE_URL if needed. Put the
matching key in config/api_keys.local.yaml as qwen_api_key, or set QWEN_API_KEY.

For image claims, import Image from defame.common and include an Image object
in the claim list. use_geolocator=False skips the optional geolocation model.
"""
from defame.common import Image
from defame.fact_checker import FactChecker


fact_checker = FactChecker(llm="qwen3_vl_plus", use_geolocator=False)
claim = [
    "许家印2026年10月无期徒刑被减刑了吗.",
    Image("/nfs/users/zhoujie/DEFAME/DEFAME/in/example/xjy.png"),
    ]
report, _ = fact_checker.verify_claim(claim)
report.save_to("out/fact-check")
