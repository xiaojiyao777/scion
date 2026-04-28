"""
使用 AiHubMix 调用 GPT-5.4-pro 一次性审核整个文档
- 从 prompt.md 读取待审核内容
- 使用 Responses API 流式输出
- 审核意见保存到 review_result.md
"""

import os
import time
from datetime import datetime
from openai import OpenAI

# ============== 配置区域 ==============
AIHUBMIX_API_KEY = os.environ.get("SCION_API_KEY")
if not AIHUBMIX_API_KEY:
    raise Exception("需要KEY")

INPUT_FILE = "v0.3-design-review.md"
OUTPUT_FILE = "v0.3-design-detail-plan.md"
MODEL = "gpt-5.4-pro"
REASONING_EFFORT = "high"       # 推理深度: medium / high / xhigh
TEXT_VERBOSITY = "high"         # 输出篇幅: low / medium / high

SYSTEM_PROMPT = (
    "用户正在设计并开发Scion：是一个面向组合优化算法自动改进的研究执行框架；当前已经做完v0.3版本的设计和开发，并完成了完整深度审核，现在需要根据审核结果进行详细的工程设计"
)

# ============== 初始化客户端 ==============
client = OpenAI(
    api_key=AIHUBMIX_API_KEY,
    base_url="https://aihubmix.com/v1",
    timeout=3600.0,
)


def main():
    print("=" * 60)
    print("  GPT-5.4-pro 内容审核工具 (via AiHubMix Responses API)")
    print("=" * 60)

    # 1. 读取内容
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 找不到文件: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"✅ 已读取文件: {INPUT_FILE} ({len(content)} 字符)")

    # 2. 调用 GPT-5.4-pro 审核
    print(f"\n🔄 正在调用 {MODEL} 审核全文...")
    print(f"   推理深度: {REASONING_EFFORT} | 输出篇幅: {TEXT_VERBOSITY}\n")

    start_time = time.time()

    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=f"请审核以下完整内容并给出详细的审核意见：\n\n{content}",
        reasoning={"effort": REASONING_EFFORT},
        text={"verbosity": TEXT_VERBOSITY},
        stream=True,
    )

    # 3. 流式收集输出
    result_parts = []
    for event in response:
        event_type = getattr(event, "type", None)

        if event_type == "response.output_text.delta":
            delta = getattr(event, "delta", "")
            if delta:
                result_parts.append(delta)
                print(delta, end="", flush=True)

        elif event_type == "response.completed":
            resp = getattr(event, "response", None)
            if resp:
                usage = getattr(resp, "usage", None)
                if usage:
                    print(f"\n\n📊 Token 使用: 输入 {getattr(usage, 'input_tokens', '?')}, "
                          f"输出 {getattr(usage, 'output_tokens', '?')}, "
                          f"总计 {getattr(usage, 'total_tokens', '?')}")

    result = "".join(result_parts)
    elapsed = time.time() - start_time
    print(f"\n⏱️  耗时: {elapsed:.1f} 秒")

    # 4. 保存审核报告
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"""# 📋 内容审核报告

- **审核时间**: {now}
- **审核模型**: {MODEL}
- **推理深度**: {REASONING_EFFORT}
- **内容来源**: {INPUT_FILE}
- **内容长度**: {len(content)} 字符
- **审核耗时**: {elapsed:.1f} 秒

---

## 📝 审核意见

{result}
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n✅ 审核报告已保存到: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
