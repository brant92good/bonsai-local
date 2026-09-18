import hashlib,json,pathlib,sys,time,os
root=pathlib.Path(os.environ.get('BONSAI_ROOT',str(pathlib.Path(__file__).resolve().parents[1])))
sys.path.insert(0,str(root/'mtp/llama/gguf-py'))
from gguf import GGUFReader
base=GGUFReader(str(root/'models/Ternary-Bonsai-2-27B-PQ2_0.gguf'))
mtp=GGUFReader(str(root/'models/Ternary-Bonsai-2-27B-PQ2_0-MTP-Q8_0.gguf'))
byname={t.name:t for t in mtp.tensors};checks=[]
for i,a in enumerate(base.tensors):
    other=byname.get(a.name)
    same_shape=other is not None and a.shape.tolist()==other.shape.tolist() and a.tensor_type==other.tensor_type and a.n_bytes==other.n_bytes
    ah=hashlib.sha256(memoryview(a.data).cast('B')).hexdigest()
    bh=hashlib.sha256(memoryview(other.data).cast('B')).hexdigest() if same_shape else None
    checks.append({'name':a.name,'bytes':a.n_bytes,'base_sha256':ah,'mtp_sha256':bh,'identical':same_shape and ah==bh})
    if (i+1)%100==0:print(f'Compared {i+1}/{len(base.tensors)} base tensors',flush=True)
original={t.name for t in base.tensors}
added=[{'name':t.name,'shape':t.shape.tolist(),'type':t.tensor_type.name,'bytes':t.n_bytes} for t in mtp.tensors if t.name not in original]
meta={k:v.contents() for k,v in mtp.fields.items() if 'nextn' in k or k in ['general.architecture','qwen35.block_count','qwen35.context_length']}
report={'base_tensor_count':len(base.tensors),'mtp_tensor_count':len(mtp.tensors),'base_tensors_identical':sum(c['identical'] for c in checks),'all_base_tensors_identical':all(c['identical'] for c in checks),'added_tensors':added,'metadata':meta,'checks':checks}
(root/'mtp/base-tensor-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('checks','added_tensors')},indent=2))
if not report['all_base_tensors_identical']:raise RuntimeError('MTP model unexpectedly changes a base tensor')
