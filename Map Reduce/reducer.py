import sys

current_key, current_count = None, 0

for line in sys.stdin:
    key, value = line.strip().split("\t")
    if key == current_key:
        current_count += int(value)
    else:
        if current_key is not None:
            print(f"{current_key}\t{current_count}")
        current_key, current_count = key, int(value)

if current_key is not None:
    print(f"{current_key}\t{current_count}")
