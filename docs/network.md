# Network Methodology

NØMADE's prediction engine uses similarity networks to identify job failure patterns. This approach draws inspiration from biogeographical network analysis.

## Theoretical Foundation

### From Biogeography to HPC

The methodology is inspired by Vilhena & Antonelli (2015), who used network analysis to identify biogeographical regions from species distribution data. Just as biogeographical regions emerge from species patterns rather than being predefined, NØMADE allows job behavior patterns to emerge from metric data.

| Biogeography Concept | NØMADE Analog |
|---------------------|---------------|
| Species | Jobs |
| Geographic regions | Compute resources (nodes, partitions) |
| Emergent biomes | Job behavior clusters |
| Species ranges | Resource usage patterns |
| Transition zones | Domain boundaries (CPU↔GPU, NFS↔local) |

### Why Cosine Similarity?

NØMADE uses **cosine similarity on continuous feature vectors** rather than Simpson similarity on categorical presence/absence data:

- **Magnitude matters**: CPU efficiency of 80% vs 20% is significant, not just "used CPU"
- **Multi-dimensional**: Jobs have 17+ continuous metrics
- **Shape over scale**: Cosine similarity captures resource *profiles*, not absolute consumption

A job requesting 64GB with 50% utilization has a similar profile to one requesting 8GB with 50% utilization—both represent reasonable memory sizing—even though absolute consumption differs by 8x.

## Network Construction

### Step 1: Feature Vector Extraction

Each completed job produces a 17-dimensional feature vector:
```
┌─────────────────────────────────────────────────────────────┐
│                    Job Feature Vector                       │
├─────────────────────────────────────────────────────────────┤
│ CPU Metrics          │ cpu_efficiency, cores_requested,    │
│                      │ cpu_time_used, avg_cpu_percent      │
├─────────────────────────────────────────────────────────────┤
│ Memory Metrics       │ mem_efficiency, mem_requested_gb,   │
│                      │ peak_mem_gb, avg_mem_percent        │
├─────────────────────────────────────────────────────────────┤
│ I/O Metrics          │ nfs_read_gb, nfs_write_gb,          │
│                      │ local_read_gb, local_write_gb,      │
│                      │ nfs_ratio, io_wait_percent          │
├─────────────────────────────────────────────────────────────┤
│ Time Metrics         │ runtime_seconds, requested_seconds, │
│                      │ time_efficiency                     │
├─────────────────────────────────────────────────────────────┤
│ GPU Metrics          │ gpu_utilization, gpu_mem_percent    │
│ (if applicable)      │                                     │
└─────────────────────────────────────────────────────────────┘
```

### Step 2: Z-Score Normalization

Features are normalized to zero mean, unit variance:

$$z_i = \frac{x_i - \mu_i}{\sigma_i}$$

This ensures all dimensions contribute equally to similarity calculations.

### Step 3: Cosine Similarity Matrix

For jobs $a$ and $b$ with feature vectors $\vec{a}$ and $\vec{b}$:

$$\text{similarity}(a, b) = \frac{\vec{a} \cdot \vec{b}}{|\vec{a}| \cdot |\vec{b}|}$$

Values range from -1 (opposite profiles) to +1 (identical profiles).

### Step 4: Edge Creation

Edges connect jobs with similarity ≥ threshold (default: 0.7):
```python
if cosine_similarity(job_a, job_b) >= 0.7:
    network.add_edge(job_a, job_b)
```

**Threshold trade-offs:**

| Threshold | Network Density | Clusters | Use Case |
|-----------|-----------------|----------|----------|
| 0.9+ | Sparse | Tight, specific | Anomaly detection |
| 0.7 (default) | Moderate | Balanced | General prediction |
| 0.5 | Dense | Broad patterns | Exploratory analysis |

### Step 5: Community Detection

Connected components and modularity-based clustering identify job communities—groups with similar resource profiles.

## Bipartite Network Approach

For advanced analysis, NØMADE implements Vilhena & Antonelli's bipartite approach:
```
┌──────────────┐          ┌──────────────┐
│    Jobs      │──────────│ Resource Bins│
├──────────────┤          ├──────────────┤
│ job_1001     │────┬────▶│ cpu_high     │
│ job_1002     │────┤     │ cpu_low      │
│ job_1003     │────┼────▶│ mem_high     │
│ job_1004     │────┤     │ mem_low      │
│ ...          │────┴────▶│ io_nfs_heavy │
└──────────────┘          └──────────────┘
```

1. **Discretize features** into bins (e.g., cpu_high, cpu_low)
2. **Create bipartite graph**: jobs connected to their resource bins
3. **Project onto job-job network**: jobs sharing bins are connected
4. **Weight by overlap**: more shared bins = stronger connection

This approach:

- Treats each resource bin as a "site" (biogeography analogy)
- Reveals emergent behavioral regions
- Handles missing data gracefully

## Network Metrics

### Assortativity

Measures whether failed jobs cluster together:

$$r = \frac{\sum_{ij}(A_{ij} - k_i k_j / 2m) \delta(c_i, c_j)}{2m - \sum_{ij}(k_i k_j / 2m) \delta(c_i, c_j)}$$

- **Positive**: Failed jobs connect to failed jobs (pattern exists)
- **Zero**: Random mixing (no predictive signal)
- **Negative**: Failed jobs connect to successful jobs (unusual)

### Clustering Coefficient

Local clustering indicates behavioral cohesion:

$$C_i = \frac{2 |\{e_{jk}\}|}{k_i(k_i - 1)}$$

High clustering = consistent failure patterns.

### Statistical Significance

NØMADE tests whether observed patterns exceed random chance using permutation tests:

1. Shuffle failure labels 1000 times
2. Compute metric for each shuffle
3. Calculate z-score: $z = (observed - \mu_{null}) / \sigma_{null}$
4. Report significance if $|z| > 2$

## Visualization

The dashboard provides a 3D force-directed network visualization:

- **Node color**: Green (healthy) to Red (failed)
- **Node position**: Fruchterman-Reingold layout
- **Axes**: NFS ratio, local I/O, I/O wait
- **Regions**: "Safe zone" vs "danger zone" emerge from data

## References

Vilhena, D.A., Antonelli, A. (2015). A network approach for identifying and delimiting biogeographical regions. *Nature Communications* 6:6848. DOI: [10.1038/ncomms7848](https://doi.org/10.1038/ncomms7848)
