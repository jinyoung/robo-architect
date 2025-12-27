# Event Storming Navigator - VS Code Extension

AI-powered Event Storming and DDD modeling tool for VS Code.

## Features

- **Sidebar Navigation**: Browse Bounded Contexts, Aggregates, Commands, Events, and Policies
- **Visual Canvas**: Interactive Event Storming canvas using Vue Flow
- **AI Chat**: Natural language modifications to your domain model
- **PRD Generation**: Generate project specifications directly to your workspace

## Installation

### From VSIX (Local)

1. Build the extension:
   ```bash
   cd vscode-extension
   npm install
   npm run build
   npm run package
   ```

2. Install the generated `.vsix` file:
   - Open VS Code
   - Go to Extensions view (Ctrl+Shift+X)
   - Click "..." menu → "Install from VSIX..."
   - Select the generated `.vsix` file

### From Marketplace (Coming Soon)

Search for "Event Storming Navigator" in VS Code Extensions.

## Development

### Prerequisites

- Node.js 18+
- Python 3.10+
- Neo4j (for the backend)

### Setup

1. Install dependencies:
   ```bash
   npm install
   cd webview && npm install && cd ..
   cd server && pip install -r requirements.txt && cd ..
   ```

2. Start development:
   ```bash
   # Option 1: Use the dev script (starts all servers)
   ./scripts/dev.sh
   
   # Option 2: Manual
   # Terminal 1: Watch extension
   npm run watch
   
   # Terminal 2: Watch webview
   cd webview && npm run dev
   
   # Terminal 3: Run backend
   cd server && python -m uvicorn api.main:app --reload
   ```

3. Test in VS Code:
   - Open `vscode-extension` folder in VS Code
   - Press `F5` to launch Extension Development Host
   - The extension will appear in the Activity Bar

## Architecture

```
vscode-extension/
├── src/                      # Extension TypeScript source
│   ├── extension.ts          # Entry point
│   ├── sidebarProvider.ts    # Sidebar webview provider
│   ├── canvasEditorProvider.ts # Full canvas panel
│   ├── serverManager.ts      # Python backend lifecycle
│   └── utils.ts              # Utilities
├── webview/                  # Vue.js webview app
│   ├── src/
│   │   ├── components/       # Vue components
│   │   ├── stores/           # Pinia stores
│   │   └── utils/vscode.js   # VS Code bridge
│   └── vite.config.ts        # Webview build config
├── server/                   # Python FastAPI backend
│   ├── api/                  # API routes
│   └── agent/                # LangGraph agent
└── .vscode/                  # VS Code debug configs
```

## Configuration

Open VS Code Settings and search for "Event Storming":

| Setting | Default | Description |
|---------|---------|-------------|
| `eventStorming.pythonPath` | (auto-detect) | Path to Python executable |
| `eventStorming.serverPort` | 8000 | Port for the backend server |
| `eventStorming.autoStartServer` | true | Auto-start backend on activation |

## Commands

| Command | Description |
|---------|-------------|
| `Event Storming: Open Canvas` | Open the full Event Storming canvas |
| `Event Storming: Start Server` | Start the backend server |
| `Event Storming: Stop Server` | Stop the backend server |

## Differences from Web Version

| Feature | Web Version | VS Code Extension |
|---------|-------------|-------------------|
| PRD Output | ZIP download | Files created in workspace |
| Backend | Separate server | Auto-managed by extension |
| Navigation | Browser tabs | VS Code sidebar |
| File Access | None | Full workspace access |

## Troubleshooting

### Backend server fails to start

1. Check if Python is installed: `python3 --version`
2. Configure Python path in settings
3. Check the "Event Storming Server" output channel

### Webview shows blank

1. Check the Developer Tools (Help → Toggle Developer Tools)
2. Look for errors in the Console tab
3. Ensure the build completed: `npm run build`

## License

MIT

