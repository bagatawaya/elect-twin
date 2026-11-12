"""Pure, deny-by-default project export preview. Does not read files or send data.

Current schema is projects.documents/decisions, not pods/Zettelkasten. This is
structural minimization plus obvious-secret redaction, NOT a PII classifier.
Selected prose may still contain private facts: exact preview approval required.
"""
import re
SECRET=re.compile(r'(?<![A-Za-z0-9])(?:sk-(?:or-v1-|ant-|proj-)?[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{16,}|gsk_[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9_.~+/-]{12,})',re.I)

def sanitize_shared_context(project,selection,*,private_values=()):
    if not isinstance(project,dict) or not isinstance(selection,dict):raise ValueError('Project and selection must be objects')
    if set(selection)-{'document_ids','decision_ids'}:raise ValueError('Only explicit document and decision selection is supported; pods and history require a separate schema')
    if not isinstance(private_values,(list,tuple)) or any(not isinstance(v,str) or len(v)<8 for v in private_values):raise ValueError('Private canaries must be strings of at least eight characters')
    secrets=sorted(private_values,key=len,reverse=True)
    def clean(value):
        if not isinstance(value,str) or len(value)>100000:raise ValueError('Invalid selected text')
        for secret in secrets:value=value.replace(secret,'[REDACTED]')
        return SECRET.sub('[REDACTED]',value)
    result={'documents':[],'decisions':[]}
    for kind,key in [('documents','document_ids'),('decisions','decision_ids')]:
        ids=selection.get(key,[])
        if not isinstance(ids,list) or len(ids)>50 or any(not isinstance(i,str) or not i or len(i)>128 for i in ids) or len(set(ids))!=len(ids):raise ValueError('Invalid explicit selection')
        items=project.get(kind,[])
        if not isinstance(items,list):raise ValueError('Unsupported project schema')
        for ident in ids:
            matches=[x for x in items if isinstance(x,dict) and x.get('id')==ident]
            if len(matches)!=1:raise ValueError('Selected item missing or ambiguous; refresh preview')
            # IDs, names, paths, links, author and arbitrary nested metadata never export.
            result[kind].append({'text':clean(matches[0].get('text'))})
    import json
    if len(json.dumps(result,ensure_ascii=False).encode())>7500:raise ValueError('Shared context too large; select less text')
    return {'context':result,'requires_exact_preview_approval':True,'warning':'Selected text can still contain personal or confidential facts. Review every character before sharing. No history, project identity, files, credentials or metadata are automatically included.'}


def sanitize_shared_text(text):
    if not isinstance(text,str) or not text.strip() or len(text)>8000:
        raise ValueError('Shared text must contain 1 to 8000 characters')
    return SECRET.sub('[REDACTED]',text)
