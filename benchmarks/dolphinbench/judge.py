"""Explicit private transport adaptation; preserve upstream judge prompts/rubrics.

This is NOT the unmodified official Azure deployment transport. Provider/model
identity, API cost and complete requests are retained by the controller gateway.
"""
from contextlib import contextmanager
import json
import time
import urllib.error
import urllib.request


@contextmanager
def openrouter_judge(gateway):
    from graders import llm_judge
    from graders.judge_recording import record_response, replay_response
    original = llm_judge._call_judge

    def call(system_prompt, user_prompt, config, timeout=None):
        replay = replay_response(system_prompt, user_prompt, config)
        if replay is not None:
            return replay
        effort = config.get('reasoning_effort', 'medium')
        if effort != 'medium':
            raise ValueError('Campaign requires fixed medium judge reasoning')
        body = {'model': 'openai/gpt-5.6-sol', 'reasoning_effort': effort,
                'max_completion_tokens': 8000, 'response_format': {'type': 'json_object'},
                'messages': [{'role': 'system', 'content': system_prompt},
                             {'role': 'user', 'content': user_prompt}]}
        request = urllib.request.Request(gateway.base_url + '/chat/completions',
            data=json.dumps(body).encode(), headers={
                'Authorization': 'Bearer ' + gateway.local_token, 'Content-Type': 'application/json'})
        start = time.monotonic()
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=max(timeout or 120, 310)) as response:
                    raw = json.load(response)
                break
            except urllib.error.HTTPError as exc:
                # Only infrastructure failures retry. The gateway retains each
                # paid/uncertain attempt; completed verdicts are never rerolled.
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
                time.sleep(15 * (attempt + 1))
        # OpenRouter requires its provider-prefixed routing alias. The upstream
        # fixed schema uses the bare Sol name; retain the exact original wire
        # body/response in the gateway and normalize only this documented alias.
        canonical = {k: v for k, v in body.items() if k != 'messages'}
        canonical['model'] = 'gpt-5.6-sol'
        record_response(canonical, body['messages'],
                        raw, (time.monotonic() - start) * 1000)
        choice = raw['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise ValueError('Judge response did not finish normally')
        parsed = llm_judge._extract_json(choice['message']['content'])
        if 'results' in parsed:
            if not isinstance(parsed['results'], list) or not parsed['results'] or any(
                    not isinstance(row, dict) or type(row.get('passed')) is not bool for row in parsed['results']):
                raise ValueError('Action judge verdicts must contain actual Boolean passed values')
            # Upstream validates the exact check IDs, count and required fields.
        elif type(parsed.get('passed')) is not bool:
            raise ValueError('Judge verdict must contain an actual Boolean passed')
        return parsed

    llm_judge._call_judge = call
    try:
        yield
    finally:
        llm_judge._call_judge = original
