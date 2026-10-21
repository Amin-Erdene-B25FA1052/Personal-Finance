import re
from finance_tool.models import ClassifyResult

def owner_key(name):
    return re.sub(r'[^\w]', '',name.split()[0]).upper()

def classify_line(description, counterparty_account, owner):
    d=description.strip();upper=d.upper()
    if (upper.startswith('МЕССЭЖ МЭДЭГДЭЛ ШИМТГЭЛ') or 'ИБ БАНК ХООРОНДЫН ГҮЙЛГЭЭНИЙ ШИМТГЭЛ' in upper or upper.startswith('ДАНС ХӨТӨЛСНИЙ ШИМТГЭЛ') or re.match(r'ATM .*fee',d,re.I) or upper.startswith('К.Б: CARD PAYMENT')):
        return ClassifyResult('rule','Bank Fees & Charges',None,None)
    if d.startswith('POS:'):
        bits=d.split(':');name=bits[2].strip().upper() if len(bits)>2 else d.upper()
        return ClassifyResult('none',None,'pos:'+name,name)
    acct=(counterparty_account or '').strip()
    # Own transfers: own name appears in destination parenthesis, not merely before '-с'.
    paren=re.search(r'\(([^)]*)\)',d)
    normalized=re.sub(r'[^\w]','',upper)
    # Own transfer only when the recipient/sender is demonstrably the holder;
    # the sender prefix alone does not establish ownership of the recipient.
    own=(upper.startswith('ДАНСНЫ ДООД ҮЛДЭГДЭЛ ШИЛЖҮҮЛЭВ')
         or normalized.startswith('ОРЛОГО'+owner)
         or (upper.startswith('ШИЛЖҮҮЛЭГЧ ') and owner in normalized)
         or (upper.endswith('-С') and owner in normalized)
         or (paren is not None and owner in re.sub(r'[^\w]','',paren.group(1).upper())))
    if own:return ClassifyResult('own','Own transfers',None,None)
    if acct:return ClassifyResult('none',None,'acct:'+acct,acct)
    return ClassifyResult('none',None,None,None)
