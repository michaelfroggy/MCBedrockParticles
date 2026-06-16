import math
nodes = [0, 0, 1, 0, 0]
n = len(nodes)
segment_count = n - 3
for i in range(11):
    t = i / 10.0
    t_clamped = max(0.0, min(1.0, t))
    scaled_t = t_clamped * segment_count
    
    seg_idx = int(math.floor(scaled_t))
    local_t = scaled_t - seg_idx
    if seg_idx >= segment_count:
        seg_idx = segment_count - 1
        local_t = 1.0

    p0 = nodes[seg_idx]
    p1 = nodes[seg_idx + 1]
    p2 = nodes[seg_idx + 2]
    p3 = nodes[seg_idx + 3]

    lt2 = local_t * local_t
    lt3 = lt2 * local_t

    res = 0.5 * (
        (2 * p1) +
        (-p0 + p2) * local_t +
        (2 * p0 - 5 * p1 + 4 * p2 - p3) * lt2 +
        (-p0 + 3 * p1 - 3 * p2 + p3) * lt3
    )
    print(f't={t:.1f} -> res={res:.3f}')
