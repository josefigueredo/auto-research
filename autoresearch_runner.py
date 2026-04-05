"""
AutoResearch Local Test Runner — CPU Edition
Faithful miniature of Karpathy's autoresearch pattern.
Optimizes a numpy neural network on synthetic data.

Usage: python autoresearch_runner.py
"""

import time
import csv
import os
import numpy as np

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
np.random.seed(42)

# ---------------------------------------------------------------------------
# Synthetic Dataset (sine wave + noise — a nontrivial regression target)
# ---------------------------------------------------------------------------
def make_dataset(n=2000):
    X = np.random.uniform(-3, 3, (n, 1)).astype(np.float32)
    y = (np.sin(X) + 0.3 * np.sin(3 * X) + 0.1 * np.random.randn(n, 1)).astype(np.float32)
    split = int(0.8 * n)
    return X[:split], y[:split], X[split:], y[split:]

X_train, y_train, X_val, y_val = make_dataset()

# ---------------------------------------------------------------------------
# Tiny Neural Network (numpy only)
# ---------------------------------------------------------------------------
def relu(x):
    return np.maximum(0, x)

def relu_grad(x):
    return (x > 0).astype(np.float32)

def tanh_act(x):
    return np.tanh(x)

def tanh_grad(x):
    t = np.tanh(x)
    return 1 - t ** 2

ACTIVATIONS = {
    "relu": (relu, relu_grad),
    "tanh": (tanh_act, tanh_grad),
}

def init_weights(layers, scale=0.1):
    """He-like init for a list of (in, out) dims."""
    params = []
    for fan_in, fan_out in layers:
        W = np.random.randn(fan_in, fan_out).astype(np.float32) * scale * np.sqrt(2.0 / fan_in)
        b = np.zeros((1, fan_out), dtype=np.float32)
        params.append((W, b))
    return params

def forward(params, X, activation="relu"):
    act_fn, _ = ACTIVATIONS[activation]
    caches = []
    h = X
    for i, (W, b) in enumerate(params):
        z = h @ W + b
        if i < len(params) - 1:  # hidden layers get activation
            caches.append((h, z))
            h = act_fn(z)
        else:  # output layer is linear
            caches.append((h, z))
            h = z
    return h, caches

def backward(params, caches, y_pred, y_true, activation="relu"):
    _, act_grad = ACTIVATIONS[activation]
    grads = []
    m = y_true.shape[0]
    # MSE gradient: d_loss/d_pred = 2/m * (pred - true)
    delta = (2.0 / m) * (y_pred - y_true)

    for i in reversed(range(len(params))):
        h_prev, z = caches[i]
        W, b = params[i]
        dW = h_prev.T @ delta
        db = delta.sum(axis=0, keepdims=True)
        grads.append((dW, db))
        if i > 0:
            delta = (delta @ W.T) * act_grad(caches[i - 1][1])

    grads.reverse()
    return grads

def mse(y_pred, y_true):
    return float(np.mean((y_pred - y_true) ** 2))

# ---------------------------------------------------------------------------
# Training function
# ---------------------------------------------------------------------------
def train(config, X_train, y_train, X_val, y_val, time_budget=2.0):
    """Train and return val_loss. Mirrors the fixed time-budget approach."""
    hidden_sizes = config["hidden_sizes"]
    lr = config["lr"]
    batch_size = config["batch_size"]
    max_steps = config["max_steps"]
    activation = config.get("activation", "relu")
    lr_decay = config.get("lr_decay", False)

    # Build layer dims
    layer_dims = []
    prev = X_train.shape[1]
    for h in hidden_sizes:
        layer_dims.append((prev, h))
        prev = h
    layer_dims.append((prev, 1))  # output

    params = init_weights(layer_dims)
    n = X_train.shape[0]
    start = time.time()

    for step in range(max_steps):
        if time.time() - start > time_budget:
            break

        # Current learning rate
        cur_lr = lr
        if lr_decay:
            cur_lr = lr * (1.0 - step / max_steps)

        # Mini-batch
        idx = np.random.randint(0, n, size=batch_size)
        xb, yb = X_train[idx], y_train[idx]

        # Forward + backward
        y_pred, caches = forward(params, xb, activation)
        grads = backward(params, caches, y_pred, yb, activation)

        # SGD update
        for j in range(len(params)):
            W, b = params[j]
            dW, db = grads[j]
            params[j] = (W - cur_lr * dW, b - cur_lr * db)

    # Validation
    y_val_pred, _ = forward(params, X_val, activation)
    val_loss = mse(y_val_pred, y_val)
    elapsed = time.time() - start
    return val_loss, elapsed

# ---------------------------------------------------------------------------
# Experiment definitions — one variable changed per experiment
# ---------------------------------------------------------------------------
BASELINE = {
    "hidden_sizes": [32],
    "lr": 0.01,
    "batch_size": 32,
    "max_steps": 200,
    "activation": "relu",
    "lr_decay": False,
}

