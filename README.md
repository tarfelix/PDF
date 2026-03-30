# Editor de PDF — Soares, Picon

Aplicação web para manipulação avançada de PDFs jurídicos.

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Zustand |
| Backend | FastAPI, Python 3.12, PyMuPDF |
| Deploy | Docker multi-stage, Coolify |

## Ferramentas

- **Smart Scan Jurídico** — identifica peças processuais (sentenças, decisões, recursos) via bookmarks e regex
- **Numeração Bates** — padrão configurável, posição e fonte ajustáveis
- **Redação/Tarja** — keywords + regex (CPF, CNPJ, email, datas)
- **Editor Visual** — thumbnails interativos, seleção, rotação, extração
- **Mesclar, Dividir, Extrair, Remover, Rotacionar, Otimizar**
- **Conversor** — imagens (JPG/PNG/TIFF) para PDF
- **Diff** — comparação textual entre dois PDFs

## Desenvolvimento local

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend (em outro terminal)
cd frontend
npm install
npm run dev
```

O frontend roda em `http://localhost:5173` e faz proxy de `/api` para o backend em `:8000`.

## Deploy (Coolify)

```bash
# Build e teste local
docker compose build
docker compose up

# Produção: usar docker-compose.coolify.yml no Coolify
```

## Variáveis de ambiente

Veja `.env.example`:

```
CORS_ORIGINS=*
TEMP_FILE_TTL_MINUTES=30
MAX_UPLOAD_SIZE_MB=200
```
