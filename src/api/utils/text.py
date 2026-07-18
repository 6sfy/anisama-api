import re


def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower().strip()) if t else ""


def base_title(t):
    if not t:
        return "", ""
    base = t.strip()
    lang = ""
    if re.search(r'\s+[Vv][Ff]\s*$', base):
        base = re.sub(r'\s+[Vv][Ff]\s*$', '', base)
        lang = "vf"
    elif re.search(r'\s+[Vv][Oo][Ss][Tt][Ff][Rr]\s*$', base):
        base = re.sub(r'\s+[Vv][Oo][Ss][Tt][Ff][Rr]\s*$', '', base)
        lang = "vostfr"
    elif re.search(r'\s+[Vv][Oo]\s*$', base):
        base = re.sub(r'\s+[Vv][Oo]\s*$', '', base)
        lang = "vo"
    return base.strip(), lang
