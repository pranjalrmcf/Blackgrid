"""Build the two-page brief from docs/technical_summary.md.

Optional documentation tooling: reportlab and pypdf; not runtime dependencies.
"""
from pathlib import Path
import html
import re

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'output/pdf/blackgrid_technical_summary.pdf'
NAVY=colors.HexColor('#16324b')

def prose(text):
    text=re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',text)
    text=text.replace('\u2013','-').replace('\u2014','-').replace('\u2019',"'")
    text=html.escape(text)
    return re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',text)

def build(size):
    body=ParagraphStyle('Body',fontName='Helvetica',fontSize=size,leading=size*1.32,
        spaceAfter=7,textColor=colors.HexColor('#263746'),alignment=TA_LEFT)
    small=ParagraphStyle('Small',parent=body,fontSize=size-1.2,leading=(size-1.2)*1.3,spaceAfter=4)
    heading=ParagraphStyle('Heading',parent=body,fontName='Helvetica-Bold',fontSize=12,
        leading=15,spaceBefore=9,spaceAfter=7,textColor=NAVY,keepWithNext=True)
    title=ParagraphStyle('Title',parent=heading,fontSize=22,leading=26,spaceBefore=0,spaceAfter=8)
    cell=ParagraphStyle('Cell',parent=small,fontSize=size-1,leading=(size-1)*1.28,spaceAfter=0)
    white=ParagraphStyle('White',parent=cell,fontName='Helvetica-Bold',textColor=colors.white)
    story=[];lines=(ROOT/'docs/technical_summary.md').read_text(encoding='utf-8').splitlines();i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('Technical summary |'):
            story.append(Paragraph('TECHNICAL BRIEF / 19 OCTOBER 2026',small));story.append(Spacer(1,5));i+=1;continue
        if line=='<!-- PAGE BREAK -->':story.append(PageBreak());i+=1;continue
        if line.startswith('# '):
            story.append(Paragraph('BLACKGRID',title))
            story.append(Paragraph('Evidence-grounded network investigations',heading));i+=1;continue
        if line.startswith('## '):story.append(Paragraph(prose(line[3:]),heading));i+=1;continue
        if line.startswith('### '):story.append(Paragraph(prose(line[4:]),heading));i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[c.strip() for c in lines[i].strip().strip('|').split('|')];i+=1
                if all(re.fullmatch(r'[-: ]+',c) for c in cells):continue
                rows.append([Paragraph(prose(c),white if not rows else cell) for c in cells])
            table=Table(rows,colWidths=[112,157,A4[0]-88-269],hAlign='LEFT',repeatRows=1)
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#edf3f7'),colors.white]),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),
                ('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),
                ('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,0),.5,NAVY)]))
            story.extend([table,Spacer(1,8)]);continue
        paragraph=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','<!--')):
            paragraph.append(lines[i].strip());i+=1
        text=' '.join(paragraph)
        style=small if re.match(r'^\d\. ',text) or text.startswith('Original project code') else body
        story.append(Paragraph(prose(text),style))
    def footer(canvas,doc):
        canvas.setStrokeColor(colors.HexColor('#cbd7df'));canvas.line(44,32,A4[0]-44,32)
        canvas.setFont('Helvetica',8);canvas.setFillColor(NAVY)
        canvas.drawString(44,20,'BLACKGRID / Methods, evidence and limits')
        canvas.drawRightString(A4[0]-44,20,str(doc.page)+' / 2')
    SimpleDocTemplate(str(OUTPUT),pagesize=A4,leftMargin=44,rightMargin=44,topMargin=37,bottomMargin=43,
        title='BLACKGRID - Technical Summary',author='BLACKGRID contributors').build(story,onFirstPage=footer,onLaterPages=footer)

if __name__=='__main__':
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    for size in (10,9.5,9):
        build(size)
        if len(PdfReader(OUTPUT).pages)==2:break
    else:raise RuntimeError('Technical summary does not fit exactly two pages')
    print(f'Created two-page PDF at {OUTPUT}; body size {size}pt')
