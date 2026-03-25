import os
import yaml
import logging
from pathlib import Path
from gateway.models.manifest import AgentManifest

logger = logging.getLogger(__name__)


class ManifestLoader:
    """Loads and validates agent manifests from a directory of YAML files."""

    def __init__(self, manifests_dir: str):
        self.manifests_dir = Path(manifests_dir)
        self._registry: dict[str, AgentManifest] = {}
        self._mtimes: dict[str, float] = {}

    def load_all(self) -> dict[str, AgentManifest]:
        """Scan manifests directory and load all YAML files."""
        if not self.manifests_dir.exists():
            logger.warning(f"Manifests directory not found: {self.manifests_dir}")
            return {}

        for yaml_file in self.manifests_dir.glob("*.yaml"):
            self._load_file(yaml_file)

        logger.info(f"Loaded {len(self._registry)} agent manifest(s): {list(self._registry.keys())}")
        return self._registry

    def _load_file(self, path: Path) -> AgentManifest | None:
        try:
            mtime = path.stat().st_mtime
            if path.stem in self._mtimes and self._mtimes[path.stem] == mtime:
                return self._registry.get(path.stem)

            with open(path) as f:
                raw = yaml.safe_load(f)

            if isinstance(raw, dict) and raw.get("kind") == "platform":
                logger.debug(f"Skipping platform manifest: {path.name}")
                return None

            manifest = AgentManifest.model_validate(raw)
            self._registry[manifest.name] = manifest
            self._mtimes[manifest.name] = mtime
            logger.info(f"Loaded manifest: {manifest.name} v{manifest.version}")
            return manifest

        except Exception as e:
            logger.error(f"Failed to load manifest {path}: {e}")
            return None

    def get(self, name: str) -> AgentManifest | None:
        """Return manifest by agent name, reloading if file changed."""
        path = self.manifests_dir / f"{name}.yaml"
        if path.exists():
            return self._load_file(path)
        return self._registry.get(name)

    def get_mtime(self, name: str) -> float:
        """Return the last-seen mtime for a manifest, or 0.0 if unknown."""
        return self._mtimes.get(name, 0.0)

    def all(self) -> dict[str, AgentManifest]:
        self.load_all()
        return self._registry

    def save(self, manifest: AgentManifest) -> None:
        """Write a manifest to disk as YAML and update the in-memory registry."""
        path = self.manifests_dir / f"{manifest.name}.yaml"
        data = manifest.model_dump(by_alias=True, exclude_none=True)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        self._registry[manifest.name] = manifest
        self._mtimes[manifest.name] = path.stat().st_mtime
        logger.info(f"Saved manifest: {manifest.name}")

    def delete(self, name: str) -> None:
        """Remove a manifest from disk and the in-memory registry."""
        path = self.manifests_dir / f"{name}.yaml"
        if path.exists():
            os.remove(path)
        self._registry.pop(name, None)
        self._mtimes.pop(name, None)
        logger.info(f"Deleted manifest: {name}")
