"""
NØMADE Machine Learning Module

- GNN: What fails (network structure)
- LSTM: When it fails (temporal patterns)  
- Autoencoder: Is this normal (anomaly detection)
"""

from .gnn import (
    SimpleGNN,
    GNNConfig,
    prepare_job_features,
    build_adjacency_from_edges,
    evaluate_gnn,
    FAILURE_NAMES
)

try:
    from .gnn_torch import (
        is_torch_available,
        FocalLoss,
        FailureGNN,
        GNNTrainer,
        train_failure_gnn,
        prepare_pyg_data
    )
    from .lstm import (
        FailureLSTM,
        LSTMTrainer,
        train_failure_lstm,
        JobTrajectoryDataset,
        generate_synthetic_trajectories
    )
    from .autoencoder import (
        JobAutoencoder,
        AutoencoderTrainer,
        train_anomaly_detector,
        prepare_autoencoder_data
    )
except ImportError:
    is_torch_available = lambda: False

__all__ = [
    # Pure Python
    'SimpleGNN', 'GNNConfig', 'prepare_job_features',
    'build_adjacency_from_edges', 'evaluate_gnn', 'FAILURE_NAMES',
    # PyTorch GNN
    'is_torch_available', 'FocalLoss', 'FailureGNN', 'GNNTrainer',
    'train_failure_gnn', 'prepare_pyg_data',
    # LSTM
    'FailureLSTM', 'LSTMTrainer', 'train_failure_lstm',
    'JobTrajectoryDataset', 'generate_synthetic_trajectories',
    # Autoencoder
    'JobAutoencoder', 'AutoencoderTrainer', 'train_anomaly_detector',
    'prepare_autoencoder_data'
]
