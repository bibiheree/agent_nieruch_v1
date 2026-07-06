FROM python:3.12-slim

# Kopiowanie binarnego narzędzia uv z oficjalnego obrazu dla ultra-szybkiej instalacji
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Kopiowanie definicji projektu
COPY pyproject.toml ./

# Usunięto flagę --frozen, aby uv mogło wygenerować lockfile automatycznie podczas budowy
RUN uv sync --no-install-project

# Kopiowanie kodu źródłowego serwera
COPY src ./src
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1

# Uruchomienie serwera za pomocą uv
CMD ["uv", "run", "src/my_mcp/server.py"]