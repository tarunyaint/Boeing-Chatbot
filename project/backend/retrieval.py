"""
retrieval.py
Finds the most relevant manual chunks for a user query
using keyword matching with synonym expansion.
"""

import re

# Words too common to be useful for search
STOP_WORDS = {
    "the","a","an","and","or","of","to","in","is","are","be","for","with",
    "this","that","it","as","at","by","on","not","from","per","if","shall",
    "must","may","should","will","can","do","no","all","any","each","such",
    "used","use","using","after","before","when","where","which","who","how",
    "its","their","they","been","has","have","had","was","were","than","then",
    "into","only","also","both","more","most","other","some","these","those",
    "during","through","between","within","without","what","give","tell","me",
    "show","explain","describe","list","find","overview","about","chapter",
    "section","please","want","need","help","get","does","the","are","steps",
}

# Synonym groups — searching any word expands to all in the group
SYNONYMS = {
    "engine":    ["engine","turbine","cfm","nacelle","fan","thrust","powerplant"],
    "gear":      ["gear","landing","wheel","tire","tyre","brake","strut","oleos"],
    "hydraulic": ["hydraulic","hyd","fluid","pump","pressure","reservoir","actuator"],
    "electric":  ["electrical","electric","power","battery","generator","idg","bus"],
    "avionics":  ["avionics","vhf","radio","radar","fmc","navigation","gps","iru","ils"],
    "fuel":      ["fuel","tank","defuel","refuel","jettison"],
    "flight":    ["flight","aileron","elevator","rudder","spoiler","flap","slat","control"],
    "fuselage":  ["fuselage","skin","stringer","frame","doubler","patch","fuselage"],
    "wing":      ["wing","spar","rib","leading","trailing","slat","flap"],
    "safety":    ["safety","warning","caution","ppe","loto","lockout","tagout","hazard","fod"],
    "torque":    ["torque","tighten","fastener","bolt","nut","screw","nm","lbf","ft"],
    "inspect":   ["inspection","inspect","check","examine","serviceable","criteria","interval"],
    "repair":    ["repair","replace","fix","restore","patch","overhaul"],
    "composite": ["composite","carbon","fibre","fiber","delamination","resin","epoxy"],
    "oxygen":    ["oxygen","o2","mask","cylinder","pressure"],
}


def tokenise(text):
    tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


def expand(tokens):
    expanded = set(tokens)
    for t in tokens:
        for synonyms in SYNONYMS.values():
            if t in synonyms:
                expanded.update(synonyms)
    return list(expanded)


def retrieve(db, query, limit=6):
    tokens   = tokenise(query)
    keywords = expand(tokens)
    if not keywords:
        return []
    return db.search_chunks(keywords, limit=limit)


def build_context(chunks):
    if not chunks:
        return "No relevant manual sections found for this query."
    parts = []
    seen  = set()
    for c in chunks:
        text = c.get("content", "").strip()
        if text in seen:
            continue
        seen.add(text)
        chapter = c.get("chapter") or "General"
        section = c.get("section") or ""
        header  = f"[{chapter}" + (f"  >  {section}" if section else "") + "]"
        parts.append(f"{header}\n{text}")
    return "\n\n---\n\n".join(parts)
