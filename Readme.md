# AI Game Engine

A powerful platform for creating and running AI-driven games where players compete using custom scripts. The engine
supports multiple games, real-time gameplay visualization, and comprehensive statistics tracking.

## Features

- Multi-game support with customizable game logic
- Real-time game visualization using WebSocket communication
- Player script execution in isolated environments
- Team-based gameplay mechanics
- Live statistics and replay functionality
- Lobby system for game session management
- Redis-based event messaging system
- Docker containerization for easy deployment

## Tech Stack

- Python Flask backend with SocketIO
- Redis for real-time messaging
- PostgreSQL database
- Docker and Docker Compose
- JavaScript frontend SDK

## Quick Start

### Production Deployment

1. Create `config.py` based on `config.py.example`
2. Run for production:

```bash
# Production deployment
docker compose up -d
```

- or for development:

```bash
# Development setup
docker compose -f compose-dev.yml build
python setup.py 
python server.py
```

## Architecture

- Game sessions run in isolated processes
- Real-time updates via Redis pub/sub
- Secure script execution environment
- Modular game implementation system
- Team and player management
- Session replay capabilities

## Project Structure

- `/blueprints` - Flask route handlers
- `/games` - Game implementations
- `/models` - Database models
- `/ge_sdk` - Game Engine SDK
- `/static` - Frontend assets
- `/redis_client` - Redis communication layer

## License

TODO: Add license information