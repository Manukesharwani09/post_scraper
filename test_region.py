import re
def get_region(affil):
    parts = affil.split(',')
    for part in reversed(parts):
        p = re.sub(r'\d+', '', part).strip().strip('.')
        if '@' in p or p.lower() in ("inc", "llc"): continue
        if any(w in p.lower() for w in ("university", "department", "hospital", "institute", "school")):
            continue
        if len(p)>2: return p
    return "Global"

print(get_region("Department of Oncology, Asan Medical Center, Seoul 05505, Republic of Korea."))
