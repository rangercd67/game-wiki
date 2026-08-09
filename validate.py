import re
from collections import Counter

with open('E:/work/workbuddy/2026-08-10-00-35-15/jiangcity-calculator/js/data.js', 'r', encoding='utf-8') as f:
    content = f.read()

recipe_count = content.count('category:')
raw_count = content.count('isRaw: true')
print(f'Total items with category: {recipe_count}')
print(f'Raw resources: {raw_count}')
print(f'Crafted recipes: {recipe_count - raw_count}')

inputs = re.findall(r'item:"([^"]+)"', content)
ids = re.findall(r'id: "([^"]+)", name:', content)
all_ids = set(ids)
missing = set(inp for inp in inputs if inp not in all_ids)
if missing:
    print(f'WARNING: Missing item references: {missing}')
else:
    print('All input references are valid!')

cats = re.findall(r'category: "([^"]+)"', content)
cat_counts = Counter(cats)
for cat, count in sorted(cat_counts.items()):
    print(f'  {cat}: {count}')
