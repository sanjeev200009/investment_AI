import json
import logging
from typing import AsyncGenerator
from sqlalchemy.orm import Session

from app.services import llm
from app.services.agent.memory import ConversationMemory, ScriptCleaner, clean_script, reply_language
from app.services.agent.tools import ToolExecutor, TOOL_SCHEMAS

logger = logging.getLogger(__name__)

MAX_LOOPS = 5
AGENT_TEMPERATURE = 0.3   # factual finance answers; 0.7 invited embellishment
# Reasoning models spend hidden tokens before any answer; at 2000 the Qwen
# fallback used all of them thinking about a Sinhala question and returned
# nothing (finish_reason=length). Length is held down by the prompt instead.
AGENT_MAX_TOKENS = 6000

# Only reachable if the model returns nothing even on the forced final round.
EMPTY_ANSWER = (
    "I couldn't put together an answer this time. Please try asking again, "
    "perhaps phrased more narrowly."
)


def _tools_for(loop_count: int):
    # The last round offers no tools, so the model must answer in prose from what
    # the earlier rounds fetched instead of spending the budget on another call
    # and leaving the user with nothing. (I-20, bug 1.)
    return TOOL_SCHEMAS if loop_count < MAX_LOOPS else None


def _start(memory: ConversationMemory, user_message: str) -> list[dict]:
    # Build the context BEFORE saving: load_history() would otherwise return the
    # just-saved row and build_context() appends it again, so the model saw the
    # question twice.
    messages = memory.build_context(user_message)
    memory.save_user_message(user_message)
    return messages


async def stream_agent(
    user_message: str,
    session_id: int,
    db: Session,
    user
) -> AsyncGenerator[str, None]:
    memory = ConversationMemory(session_id, db, user)
    tool_executor = ToolExecutor(db, str(user.user_id))
    messages = _start(memory, user_message)
    lang = reply_language(user, user_message)

    final_response = ""
    # Which provider/model actually answered, for ai_model_used. Set per loop
    # because failover is decided per request, not once per conversation.
    served_label = "unavailable"

    for loop_count in range(1, MAX_LOOPS + 1):
        response_stream, served = await llm.acreate(
            messages=messages,
            tools=_tools_for(loop_count),
            stream=True,
            role=llm.Role.AGENT,
            temperature=AGENT_TEMPERATURE,
            max_tokens=AGENT_MAX_TOKENS,
        )
        served_label = served.label

        tool_calls = {}
        turn_text = ""
        cleaner = ScriptCleaner(lang)

        async for chunk in response_stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # Prose is streamed in order whether or not a tool call is in flight:
            # models often say "let me check that" alongside the call, and it
            # belongs on screen, in the saved message, and in the assistant turn
            # the next round sees. (I-20, bug 2.)
            content = cleaner.feed(delta.content or "")
            if content:
                turn_text += content
                final_response += content
                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

            for tc in delta.tool_calls or []:
                slot = tool_calls.setdefault(
                    tc.index, {"id": "", "function": {"name": "", "arguments": ""}}
                )
                if tc.id:
                    slot["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        slot["function"]["name"] += tc.function.name
                    if tc.function.arguments:
                        slot["function"]["arguments"] += tc.function.arguments

        tail = cleaner.flush()
        if tail:
            turn_text += tail
            final_response += tail
            yield f"data: {json.dumps({'type': 'token', 'content': tail})}\n\n"

        if not tool_calls:
            break

        tool_call_list = [
            {"id": tc["id"], "type": "function", "function": tc["function"]}
            for tc in tool_calls.values()
        ]
        messages.append({
            "role": "assistant",
            "content": turn_text or None,
            "tool_calls": tool_call_list,
        })
        # Separate this round's prose from the next round's answer.
        if turn_text and not turn_text.endswith("\n"):
            final_response += "\n\n"
            yield f"data: {json.dumps({'type': 'token', 'content': chr(10) * 2})}\n\n"

        for tc in tool_call_list:
            tool_name = tc["function"]["name"]
            try:
                tool_args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                tool_args = {}

            yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name, 'args': tool_args})}\n\n"
            result_json = await tool_executor.execute(tool_name, tool_args)
            messages.append({
                "tool_call_id": tc["id"],
                "role": "tool",
                "name": tool_name,
                "content": result_json,
            })
            yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'summary': 'Done'})}\n\n"

    if not final_response.strip():
        final_response = EMPTY_ANSWER
        yield f"data: {json.dumps({'type': 'token', 'content': final_response})}\n\n"

    msg_id = memory.save_assistant_message(final_response.strip(), served_label)
    yield f"data: {json.dumps({'type': 'done', 'message_id': msg_id})}\n\n"


async def run_agent(
    user_message: str,
    session_id: int,
    db: Session,
    user
) -> tuple[str, list[dict]]:
    memory = ConversationMemory(session_id, db, user)
    tool_executor = ToolExecutor(db, str(user.user_id))
    messages = _start(memory, user_message)
    lang = reply_language(user, user_message)

    parts: list[str] = []
    tools_used = []
    served_label = "unavailable"

    for loop_count in range(1, MAX_LOOPS + 1):
        response, served = await llm.acreate(
            messages=messages,
            tools=_tools_for(loop_count),
            role=llm.Role.AGENT,
            temperature=AGENT_TEMPERATURE,
            max_tokens=AGENT_MAX_TOKENS,
        )
        served_label = served.label
        message = response.choices[0].message

        # Prose sent alongside tool calls is real output and belongs to the
        # answer, in order, same as the streaming path.
        if message.content:
            parts.append(clean_script(message.content, lang).strip())

        if not message.tool_calls:
            break

        tool_calls = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in message.tool_calls
        ]
        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            tools_used.append({"tool": tool_name})
            try:
                tool_args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                tool_args = {}
            result_json = await tool_executor.execute(tool_name, tool_args)
            messages.append({
                "tool_call_id": tc["id"],
                "role": "tool",
                "name": tool_name,
                "content": result_json,
            })

    final_response = "\n\n".join(p for p in parts if p) or EMPTY_ANSWER
    memory.save_assistant_message(final_response, served_label)
    return final_response, tools_used
