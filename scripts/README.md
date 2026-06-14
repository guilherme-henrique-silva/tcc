# Scripts Directory

Esta pasta contém scripts utilitários isolados do projeto principal.

## test_docling_markdown_standalone.py

Script para testar a geração de markdown usando Docling a partir de uma URL.

### Pré-requisitos

O script requer que as dependências do backend estejam instaladas:

```bash
pip install -r backend/requirements.txt
```

### Uso

```bash
# Básico (usa URL padrão do ArXiv)
python scripts/test_docling_markdown_standalone.py

# Com URL customizada
python scripts/test_docling_markdown_standalone.py https://example.com/document.pdf

# Com saída em arquivo específico
python scripts/test_docling_markdown_standalone.py https://example.com/doc.pdf --output output.md

# Com output verbose (mostra primeiros 500 caracteres)
python scripts/test_docling_markdown_standalone.py https://example.com/doc.pdf --verbose

# Combinado
python scripts/test_docling_markdown_standalone.py https://example.com/doc.pdf --output my_doc.md --verbose
```

### Exemplos de URLs para testar

- **ArXiv Paper**: https://arxiv.org/pdf/2408.15169.pdf
- **Documentação PDF**: Qualquer PDF publicamente acessível

### Features

- ✅ Download e parsing de documentos de URL
- ✅ Conversão automática para markdown
- ✅ Logging com timestamp
- ✅ Auto-geração de nomes de arquivo (timestamp)
- ✅ Output customizável
- ✅ Modo verbose para debug
- ✅ Tratamento de erros informativo

### Output

O script:
1. Faz download do documento da URL
2. Parse usando Docling
3. Converte para markdown
4. Salva em arquivo (auto-nomeado ou customizado)
5. Exibe informações da conversão (formato detectado, tamanho, etc.)

### Troubleshooting

**ImportError: No module named 'docling'**

Instale as dependências do backend:
```bash
pip install -r backend/requirements.txt
```

**Connection errors**

Se receber erros de conexão ao tentar acessar a URL:
- Verifique sua conexão com a internet
- Tente uma URL diferente
- Verifique se a URL está acessível no navegador

## test_docling_markdown.py

Versão alternativa que requer um venv isolado. Use quando as dependências do backend não estiverem disponíveis.

### Setup

```bash
cd scripts
python -m venv venv
source venv/Scripts/activate  # Windows
# ou
source venv/bin/activate      # macOS/Linux
pip install -r requirements.txt
python test_docling_markdown.py
```
