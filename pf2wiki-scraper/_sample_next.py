# -*- coding: utf-8 -*-
# Generate next live_sample batch at a given seed, size 300.
import json, random, sys, os

GLOSSARY = r'C:\Users\Taka\Desktop\fvtt\glossary.json'
OUT_DIR = r'C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\out'

def gen(seed):
    with open(GLOSSARY, 'r', encoding='utf-8') as f:
        d = json.load(f)
    keys = list(d.keys())
    rng = random.Random(seed)
    samp = rng.sample(keys, 300)
    out_path = os.path.join(OUT_DIR, f'live_sample_{seed}.txt')
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        for k in samp:
            v = d[k]
            # quoting style: use double if key has single, else single
            if "'" in k:
                kq = '"' + k + '"'
            else:
                kq = "'" + k + "'"
            if "'" in v:
                vq = '"' + v + '"'
            else:
                vq = "'" + v + "'"
            f.write(f'{kq} => {vq}\n')
    print(f'wrote {out_path} ({len(samp)} lines), total glossary = {len(d)}')

if __name__ == '__main__':
    seed = int(sys.argv[1])
    gen(seed)
