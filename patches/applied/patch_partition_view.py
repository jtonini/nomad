#!/usr/bin/env python3
"""
Add partition sections to ClusterView.

Transforms the flat node grid into grouped partition sections,
each with a header showing partition name, node count, and
CPU/Memory utilization bars - matching the nomad demo appearance.
"""
import sys
from pathlib import Path

def patch_cluster_view(path):
    content = open(path).read()
    
    # Find the old node-grid section
    old_grid = '''                    <div className="node-grid">
                        {nodes.map(node => (
                            <div
                                key={node.name}
                                className={`node-card ${node.status === 'down' ? 'down' : ''} ${selectedNode === node.name ? 'selected' : ''}`}
                                onClick={() => onSelectNode(node.name)}
                            >
                                <div className="node-name">{node.name}</div>
                                <div className={`node-indicator ${node.status === 'down' ? 'offline' : getHealthColor(node.success_rate || 0)}`}>
                                    {node.status === 'down' ? '—' : `${Math.round((node.success_rate || 0) * 100)}%`}
                                </div>
                                <div className="node-jobs">
                                    {node.status === 'down' ? (node.slurm_state || 'OFFLINE') : `${node.jobs_today || 0} jobs`}
                                </div>
                                <div className="node-gpu-badge" style={{ background: node.has_gpu ? "#1a1a1a" : "rgba(255,255,255,0.9)", color: node.has_gpu ? "#ffffff" : "#1a1a1a" }}>{node.has_gpu ? "GPU" : "CPU"}</div>
                            </div>
                        ))}
                    </div>'''
    
    new_grid = '''                    {(() => {
                        // Group nodes by partition
                        const partitions = cluster.partitions || {};
                        const partitionNames = Object.keys(partitions);
                        
                        // If no partition info, render flat grid
                        if (partitionNames.length === 0) {
                            return (
                                <div className="node-grid">
                                    {nodes.map(node => (
                                        <div
                                            key={node.name}
                                            className={`node-card ${node.status === 'down' ? 'down' : ''} ${selectedNode === node.name ? 'selected' : ''}`}
                                            onClick={() => onSelectNode(node.name)}
                                        >
                                            <div className="node-name">{node.name}</div>
                                            <div className={`node-indicator ${node.status === 'down' ? 'offline' : getHealthColor(node.success_rate || 0)}`}>
                                                {node.status === 'down' ? '—' : `${Math.round((node.success_rate || 0) * 100)}%`}
                                            </div>
                                            <div className="node-jobs">
                                                {node.status === 'down' ? (node.slurm_state || 'OFFLINE') : `${node.jobs_today || 0} jobs`}
                                            </div>
                                            <div className="node-gpu-badge" style={{ background: node.has_gpu ? "#1a1a1a" : "rgba(255,255,255,0.9)", color: node.has_gpu ? "#ffffff" : "#1a1a1a" }}>{node.has_gpu ? "GPU" : "CPU"}</div>
                                        </div>
                                    ))}
                                </div>
                            );
                        }
                        
                        // Render partition sections
                        return partitionNames.map(partName => {
                            const partNodeNames = partitions[partName] || [];
                            const partNodes = nodes.filter(n => partNodeNames.includes(n.name));
                            if (partNodes.length === 0) return null;
                            
                            const online = partNodes.filter(n => n.status === 'online');
                            const down = partNodes.length - online.length;
                            const hasGpu = partNodes.some(n => n.has_gpu);
                            
                            // Calculate utilization
                            const avgCpu = online.length > 0 
                                ? Math.round(online.reduce((s, n) => s + (n.cpu_percent || 0), 0) / online.length)
                                : 0;
                            const avgMem = online.length > 0
                                ? Math.round(online.reduce((s, n) => s + (n.memory_percent || 0), 0) / online.length)
                                : 0;
                            const avgGpu = hasGpu && online.length > 0
                                ? Math.round(online.filter(n => n.has_gpu).reduce((s, n) => s + (n.gpu_percent || 0), 0) / online.filter(n => n.has_gpu).length)
                                : 0;
                            
                            // Job stats for this partition
                            const totalJobs = partNodes.reduce((s, n) => s + (n.jobs_today || 0), 0);
                            const okJobs = partNodes.reduce((s, n) => s + (n.jobs_success || 0), 0);
                            const failJobs = totalJobs - okJobs;
                            
                            // Partition type description
                            const partType = hasGpu ? 'GPU-accelerated partition' 
                                : partName.toLowerCase().includes('highmem') ? 'High-memory partition'
                                : partName.toLowerCase().includes('debug') ? 'Debug partition'
                                : partName.toLowerCase().includes('short') ? 'Short jobs partition'
                                : 'General CPU partition';
                            
                            return (
                                <div key={partName} className="partition-section">
                                    <div className="partition-header">
                                        <div className="partition-title">
                                            <span className="partition-name">{partName}</span>
                                            <span className="partition-type">{partType}</span>
                                            <span className="partition-count">
                                                {online.length}/{partNodes.length} nodes
                                                {down > 0 && <span className="partition-down"> ({down} down)</span>}
                                            </span>
                                        </div>
                                        <div className="partition-stats">
                                            <span className="partition-jobs">
                                                {totalJobs} jobs  <span style={{color: '#22c55e'}}>{okJobs} ok</span>  <span style={{color: '#ef4444'}}>{failJobs} fail</span>
                                            </span>
                                        </div>
                                        <div className="partition-bars">
                                            <div className="util-bar">
                                                <span className="util-label">CPU</span>
                                                <div className="util-track">
                                                    <div className="util-fill cpu" style={{width: avgCpu + '%'}}></div>
                                                </div>
                                                <span className="util-value">{avgCpu}%</span>
                                            </div>
                                            <div className="util-bar">
                                                <span className="util-label">Memory</span>
                                                <div className="util-track">
                                                    <div className="util-fill mem" style={{width: avgMem + '%'}}></div>
                                                </div>
                                                <span className="util-value">{avgMem}%</span>
                                            </div>
                                            {hasGpu && (
                                                <div className="util-bar">
                                                    <span className="util-label">GPU</span>
                                                    <div className="util-track">
                                                        <div className="util-fill gpu" style={{width: avgGpu + '%'}}></div>
                                                    </div>
                                                    <span className="util-value">{avgGpu}%</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                    <div className="node-grid">
                                        {partNodes.map(node => (
                                            <div
                                                key={node.name}
                                                className={`node-card ${node.status === 'down' ? 'down' : ''} ${selectedNode === node.name ? 'selected' : ''}`}
                                                onClick={() => onSelectNode(node.name)}
                                            >
                                                <div className="node-name">{node.name}</div>
                                                <div className={`node-indicator ${node.status === 'down' ? 'offline' : getHealthColor(node.success_rate || 0)}`}>
                                                    {node.status === 'down' ? '—' : `${Math.round((node.success_rate || 0) * 100)}%`}
                                                </div>
                                                <div className="node-jobs">
                                                    {node.status === 'down' ? (node.slurm_state || 'OFFLINE') : `${node.jobs_today || 0} jobs`}
                                                </div>
                                                <div className="node-gpu-badge" style={{ background: node.has_gpu ? "#1a1a1a" : "rgba(255,255,255,0.9)", color: node.has_gpu ? "#ffffff" : "#1a1a1a" }}>{node.has_gpu ? "GPU" : "CPU"}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            );
                        });
                    })()}'''
    
    if old_grid in content:
        content = content.replace(old_grid, new_grid, 1)
        print("  + Replaced node-grid with partition sections")
    else:
        print("  ! Could not find node-grid block")
        return False
    
    # Add CSS for partition sections
    # Find the existing .node-grid CSS and add partition styles after it
    css_marker = '.node-grid {'
    if css_marker in content:
        # Find a good place to insert - after node-grid styles
        idx = content.index(css_marker)
        # Find the closing brace of .node-grid
        brace_count = 0
        end_idx = idx
        for i in range(idx, len(content)):
            if content[i] == '{':
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        partition_css = '''
                    .partition-section {
                        background: rgba(255,255,255,0.02);
                        border: 1px solid rgba(255,255,255,0.06);
                        border-radius: 12px;
                        padding: 20px;
                        margin-bottom: 24px;
                    }
                    .partition-header {
                        margin-bottom: 16px;
                    }
                    .partition-title {
                        display: flex;
                        align-items: baseline;
                        gap: 12px;
                        margin-bottom: 8px;
                    }
                    .partition-name {
                        font-size: 18px;
                        font-weight: 600;
                        color: #e0e0e0;
                    }
                    .partition-type {
                        font-size: 13px;
                        color: #808080;
                    }
                    .partition-count {
                        font-size: 13px;
                        color: #a0a0a0;
                        margin-left: auto;
                    }
                    .partition-down {
                        color: #ef4444;
                    }
                    .partition-stats {
                        font-size: 12px;
                        color: #808080;
                        margin-bottom: 12px;
                    }
                    .partition-jobs {
                        display: flex;
                        gap: 12px;
                    }
                    .partition-bars {
                        display: flex;
                        gap: 16px;
                        flex-wrap: wrap;
                    }
                    .util-bar {
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        min-width: 180px;
                    }
                    .util-label {
                        font-size: 12px;
                        color: #808080;
                        width: 50px;
                    }
                    .util-track {
                        flex: 1;
                        height: 6px;
                        background: rgba(255,255,255,0.1);
                        border-radius: 3px;
                        overflow: hidden;
                        min-width: 80px;
                    }
                    .util-fill {
                        height: 100%;
                        border-radius: 3px;
                        transition: width 0.3s;
                    }
                    .util-fill.cpu { background: linear-gradient(90deg, #22c55e, #4ade80); }
                    .util-fill.mem { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
                    .util-fill.gpu { background: linear-gradient(90deg, #8b5cf6, #a78bfa); }
                    .util-value {
                        font-size: 12px;
                        color: #a0a0a0;
                        width: 36px;
                        text-align: right;
                    }
'''
        # Check if we already have partition-section CSS
        if '.partition-section' not in content:
            content = content[:end_idx] + partition_css + content[end_idx:]
            print("  + Added partition CSS styles")
        else:
            print("  = Partition CSS already exists")
    else:
        print("  ! Could not find .node-grid CSS")
    
    open(path, 'w').write(content)
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 patch_partition_view.py /path/to/nomad/nomad/viz/server.py")
        sys.exit(1)
    
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: {path} not found")
        sys.exit(1)
    
    print()
    print("Adding partition sections to ClusterView")
    print("=" * 40)
    
    ok = patch_cluster_view(path)
    
    if ok:
        print()
        print("Done! Test with: nomad dashboard")
    else:
        print("Patch failed - may need manual edit")


if __name__ == '__main__':
    main()
