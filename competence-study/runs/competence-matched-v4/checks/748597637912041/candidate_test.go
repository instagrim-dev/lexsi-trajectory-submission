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
if got := Calculate([]Line{{101,1,true},{203,3,false}},2500,1000); got != 543 { t.Errorf("case=0 got=%d want=543",got) }
if got := Calculate([]Line{{5,1,true},{5,1,true},{19,1,false}},1000,2500); got != 30 { t.Errorf("case=1 got=%d want=30",got) }
if got := Calculate([]Line{{799,2,true},{1100,1,true}},1700,875); got != 2475 { t.Errorf("case=2 got=%d want=2475",got) }
if got := Calculate([]Line{{99,4,false},{51,3,true}},3333,2000); got != 397 { t.Errorf("case=3 got=%d want=397",got) }
if got := Calculate([]Line{{7,1,true},{11,1,false},{13,1,true}},3700,1850); got != 23 { t.Errorf("case=4 got=%d want=23",got) }
}
