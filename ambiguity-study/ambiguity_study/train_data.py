"""Create scripted Go clarification demonstrations, distinct from evaluation families."""
import json, random
from pathlib import Path
from ambiguity_study.prompt import SYSTEM

LINE='func Compute(values []int64) int64 { var sum, fee int64; for _,x := range values { sum += x; fee += (x+5)/10 }; return sum+fee }'
TOTAL='func Compute(values []int64) int64 { var sum int64; for _,x := range values { sum += x }; return sum+(sum+5)/10 }'
LOWER='func Compute(values []int64) int64 { a:=append([]int64(nil), values...); for i:=0;i<len(a);i++ { for j:=i+1;j<len(a);j++ { if a[j]<a[i] { a[i],a[j]=a[j],a[i] } } }; return a[(len(a)-1)/2] }'
UPPER='func Compute(values []int64) int64 { a:=append([]int64(nil), values...); for i:=0;i<len(a);i++ { for j:=i+1;j<len(a);j++ { if a[j]<a[i] { a[i],a[j]=a[j],a[i] } } }; return a[len(a)/2] }'
# The two training families differ from held-out finance and grouped events.
FAMILIES=[
 ('surcharge','Implement func Compute(values []int64) int64. Each nonnegative value is a price in cents. Add a 10 percent surcharge, rounded half up with (x+5)/10, and return prices plus the surcharge. ',
  ['This routine computes a service surcharge.','This calculation handles a usage fee.','This operation adds a processing surcharge.','This reports an administrative fee.'],
  'Should the surcharge be rounded separately for each price or once after summing all prices?',LINE,TOTAL,{'values':[5,5]},
  ['Round surcharge separately for each price.','Sum the prices first, then round the surcharge once.']),
 ('median','Implement func Compute(values []int64) int64. The slice is nonempty and has even length. Return a median value after sorting, but do not modify the input. ',
  ['This routine summarizes laboratory readings.','This operation reports a central measurement.','This algorithm summarizes sample observations.','This reports the center of a numeric sample.'],
  'For an even number of observations, should the lower or upper middle value be returned?',LOWER,UPPER,{'values':[1,9]},
  ['Return the lower middle element.','Return the upper middle element.'])]

def rows():
 data=[]
 for family,base,contexts,question,left,right,witness,details in FAMILIES:
  for i,context in enumerate(contexts):
   request=base+context
   ask={'action':'ask','question':question,'left_code':left,'right_code':right,'witness':witness}
   data.append({'id':f'{family}-{i}-amb','family':family,'prompt':json.dumps({'request':request},ensure_ascii=False),'response':json.dumps(ask,ensure_ascii=False),'system':SYSTEM})
   for choice,code in enumerate((left,right)):
    data.append({'id':f'{family}-{i}-clear-{choice}','family':family,'prompt':json.dumps({'request':request+' '+details[choice]},ensure_ascii=False),'response':json.dumps({'action':'solve','code':code},ensure_ascii=False),'system':SYSTEM})
 random.Random(42).shuffle(data)
 return data

if __name__=='__main__':
 p=Path('runs/ambiguity-teacher-v1.jsonl');p.parent.mkdir(exist_ok=True);data=rows()
 with p.open('x') as f:
  for row in data: f.write(json.dumps(row,ensure_ascii=False)+'\n')
 print('rows',len(data),'families',sorted({r['family'] for r in data}),'path',p)
