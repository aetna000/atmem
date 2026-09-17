"""Deterministic rank fusion; scores are nomination priors, not confidence."""
from collections import defaultdict

FUSION_VERSION = 'core-rrf-v1'
RANK_CONSTANT = 60


def fuse_rankings(channels):
    active = {name: list(dict.fromkeys(ids)) for name, ids in channels.items() if ids}
    ranks = defaultdict(dict)
    for name, ids in active.items():
        for rank, record_id in enumerate(ids, 1):
            ranks[record_id][name] = rank
    denominator = len(active) / (RANK_CONSTANT + 1) if active else 1
    result = [dict(record_id=record_id, channel_ranks=positions,
                   score=sum(1 / (RANK_CONSTANT + rank) for rank in positions.values()) / denominator)
              for record_id, positions in ranks.items()]
    return sorted(result, key=lambda row: (-row['score'], row['record_id']))
