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
