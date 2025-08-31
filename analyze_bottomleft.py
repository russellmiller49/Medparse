#\!/usr/bin/env python3

# From the debug output:
# l=483.951416015625, t=680.9680480957031
# r=560.5543823242188, b=654.4055633544922

# In BOTTOMLEFT coordinate system:
# - origin (0,0) is at bottom-left
# - y increases upward
# - So "t" (top) should have a LARGER y value than "b" (bottom)

l = 483.951416015625
t = 680.9680480957031  
r = 560.5543823242188
b = 654.4055633544922

print("Analysis of BOTTOMLEFT coordinates:")
print(f"Left: {l}")
print(f"Top: {t}")
print(f"Right: {r}") 
print(f"Bottom: {b}")
print()
print(f"Width (r - l): {r - l}")
print(f"Height (t - b): {t - b}")
print()
print(f"Is t > b (as expected for BOTTOMLEFT)? {t > b}")
print()
print("So in BOTTOMLEFT:")
print(f"  - Bottom edge is at y={b}")
print(f"  - Top edge is at y={t}")
print(f"  - The figure is {t - b} points tall")
