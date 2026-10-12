from commercial_stream import CommercialBillboard
from rich.console import Console

console = Console()
b = CommercialBillboard()

for i in range(24): # Test a full loop of slides
    try:
        panel = b.get_slide_panel(i)
        console.print(panel)
    except Exception as e:
        print(f"Error on slide {i}: {e}")
        exit(1)
        
print("All slides rendered successfully.")
