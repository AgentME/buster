from pathlib import PurePosixPath

def normpath(path):
    new_parts = []
    for part in path.parts:
        if part == '..':
            new_parts.pop()
        else:
            new_parts.append(part)
    return PurePosixPath(*new_parts)
