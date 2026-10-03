import os
import math
from abc import ABC, abstractmethod
from typing import List

class EmbeddingValidationError(Exception):
    """Domain specific exception raised when embedding provider returns malformed output."""
    pass

class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string and validate output."""
        result = self._embed_text(text)
        self._validate_embedding(result)
        return result

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of text strings and validate output."""
        results = self._embed_texts(texts)
        if len(results) != len(texts):
            raise EmbeddingValidationError(f"Expected {len(texts)} embeddings, got {len(results)}")
        for r in results:
            self._validate_embedding(r)
        return results

    def _validate_embedding(self, vector: List[float]):
        if not isinstance(vector, list):
            raise EmbeddingValidationError("Embedding must be a list of floats.")
        if len(vector) != self.dimensions:
            raise EmbeddingValidationError(f"Expected dimension {self.dimensions}, got {len(vector)}")
        for val in vector:
            if not isinstance(val, (float, int)):
                raise EmbeddingValidationError("Embedding coordinate must be numeric.")
            if math.isnan(val):
                raise EmbeddingValidationError("Embedding coordinate cannot be NaN.")
            if math.isinf(val):
                raise EmbeddingValidationError("Embedding coordinate cannot be infinity.")

    @abstractmethod
    def _embed_text(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the embedding model."""
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Dimensions of the embeddings produced."""
        pass


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic fake provider for testing and acceptance audit without a real model."""

    def __init__(self, dimensions: int = 384):
        self._dimensions = dimensions

    def _embed_text(self, text: str) -> List[float]:
        # Simple deterministic hashing mechanism mapping characters to float vectors
        v = [0.0] * self._dimensions
        for i, char in enumerate(text):
            v[i % self._dimensions] += (ord(char) / 128.0)
        # Normalize the vector to unit length
        norm = math.sqrt(sum(x * x for x in v))
        if norm > 0:
            v = [x / norm for x in v]
        return v

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_text(t) for t in texts]

    @property
    def model_name(self) -> str:
        return "fake-embedding-model-v1"

    @property
    def dimensions(self) -> int:
        return self._dimensions


class SentenceTransformerProvider(EmbeddingProvider):
    """Real sentence-transformer provider."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self._model_name = model_name
        # Lazy loading
        self._model = None
        self._dimensions = 384

    def _get_model(self):
        if self._model is None:
            # sentence_transformers can be slow to import, so we do it here
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def _embed_text(self, text: str) -> List[float]:
        model = self._get_model()
        return model.encode(text).tolist()

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        return model.encode(texts).tolist()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

def get_embedding_provider() -> EmbeddingProvider:
    """Dependency injection method to get standard provider."""
    # Using the fake in testing environments or if a specific ENV flag is set
    if os.getenv("TESTING") == "1" or os.getenv("USE_FAKE_EMBEDDING") == "1":
        return FakeEmbeddingProvider()
    from app.core.config import settings
    return SentenceTransformerProvider(model_name=settings.embedding_model)
