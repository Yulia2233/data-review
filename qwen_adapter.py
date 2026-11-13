"""Lossless message-field adapter for displaying saved Qwen training samples."""
import json


def display(sample):
    output = []
    pending = {}
    metadata = sample.get('message_meta', [])
    for index, message in enumerate(sample['messages']):
        role = message['role']
        meta = (metadata[index] or {}) if index < len(metadata) else {}
        if role == 'tool':
            call = message.get('tool_call_id')
            if call not in pending:
                raise ValueError('Tool observation without matching call: ' + str(call))
            part = pending.pop(call)
            part['state']['output'] = message.get('content', '')
            part['state']['status'] = 'completed'
            continue
        parts = []
        reasoning = message.get('reasoning_content')
        if reasoning is not None:
            sources = meta.get('reasoning_sources') or []
            annotated = any(source.get('origin') == 'codex_synthesized_annotation' or
                            (source.get('annotation_provenance') or {}).get('origin') == 'posthoc_annotation_not_original_hidden_thought'
                            for source in sources if isinstance(source, dict))
            parts.append({'type': 'reasoning', 'text': reasoning,
                          'source_label': '事后补写解释' if annotated else '数据中保存的思考',
                          'reasoning_sources': [source for source in sources if source is not None], 'source_message_index': index})
        content = message.get('content')
        if content:
            if isinstance(content, str):
                parts.append({'type': 'text', 'text': content})
            else:
                for item in content:
                    if item.get('type') in ('text', 'input_text'):
                        parts.append({'type': 'text', 'text': item.get('text', '')})
                    else:
                        parts.append({'type': 'source-content', 'content': item})
        for call in message.get('tool_calls', []):
            function = call['function']
            arguments = function.get('arguments', {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    pass
            part = {'type': 'tool', 'tool': function['name'], 'callID': call['id'],
                    'state': {'input': arguments, 'status': 'pending'}, 'source_message_index': index}
            if call['id'] in pending:
                raise ValueError('Duplicate tool call id')
            parts.append(part)
            pending[call['id']] = part
        output.append({'info': {'role': role, 'source_message_index': index}, 'parts': parts})
    return {'schema_version': 'datav1-display-v1', 'id': sample['id'], 'messages': output,
            'tool_media': [], 'source_schema_version': sample.get('schema_version'),
            'source_message_count': len(sample['messages'])}
