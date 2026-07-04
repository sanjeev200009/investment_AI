import json
import logging
from typing import AsyncGenerator
import openai
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.agent.memory import ConversationMemory
from app.services.agent.tools import ToolExecutor, TOOL_SCHEMAS

logger = logging.getLogger(__name__)
settings = get_settings()

def get_openrouter_client():
    return openai.AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
        timeout=15.0
    )

MODEL = "google/gemini-2.5-flash"

async def stream_agent(
    user_message: str,
    session_id: int,
    db: Session,
    user
) -> AsyncGenerator[str, None]:
    memory = ConversationMemory(session_id, db, user)
    tool_executor = ToolExecutor(db, str(user.user_id))

    memory.save_user_message(user_message)
    messages = memory.build_context(user_message)
    client = get_openrouter_client()

    max_loops = 5
    loop_count = 0
    final_response = ""

    while loop_count < max_loops:
        loop_count += 1
        response_stream = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            stream=True,
            temperature=0.7,
            max_tokens=2000,
        )

        tool_calls = {}
        tool_active = False

        async for chunk in response_stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            if delta.tool_calls:
                tool_active = True
                for tc in delta.tool_calls:
                    if tc.index not in tool_calls:
                        tool_calls[tc.index] = {
                            "id": tc.id or "",
                            "function": {"name": "", "arguments": ""}
                        }
                    if tc.id:
                        tool_calls[tc.index]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls[tc.index]["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments
            elif delta.content:
                if not tool_active:
                    final_response += delta.content
                    yield f"data: {json.dumps({'type': 'token', 'content': delta.content})}\n\n"
        
        if tool_active:
            # Reconstruct the tool call message to append to messages
            tool_call_list = []
            for idx, tc in tool_calls.items():
                tool_call_list.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": tc["function"]
                })
            
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tool_call_list
            })

            # Execute tools
            for tc in tool_call_list:
                tool_name = tc["function"]["name"]
                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}
                
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name, 'args': tool_args})}\n\n"
                
                result_json = await tool_executor.execute(tool_name, tool_args)
                
                messages.append({
                    "tool_call_id": tc["id"],
                    "role": "tool",
                    "name": tool_name,
                    "content": result_json
                })
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'summary': 'Done'})}\n\n"
        else:
            break

    msg_id = memory.save_assistant_message(final_response, MODEL)
    yield f"data: {json.dumps({'type': 'done', 'message_id': msg_id})}\n\n"

async def run_agent(
    user_message: str,
    session_id: int,
    db: Session,
    user
) -> tuple[str, list[dict]]:
    memory = ConversationMemory(session_id, db, user)
    tool_executor = ToolExecutor(db, str(user.user_id))

    memory.save_user_message(user_message)
    messages = memory.build_context(user_message)
    client = get_openrouter_client()

    max_loops = 5
    loop_count = 0
    final_response = ""
    tools_used = []

    while loop_count < max_loops:
        loop_count += 1
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            temperature=0.7,
            max_tokens=2000,
        )

        message = response.choices[0].message
        
        if message.tool_calls:
            # Need to convert to dict for appending to context
            tool_calls = []
            for tc in message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })
            
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": tool_calls
            })

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tools_used.append({"tool": tool_name})
                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except:
                    tool_args = {}
                result_json = await tool_executor.execute(tool_name, tool_args)
                messages.append({
                    "tool_call_id": tc["id"],
                    "role": "tool",
                    "name": tool_name,
                    "content": result_json
                })
        else:
            final_response = message.content or ""
            break
            
    memory.save_assistant_message(final_response, MODEL)
    return final_response, tools_used
