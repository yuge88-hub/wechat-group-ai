"""LLM client wrapper for the WeChat Group AI Agent.

Supports two providers:
- anthropic: Native Anthropic API (with prompt caching)
- openai: OpenAI-compatible API (Hermes, OpenRouter, etc.)
"""

import json
import time
from typing import List, Dict


class LLMClient:
    def __init__(self, config):
        self.provider = getattr(config, 'provider', 'anthropic')
        self.api_key = config.api_key
        self.base_url = getattr(config, 'base_url', None)
        self.model_filter = config.model_filter
        self.model_digest = config.model_digest
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        self._total_tokens = 0
        self._total_calls = 0

        self._anthropic = None
        self._openai = None

        if self.provider == 'openai' and self.base_url:
            self._init_openai()  # Hermes/local doesn't require API key
        elif self.api_key:
            if self.provider == 'anthropic':
                self._init_anthropic()
            else:
                self._init_openai()

    def _init_anthropic(self):
        from anthropic import Anthropic
        self._anthropic = Anthropic(api_key=self.api_key)

    def _init_openai(self):
        from openai import OpenAI
        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._openai = OpenAI(**kwargs)

    @property
    def usage(self) -> dict:
        return {
            'total_tokens': self._total_tokens,
            'total_calls': self._total_calls,
            'estimated_cost_usd': round(self._total_tokens / 1_000_000 * 0.25, 4),
        }

    # ---- classify_messages ----

    def classify_messages(self, system_prompt: str, user_prompt: str,
                          max_retries: int = 3) -> List[Dict]:
        if not self._anthropic and not self._openai:
            return self._mock_classify(user_prompt)

        if self._openai:
            return self._classify_openai(system_prompt, user_prompt, max_retries)
        if self._anthropic:
            return self._classify_anthropic(system_prompt, user_prompt, max_retries)
        else:
            return self._classify_openai(system_prompt, user_prompt, max_retries)

    def _classify_anthropic(self, system_prompt, user_prompt, max_retries):
        from anthropic import RateLimitError, APIStatusError
        for attempt in range(max_retries):
            try:
                response = self._anthropic.messages.create(
                    model=self.model_filter,
                    max_tokens=min(self.max_tokens, 2048),
                    temperature=0.1,
                    system=[{
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    messages=[{"role": "user", "content": user_prompt}],
                )
                self._total_calls += 1
                self._total_tokens += response.usage.input_tokens + response.usage.output_tokens
                return self._parse_json_response(response.content[0].text)
            except RateLimitError:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt * 5)
                else:
                    return []
            except APIStatusError as e:
                if e.status_code >= 500 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt * 3)
                else:
                    print(f"[llm] API error: {e}")
                    return []
            except (json.JSONDecodeError, KeyError, IndexError):
                if attempt >= max_retries - 1:
                    print("[llm] Failed to parse classify response")
                    return []
        return []

    def _classify_openai(self, system_prompt, user_prompt, max_retries):
        for attempt in range(max_retries):
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                response = self._openai.chat.completions.create(
                    model=self.model_filter,
                    messages=messages,
                    max_tokens=min(self.max_tokens, 2048),
                    temperature=0.1,
                )
                self._total_calls += 1
                self._total_tokens += response.usage.total_tokens
                text = response.choices[0].message.content
                return self._parse_json_response(text)
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt * 3)
                else:
                    print(f"[llm] OpenAI classify error: {e}")
                    return []
        return []

    # ---- generate_digest ----

    def generate_digest(self, system_prompt: str, user_prompt: str,
                        max_retries: int = 2) -> str:
        if not self._anthropic and not self._openai:
            return self._mock_digest(user_prompt)

        if self._openai:
            return self._digest_openai(system_prompt, user_prompt, max_retries)
        if self._anthropic:
            return self._digest_anthropic(system_prompt, user_prompt, max_retries)
        else:
            return self._digest_openai(system_prompt, user_prompt, max_retries)

    def _digest_anthropic(self, system_prompt, user_prompt, max_retries):
        from anthropic import RateLimitError, APIStatusError
        for attempt in range(max_retries):
            try:
                response = self._anthropic.messages.create(
                    model=self.model_digest,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=[{
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    messages=[{"role": "user", "content": user_prompt}],
                )
                self._total_calls += 1
                self._total_tokens += response.usage.input_tokens + response.usage.output_tokens
                return response.content[0].text
            except RateLimitError:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt * 10)
                else:
                    return "## 生成失败\n\nAPI 限流，请稍后再试。"
            except APIStatusError as e:
                if e.status_code >= 500 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt * 5)
                else:
                    return f"## 生成失败\n\nAPI 错误 ({e.status_code}): {e.message}"
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(3)
                else:
                    return f"## 生成失败\n\n错误: {str(e)}"
        return "## 生成失败\n\n未知错误。"

    def _digest_openai(self, system_prompt, user_prompt, max_retries):
        for attempt in range(max_retries):
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                response = self._openai.chat.completions.create(
                    model=self.model_digest,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
                self._total_calls += 1
                self._total_tokens += response.usage.total_tokens
                return response.choices[0].message.content
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt * 5)
                else:
                    return f"## 生成失败\n\n错误: {str(e)}"
        return "## 生成失败\n\n未知错误。"

    # ---- JSON parsing ----

    def _parse_json_response(self, text: str) -> List[Dict]:
        text = text.strip()
        if text.startswith('```') and text.endswith('```'):
            text = text[3:-3].strip()
            if text.startswith('json'):
                text = text[4:].strip()
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
            return []
        except json.JSONDecodeError:
            pass
        import re
        match = re.search(r'\[[\s\S]*?\]', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        match = re.search(r'\{[\s\S]*?\}', text)
        if match:
            try:
                data = json.loads(match.group())
                return [data] if isinstance(data, dict) else []
            except json.JSONDecodeError:
                pass
        return []

    # ---- Mock methods ----

    def _mock_classify(self, user_prompt: str) -> List[Dict]:
        import random
        random.seed(42)
        results = []
        for line in user_prompt.split('\n'):
            if '[群:' in line:
                imp = random.choices([1, 2, 3, 4, 5], weights=[10, 30, 35, 20, 5])[0]
                results.append({
                    'importance': imp,
                    'topic_tags': ['测试'],
                    'summary_zh': '模拟分类（未配置 API Key）',
                    'action_items': [],
                    'is_question': False,
                    'should_report': imp >= 3,
                })
        print(f"[llm] MOCK: classified {len(results)} message blocks (no API key)")
        return results

    def _mock_digest(self, user_prompt: str) -> str:
        return "## 微信群消息摘要（模拟）\n\n" \
               "> 注意：这是模拟输出。请配置 API Key 或启动 Hermes 以使用真实 AI 摘要。\n\n" \
               "### 总览\n\n本次分析覆盖了微信消息。由于未配置 LLM，此报告为占位内容。\n\n" \
               "### 下一步\n\n" \
               "1. 启动 Hermes: `hermes gateway start`\n" \
               "2. 或在 config.yaml 中配置 anthropic/openai API Key\n" \
               "3. 重新运行 agent\n"
