#!/usr/bin/env python3
"""Read-only source extraction. Run with bundled Python; openpyxl is verification only."""
import base64, collections, csv, hashlib, json, posixpath, re, sys, urllib.parse, zipfile, zlib
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

BASE = Path(__file__).resolve().parent
SRC = BASE.parent
XLSX = SRC / 'Gouda_architecture_detail.xlsx'
DRAW = SRC / 'SystemArchitecture.drawio'
N = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
def digest(b): return hashlib.sha256(b).hexdigest()
def dump(name, data):
    (BASE/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def jsonl(name, records):
    (BASE/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
def table(name, records, fields):
    with (BASE/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader()
        for r in records:
            w.writerow({k:json.dumps(r[k],ensure_ascii=False) if isinstance(r.get(k),(dict,list)) else r.get(k) for k in fields})
def richtext(e):
    return ''.join(t.text or '' for t in e.findall('s:t',N)+e.findall('s:r/s:t',N)) if e is not None else None
def status(raw, location, body='', special=False):
    # Do not infer approval from implementation progress, color, or mere presence.
    pending = r'未確定|未決|未定|未固定|草案|提案|設計案|確認中|Q-\d+|[はの・]案|閾値は案'
    confirmed = bool(re.search(r'(?<!未)確定|承認済み',raw or ''))
    unresolved = special or bool(re.search(pending,(raw or '')+'\n'+body))
    certain = confirmed and not unresolved and raw != 'この版の確定範囲'
    return dict(status='確定' if certain else '未決',status_raw=raw,
                status_source=location,status_basis='原文の確定表記' if certain else ('確定事項を含むが未決条件も併記' if confirmed and unresolved else '原文の未決・草案表記' if unresolved else '確定の明示なし'),
                contains_confirmed=confirmed)

def main():
    original={str(p):digest(p.read_bytes()) for p in (XLSX,DRAW)}
    cells=[]; rows=[]; sheets=[]; ids=[]; nodes=[]; checks=[]; issues=[]
    with zipfile.ZipFile(XLSX) as z:
        # Preserve every package entry byte-for-byte, including comments/styles/relationships.
        package=[]
        for name in z.namelist():
            dst=BASE/'raw_xlsx'/name; dst.parent.mkdir(parents=True,exist_ok=True)
            data=z.read(name); dst.write_bytes(data)
            package.append({'part':name,'sha256':digest(data),'bytes':len(data)})
        ss=[richtext(x) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        for sh in wb.findall('s:sheets/s:sheet',N):
            name=sh.attrib['name']; target=rels[sh.attrib[R]]
            part=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            root=ET.fromstring(z.read(part)); local=[]; rr=[]
            for row in root.findall('s:sheetData/s:row',N):
                rowcells=[]
                for c in row.findall('s:c',N):
                    v=c.find('s:v',N); f=c.find('s:f',N); inline=c.find('s:is',N)
                    stored=v.text if v is not None else None
                    value=ss[int(stored)] if c.get('t')=='s' else richtext(inline) if c.get('t')=='inlineStr' else stored
                    rec=dict(source_file=str(XLSX),sheet=name,sheet_id=sh.get('sheetId'),part=part,
                             cell=c.get('r'),row=int(row.get('r')),attributes=dict(c.attrib),value=value,
                             stored_value=stored,formula=f.text if f is not None else None,
                             formula_attributes=dict(f.attrib) if f is not None else None,
                             has_content=v is not None or f is not None or inline is not None,
                             xml=ET.tostring(c,encoding='unicode'))
                    local.append(rec); rowcells.append(rec)
                rr.append(dict(source_file=str(XLSX),sheet=name,row=int(row.get('r')),attributes=dict(row.attrib),
                               cell_ids=[c['cell'] for c in rowcells],values={c['cell']:c['value'] for c in rowcells if c['has_content']},
                               content_cells=sum(c['has_content'] for c in rowcells)))
            header={re.sub(r'\d','',c['cell']):c['value'] for c in local if c['row']==1}
            statuscols=[k for k,v in header.items() if v in ('定義Status','区分・根拠','状態')]
            byrow=collections.defaultdict(list)
            for c in local: byrow[c['row']].append(c)
            for row in rr:
                rc=byrow[row['row']]
                sc=[c for c in rc if re.sub(r'\d','',c['cell']) in statuscols and row['row']>1]
                raw='\n'.join(c['value'] or '' for c in sc)
                loc=[f"{name}!{c['cell']}" for c in sc]
                body='\n'.join(c['value'] or '' for c in rc)
                st=status(raw,loc,body,special=name=='未決事項' and row['row']>1)
                row.update(st)
                for c in rc: c.update(st)
                for c in rc:
                    if c['value'] and re.fullmatch(r'(?:M|IF|S|D|ST|T|Q|REF)-\d+',c['value']):
                        ids.append(dict(id=c['value'],sheet=name,cell=c['cell'],role='definition' if header.get(re.sub(r'\d','',c['cell'])) in ('ID','Module_ID','IF_ID') else 'reference',**st))
            sheets.append(dict(name=name,attributes=dict(sh.attrib),part=part,
                               dimension=root.find('s:dimension',N).get('ref') if root.find('s:dimension',N) is not None else None,
                               stored_rows=len(rr),content_rows=sum(bool(r['content_cells']) for r in rr),
                               nonempty_rows=sum(any(v not in (None,'') for v in r['values'].values()) for r in rr),
                               stored_cells=len(local),content_cells=sum(c['has_content'] for c in local),
                               nonempty_cells=sum(c['value'] not in (None,'') or c['formula'] is not None for c in local),
                               merges=[e.get('ref') for e in root.findall('s:mergeCells/s:mergeCell',N)]))
            cells.extend(local); rows.extend(rr)
    drawbytes=DRAW.read_bytes(); (BASE/'raw.drawio').write_bytes(drawbytes)
    document=ET.fromstring(drawbytes); pages=[]
    for pageindex, page in enumerate(document.findall('diagram')):
        model=page.find('mxGraphModel')
        if model is None:
            decoded=urllib.parse.unquote(zlib.decompress(base64.b64decode(page.text),-15).decode())
            model=ET.fromstring(decoded)
        (BASE/f'drawio_page_{pageindex+1}.xml').write_bytes(ET.tostring(model,encoding='utf-8'))
        root=model.find('root'); page_nodes=[]
        for index, wrapper in enumerate(root):
            c=wrapper if wrapper.tag=='mxCell' else wrapper.find('mxCell')
            if c is None: raise ValueError('Unknown drawio object: '+wrapper.tag)
            ident=wrapper.get('id') or c.get('id'); raw=c.get('value',wrapper.get('label',''))
            rec=dict(source_file=str(DRAW),page=page.get('name'),page_id=page.get('id'),order=index,id=ident,
                     location=f"diagram[{pageindex+1}]/root/*[{index+1}] (id={ident})",
                     kind='edge' if c.get('edge')=='1' else 'vertex' if c.get('vertex')=='1' else 'structural',
                     value_raw=raw,attributes=dict(c.attrib),wrapper_attributes=dict(wrapper.attrib),
                     parent=c.get('parent'),source=c.get('source'),target=c.get('target'),
                     geometry_xml=ET.tostring(c.find('mxGeometry'),encoding='unicode') if c.find('mxGeometry') is not None else None,
                     xml=ET.tostring(wrapper,encoding='unicode'),**status('',[],raw))
            page_nodes.append(rec)
        lookup={r['id']:r for r in page_nodes}
        for r in page_nodes:
            for key in ('parent','source','target'):
                if r[key] is not None and r[key] not in lookup: issues.append(dict(page=page.get('id'),id=r['id'],issue='missing_reference',field=key,value=r[key]))
            if r['kind']=='edge':
                r['label_ids']=[n['id'] for n in page_nodes if n['parent']==r['id'] and n['kind']=='vertex']
                for end in ('source','target'):
                    if r[end] is None: issues.append(dict(page=page.get('id'),id=r['id'],issue='unbound_endpoint',field=end))
        nodes.extend(page_nodes)
        pages.append(dict(attributes=dict(page.attrib),model_attributes=dict(model.attrib),counts=dict(collections.Counter(r['kind'] for r in page_nodes))))
    jsonl('excel_cells.jsonl',cells); jsonl('excel_rows.jsonl',rows); jsonl('drawio_objects.jsonl',nodes)
    edges=[r for r in nodes if r['kind']=='edge']; vertices=[r for r in nodes if r['kind']=='vertex']
    table('excel_cells.csv',cells,['sheet','cell','row','value','formula','stored_value','status','status_raw','status_basis','status_source','has_content','source_file'])
    table('excel_rows.csv',rows,['sheet','row','values','content_cells','status','status_raw','status_basis','status_source'])
    table('excel_ids.csv',ids,['id','sheet','cell','role','status','status_raw','status_basis'])
    table('drawio_parts.csv',vertices,['page','id','parent','value_raw','status','status_basis','location','attributes','geometry_xml'])
    table('drawio_connections.csv',edges,['page','id','source','target','parent','value_raw','label_ids','status','status_basis','location','attributes','geometry_xml'])
    dump('excel_sheets.json',sheets); dump('drawio_pages.json',pages); dump('source_manifest.json',dict(sha256=original,package=package))
    # Independent DOM inventories compare original files to RELOADED output records.
    outcells=[json.loads(s) for s in (BASE/'excel_cells.jsonl').read_text().splitlines()]
    outrows=[json.loads(s) for s in (BASE/'excel_rows.jsonl').read_text().splitlines()]
    outnodes=[json.loads(s) for s in (BASE/'drawio_objects.jsonl').read_text().splitlines()]
    def check(label, actual, expected):
        checks.append(dict(check=label,pass_=actual==expected,source_count=len(expected) if isinstance(expected,(list,dict)) else expected,output_count=len(actual) if isinstance(actual,(list,dict)) else actual))
        if actual!=expected: issues.append(dict(issue='conversion_mismatch',check=label))
    with zipfile.ZipFile(XLSX) as z:
        for s in sheets:
            dom=minidom.parseString(z.read(s['part']))
            dc=dom.getElementsByTagName('c'); dr=dom.getElementsByTagName('row')
            cc=[c for c in outcells if c['sheet']==s['name']]
            check(s['name']+' cell ID ordered list',[c['cell'] for c in cc],[c.getAttribute('r') for c in dc])
            check(s['name']+' row ordered list',[r['row'] for r in outrows if r['sheet']==s['name']],[int(r.getAttribute('r')) for r in dr])
            check(s['name']+' XML element equality',[ET.canonicalize(c['xml']) for c in cc],[ET.canonicalize(ET.tostring(c,encoding='unicode')) for c in ET.fromstring(z.read(s['part'])).findall('s:sheetData/s:row/s:c',N)])
        check('raw XLSX package byte hashes',[digest((BASE/'raw_xlsx'/n).read_bytes()) for n in z.namelist()],[digest(z.read(n)) for n in z.namelist()])
    # Separate library independently checks decoded strings and source business IDs.
    import openpyxl
    book=openpyxl.load_workbook(XLSX,data_only=False)
    lookup={(c['sheet'],c['cell']):c for c in outcells}
    mismatch=[]; libids=[]
    for sh in book:
        for row in sh:
            for c in row:
                if c.value is None: continue
                rec=lookup.get((sh.title,c.coordinate))
                if not rec: mismatch.append([sh.title,c.coordinate,'absent']); continue
                expected='='+rec['formula'] if rec['formula'] is not None else rec['value']
                if str(c.value)!=expected: mismatch.append([sh.title,c.coordinate,str(c.value),expected])
                if isinstance(c.value,str) and re.fullmatch(r'(?:M|IF|S|D|ST|T|Q|REF)-\d+',c.value): libids.append([c.value,sh.title,c.coordinate])
    check('independent openpyxl decoded values/formulas',mismatch,[])
    with (BASE/'excel_ids.csv').open(encoding='utf-8-sig',newline='') as f: savedids=list(csv.DictReader(f))
    check('business ID occurrence list',[[r['id'],r['sheet'],r['cell']] for r in savedids],libids)
    dom=minidom.parseString(drawbytes)
    sourcecells=dom.getElementsByTagName('mxCell')
    check('drawio ordered ID list',[r['id'] for r in outnodes],[c.getAttribute('id') for c in sourcecells])
    check('drawio edge ID + endpoints',[[r['id'],r['source'] or '',r['target'] or ''] for r in outnodes if r['kind']=='edge'],[[c.getAttribute('id'),c.getAttribute('source'),c.getAttribute('target')] for c in sourcecells if c.getAttribute('edge')=='1'])
    check('drawio labels',[r['value_raw'] for r in outnodes],[c.getAttribute('value') for c in sourcecells])
    check('drawio all attributes',[r['attributes'] for r in outnodes],[dict(c.attributes.items()) for c in sourcecells])
    check('drawio full XML including geometry',[ET.canonicalize(r['xml']) for r in outnodes],[ET.canonicalize(ET.tostring(c,encoding='unicode')) for c in ET.fromstring(drawbytes).findall('diagram/mxGraphModel/root/mxCell')])
    for file, data in [('drawio_parts.csv',vertices),('drawio_connections.csv',edges),('excel_cells.csv',cells),('excel_rows.csv',rows)]:
        with (BASE/file).open(encoding='utf-8-sig',newline='') as f: count=sum(1 for r in csv.DictReader(f))
        check(file+' logical record count',count,len(data))
    duplicate_ids=[k for k,v in collections.Counter((r['page_id'],r['id']) for r in outnodes).items() if v>1]
    check('drawio duplicate IDs',duplicate_ids,[])
    business_duplicates=[k for k,v in collections.Counter(r['id'] for r in savedids if r['role']=='definition').items() if v>1]
    check('Excel duplicate definition IDs',business_duplicates,[])
    check('sources unchanged',{str(p):digest(p.read_bytes()) for p in (XLSX,DRAW)},original)
    dump('verification.json',dict(passed=all(c['pass_'] for c in checks),checks=checks,source_issues=issues,
          counts=dict(sheets=len(sheets),stored_rows=len(rows),content_rows=sum(s['content_rows'] for s in sheets),stored_cells=len(cells),content_cells=sum(s['content_cells'] for s in sheets),business_id_whole_cell_occurrences=len(ids),definition_ids=sum(r['role']=='definition' for r in ids),drawio_objects=len(nodes),vertices=len(vertices),edges=len(edges)),
          status_counts=dict(excel_rows=dict(collections.Counter(r['status'] for r in rows if r['content_cells'])),drawio=dict(collections.Counter(r['status'] for r in nodes)))))
    lines=['# 抽出・検証結果','',f"検証: {'PASS' if all(c['pass_'] for c in checks) else 'FAIL'}（{len(checks)}項目）",'',
           '原本は変更していません。Excelは非表示シート、書式のみのセル・行、空文字を含め、保存されている全セルを抽出しました。未保存の空白座標は生成していません。',
           'JSONLが原文保持の正本です。CSVも改行を保持するため、物理行数ではなくCSVとして読み込んだレコード数で照合しています。数値は保存文字列、数式は式とキャッシュを分離しています。',
           'drawioのvertexには部品のほか枠・注記・接続ラベルも含まれます。parent、source、target、HTMLを含むvalue、style、geometryを保持し、ラベルを部品名へ統合していません。','',
           '## 確定／未決の規則','',
           '定義Status・区分・根拠・状態の原文をstatus_raw、根拠セルをstatus_sourceに保持。明示的な確定表記があり未決条件の併記がない行のみ確定。草案・提案・未確定・確認中・Q参照を含む混在行は未決としcontains_confirmedを保持します。行の区分はそのセルに継承します。',
           '確定の明示がない行、見出し、空白、選択肢、drawio部品・接続は未決（確定の明示なし）。これは新たな設計判断ではなく保守的な機械分類です。実装済み・試験済みを意味しません。部分確定の文章を意味単位へ書き換えたり分割したりしていません。','',
           '## 件数','', '| シート | 保存行 | 内容を持つ行 | 保存セル | 内容を持つセル |','|---|---:|---:|---:|---:|']
    for s in sheets: lines.append(f"| {s['name']} | {s['stored_rows']} | {s['content_rows']} | {s['stored_cells']} | {s['content_cells']} |")
    lines += ['',f'Excel ID: セル全体がIDの出現{len(ids)}件（定義{sum(r["role"]=="definition" for r in ids)}件、残りは参照）。文章中の部分文字列IDは原文セルに保持。drawio: {len(nodes)}要素（vertex {len(vertices)}、edge {len(edges)}、構造要素 {len(nodes)-len(vertices)-len(edges)}）。','',
              '## 照合内容','', '元XMLと再読込した出力のセル座標一覧・行番号一覧・セルXML、独立ライブラリによる値/数式と業務ID一覧、drawioのID順序・全属性・ラベル・接続端点、CSV件数、重複ID、原本SHA-256、Excel全パッケージのバイト同一性を照合。詳細はverification.json。',
              'ExcelのIF定義とdrawioのedgeは別の記録単位です。件数が同じという仮定や名前からの推測対応付けは行っていません。各資料から各抽出物への照合結果です。','',
              '## 原資料の接続上の注意','',json.dumps(issues,ensure_ascii=False,indent=2),'',
              '## ファイル','', '- excel_cells.jsonl / excel_cells.csv: セル原文・位置・区分', '- excel_rows.jsonl / excel_rows.csv: 行とセルの対応・区分', '- excel_ids.csv: 業務IDの全出現位置', '- drawio_objects.jsonl: 全要素・接続・構造要素', '- drawio_parts.csv / drawio_connections.csv: 部品等と接続の一覧', '- excel_sheets.json: シート状態・結合範囲・件数', '- raw_xlsx/: 元ZIPの全パーツ（コメント・書式等を含む）', '- raw.drawio: バイト同一の原本コピー', '- verification.json / source_manifest.json: 照合結果と原本ハッシュ', '- extract_verify.py: 再実行用抽出・検証スクリプト','']
    (BASE/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    print((BASE/'verification.json').read_text())
    if not all(c['pass_'] for c in checks): sys.exit(1)
if __name__=='__main__': main()
