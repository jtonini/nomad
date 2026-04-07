# System Dynamics

The `nomad dyn` command family applies quantitative frameworks from ecology and economics to research computing resource usage patterns.

## Commands

### Full Summary
```bash
nomad dyn --db nomad.db
```
Generates a comprehensive narrative combining all dynamics metrics.

### Diversity
```bash
nomad dyn diversity --window 30d --by group
```
Computes Simpson's and Shannon diversity indices over job types, research groups, or partitions.

**Simpson's D** = 1 - sum(p_i^2) — probability that two randomly chosen jobs belong to different categories.

**Shannon H'** = -sum(p_i * ln(p_i)) — information-theoretic uncertainty about category membership.

**Pielou's J** = H' / ln(S) — evenness of distribution across categories.

### Niche Overlap
```bash
nomad dyn niche --window 30d
```
Measures pairwise resource usage overlap between user communities using Pianka's overlap index.

### Carrying Capacity
```bash
nomad dyn capacity
```
Multi-dimensional capacity analysis identifying the binding constraint — which resource dimension will be exhausted first.

### Resilience
```bash
nomad dyn resilience
```
Recovery time after disturbance events (node failures, storage outages). Tracks whether the cluster is becoming more or less resilient over time.

### Externality
```bash
nomad dyn externality --window 30d
```
Quantifies how each user's resource-intensive behavior impacts other users' job outcomes.

## Configuration

```toml
[dynamics]
default_window = "30d"

[dynamics.diversity]
by = "group"
min_jobs = 10

[dynamics.niche]
overlap_threshold = 0.7

[dynamics.capacity]
saturation_threshold = 0.9

[dynamics.resilience]
min_history = 30

[dynamics.externality]
correlation_threshold = 0.5
```

## Theoretical Foundation

These metrics are adapted from ecological and economic frameworks for their mathematical properties, not as ontological claims. Users are intentional agents shaped by decisions and incentives, not natural selection. See Tonini (2026), *Ecological, Economic, and Governance Metrics for Research Computing*.
