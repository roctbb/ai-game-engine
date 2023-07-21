# AI-GAME-ENGINE
Some description

## Launch engine for product:
- create `config.py` and fill in as `config.py.example`
- execute `pip3 install flask`
- execute `flask db init`, `flask db migrate`, `flask db upgrade`
- execute `docker compose up`

## Launch engine for development:
- create `config.py` and fill in as `config.py.example`
- execute `pip install -r requirements.txt`
- execute `python -m build ge_sdk`
- execute `pip install .\ge_sdk\dist\ge_sdk-1.0.0-py3-none-any.whl`
- execute `flask db init`, `flask db migrate`, `flask db upgrade`
- execute `python server.py`