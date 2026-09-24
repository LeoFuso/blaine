"""Scoped ACP read requests and results. Neither contract grants authority."""
from pathlib import PurePosixPath

from runtime.kernel.contracts import fields, identifier, text, unpack


def validate_read(value):
    fields(value, {'workspace', 'path', 'artifact'})
    text(value['workspace'], 512)
    text(value['path'], 512)
    identifier(value['artifact'])
    root, path = PurePosixPath(value['workspace']), PurePosixPath(value['path'])
    if (not root.is_absolute() or '..' in root.parts or path.is_absolute()
            or '..' in path.parts or path == PurePosixPath('.')
            or '\\' in value['path'] or '\\' in value['workspace']):
        raise ValueError('Expected absolute POSIX workspace and confined relative path')
    return value


def validate_read_result(raw, request):
    result = fields(unpack(raw, 'CapabilityResult'),
        {'operation_id', 'outcome', 'output', 'artifacts', 'error'})
    if (result['operation_id'] != request['operation_id'] or result['outcome'] != 'success'
            or result['artifacts'] != {} or result['error'] is not None):
        raise ValueError('Invalid workspace capability result')
    output = fields(result['output'], {'content'})
    text(output['content'])
    return output['content']


def legacy_receipt(task_id, request_ref, request, content_ref, content):
    """Receipt for the D2 exact-path form, admitted as capability-journal evidence.

    The returned text is the whole file as delivered by the authorized ACP client
    read (editor content may include unsaved edits), so the line range is the full
    returned text. E1.C replaces this with provider receipts of the same kind.
    """
    import hashlib
    from runtime.kernel.contracts import message
    lines = content.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    data = content.encode('utf-8')
    return message('WorkspaceReadReceipt', {
        'task_id': task_id, 'operation_id': request['operation_id'],
        'request_sha256': request_ref.rsplit(':', 1)[1], 'workspace_id': request['workspace'],
        'provider': {'kind': 'acp-client'}, 'operation': 'read_file', 'state': 'SUCCESS',
        'source': {'view': 'acp_text_file', 'class': 'project', 'path': request['path'],
                   'lines': [1, max(len(lines), 1)]},
        'response_ref': content_ref, 'response_sha256': hashlib.sha256(data).hexdigest(),
        'response_bytes': len(data), 'truncated': False})
