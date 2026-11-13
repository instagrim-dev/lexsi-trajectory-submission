package main
import "testing"
type Line struct { Price int64; Qty int64; Taxable bool }
func Calculate(lines []Line, discountBP int64, taxBP int64) int64 {
	var discountedSubtotal int64
	var taxableOriginalSubtotal int64

	for _, line := range lines {
		if line.Price <= 0 || line.Qty <= 0 {
			continue
		}

		lineTotal := line.Price * line.Qty

		// Calculate discounted line amount
		// Formula: (lineTotal * (10000 - discountBP) + 5000) / 10000
		numerator := lineTotal * (10000 - discountBP)
		discountedLine := (numerator + 5000) / 10000

		discountedSubtotal += discountedLine

		// Compute tax from the ORIGINAL taxable subtotal
		if line.Taxable {
			taxableOriginalSubtotal += lineTotal
		}
	}

	// Compute tax from the ORIGINAL taxable subtotal
	// Tax = (taxableOriginalSubtotal * taxBP)
	// Rounding: (taxNumerator + 5000) / 10000
	taxNumerator := taxableOriginalSubtotal * taxBP
	tax := (taxNumerator + 5000) / 10000

	return discountedSubtotal + tax
}
func TestCandidate(t *testing.T) {
if got := Calculate([]Line{{101,1,true},{203,3,false}},2500,1000); got != 543 { t.Errorf("case=0 got=%d want=543",got) }
if got := Calculate([]Line{{5,1,true},{5,1,true},{19,1,false}},1000,2500); got != 30 { t.Errorf("case=1 got=%d want=30",got) }
if got := Calculate([]Line{{799,2,true},{1100,1,true}},1700,875); got != 2475 { t.Errorf("case=2 got=%d want=2475",got) }
if got := Calculate([]Line{{99,4,false},{51,3,true}},3333,2000); got != 397 { t.Errorf("case=3 got=%d want=397",got) }
if got := Calculate([]Line{{7,1,true},{11,1,false},{13,1,true}},3700,1850); got != 23 { t.Errorf("case=4 got=%d want=23",got) }
}
