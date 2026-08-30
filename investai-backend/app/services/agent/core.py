import json
import logging
from typing import AsyncGenerator
from sqlalchemy.orm import Session

from app.services import llm
from app.services.agent.memory import ConversationMemory
from app.services.agent.tools import ToolExecutor, TOOL_SCHEMAS

logger = logging.getLogger(__name__)

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

    max_loops = 5
    loop_count = 0
    final_response = ""
    # Which provider/model actually answered, for ai_model_used. Set per loop
    # because failover is decided per request, not once per conversation.
    served_label = "unavailable"

    while loop_count < max_loops:
        loop_count += 1
        response_stream, served = await llm.acreate(
            messages=messages,
            tools=TOOL_SCHEMAS,
            stream=True,
            role=llm.Role.AGENT,
            temperature=0.7,
            max_tokens=2000,
        )
        served_label = served.label

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

    msg_id = memory.save_assistant_message(final_response, served_label)
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

    max_loops = 5
    loop_count = 0
    final_response = ""
    tools_used = []
    served_label = "unavailable"

    while loop_count < max_loops:
        loop_count += 1
        response, served = await llm.acreate(
            messages=messages,
            tools=TOOL_SCHEMAS,
            role=llm.Role.AGENT,
            temperature=0.7,
            max_tokens=2000,
        )
        served_label = served.label

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
            
    memory.save_assistant_message(final_response, served_label)
    return final_response, tools_used
