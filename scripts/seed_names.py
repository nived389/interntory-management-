import re,json
from pathlib import Path
text=Path('docs/requirements.txt').read_text()
result={}
for section,start,end,expected in [('Cafe','Appendix A -','Appendix B -',61),('Service','Appendix B -','Appendix C -',123)]:
    part=text[text.index(start):text.index(end)]
    names=[]
    for line in part.splitlines():
        if re.match(r'^\d+\. ',line):
            names.extend(re.split(r'(?:\d+|—)\. ',line)[1:])
    names=[n.replace('[PHOTO NEEDED]','').strip() for n in names]
    assert len(names)==expected,(section,len(names))
    result[section]=names
Path('seed-items.json').write_text(json.dumps(result,indent=2))
