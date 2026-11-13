package main
import "testing"
type Line struct { Price int64; Qty int64; Taxable bool }
func Calculate(lines []Line, discountBP int64, taxBP int64) int64 {
	var discountedSubtotal int64
	var taxableDiscountedSubtotal int64

	for _, line := range lines {
		if line.Qty <= 0 || line.Price <= 0 {
			continue
		}

		// Line Total in cents (assuming Price is in cents)
		// To handle basis points correctly, we treat the math as:
		// Total = (Price * Qty * (10000 - discountBP)) / 10000
		// We need to round this specific line after discount.
		// Formula: round(numerator / 10000) = (numerator + 5000) / 10000
		
		lineTotalNumerator := line.Price * line.Qty * (10000 - discountBP)
		roundedLineTotal := (lineTotalNumerator + 5000) / 10000

		discountedSubtotal += roundedLineTotal

		if line.Taxable {
			// We need the taxable subtotal to calculate tax later.
			// The prompt says: "Compute tax from the DISCOUNTED taxable subtotal."
			// This implies we sum the discounted values of the taxable lines.
			taxableDiscountedSubtotal += roundedLineTotal
		}
	}

	// Calculate tax: round(taxableDiscountedSubtotal * taxBP / 10000)
	// Formula: round(numerator / 10000)
	taxNumerator := taxableDiscountedSubtotal * taxBP
	roundedTax := (taxNumerator + 5000) / 10000

	return discountedSubtotal + roundedTax
}
func TestCandidate(t *testing.T) {
if got := Calculate([]Line{{1000,2,true}},0,1000); got != 2200 { t.Errorf("case=5 got=%d want=2200",got) }
if got := Calculate([]Line{{12,2,false}},10000,2500); got != 0 { t.Errorf("case=6 got=%d want=0",got) }
if got := Calculate([]Line{},1000,1000); got != 0 { t.Errorf("case=7 got=%d want=0",got) }
if got := Calculate([]Line{{29,3,true},{41,2,false},{13,5,true}},2750,1375); got != 184 { t.Errorf("case=8 got=%d want=184",got) }
if got := Calculate([]Line{{1,5,true},{1,5,true},{15,1,false}},3000,9000); got != 26 { t.Errorf("case=9 got=%d want=26",got) }
if got := Calculate([]Line{{149,2,false},{37,9,true}},1999,1711); got != 550 { t.Errorf("case=10 got=%d want=550",got) }
}
