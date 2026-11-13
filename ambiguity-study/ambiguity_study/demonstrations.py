"""Hand-authored training demonstrations; not used by the hidden oracle."""
FINANCE_LINE='''func Compute(lines []Line, discountBP, taxBP int64) int64 {
 var total, taxable int64
 for _, l := range lines { v := (l.Price*l.Qty*(10000-discountBP)+5000)/10000; total += v; if l.Taxable { taxable += v } }
 return total+(taxable*taxBP+5000)/10000
}'''
FINANCE_SUBTOTAL='''func Compute(lines []Line, discountBP, taxBP int64) int64 {
 var a,b int64
 for _, l := range lines { if l.Taxable {a += l.Price*l.Qty} else {b += l.Price*l.Qty} }
 a = (a*(10000-discountBP)+5000)/10000; b = (b*(10000-discountBP)+5000)/10000
 return a+b+(a*taxBP+5000)/10000
}'''
EVENT_EARLIEST='''func Compute(events []Event) int64 {
 selected := map[string]Event{}
 for _, e := range events { old, ok := selected[e.Key]; if !ok || e.Sequence < old.Sequence { selected[e.Key] = e } }
 var total int64; for _, e := range selected { total += e.Value }; return total
}'''
EVENT_LATEST='''func Compute(events []Event) int64 {
 selected := map[string]Event{}
 for _, e := range events { old, ok := selected[e.Key]; if !ok || e.Sequence > old.Sequence { selected[e.Key] = e } }
 var total int64; for _, e := range selected { total += e.Value }; return total
}'''
WITNESSES={'finance':{'lines':[{'price':5,'qty':1,'taxable':True},{'price':5,'qty':1,'taxable':True},{'price':19,'qty':1,'taxable':False}], 'discount_bp':1000,'tax_bp':2500}, 'events':{'events':[{'key':'east','sequence':5,'value':19},{'key':'east','sequence':2,'value':7}]}}
PROGRAMS={'finance':{'line':FINANCE_LINE,'subtotal':FINANCE_SUBTOTAL},'events':{'earliest':EVENT_EARLIEST,'latest':EVENT_LATEST}}
