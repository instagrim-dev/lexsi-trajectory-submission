package main
import "testing"
type Line struct { Price int64; Qty int64; Taxable bool }
func Calculate(lines []Line, discountBP int64, taxBP int64) int64 {
	var discountedSubtotal int64
	var taxableOriginalSubtotal int64

	for _, line := range lines {
		if line.Qty <= 0 || line.Price <= 0 {
			continue
		}

		// Calculate line total before discount
		originalLineTotal := line.Price * line.Qty

		// Round each line after its discount.
		// Formula: round(numerator / 10000) = (numerator + 5000) / 10000
		lineTotalNumerator := originalLineTotal * (10000 - discountBP)
		roundedLineTotal := (lineTotalNumerator + 5000) / 10000

		discountedSubtotal += roundedLineTotal

		if line.Taxable {
			// Compute tax from the ORIGINAL taxable subtotal before discount.
			taxableOriginalSubtotal += originalLineTotal
		}
	}

	// Calculate tax once: round(taxableOriginalSubtotal * taxBP / 10000)
	taxNumerator := taxableOriginalSubtotal * taxBP
	roundedTax := (taxNumerator + 5000) / 10000

	return discountedSubtotal + roundedTax
}
func TestCandidate(t *testing.T) {
if got := Calculate([]Line{{1000,2,true}},0,1000); got != 2200 { t.Errorf("case=5 got=%d want=2200",got) }
if got := Calculate([]Line{{12,2,false}},10000,2500); got != 0 { t.Errorf("case=6 got=%d want=0",got) }
if got := Calculate([]Line{},1000,1000); got != 0 { t.Errorf("case=7 got=%d want=0",got) }
if got := Calculate([]Line{{29,3,true},{41,2,false},{13,5,true}},2750,1375); got != 190 { t.Errorf("case=8 got=%d want=190",got) }
if got := Calculate([]Line{{1,5,true},{1,5,true},{15,1,false}},3000,9000); got != 28 { t.Errorf("case=9 got=%d want=28",got) }
if got := Calculate([]Line{{149,2,false},{37,9,true}},1999,1711); got != 561 { t.Errorf("case=10 got=%d want=561",got) }
}
