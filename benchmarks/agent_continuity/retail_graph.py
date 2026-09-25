"""Ordinary LangGraph application around native retail participants.

This module defines workload routing, not recovery. SqliteSaver owns checkpoints;
AtMem's installed node owns governed dispatch. No retry, receipt or repair code.
"""
from __future__ import annotations

import json
from typing import TypedDict
import uuid


class Conversation(TypedDict):
    agent_state: dict
    user_state: dict
    message: dict
    trajectory: list
    steps: int
    errors: int
    next_role: str
    termination: str
    host_message_id: str


def build_graph(agent, user, *, checkpointer, public_call, governed_node=None, observer=None):
    from langgraph.graph import StateGraph, START, END
    from tau2.agent.llm_agent import LLMAgentState
    from tau2.user.user_simulator_base import UserState
    from tau2.data_model.message import AssistantMessage, UserMessage, ToolMessage, MultiToolMessage

    def message(value):
        if value.get('tool_messages') is not None:
            return MultiToolMessage.model_validate(value)
        return {'assistant': AssistantMessage, 'user': UserMessage, 'tool': ToolMessage}[value['role']].model_validate(value)

    def update(state, output, *, role, participant_state=None):
        value = output.model_dump(mode='json')
        termination = 'user_stop' if role == 'user' and user.is_stop(output) else 'agent_stop' if role == 'agent' and agent.is_stop(output) else ''
        if role == 'user' and output.is_tool_call():
            raise ValueError('This qualified retail profile has no user tools')
        next_role = 'tools' if role == 'agent' and output.is_tool_call() else 'agent' if role == 'user' else 'user'
        result = {'message': value, 'trajectory': state['trajectory'] + [value],
                  'steps': state['steps'] + 1, 'next_role': next_role, 'termination': termination}
        if participant_state is not None:
            result[role + '_state'] = participant_state.model_dump(mode='json')
        return result

    def user_node(state):
        output, participant = user.generate_next_message(message(state['message']), UserState.model_validate(state['user_state']))
        output.validate()
        return update(state, output, role='user', participant_state=participant)

    def agent_node(state):
        output, participant = agent.generate_next_message(message(state['message']), LLMAgentState.model_validate(state['agent_state']))
        output.validate()
        result = update(state, output, role='agent', participant_state=participant)
        result['host_message_id'] = 'message_' + uuid.uuid4().hex
        return result

    def tools_node(state, config):
        original = AssistantMessage.model_validate(state['message'])
        if governed_node is not None:
            # Pure wire conversion. No key derivation, cache, receipt check or retry.
            calls = [{'id': call.id, 'name': call.name, 'args': call.model_dump(mode='json')}
                     for call in original.tool_calls]
            result = governed_node({'messages': [{'role': 'assistant', 'id': state['host_message_id'], 'tool_calls': calls}]}, config)
            if [item.get('tool_call_id') for item in result['messages']] != [call.id for call in original.tool_calls]:
                raise ValueError('governed replies do not match the requested tool calls')
            replies = [json.loads(item['content']) for item in result['messages']]
        else:
            replies = []
            for call in original.tool_calls:
                if observer is None:
                    replies.append(public_call(call.model_dump(mode='json')))
                else:
                    # Instrumentation only. No observer result affects routing.
                    with observer.attempt(workflow_id='retail', operation_id=call.id, run_id=config['configurable']['run_id']):
                        replies.append(public_call(call.model_dump(mode='json')))
        values = [ToolMessage.model_validate(reply) for reply in replies]
        if [value.id for value in values] != [call.id for call in original.tool_calls]:
            raise ValueError('native tool replies do not match their calls')
        incoming = MultiToolMessage(role='tool', tool_messages=values) if len(values) > 1 else values[0]
        return {'message': incoming.model_dump(mode='json'),
                'trajectory': state['trajectory'] + [value.model_dump(mode='json') for value in values],
                'errors': state['errors'] + sum(value.error for value in values),
                'steps': state['steps'] + 1, 'next_role': 'agent'}

    def route(state):
        if state['termination'] or state['steps'] >= 58 or state['errors'] >= 5:
            return END
        return state['next_role']

    graph = StateGraph(Conversation)
    for name, node in [('agent', agent_node), ('user', user_node), ('tools', tools_node)]:
        graph.add_node(name, node)
        graph.add_conditional_edges(name, route, ['agent', 'user', 'tools', END])
    graph.add_conditional_edges(START, route, ['agent', 'user', 'tools', END])
    return graph.compile(checkpointer=checkpointer)


def initial_state(agent, user):
    from tau2.orchestrator.orchestrator import DEFAULT_FIRST_AGENT_MESSAGE
    first = DEFAULT_FIRST_AGENT_MESSAGE.model_copy(deep=True)
    return {'agent_state': agent.get_init_state([first]).model_dump(mode='json'),
            'user_state': user.get_init_state().model_dump(mode='json'),
            'message': first.model_dump(mode='json'), 'trajectory': [first.model_dump(mode='json')],
            'steps': 0, 'errors': 0, 'next_role': 'user', 'termination': '', 'host_message_id': ''}
