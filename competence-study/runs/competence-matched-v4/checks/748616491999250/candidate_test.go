package main
import "testing"
type Line struct { Price int64; Qty int64; Taxable bool }
func PriceOrder(lines []Line, discountBP int64, taxBP int64) int64 {
	var taxableSum int64
	var nonTaxableSum int64

	for _, line := range lines {
		if line.Price <= 0 || line.Qty <= 0 {
			continue
		}
		if line.Taxable {
			taxableSum += line.Price * line.Qty
		} else {
			nonTaxableSum += line.Price * line.Qty
		}
	}

	discountedTaxable := (taxableSum*(10000-discountBP) + 5000) / 10000
	discountedNonTaxable := (nonTaxableSum*(10000-discountBP) + 5000) / 10000

	tax := (discountedTaxable*taxBP + 5000) / 10000

	return discountedTaxable + discountedNonTaxable + tax
}
func TestCandidate(t *testing.T) {
if got := PriceOrder([]Line{{101,1,true},{203,3,false}},2500,1000); got != 541 { t.Errorf("case=0 got=%d want=541",got) }
if got := PriceOrder([]Line{{5,1,true},{5,1,true},{19,1,false}},1000,2500); got != 28 { t.Errorf("case=1 got=%d want=28",got) }
if got := PriceOrder([]Line{{799,2,true},{1100,1,true}},1700,875); got != 2435 { t.Errorf("case=2 got=%d want=2435",got) }
if got := PriceOrder([]Line{{99,4,false},{51,3,true}},3333,2000); got != 386 { t.Errorf("case=3 got=%d want=386",got) }
if got := PriceOrder([]Line{{7,1,true},{11,1,false},{13,1,true}},3700,1850); got != 22 { t.Errorf("case=4 got=%d want=22",got) }
}
