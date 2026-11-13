package main
import "testing"
type Line struct { Price int64; Qty int64; Taxable bool }
func PriceOrder(lines []Line, discountBP int64, taxBP int64) int64 {
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

	// PriceOrder tax: round(taxableDiscountedSubtotal * taxBP / 10000)
	// Formula: round(numerator / 10000)
	taxNumerator := taxableDiscountedSubtotal * taxBP
	roundedTax := (taxNumerator + 5000) / 10000

	return discountedSubtotal + roundedTax
}
func TestCandidate(t *testing.T) {
if got := PriceOrder([]Line{{101,1,true},{203,3,false}},2500,1000); got != 541 { t.Errorf("case=0 got=%d want=541",got) }
if got := PriceOrder([]Line{{5,1,true},{5,1,true},{19,1,false}},1000,2500); got != 30 { t.Errorf("case=1 got=%d want=30",got) }
if got := PriceOrder([]Line{{799,2,true},{1100,1,true}},1700,875); got != 2435 { t.Errorf("case=2 got=%d want=2435",got) }
if got := PriceOrder([]Line{{99,4,false},{51,3,true}},3333,2000); got != 386 { t.Errorf("case=3 got=%d want=386",got) }
if got := PriceOrder([]Line{{7,1,true},{11,1,false},{13,1,true}},3700,1850); got != 21 { t.Errorf("case=4 got=%d want=21",got) }
}
