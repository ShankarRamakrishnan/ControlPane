from fastapi import APIRouter, HTTPException, Request, status
from gateway.models.manifest import AgentManifest

router = APIRouter(prefix="/manifests", tags=["manifests"])


@router.get("", response_model=list[AgentManifest])
def list_manifests(request: Request):
    loader = request.app.state.manifest_loader
    return list(loader.all().values())


@router.get("/{name}", response_model=AgentManifest)
def get_manifest(name: str, request: Request):
    loader = request.app.state.manifest_loader
    manifest = loader.get(name)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Manifest '{name}' not found")
    return manifest


@router.post("", response_model=AgentManifest, status_code=status.HTTP_201_CREATED)
def create_manifest(manifest: AgentManifest, request: Request):
    loader = request.app.state.manifest_loader
    if loader.get(manifest.name):
        raise HTTPException(status_code=409, detail=f"Manifest '{manifest.name}' already exists")
    loader.save(manifest)
    return manifest


@router.put("/{name}", response_model=AgentManifest)
def update_manifest(name: str, manifest: AgentManifest, request: Request):
    loader = request.app.state.manifest_loader
    if not loader.get(name):
        raise HTTPException(status_code=404, detail=f"Manifest '{name}' not found")
    if manifest.name != name:
        raise HTTPException(status_code=422, detail="Manifest name in body must match URL parameter")
    loader.save(manifest)
    request.app.state.runtime_registry._invalidate_name(name)
    return manifest


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_manifest(name: str, request: Request):
    loader = request.app.state.manifest_loader
    if not loader.get(name):
        raise HTTPException(status_code=404, detail=f"Manifest '{name}' not found")
    loader.delete(name)
    request.app.state.runtime_registry._invalidate_name(name)
