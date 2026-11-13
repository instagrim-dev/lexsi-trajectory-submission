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
if got := PriceOrder([]Line{{1000,2,true}},0,1000); got != 2200 { t.Errorf("case=5 got=%d want=2200",got) }
if got := PriceOrder([]Line{{12,2,false}},10000,2500); got != 0 { t.Errorf("case=6 got=%d want=0",got) }
if got := PriceOrder([]Line{},1000,1000); got != 0 { t.Errorf("case=7 got=%d want=0",got) }
if got := PriceOrder([]Line{{29,3,true},{41,2,false},{13,5,true}},2750,1375); got != 184 { t.Errorf("case=8 got=%d want=184",got) }
if got := PriceOrder([]Line{{1,5,true},{1,5,true},{15,1,false}},3000,9000); got != 24 { t.Errorf("case=9 got=%d want=24",got) }
if got := PriceOrder([]Line{{149,2,false},{37,9,true}},1999,1711); got != 550 { t.Errorf("case=10 got=%d want=550",got) }
}
