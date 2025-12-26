"""
Autoencoder for anomaly detection.

Learns "normal" job patterns and flags deviations.
High reconstruction error = anomaly = potential failure.
"""

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader, TensorDataset
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


if HAS_TORCH:

    class JobAutoencoder(nn.Module):
        """
        Autoencoder for learning normal job patterns.
        
        Architecture:
            Input -> Encoder -> Latent -> Decoder -> Reconstruction
            
        High reconstruction error indicates anomaly.
        """
        
        def __init__(self, input_dim: int, latent_dim: int = 8,
                     hidden_dims: list = None):
            super().__init__()
            
            if hidden_dims is None:
                hidden_dims = [32, 16]
            
            # Encoder
            encoder_layers = []
            prev_dim = input_dim
            for h_dim in hidden_dims:
                encoder_layers.extend([
                    nn.Linear(prev_dim, h_dim),
                    nn.ReLU(),
                    nn.BatchNorm1d(h_dim)
                ])
                prev_dim = h_dim
            encoder_layers.append(nn.Linear(prev_dim, latent_dim))
            self.encoder = nn.Sequential(*encoder_layers)
            
            # Decoder (mirror of encoder)
            decoder_layers = []
            prev_dim = latent_dim
            for h_dim in reversed(hidden_dims):
                decoder_layers.extend([
                    nn.Linear(prev_dim, h_dim),
                    nn.ReLU(),
                    nn.BatchNorm1d(h_dim)
                ])
                prev_dim = h_dim
            decoder_layers.append(nn.Linear(prev_dim, input_dim))
            self.decoder = nn.Sequential(*decoder_layers)
        
        def encode(self, x):
            return self.encoder(x)
        
        def decode(self, z):
            return self.decoder(z)
        
        def forward(self, x):
            z = self.encode(x)
            return self.decode(z)
        
        def reconstruction_error(self, x):
            """Compute per-sample reconstruction error."""
            self.eval()
            with torch.no_grad():
                recon = self.forward(x)
                error = ((x - recon) ** 2).mean(dim=1)
            return error
        
        def is_anomaly(self, x, threshold: float = None):
            """
            Detect anomalies based on reconstruction error.
            
            Args:
                x: Input features
                threshold: Error threshold (default: mean + 2*std from training)
                
            Returns:
                Boolean mask of anomalies
            """
            error = self.reconstruction_error(x)
            if threshold is None:
                threshold = self.anomaly_threshold
            return error > threshold


    class AutoencoderTrainer:
        """Trainer for autoencoder with anomaly threshold calculation."""
        
        def __init__(self, model: JobAutoencoder, lr: float = 0.001,
                     device: str = 'auto'):
            self.model = model
            
            if device == 'auto':
                self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            else:
                self.device = torch.device(device)
            
            self.model.to(self.device)
            self.optimizer = torch.optim.Adam(model.parameters(), lr=lr)
            self.history = []
            self.threshold = None
        
        def train_epoch(self, dataloader):
            self.model.train()
            total_loss = 0
            
            for x, in dataloader:
                x = x.to(self.device)
                
                self.optimizer.zero_grad()
                recon = self.model(x)
                loss = F.mse_loss(recon, x)
                loss.backward()
                self.optimizer.step()
                
                total_loss += loss.item()
            
            return total_loss / len(dataloader)
        
        def compute_threshold(self, dataloader, n_std: float = 2.0):
            """Compute anomaly threshold from training data."""
            self.model.eval()
            errors = []
            
            with torch.no_grad():
                for x, in dataloader:
                    x = x.to(self.device)
                    error = self.model.reconstruction_error(x)
                    errors.extend(error.cpu().tolist())
            
            import statistics
            mean_error = statistics.mean(errors)
            std_error = statistics.stdev(errors) if len(errors) > 1 else 0
            
            self.threshold = mean_error + n_std * std_error
            self.model.anomaly_threshold = self.threshold
            
            return {
                'mean': mean_error,
                'std': std_error,
                'threshold': self.threshold
            }
        
        def train(self, train_loader, val_loader=None, epochs: int = 100,
                  verbose: bool = True):
            for epoch in range(epochs):
                train_loss = self.train_epoch(train_loader)
                
                record = {'epoch': epoch, 'loss': train_loss}
                self.history.append(record)
                
                if verbose and (epoch % 10 == 0 or epoch == epochs - 1):
                    print(f"Epoch {epoch+1:3d}: loss={train_loss:.6f}")
            
            # Compute threshold after training
            threshold_info = self.compute_threshold(train_loader)
            if verbose:
                print(f"\nAnomaly threshold: {threshold_info['threshold']:.6f}")
                print(f"  (mean={threshold_info['mean']:.6f}, std={threshold_info['std']:.6f})")
            
            return self.history
        
        @torch.no_grad()
        def evaluate(self, dataloader, labels=None):
            """
            Evaluate anomaly detection.
            
            Args:
                dataloader: Data to evaluate
                labels: True failure labels (0=success, >0=failure)
            """
            self.model.eval()
            errors = []
            all_labels = []
            
            for batch in dataloader:
                if len(batch) == 2:
                    x, y = batch
                    all_labels.extend(y.tolist())
                else:
                    x = batch[0]
                x = x.to(self.device)
                error = self.model.reconstruction_error(x)
                errors.extend(error.cpu().tolist())
            
            # Compute metrics
            predictions = [e > self.threshold for e in errors]
            
            if all_labels or labels is not None:
                if labels is not None:
                    all_labels = labels
                # True anomaly = any failure
                true_anomaly = [l > 0 for l in all_labels]
                
                tp = sum(p and t for p, t in zip(predictions, true_anomaly))
                fp = sum(p and not t for p, t in zip(predictions, true_anomaly))
                fn = sum(not p and t for p, t in zip(predictions, true_anomaly))
                tn = sum(not p and not t for p, t in zip(predictions, true_anomaly))
                
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
                
                return {
                    'errors': errors,
                    'predictions': predictions,
                    'precision': precision,
                    'recall': recall,
                    'f1': f1,
                    'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn
                }
            
            return {
                'errors': errors,
                'predictions': predictions,
                'n_anomalies': sum(predictions)
            }


    def prepare_autoencoder_data(jobs: list, feature_names: list = None):
        """Prepare job features for autoencoder."""
        if feature_names is None:
            feature_names = [
                'req_gpus', 'req_time_seconds', 'runtime_seconds',
                'req_mem_mb', 'req_cpus', 'wait_time_seconds'
            ]
        
        available = [f for f in feature_names if any(j.get(f) is not None for j in jobs)]
        if not available:
            available = ['req_cpus', 'req_mem_mb']
        
        features = []
        labels = []
        for job in jobs:
            feat = [float(job.get(f, 0) or 0) for f in available]
            features.append(feat)
            labels.append(job.get('failure_reason', 0))
        
        x = torch.tensor(features, dtype=torch.float)
        # Normalize
        x = (x - x.mean(dim=0)) / (x.std(dim=0) + 1e-8)
        
        return x, labels, available


    def train_anomaly_detector(jobs: list, epochs: int = 100,
                               latent_dim: int = 4, verbose: bool = True) -> dict:
        """
        Train autoencoder for anomaly detection.
        
        Trains on SUCCESS jobs only, then detects failures as anomalies.
        """
        from nomade.ml.gnn import FAILURE_NAMES
        
        # Prepare data
        x, labels, feature_names = prepare_autoencoder_data(jobs)
        
        if verbose:
            print(f"Features: {feature_names}")
            print(f"Total jobs: {len(jobs)}")
        
        # Split: train on SUCCESS only
        success_mask = torch.tensor([l == 0 for l in labels])
        failure_mask = ~success_mask
        
        x_success = x[success_mask]
        x_failure = x[failure_mask]
        labels_failure = [l for l, m in zip(labels, failure_mask.tolist()) if m]
        
        if verbose:
            print(f"Success jobs (training): {len(x_success)}")
            print(f"Failure jobs (testing): {len(x_failure)}")
            print()
        
        # Train/val split on success jobs
        n = len(x_success)
        perm = torch.randperm(n)
        train_size = int(0.8 * n)
        
        train_data = TensorDataset(x_success[perm[:train_size]])
        val_data = TensorDataset(x_success[perm[train_size:]])
        
        train_loader = DataLoader(train_data, batch_size=32, shuffle=True)
        val_loader = DataLoader(val_data, batch_size=32)
        
        # Model
        model = JobAutoencoder(
            input_dim=x.size(1),
            latent_dim=latent_dim,
            hidden_dims=[32, 16]
        )
        
        # Train
        trainer = AutoencoderTrainer(model, lr=0.001)
        history = trainer.train(train_loader, val_loader, epochs=epochs, verbose=verbose)
        
        # Evaluate on failures
        if len(x_failure) > 0:
            failure_loader = DataLoader(
                TensorDataset(x_failure, torch.tensor(labels_failure)),
                batch_size=32
            )
            results = trainer.evaluate(failure_loader)
            
            if verbose:
                print(f"\nAnomaly detection on failures:")
                print(f"  Detected: {results['n_anomalies'] if 'n_anomalies' in results else results['tp']}/{len(x_failure)}")
                if 'precision' in results:
                    print(f"  Precision: {results['precision']:.2%}")
                    print(f"  Recall: {results['recall']:.2%}")
                    print(f"  F1: {results['f1']:.2%}")
        else:
            results = {}
        
        return {
            'model': model,
            'trainer': trainer,
            'history': history,
            'threshold': trainer.threshold,
            'feature_names': feature_names,
            'results': results
        }


