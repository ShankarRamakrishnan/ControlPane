# OpenWebUI — Manifest Manager

An OpenWebUI **Pipe** function that provides a GUI for creating, editing, and deleting ControlPane agent manifests directly from the OpenWebUI chat interface.

## How it works

- Select **Manifest Manager** from the model picker in OpenWebUI
- Send any message — the editor loads immediately
- The Pipe fetches the manifest list server-side on each load
- All CRUD operations (create, save, delete) call ControlPane directly from your browser via `fetch()`

## Setup

### 1. Install the function in OpenWebUI

Admin Panel → Functions → "+" → paste the contents of `manifest_manager.py` → Save

### 2. Configure the Valves

After saving, click the ⚙ icon next to the function and set:

| Valve | Value | Notes |
|---|---|---|
| `CONTROLPANE_URL` | `http://gateway:8000` | URL reachable from the **OpenWebUI server** (used for initial manifest load) |
| `CONTROLPANE_BROWSER_URL` | `http://localhost:8000` | URL reachable from your **browser** (used for CRUD operations) |

In a standard `docker-compose` setup:
- `CONTROLPANE_URL` = `http://gateway:8000` (Docker internal network)
- `CONTROLPANE_BROWSER_URL` = `http://localhost:8000` (exposed port on your machine)

For remote deployments, `CONTROLPANE_BROWSER_URL` should be the public hostname or IP of the gateway.

### 3. CORS

ControlPane's gateway already sets `allow_origins=["*"]`, so no additional CORS configuration is needed.

## Usage

| Action | How |
|---|---|
| View agents | Open the editor — all agents are listed on the left |
| Edit an agent | Click an agent name → edit fields → **Save Changes** |
| Create an agent | Click **+ New Agent** → fill form → **Create Agent** |
| Delete an agent | Select agent → **Delete** → confirm |

### Tools field format

Enter one tool per line as `name: description`:

```
web_search: Search the web for current information
calculator: Evaluate math expressions
```

Tool names must match tools registered in ControlPane's tool registry (`/tools/*.py`).
