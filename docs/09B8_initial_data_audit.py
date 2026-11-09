from pathlib import Path
import csv,re,json,numpy as np
root=Path('09B8数据');report={'root':str(root.resolve()),'folders':[],'problems':[]}
for region,folder in [('full',root/'全段测试'),('end15cm',root/'末端测试'/'15cm'),('end5cm',root/'末端测试'/'5cm')]:
 for case in sorted(folder.iterdir()):
  if not case.is_dir():continue
  channels={};issues=[]
  for f in case.glob('*.csv'):
   m=re.search(r'Channel_(\d+)',f.name)
   if not m:continue
   with f.open(encoding='utf-8-sig',newline='') as stream:
    reader=csv.reader(stream);header=next(reader);rows=[];bad=0
    for i,row in enumerate(reader):
     if i>=200:break
     try:
      values=np.array([float(v) for v in row[2:]],dtype=float)
      if len(values)!=22 or not np.all(np.isfinite(values)):bad+=1;continue
      rows.append(values)
     except ValueError:bad+=1
   channels[m.group(1)]={'file':str(f),'wl_columns':len(header)-2,'valid_first200':len(rows),'invalid_first200':bad,'sample_mean':np.mean(rows,axis=0).tolist() if rows else None}
  if set(channels)!={'1','2','3','4'}:issues.append('missing_or_extra_channels')
  if any(v['wl_columns']!=22 or v['valid_first200']==0 for v in channels.values()):issues.append('invalid_channel_shape_or_no_valid_rows')
  entry={'region':region,'case':case.name,'channels':channels,'issues':issues};report['folders'].append(entry)
  if issues:report['problems'].append({'region':region,'case':case.name,'issues':issues})
Path('docs/09B8_initial_data_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('case_count',len(report['folders']),'problems',report['problems']);print('per_region',{r:sum(e['region']==r for e in report['folders']) for r in ('full','end15cm','end5cm')})
for e in report['folders']:
 if e['region']=='full' and e['case'] in ('0-0','0-200'):
  c=e['channels'];central=np.array(c['1']['sample_mean']);diff=np.array([c[x]['sample_mean'] for x in ('2','3','4')])-central;print(e['case'],'outer-minus-center at first3',diff[:,:3].round(2).tolist())
