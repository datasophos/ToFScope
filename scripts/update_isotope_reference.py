"""Manually build the offline catalog from saved NIST/CIAAW source pages.

No download occurs: fetch/save the named official pages, then pass their paths.
"""
import argparse
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tofscope.science.isotopes import IsotopeRecord,records_checksum


class ReferenceHTML(HTMLParser):
    def __init__(self):
        super().__init__();self.in_pre=False;self.pre='';self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='pre':self.in_pre=True
        if tag=='tr':self.row=[]
        if tag=='td':
            # The published table omits some <tr> and </td> tags. Apply the
            # browser's implicit-cell closure rather than dropping those rows.
            if self.row is None:self.row=[]
            if self.cell is not None:self.row.append(self.cell.strip())
            self.cell=''
    def handle_endtag(self,tag):
        if tag=='pre':self.in_pre=False
        if tag=='td' and self.cell is not None and self.row is not None:self.row.append(self.cell.strip());self.cell=None
        if tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None
    def handle_data(self,data):
        if self.in_pre:self.pre+=data
        if self.cell is not None:self.cell+=data


def number_with_uncertainty(text):
    text=''.join(text.split())
    match=re.fullmatch(r'(\d+(?:\.\d+)?)(?:\((\d+)(#?)\))?',text)
    if not match:raise ValueError(f'Unsupported reference number: {text!r}')
    value=float(match[1]);digits=len(match[1].split('.')[1]) if '.' in match[1] else 0
    uncertainty=float(Decimal(match[2]).scaleb(-digits)) if match[2] else None
    return value,uncertainty,bool(match[3])


def parse_nist(text):
    parser=ReferenceHTML();parser.feed(text);records=[]
    for block in re.split(r'\n\s*\n',parser.pre):
        if 'Atomic Number =' not in block:continue
        fields=dict(line.split(' = ',1) for line in block.strip().splitlines() if ' = ' in line)
        mass,uncertainty,estimated=number_with_uncertainty(fields['Relative Atomic Mass'])
        symbol=fields['Atomic Symbol'];symbol='H' if symbol in ('D','T') else symbol
        records.append(dict(symbol=symbol,mass_number=int(fields['Mass Number']),neutral_mass_u=mass,
                            mass_uncertainty_u=uncertainty,mass_estimated=estimated))
    if len(records)<300:raise ValueError('NIST source did not contain a complete isotope table.')
    return records


def parse_ciaaw(text):
    parser=ReferenceHTML();parser.feed(text);result={};symbol=None
    for row in parser.rows:
        if len(row)>=5 and row[0].isdigit():symbol=row[1];mass,composition=row[3:5]
        elif len(row)==2 and symbol is not None:mass,composition=row
        else:continue
        mass=int(mass.strip('[]'));composition=''.join(composition.split())
        if composition=='-':lo=hi=uncertainty=None
        elif composition.startswith('['):
            lo,hi=(float(x) for x in composition.strip('[]').split(','));uncertainty=None
        else:lo,uncertainty,_=number_with_uncertainty(composition);hi=lo
        result[symbol,mass]=(lo,hi,uncertainty)
    if len(result)<280:raise ValueError('CIAAW source did not contain a complete abundance table.')
    return result


def build(nist_path,ciaaw_path,output):
    nist=Path(nist_path).read_bytes();ciaaw=Path(ciaaw_path).read_bytes()
    rows=parse_nist(nist.decode('cp1252'));abundances=parse_ciaaw(ciaaw.decode('utf-8'))
    records=[]
    for row in rows:
        lo,hi,uncertainty=abundances.get((row['symbol'],row['mass_number']),(None,None,None))
        record=IsotopeRecord(**row,abundance_low=lo,abundance_high=hi,abundance_uncertainty=uncertainty,source_id='NIST-2015-CIAAW-2024')
        records.append(asdict(record))
    records.sort(key=lambda r:(r['symbol'],r['mass_number']))
    data=dict(metadata=dict(schema_version=1,retrieved=str(date.today()),records_sha256=records_checksum(records),
        sources=[dict(id='NIST-2015',revision='January 2015; isotope masses AME2012',url='https://www.nist.gov/pml/atomic-weights-and-isotopic-compositions-relative-atomic-masses',sha256=hashlib.sha256(nist).hexdigest()),
                 dict(id='CIAAW-2024',revision='Isotopic Compositions of the Elements 2024',url='https://ciaaw.org/isotopic-abundances.htm',sha256=hashlib.sha256(ciaaw).hexdigest())],
        electron_mass=dict(value_u=.0005485799090441,source='CODATA2022',url='https://physics.nist.gov/cgi-bin/cuu/Value?meu'),
        redistribution_review='Extracted factual numerical records only, with source attribution; no source HTML, scripts, table layout or prose redistributed. No explicit CIAAW data license found; no open-license claim is made.'),isotopes=records)
    Path(output).write_text(json.dumps(data,indent=2)+'\n');print(f'Wrote {len(records)} isotope records to {output}')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--nist',required=True);parser.add_argument('--ciaaw',required=True);parser.add_argument('--output',default='data/reference/isotopes.json')
    args=parser.parse_args();build(args.nist,args.ciaaw,args.output)
