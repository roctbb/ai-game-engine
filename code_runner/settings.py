import pydantic_settings

class Settings(pydantic_settings.BaseSettings):
    rmq_username: str
    rmq_password: str
    rmq_hostname: str
    rmq_port: int

    pyston_hostname: str
