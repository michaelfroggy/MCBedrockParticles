import sys
import re

path = r'c:\Users\MrRob\Downloads\New folder\MCBedrockParticles\simulator.py'
src = open(path, 'r', encoding='utf-8').read()

# I will find 'if curve_type == "catmull_rom"' and replace the block
pattern = r'(?s)if curve_type == "catmull_rom".*?lt3 = lt2 \* local_t'

new_block = '''if curve_type == "catmull_rom" and len(nodes) >= 4:
                    n = len(nodes)
                    segment_count = n - 3
                    
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
                    lt3 = lt2 * local_t'''

src_new = re.sub(pattern, new_block, src, count=1)
if src_new != src:
    open(path, 'w', encoding='utf-8').write(src_new)
    print('Patched successfully!')
else:
    print('Failed to patch!')
