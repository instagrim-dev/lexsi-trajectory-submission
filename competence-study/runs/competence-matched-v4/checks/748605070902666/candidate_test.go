package main
import "testing"
type Line struct { Price int64; Qty int64; Taxable bool }
func PriceOrder(lines []Line, discountBP int64, taxBP int64) int64 {
	var taxableOriginalSubtotal int64
	var nonTaxableOriginalSubtotal int64

	for _, line := range lines {
		if line.Qty <= 0 || line.Price <= 0 {
			continue
		}

		lineSum := line.Price * line.Qty
		if line.Taxable {
			taxableOriginalSubtotal += lineSum
		} else {
			nonTaxableOriginalSubtotal += lineSum
		}
	}

	// "Sum taxable lines and non-taxable lines into two subtotals, 
	// then separately discount and round each subtotal."
	
	// Discount and round taxable subtotal
	taxableNumerator := taxableOriginalSubtotal * (10000 - discountBP)
	roundedTaxableSubtotal := (taxableNumerator + 5000) / 10000

	// Discount and round non-taxable subtotal
	nonTaxableNumerator := nonTaxableOriginalSubtotal * (10000 - discountBP)
	roundedNonTaxableSubtotal := (nonTaxableNumerator + 5000) / 10000

	// "Compute tax from the DISCOUNTED taxable subtotal."
	taxNumerator := roundedTaxableSubtotal * taxBP
	roundedTax := (taxNumerator + 5000) / 10000

	// "Round tax once and add it to the discounted total."
	// The discounted total is the sum of the two rounded subtotals.
	return roundedTaxableSubtotal + roundedNonTaxableSubtotal + roundedTax
}
func TestCandidate(t *testing.T) {
if got := PriceOrder([]Line{{1000,2,true}},0,1000); got != 2200 { t.Errorf("case=5 got=%d want=2200",got) }
if got := PriceOrder([]Line{{12,2,false}},10000,2500); got != 0 { t.Errorf("case=6 got=%d want=0",got) }
if got := PriceOrder([]Line{},1000,1000); got != 0 { t.Errorf("case=7 got=%d want=0",got) }
if got := PriceOrder([]Line{{29,3,true},{41,2,false},{13,5,true}},2750,1375); got != 184 { t.Errorf("case=8 got=%d want=184",got) }
if got := PriceOrder([]Line{{1,5,true},{1,5,true},{15,1,false}},3000,9000); got != 24 { t.Errorf("case=9 got=%d want=24",got) }
if got := PriceOrder([]Line{{149,2,false},{37,9,true}},1999,1711); got != 550 { t.Errorf("case=10 got=%d want=550",got) }
}
