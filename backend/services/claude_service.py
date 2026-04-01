import anthropic

# Claude Haiku API 呼叫服務
# 應用場景：分流判斷、白話解讀、小禾對話、問診清單、30天報告

anthropic_client = anthropic.Anthropic()  # 讀取 ANTHROPIC_API_KEY

def call_claude(system_prompt: str, user_message: str) -> str:
    claude_api_response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    return claude_api_response.content[0].text
