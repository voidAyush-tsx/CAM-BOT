import hashlib, json, subprocess
from pathlib import Path
baseline='e58b8028329b9dfed92b37598eb9ff5cd934e7ed'
prefixes=('docs/evidence/','experiments/','Task2/','media/','config/')
paths=subprocess.check_output(['git','ls-tree','-r','--name-only',baseline],text=True).splitlines()
protected=[p for p in paths if p.startswith(prefixes) or p=='artifacts/verification/cambot_build_report.json']
rows=[]
for name in protected:
    blob=subprocess.check_output(['git','show',f'{baseline}:{name}'])
    is_lfs=blob.startswith(b'version https://git-lfs.github.com/spec/v1\n')
    expected=next(x.split(b':',1)[1].decode() for x in blob.splitlines() if x.startswith(b'oid sha256:')) if is_lfs else hashlib.sha256(blob).hexdigest()
    actual=hashlib.sha256(Path(name).read_bytes()).hexdigest()
    assert actual==expected, name
    rows.append({'path':name,'sha256':actual,'storage':'lfs' if is_lfs else 'git'})
print(json.dumps({'result':'PASS','baseline_commit':baseline,'count':len(rows),'scope':'all pre-existing evidence, experiments, media, Task2, root config and published build report','files':rows},indent=2))