else:
    class JobAutoencoder:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required")
    
    class AutoencoderTrainer:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required")
    
    def train_anomaly_detector(*args, **kwargs):
        raise ImportError("PyTorch required")


def is_torch_available() -> bool:
    return HAS_TORCH


if __name__ == '__main__':
    if not HAS_TORCH:
        print("PyTorch not available")
    else:
        print("Testing Autoencoder anomaly detection...")
        print(f"Device: {'CUDA' if torch.cuda.is_available() else 'CPU'}")
        print()
        
        # Generate test data
        import random
        jobs = []
        for i in range(1000):
            failure = random.choices([0, 1, 2, 3, 4, 5, 6, 7],
                                     weights=[80, 5, 2, 5, 4, 2, 1, 1])[0]
            # Normal jobs
            base_mem = random.randint(4096, 32768)
            base_cpu = random.randint(4, 16)
            base_time = random.randint(3600, 36000)
            
            # Anomalous patterns for failures
            if failure == 4:  # OOM
                base_mem *= 3
            elif failure == 1:  # TIMEOUT
                base_time *= 5
            elif failure == 3:  # FAILED
                base_cpu = random.randint(1, 2)  # Under-resourced
            
            jobs.append({
                'failure_reason': failure,
                'req_mem_mb': base_mem,
                'req_cpus': base_cpu,
                'req_time_seconds': base_time,
                'runtime_seconds': base_time * random.uniform(0.5, 1.5),
                'wait_time_seconds': random.randint(0, 3600),
                'req_gpus': 0
            })
        
        result = train_anomaly_detector(jobs, epochs=50, latent_dim=4)
        print(f"\nThreshold: {result['threshold']:.6f}")
