"""
LSTM for temporal failure prediction.

Predicts WHEN a job might fail based on resource usage trajectory.
Input: Time series of job metrics
Output: Failure probability over time
"""

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


if HAS_TORCH:

    class JobTrajectoryDataset(Dataset):
        """Dataset of job metric trajectories."""
        
        def __init__(self, trajectories: list, labels: list, seq_len: int = 20):
            """
            Args:
                trajectories: List of (n_timesteps, n_features) arrays
                labels: Failure reason for each trajectory (0=success)
                seq_len: Fixed sequence length (pad/truncate)
            """
            self.seq_len = seq_len
            self.data = []
            self.labels = []
            
            for traj, label in zip(trajectories, labels):
                # Pad or truncate to seq_len
                if len(traj) >= seq_len:
                    traj = traj[-seq_len:]  # Take last seq_len steps
                else:
                    # Pad with zeros at the beginning
                    padding = [[0.0] * len(traj[0])] * (seq_len - len(traj))
                    traj = padding + list(traj)
                
                self.data.append(torch.tensor(traj, dtype=torch.float))
                self.labels.append(label)
            
            self.labels = torch.tensor(self.labels, dtype=torch.long)
        
        def __len__(self):
            return len(self.data)
        
        def __getitem__(self, idx):
            return self.data[idx], self.labels[idx]


    class FailureLSTM(nn.Module):
        """
        LSTM for predicting job failure from metric trajectories.
        
        Architecture:
            Input (seq_len, n_features) 
            -> LSTM layers
            -> Attention pooling
            -> Classification head
        """
        
        def __init__(self, input_dim: int, hidden_dim: int = 64,
                     n_layers: int = 2, output_dim: int = 8,
                     dropout: float = 0.3, bidirectional: bool = True):
            super().__init__()
            
            self.hidden_dim = hidden_dim
            self.n_layers = n_layers
            self.bidirectional = bidirectional
            self.n_directions = 2 if bidirectional else 1
            
            # LSTM layers
            self.lstm = nn.LSTM(
                input_dim,
                hidden_dim,
                n_layers,
                batch_first=True,
                dropout=dropout if n_layers > 1 else 0,
                bidirectional=bidirectional
            )
            
            # Attention mechanism
            self.attention = nn.Linear(hidden_dim * self.n_directions, 1)
            
            # Classification head
            self.classifier = nn.Sequential(
                nn.Linear(hidden_dim * self.n_directions, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, output_dim)
            )
        
        def forward(self, x):
            """
            Args:
                x: (batch, seq_len, n_features)
            Returns:
                logits: (batch, output_dim)
            """
            # LSTM encoding
            lstm_out, _ = self.lstm(x)  # (batch, seq_len, hidden*directions)
            
            # Attention pooling
            attn_weights = F.softmax(self.attention(lstm_out), dim=1)
            context = torch.sum(attn_weights * lstm_out, dim=1)  # (batch, hidden*directions)
            
            # Classification
            return self.classifier(context)
        
        def predict_proba(self, x):
            """Get failure probabilities."""
            self.eval()
            with torch.no_grad():
                logits = self.forward(x)
                return F.softmax(logits, dim=1)
        
        def get_attention_weights(self, x):
            """Get attention weights for interpretability."""
            self.eval()
            with torch.no_grad():
                lstm_out, _ = self.lstm(x)
                attn_weights = F.softmax(self.attention(lstm_out), dim=1)
                return attn_weights.squeeze(-1)


    class LSTMTrainer:
        """Trainer for LSTM with early stopping."""
        
        def __init__(self, model: FailureLSTM, lr: float = 0.001,
                     device: str = 'auto', gamma: float = 1.0):
            self.model = model
            self.gamma = gamma
            
            if device == 'auto':
                self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            else:
                self.device = torch.device(device)
            
            self.model.to(self.device)
            self.optimizer = torch.optim.Adam(model.parameters(), lr=lr)
            self.history = []
        
        def _focal_loss(self, logits, targets, weights=None):
            """Focal loss for imbalanced classes."""
            ce = F.cross_entropy(logits, targets, weight=weights, reduction='none')
            pt = torch.exp(-ce)
            return ((1 - pt) ** self.gamma * ce).mean()
        
        def train_epoch(self, dataloader, class_weights=None):
            self.model.train()
            total_loss = 0
            correct = 0
            total = 0
            
            weights = class_weights.to(self.device) if class_weights is not None else None
            
            for x, y in dataloader:
                x, y = x.to(self.device), y.to(self.device)
                
                self.optimizer.zero_grad()
                logits = self.model(x)
                loss = self._focal_loss(logits, y, weights)
                loss.backward()
                self.optimizer.step()
                
                total_loss += loss.item()
                pred = logits.argmax(dim=1)
                correct += (pred == y).sum().item()
                total += y.size(0)
            
            return {
                'loss': total_loss / len(dataloader),
                'accuracy': correct / total
            }
        
        @torch.no_grad()
        def evaluate(self, dataloader):
            self.model.eval()
            correct = 0
            total = 0
            per_class = {}
            
            for x, y in dataloader:
                x, y = x.to(self.device), y.to(self.device)
                pred = self.model(x).argmax(dim=1)
                correct += (pred == y).sum().item()
                total += y.size(0)
                
                # Per-class accuracy
                for c in range(8):
                    mask = (y == c)
                    if mask.sum() > 0:
                        c_correct = (pred[mask] == c).sum().item()
                        c_total = mask.sum().item()
                        if c not in per_class:
                            per_class[c] = {'correct': 0, 'total': 0}
                        per_class[c]['correct'] += c_correct
                        per_class[c]['total'] += c_total
            
            return {
                'accuracy': correct / total if total > 0 else 0,
                'per_class': {c: v['correct']/v['total'] for c, v in per_class.items() if v['total'] > 0}
            }
        
        def train(self, train_loader, val_loader=None, epochs: int = 100,
                  class_weights=None, patience: int = 10, verbose: bool = True):
            best_val_acc = 0
            no_improve = 0
            
            for epoch in range(epochs):
                train_result = self.train_epoch(train_loader, class_weights)
                val_result = self.evaluate(val_loader) if val_loader else None
                
                record = {
                    'epoch': epoch,
                    'loss': train_result['loss'],
                    'train_acc': train_result['accuracy']
                }
                
                if val_result:
                    record['val_acc'] = val_result['accuracy']
                    if val_result['accuracy'] > best_val_acc:
                        best_val_acc = val_result['accuracy']
                        no_improve = 0
                    else:
                        no_improve += 1
                
                self.history.append(record)
                
                if verbose and (epoch % 10 == 0 or epoch == epochs - 1):
                    msg = f"Epoch {epoch+1:3d}: loss={train_result['loss']:.4f}, train_acc={train_result['accuracy']:.2%}"
                    if val_result:
                        msg += f", val_acc={val_result['accuracy']:.2%}"
                    print(msg)
                
                # Early stopping
                if patience and no_improve >= patience:
                    if verbose:
                        print(f"Early stopping at epoch {epoch+1}")
                    break
            
            return self.history


    def generate_synthetic_trajectories(jobs: list, n_steps: int = 20) -> list:
        """
        Generate synthetic trajectories from job data.
        
        In production, this would come from real-time monitoring.
        For simulation, we create plausible trajectories based on job outcome.
        """
        import random
        
        trajectories = []
        labels = []
        
        for job in jobs:
            failure = job.get('failure_reason', 0)
            runtime = job.get('runtime_seconds', 3600) or 3600
            mem = job.get('req_mem_mb', 4096) or 4096
            cpus = job.get('req_cpus', 4) or 4
            
            # Generate trajectory
            traj = []
            for t in range(n_steps):
                progress = t / n_steps
                
                # Base metrics
                cpu_util = 0.3 + 0.5 * progress + random.gauss(0, 0.1)
                mem_util = 0.2 + 0.4 * progress + random.gauss(0, 0.1)
                io_rate = 0.1 + 0.2 * progress + random.gauss(0, 0.05)
                
                # Failure-specific patterns
                if failure == 1:  # TIMEOUT - gradual slowdown
                    cpu_util *= (1 - 0.3 * progress)
                    io_rate *= 2  # Excessive I/O
                elif failure == 4:  # OOM - memory spike
                    mem_util = min(1.0, mem_util + 0.4 * progress ** 2)
                elif failure == 3:  # FAILED - erratic
                    cpu_util += random.gauss(0, 0.3)
                elif failure == 5:  # SEGFAULT - sudden spike
                    if progress > 0.7:
                        cpu_util = random.uniform(0.9, 1.0)
                        mem_util = random.uniform(0.8, 1.0)
                
                traj.append([
                    max(0, min(1, cpu_util)),
                    max(0, min(1, mem_util)),
                    max(0, min(1, io_rate)),
                    progress  # Time feature
                ])
            
            trajectories.append(traj)
            labels.append(failure)
        
        return trajectories, labels


    def train_failure_lstm(jobs: list, epochs: int = 100,
                           hidden_dim: int = 64, seq_len: int = 20,
                           verbose: bool = True) -> dict:
        """Train LSTM on job trajectories."""
        from nomade.ml.gnn import FAILURE_NAMES
        
        # Generate trajectories
        trajectories, labels = generate_synthetic_trajectories(jobs, seq_len)
        
        if verbose:
            print(f"Generated {len(trajectories)} trajectories")
            print(f"Sequence length: {seq_len}, Features: 4")
        
        # Create dataset
        dataset = JobTrajectoryDataset(trajectories, labels, seq_len)
        
        # Split
        n = len(dataset)
        train_size = int(0.7 * n)
        val_size = int(0.15 * n)
        
        indices = torch.randperm(n)
        train_idx = indices[:train_size]
        val_idx = indices[train_size:train_size+val_size]
        test_idx = indices[train_size+val_size:]
        
        train_data = torch.utils.data.Subset(dataset, train_idx)
        val_data = torch.utils.data.Subset(dataset, val_idx)
        test_data = torch.utils.data.Subset(dataset, test_idx)
        
        train_loader = DataLoader(train_data, batch_size=32, shuffle=True)
        val_loader = DataLoader(val_data, batch_size=32)
        test_loader = DataLoader(test_data, batch_size=32)
        
        if verbose:
            print(f"Train/Val/Test: {len(train_data)}/{len(val_data)}/{len(test_data)}")
            print()
        
        # Class weights
        label_counts = torch.bincount(dataset.labels, minlength=8).float().clamp(min=1)
        class_weights = 1.0 / torch.sqrt(label_counts)
        class_weights = class_weights / class_weights.sum() * 8
        
        # Model
        model = FailureLSTM(
            input_dim=4,  # cpu, mem, io, time
            hidden_dim=hidden_dim,
            n_layers=2,
            output_dim=8
        )
        
        # Train
        trainer = LSTMTrainer(model, lr=0.001, gamma=1.0)
        history = trainer.train(
            train_loader, val_loader,
            epochs=epochs,
            class_weights=class_weights,
            patience=15,
            verbose=verbose
        )
        
        # Test
        test_result = trainer.evaluate(test_loader)
        
        if verbose:
            print(f"\nTest accuracy: {test_result['accuracy']:.2%}")
            print("Per-class:")
            for c, acc in sorted(test_result['per_class'].items()):
                print(f"  {FAILURE_NAMES.get(c, f'Class {c}')}: {acc:.2%}")
        
        return {
            'model': model,
            'trainer': trainer,
            'history': history,
            'test_accuracy': test_result['accuracy'],
            'per_class': test_result['per_class']
        }


else:
    class FailureLSTM:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required")
    
    class LSTMTrainer:
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch required")
    
    def train_failure_lstm(*args, **kwargs):
        raise ImportError("PyTorch required")


def is_torch_available() -> bool:
    return HAS_TORCH


if __name__ == '__main__':
    if not HAS_TORCH:
        print("PyTorch not available")
    else:
        print("Testing LSTM with synthetic trajectories...")
        print(f"Device: {'CUDA' if torch.cuda.is_available() else 'CPU'}")
        print()
        
        # Generate fake jobs
        import random
        jobs = []
        for i in range(1000):
            failure = random.choices([0, 1, 2, 3, 4, 5, 6, 7], 
                                     weights=[80, 5, 2, 5, 4, 2, 1, 1])[0]
            jobs.append({
                'failure_reason': failure,
                'runtime_seconds': random.randint(60, 86400),
                'req_mem_mb': random.randint(1024, 65536),
                'req_cpus': random.randint(1, 32)
            })
        
        result = train_failure_lstm(jobs, epochs=50, hidden_dim=32)
        print(f"\nFinal test accuracy: {result['test_accuracy']:.2%}")
