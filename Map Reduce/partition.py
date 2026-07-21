def custom_hash_partitioner(key, num_reducers):
    h = 0
    prime = 31
    for ch in key:
        h = (h * prime + ord(ch)) & 0xFFFFFFFF
    return h % num_reducers