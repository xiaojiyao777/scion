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
AIHUBMIX_API_KEY = "REDACTED"
INPUT_FILE = "prompt.md"
OUTPUT_FILE = "review_result_final.md"
MODEL = "gpt-5.4-pro"
REASONING_EFFORT = "high"       # 推理深度: medium / high / xhigh
TEXT_VERBOSITY = "high"         # 输出篇幅: low / medium / high

SYSTEM_PROMPT = (
    "我需要你帮我完成一版可工程落地的，可以靠近论文化的 v2 蓝图结构，不要求4周完成，而是4周完成MVP，我是工程师，工程价值大于学术价值"
    "请用中文回复，条理清晰，分点列出。输出格式：Markdown。"
)

# ============== 初始化客户端 ==============
client = OpenAI(
    api_key=AIHUBMIX_API_KEY,
    base_url="https://aihubmix.com/v1",
    timeout=1200.0,
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
    
    # 直接使用官方示例的方式
    response = client.responses.create(
        model=MODEL,
        input=f"这是用户原始的设计构想以及审核意见，需要根据审核意见完成设计蓝图，当前是在设计阶段，已经2次评审，这次希望能把完整设计方案做好，用Markdown格式输出：\n\n{content}",
        instructions=SYSTEM_PROMPT,  # 系统提示词
        reasoning={
            "effort": REASONING_EFFORT
        },
        text={
            "verbosity": TEXT_VERBOSITY
        },
        stream=True
    )

    # 3. 收集输出（参考官方示例，直接遍历事件）
    result_parts = []
    
    for event in response:
        # 打印事件类型用于调试（可选，确认后可以注释掉）
        print(f"[DEBUG] {event}", flush=True)
        
        # 检查事件是否有 delta 属性（文本增量）
        if hasattr(event, 'delta') and event.delta:
            result_parts.append(event.delta)
            print(event.delta, end="", flush=True)
        
        # 检查是否有 output_text 属性（某些事件可能包含完整文本）
        elif hasattr(event, 'output_text') and event.output_text:
            # 如果之前没有收集到内容，这可能是完整输出
            if not result_parts:
                result_parts.append(event.output_text)
                print(event.output_text, end="", flush=True)
        
        # 检查是否是最终响应（如果有 usage 信息）
        if hasattr(event, 'usage') and event.usage:
            print(f"\n\n📊 Token 使用: 输入 {event.usage.get('input_tokens', '?')}, "
                  f"输出 {event.usage.get('output_tokens', '?')}, "
                  f"总计 {event.usage.get('total_tokens', '?')}")
    
    result = "".join(result_parts)
    elapsed = time.time() - start_time
    
    # 如果没有收集到内容，显示警告
    if not result:
        print("\n⚠️ 警告: 未收集到任何输出内容")
        print("尝试检查 API 响应格式...")
        # 重新调用一次非流式来调试
        print("\n尝试非流式调用...")
        response2 = client.responses.create(
            model=MODEL,
            input=f"请审核以下完整内容并给出详细的审核意见，用Markdown格式输出：\n\n{content}",
            instructions=SYSTEM_PROMPT,
            reasoning={"effort": REASONING_EFFORT},
            text={"verbosity": TEXT_VERBOSITY},
            stream=False
        )
        print(f"非流式响应: {response2}")
        if hasattr(response2, 'output_text'):
            result = response2.output_text
            print(result)
    
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
