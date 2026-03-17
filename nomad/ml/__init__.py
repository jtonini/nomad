# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 João Tonini
"""
NØMAD Machine Learning Module

- GNN: What fails (network structure)
- LSTM: When it fails (temporal patterns)
- Autoencoder: Is this normal (anomaly detection)
- Ensemble: Combined prediction
- Persistence: Save/load models and predictions
"""

from .gnn import (
    FAILURE_NAMES,
    GNNConfig,
    SimpleGNN,
    build_adjacency_from_edges,
    evaluate_gnn,
    prepare_job_features,
)

try:
    from .autoencoder import (
        AutoencoderTrainer,
        JobAutoencoder,
        prepare_autoencoder_data,
        train_anomaly_detector,
    )
    from .ensemble import FailureEnsemble, train_and_save_ensemble, train_ensemble
    from .gnn_torch import (
        FailureGNN,
        FocalLoss,
        GNNTrainer,
        is_torch_available,
        prepare_pyg_data,
        train_failure_gnn,
    )
    from .lstm import (
        FailureLSTM,
        JobTrajectoryDataset,
        LSTMTrainer,
        generate_synthetic_trajectories,
        train_failure_lstm,
    )
    from .persistence import (
        get_prediction_history,
        init_ml_tables,
        load_latest_models,
        load_predictions_from_db,
        save_ensemble_models,
        save_predictions_to_db,
    )
except ImportError:
    is_torch_available = lambda: False

__all__ = [
    'SimpleGNN', 'GNNConfig', 'prepare_job_features',
    'build_adjacency_from_edges', 'evaluate_gnn', 'FAILURE_NAMES',
    'is_torch_available', 'FocalLoss', 'FailureGNN', 'GNNTrainer',
    'train_failure_gnn', 'prepare_pyg_data',
    'FailureLSTM', 'LSTMTrainer', 'train_failure_lstm',
    'JobTrajectoryDataset', 'generate_synthetic_trajectories',
    'JobAutoencoder', 'AutoencoderTrainer', 'train_anomaly_detector',
    'prepare_autoencoder_data',
    'FailureEnsemble', 'train_ensemble', 'train_and_save_ensemble',
    'init_ml_tables', 'save_predictions_to_db', 'load_predictions_from_db',
    'save_ensemble_models', 'load_latest_models', 'get_prediction_history'
]

try:
    from .continuous import ContinuousLearner
except ImportError:
    pass
