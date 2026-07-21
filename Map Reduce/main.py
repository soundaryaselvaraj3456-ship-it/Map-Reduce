"""
main.py
-------
The MapReduce driver. mapper.py and reducer.py are intentionally tiny
(stdin -> stdout only). ALL the framework logic lives here:

    1. SPLIT    : break input.txt into N input splits.
    2. MAP      : fork one independent mapper subprocess per split,
                  feed it the split via stdin, capture its "key\\tvalue"
                  output from stdout.
    3. PARTITION: route every (key, value) pair through a CUSTOM HASH
                  PARTITIONER (not Python's randomized hash()) to decide
                  which reducer it belongs to.
    4. WRITE    : write each partition's key-value pairs to a local
                  disk file under intermediate/.
    5. SORT     : sort each partition file by key (shuffle & sort).
    6. REDUCE   : fork one independent reducer subprocess per partition,
                  feed it the sorted partition via stdin, capture the
                  final "key\\tcount" output from stdout, save to output/.
"""

import os
import sys
import shutil
import subprocess

NUM_MAPPERS = 3
NUM_REDUCERS = 3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, "input.txt")
INTERMEDIATE_DIR = os.path.join(BASE_DIR, "intermediate")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
MAPPER_SCRIPT = os.path.join(BASE_DIR, "mapper.py")
REDUCER_SCRIPT = os.path.join(BASE_DIR, "reducer.py")


def reset_dirs():
    for d in (INTERMEDIATE_DIR, OUTPUT_DIR):
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)


def custom_hash_partitioner(key: str, num_reducers: int) -> int:
    """Deterministic hash (Python's built-in hash() is randomized per-process)."""
    h = 0
    prime = 31
    for ch in key:
        h = (h * prime + ord(ch)) & 0xFFFFFFFF
    return h % num_reducers


def split_input(input_path: str, num_splits: int):
    with open(input_path, "r") as f:
        lines = f.readlines()

    if not lines:
        print("Input file is empty. Nothing to do.")
        sys.exit(1)

    chunk_size = max(1, (len(lines) + num_splits - 1) // num_splits)
    splits = []
    for i in range(num_splits):
        chunk = lines[i * chunk_size:(i + 1) * chunk_size]
        if chunk:
            splits.append("".join(chunk))
    return splits


def run_mapper(split_text: str, mapper_id: int) -> str:
    """Forks an independent mapper subprocess, pipes the split in, returns its stdout."""
    proc = subprocess.run(
        [sys.executable, MAPPER_SCRIPT],
        input=split_text,
        capture_output=True,
        text=True,
    )
    print(f"[mapper {mapper_id}] processed split -> {len(proc.stdout.splitlines())} pairs emitted")
    return proc.stdout


def run_reducer(sorted_text: str, partition_id: int) -> str:
    """Forks an independent reducer subprocess, pipes the sorted partition in, returns its stdout."""
    proc = subprocess.run(
        [sys.executable, REDUCER_SCRIPT],
        input=sorted_text,
        capture_output=True,
        text=True,
    )
    print(f"[reducer {partition_id}] reduced -> {len(proc.stdout.splitlines())} keys")
    return proc.stdout


def main():
    reset_dirs()

    print(f"MapReduce job starting | mappers={NUM_MAPPERS} reducers={NUM_REDUCERS}")

    # 1. SPLIT
    splits = split_input(INPUT_FILE, NUM_MAPPERS)

    # 2. MAP (fork one mapper subprocess per split)
    print("\n=== MAP PHASE ===")
    partitions = {p: [] for p in range(NUM_REDUCERS)}

    for mapper_id, split_text in enumerate(splits):
        mapper_output = run_mapper(split_text, mapper_id)

        # 3. PARTITION each emitted pair with the custom hash partitioner
        for line in mapper_output.splitlines():
            if not line.strip():
                continue
            key, value = line.split("\t")
            partition = custom_hash_partitioner(key, NUM_REDUCERS)
            partitions[partition].append(line)

    # 4. WRITE intermediate key-value pairs to local disk, one file per partition
    print("\n=== WRITE INTERMEDIATE PARTITIONS TO DISK ===")
    for p in range(NUM_REDUCERS):
        path = os.path.join(INTERMEDIATE_DIR, f"partition_{p}.txt")
        with open(path, "w") as f:
            f.write("\n".join(partitions[p]) + ("\n" if partitions[p] else ""))
        print(f"  partition {p}: {len(partitions[p])} pairs -> {path}")

    # 5. SORT each partition file by key
    print("\n=== SORT PHASE ===")
    sorted_partitions = {}
    for p in range(NUM_REDUCERS):
        path = os.path.join(INTERMEDIATE_DIR, f"partition_{p}.txt")
        with open(path, "r") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        lines.sort(key=lambda l: l.split("\t")[0])

        sorted_path = os.path.join(INTERMEDIATE_DIR, f"partition_{p}_sorted.txt")
        with open(sorted_path, "w") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
        sorted_partitions[p] = "\n".join(lines) + ("\n" if lines else "")
        print(f"  partition {p} sorted -> {sorted_path}")

    # 6. REDUCE (fork one reducer subprocess per partition)
    print("\n=== REDUCE PHASE ===")
    results = {}
    for p in range(NUM_REDUCERS):
        reducer_output = run_reducer(sorted_partitions[p], p)

        out_path = os.path.join(OUTPUT_DIR, f"part-{p:05d}.txt")
        with open(out_path, "w") as f:
            f.write(reducer_output)

        for line in reducer_output.splitlines():
            if line.strip():
                key, value = line.split("\t")
                results[key] = int(value)

    # Final summary
    print("\n=== FINAL OUTPUT ===")
    for key in sorted(results):
        print(f"  {key}: {results[key]}")

    print(f"\nJob complete. Output files are in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
