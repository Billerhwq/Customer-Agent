"""跑 tests/test_cases.json 中的 5 条用例，打印并保存每条输出到 tests/outputs/。

用法： python tests/run_tests.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from src.agent import Agent  # noqa: E402

CASES = json.loads((ROOT / "tests" / "test_cases.json").read_text(encoding="utf-8"))
OUT_DIR = ROOT / "tests" / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    agent = Agent()
    print(f"LLM mode: {agent.llm.name}\n" + "=" * 70)
    summary = []
    for case in CASES:
        cid = case["id"]
        msg = case["message"]
        result = agent.chat(msg, session_id=f"case-{cid}",
                            visitor={"country": "", "email": ""})
        (OUT_DIR / f"{cid}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[{cid}] {msg}")
        print(f"expected: {case['expected_behavior']}")
        print(f"answer:   {result['answer']}")
        print(f"need_human={result['need_human']} confidence={result['confidence']} "
              f"sources={[s['id'] for s in result['sources']]}")
        print(f"lead:     {json.dumps(result['lead_fields'], ensure_ascii=False)}")
        summary.append({"id": cid, "need_human": result["need_human"],
                        "sources": [s["id"] for s in result["sources"]]})
    (OUT_DIR / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 70)
    print(f"Saved {len(CASES)} outputs to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
