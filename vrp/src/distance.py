import numpy as np

DIST_MATRIX_THRESHOLD = 5000


def compute_distance_matrix(coords: np.ndarray, use_integer: bool) -> np.ndarray:
    """Compute full pairwise Euclidean distance matrix."""
    diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
    dist = np.sqrt(np.sum(diff ** 2, axis=2))
    if use_integer:
        dist = np.floor(dist + 0.5)
    np.fill_diagonal(dist, 0.0)
    return dist
