from itertools import accumulate

from scripts.inspect_draw_bucket_coverage import (
    enumerate_bucket_frequencies,
)

freq = enumerate_bucket_frequencies()
counts = sorted(freq.values(), reverse=True)
total = sum(counts)

print("universe size:", len(counts))
print("total hands:", f"{total:,}")

cum = list(accumulate(counts))

for target in (0.5, 0.9, 0.99, 0.999):
    n = next(
        i + 1
        for i, c in enumerate(cum)
        if c / total >= target
    )
    print(f"buckets covering {target:.1%} of hands: {n}")

print("rarest bucket hand count:", counts[-1])
