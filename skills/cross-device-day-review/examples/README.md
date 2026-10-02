# Synthetic example — no real person's day

Every source, record, label and time in this directory was created from scratch for testing. The example date is 2030-01-15, timezone UTC. This directory is safe demo input, not a location for your own files.

From the installed skill directory:

```sh
python3 scripts/day_review.py --config examples/config.json --input examples/day.json --output-dir /tmp/my-new-synthetic-day-report
```

The output directory must not exist. On another host choose your own existing private parent directory and a fresh child name.

Expected result:

- human/device interval union: **140 minutes**;
- shared learning episode: **80 minutes**, despite three overlapping records;
- writing: **40 minutes**, walk: **20 minutes**;
- an untimed conversation: **null**, last in the list;
- agent summed runtime: **90 minutes**, union wall time: **60 minutes**;
- tablet: missing source, **null**, not zero;
- status: `partial`, with `complete_day_claim: false`.

A correction exercise: replace the three learning records with reviewed bounds 09:10–09:50 for that same episode. The CLI will report 40 minutes for learning. Appending these bounds to the old records would preserve the original 80-minute union; the tool does not apply corrections automatically.
