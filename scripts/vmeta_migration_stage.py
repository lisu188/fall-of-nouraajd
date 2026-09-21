from pathlib import Path
import json
import os
import subprocess

path = 'src/object/CCreature.h'
file = Path(path)
text = file.read_text()
old = 'V_METHOD(CCreature, getManaRegRate, int),\n           V_METHOD(CCreature, getEffects, std::set<std::shared_ptr<CEffect>>))'
new = 'V_METHOD(CCreature, getManaRegRate, int))'
if text.count(old) != 1:
    raise RuntimeError('expected exactly one redundant getEffects method registration')
file.write_text(text.replace(old, new))
subprocess.run(['clang-format', '-i', path], check=True)
subprocess.run(['clang-format', '--dry-run', '--Werror', path], check=True)
subprocess.run(['git', 'diff', '--check'], check=True)
subprocess.run(['git', 'diff', '--', path], check=True)
payload = json.dumps({'content': file.read_text(), 'encoding': 'utf-8'})
result = subprocess.run(['gh', 'api', '--method', 'POST', 'repos/' + os.environ['GITHUB_REPOSITORY'] + '/git/blobs', '--input', '-'], input=payload, text=True, capture_output=True, check=True)
print('FORMATTED_TREE=' + json.dumps([{'path': path, 'mode': '100644', 'type': 'blob', 'sha': json.loads(result.stdout)['sha']}]))
