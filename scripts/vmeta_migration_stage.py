from pathlib import Path
import collections
import re
import subprocess


def split_arguments(text):
    result = []
    start = 0
    depth = 0
    for position, char in enumerate(text):
        if char in '(<[{':
            depth += 1
        elif char in ')>]}':
            depth -= 1
        elif char == ',' and depth == 0:
            result.append(text[start:position].strip())
            start = position + 1
    result.append(text[start:].strip())
    return result


def macros(text, pattern):
    for match in re.finditer(pattern, text):
        start = match.end()
        depth = 1
        end = start
        while end < len(text) and depth:
            depth += (text[end] == '(') - (text[end] == ')')
            end += 1
        if depth:
            raise RuntimeError('unbalanced metadata declaration')
        yield split_arguments(text[start:end - 1])


def normalize(value):
    value = re.sub(r'\b(const|volatile)\b', '', value)
    return re.sub(r'\s|&', '', value)


files = subprocess.check_output(['git', 'ls-files', 'src', 'tests/unit'], text=True).splitlines()
names = collections.defaultdict(list)
issues = []
registrations = 0
for filename in files:
    if not filename.endswith(('.h', '.hpp', '.cpp')):
        continue
    text = Path(filename).read_text()
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    for arguments in macros(text, r'\bV_META\s*\('):
        registrations += 1
        name = arguments[0]
        names[name].append(filename)
        seen = set()
        properties = set()
        body = ','.join(arguments[2:])
        for prop in macros(body, r'\bV_PROPERTY\s*\('):
            if len(prop) != 5:
                issues.append((filename, name, 'unparsed property', prop))
                continue
            if prop[2] in properties:
                issues.append((filename, name, 'duplicate property', prop[2]))
            properties.add(prop[2])
            for key in [(prop[3], ()), (prop[4], (normalize(prop[1]),))]:
                if key in seen:
                    issues.append((filename, name, 'duplicate accessor', key))
                seen.add(key)
        for method in macros(body, r'\bV_METHOD\s*\('):
            key = (method[1], tuple(normalize(value) for value in method[3:]))
            if key in seen:
                issues.append((filename, name, 'duplicate method', key))
            seen.add(key)
for name, locations in names.items():
    if len(locations) > 1:
        issues.append(('name collision candidate', name, locations))
print('REGISTRATION_AUDIT: declarations=' + str(registrations) + ' findings=' + str(len(issues)))
for issue in issues:
    print(issue)
