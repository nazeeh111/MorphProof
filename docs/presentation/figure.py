"""Recorded code excerpts, exact behavioral witness, and bounded fresh campaign."""
from pathlib import Path
import json,html
P=Path(__file__).resolve().parent;cases=json.loads((P/'failed/counterexamples.json').read_text());w=next(c for c in cases if c.get('input')==[1.,-1.]and not c.get('keyword'));r=json.loads((P/'repaired/report.json').read_text());assert w['minimized_input']==[1.]and w['minimized_reference']['value']==1. and w['minimized_candidate']['value']==0.;assert r['totals']['tested']==64 and r['totals']['api_tested']==3 and r['totals']['failures']==0;assert'.copied().skip(1)'in(P/'initial.rs').read_text()and'.skip(1)'not in(P/'repaired.rs').read_text()
def t(x,y,s,size=16,c='#242923',mono=False):return f'<text x="{x}" y="{y}" font-family="{("Courier New, Courier, monospace"if mono else"Arial, Helvetica, sans-serif")}" font-size="{size}" fill="{c}">{html.escape(s)}</text>'
def draw(phone):
 W=375 if phone else 1200;H=1060 if phone else 640;p=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc"><title id="title">One omitted item changes the answer</title><desc id="desc">Actual synthetic ordered sum-of-squares transformation. A disclosed Rust loop omission reduces the failing input from two values to one. On [1.0], Python returns 1.0 and seeded Rust returns 0.0. Restoring the generated loop passes 64 positional and 3 keyword checks with a fresh seed. These are finite observations, not universal equivalence or autonomous repair.</desc><rect width="100%" height="100%" fill="#f5f3ec"/>',t(22,33,'MorphProof / BEHAVIORAL EVIDENCE',13,'#236f61')]
 if phone:p +=[t(22,76,'One omitted item.',29),t(22,113,'A different answer.',29)]
 else:p +=[t(22,82,'One omitted item. A different answer.',40)]
 panels=[(18,150,339,178),(18,347,339,164),(18,530,339,250),(18,799,339,202)]if phone else[(22,135,345,170),(387,135,345,170),(752,135,426,320),(22,355,710,190)]
 for i,(x,y,ww,hh)in enumerate(panels):
  p.append(f'<rect x="{x}" y="{y}" width="{ww}" height="{hh}" fill="#fffefa" stroke="#cbd1c6"/>')
  if i==0:p +=[t(x+16,y+29,'01 / PYTHON REFERENCE',13,'#687068'),t(x+16,y+69,'for value in values:',15,mono=True),t(x+16,y+99,'total += value * value',15,mono=True),t(x+16,y+143,'Ordered accumulation; source excerpt.',13,'#687068')]
  if i==1:p +=[t(x+16,y+29,'02 / DISCLOSED SEED',13,'#a33f20'),t(x+16,y+69,'values.iter().copied()',15,mono=True),t(x+16,y+99,'    .skip(1)',15,'#a33f20',True),t(x+16,y+143,'Generated Rust excerpt: omit item zero.',13,'#687068')]
  if i==2:
   p +=[t(x+16,y+29,'03 / SAVED COUNTEREXAMPLE',13,'#a33f20'),t(x+16,y+67,'[1.0, -1.0]  →  [1.0]',17,mono=True),t(x+16,y+105,'5 bounded minimization calls',14,'#687068'),t(x+16,y+153,'Python   1.0',25,'#236f61',True),t(x+16,y+192,'Rust     0.0',25,'#a33f20',True),t(x+16,y+229,'Same declared input; observed mismatch.',13,'#687068')]
  if i==3:p +=[t(x+16,y+29,'04 / RESTORE + CHALLENGE AGAIN',13,'#236f61'),t(x+16,y+69,'values.iter().copied()',15,mono=True),t(x+16,y+106,'64 positional + 3 keyword checks',17,'#236f61'),t(x+16,y+139,'Fresh seed 97; no mismatch observed.',14,'#687068'),t(x+16,y+172,'Deterministic restoration. No model call.',13,'#687068')]
 if phone:p.append(t(22,1035,'Finite evidence. Universal equivalence untested.',13,'#687068'))
 else:p +=[t(22,592,'One synthetic sum-of-squares function. Rust 1.100.0 / PyO3 0.27.2 / Python 3.12.13.',17,'#687068'),t(22,623,'Finite evidence, not a proof. Source pin 1.99.1 was not exercised; no adaptive-selection or autonomous-repair claim.',15,'#687068')]
 p.append('</svg>');return''.join(p)
for phone in[False,True]:(P/('witness-mobile.svg'if phone else'witness.svg')).write_text(draw(phone))