EXPERIMENTS = [
    {
        "name": "double_hidden",
        "description": "double hidden size (32 -> 64)",
        "changes": {"hidden_sizes": [64]},
    },
    {
        "name": "halve_lr",
        "description": "halve learning rate (0.01 -> 0.005)",
        "changes": {"lr": 0.005},
    },
    {
        "name": "add_layer",
        "description": "add second hidden layer (32, 32)",
        "changes": {"hidden_sizes": [32, 32]},
    },
    {
        "name": "tanh_activation",
        "description": "switch activation relu -> tanh",
        "changes": {"activation": "tanh"},
    },
    {
        "name": "more_steps",
        "description": "increase training steps (200 -> 500)",
        "changes": {"max_steps": 500},
    },
    {
        "name": "bigger_batch",
        "description": "increase batch size (32 -> 128)",
        "changes": {"batch_size": 128},
    },
    {
        "name": "lr_decay",
        "description": "enable linear learning rate decay",
        "changes": {"lr_decay": True},
    },
    {
        "name": "wide_network",
        "description": "wide hidden layer (128 neurons)",
        "changes": {"hidden_sizes": [128]},
    },
    {
        "name": "deep_wide",
        "description": "two hidden layers of 64",
        "changes": {"hidden_sizes": [64, 64]},
    },
    {
        "name": "high_lr",
        "description": "increase learning rate (0.01 -> 0.03)",
        "changes": {"lr": 0.03},
    },
]

# ---------------------------------------------------------------------------
# AutoResearch Loop
# ---------------------------------------------------------------------------
def run():
    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.tsv")

    print("=" * 65)
    print("  AutoResearch Local Test Runner")
    print("  Pattern: Hypothesis -> Execute -> Measure -> Evaluate -> Decide")
    print("=" * 65)
    print()

    # --- Step 0: Baseline ---
    print("[baseline] Training with default config...")
    best_config = dict(BASELINE)
    best_loss, elapsed = train(best_config, X_train, y_train, X_val, y_val)
    baseline_loss = best_loss
    print(f"  val_loss: {best_loss:.6f}  ({elapsed:.2f}s)")
    print(f"  config:   {best_config}")
    print()

    results = []
    results.append({
        "experiment": "baseline",
        "val_loss": f"{best_loss:.6f}",
        "status": "keep",
        "description": f"2-layer MLP, lr={BASELINE['lr']}, hidden={BASELINE['hidden_sizes']}, steps={BASELINE['max_steps']}",
    })

    # --- Experiment Loop ---
    for i, exp in enumerate(EXPERIMENTS):
        exp_id = f"exp_{i + 1:03d}"
        print(f"[{exp_id}] Hypothesis: {exp['description']}")

        # Build config: apply single change on top of current best
        config = dict(best_config)
        config.update(exp["changes"])

        # Execute
        print(f"  Training...")
        try:
            val_loss, elapsed = train(config, X_train, y_train, X_val, y_val)
        except Exception as e:
            print(f"  CRASH: {e}")
            results.append({
                "experiment": exp_id,
                "val_loss": "0.000000",
                "status": "crash",
                "description": exp["description"],
            })
            continue

        # Evaluate
        improved = val_loss < best_loss
        delta = best_loss - val_loss
        status = "keep" if improved else "discard"
        marker = "<-- NEW BEST" if improved else ""

        print(f"  val_loss: {val_loss:.6f}  (delta: {delta:+.6f})  [{status}] {marker}")

        # Decide
        if improved:
            best_loss = val_loss
            best_config = config
            print(f"  Advancing: config updated.")
        else:
            print(f"  Reverting: keeping previous best.")

        results.append({
            "experiment": exp_id,
            "val_loss": f"{val_loss:.6f}",
            "status": status,
            "description": exp["description"],
        })
        print()

    # --- Write results.tsv ---
    with open(results_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["experiment", "val_loss", "status", "description"], delimiter="\t")
        writer.writeheader()
        writer.writerows(results)

    # --- Summary ---
    print("=" * 65)
    print("  RESULTS")
    print("=" * 65)
    print(f"  {'Experiment':<12} {'val_loss':<12} {'Status':<10} Description")
    print(f"  {'-'*12} {'-'*12} {'-'*10} {'-'*30}")
    for r in results:
        print(f"  {r['experiment']:<12} {r['val_loss']:<12} {r['status']:<10} {r['description']}")

    improvement = ((baseline_loss - best_loss) / baseline_loss) * 100
    print()
    print(f"  Baseline val_loss:  {baseline_loss:.6f}")
    print(f"  Best val_loss:      {best_loss:.6f}")
    print(f"  Improvement:        {improvement:.1f}%")
    print(f"  Best config:        {best_config}")
    print(f"  Results saved to:   {results_path}")
    print()
    kept = sum(1 for r in results if r["status"] == "keep") - 1  # exclude baseline
    print(f"  Experiments run: {len(EXPERIMENTS)}  |  Kept: {kept}  |  Discarded: {len(EXPERIMENTS) - kept}")
    print("=" * 65)

if __name__ == "__main__":
    run()
