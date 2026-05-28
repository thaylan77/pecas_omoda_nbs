# Importador NBS - Omoda Jaecoo 📦🔧

Aplicação web local de intranet projetada para automatizar o processo de validação, tratamento e importação de planilhas Excel de peças de reposição e tempos de serviço padrão (TMO) diretamente para o banco de dados Oracle do ERP NBS.

---

## 🚀 Funcionalidades

1. **Indicador de Banco em Tempo Real**: Status dinâmico da conexão ativa com o banco Oracle do ERP NBS (`10.2.2.14/nbs`).
2. **Importação e Correção de Preços (Peças)**:
   - Upload de planilhas com tratamento automático de NCM, descrições e códigos.
   - Aplicação da inversão de preços comerciais:
     - **Preço de Venda** = `PPS` (Preço Público Sugerido)
     - **Preço de Custo** = `PREÇO VENDA OJ` (Custo de reposição para a concessionária)
   - Atualização transacional em lote (MERGE) de 1.000 itens por vez nas tabelas: `ITENS`, `ITENS_FORNECEDOR`, `ESTOQUE`, `ITENS_CUSTOS` e `AGRUPADOS_PRODMOD_PECA`.
   - Parametrização avançada na tela de upload (Empresa, Fornecedor, Fabricante, Marca, Produto, Modelo).
3. **Importação e Enriquecimento de Serviços TMO**:
   - Tratamento e limpeza de códigos da montadora excedentes de 15 caracteres (limitação física do campo no ERP).
   - Associação de tempos ao respectivo modelo de veículo (`T19C EV`, `T19C HEV`, `T1EJ PHEV`, `T1GC PHEV`) por meio de grupos e subgrupos parametrizados no NBS (215 a 218).
   - Armazenamento do código completo original no campo `COD_FABRICANTE` para fins de auditoria e garantia.
   - Preenchimento automático das flags comportamentais do ERP.

---

## 📁 Estrutura do Projeto

```text
importador_nbs/
├── backend/            # API REST em FastAPI (Python)
│   ├── main.py         # Arquivo de rotas e processamento das planilhas
│   ├── database_helper.py # Módulo de conexão e transações no Oracle (Modo Thick)
│   └── requirements.txt # Dependências Python
├── frontend/           # Interface do Usuário em React (Vite)
│   ├── src/            # Componentes React e estilos personalizados
│   └── package.json    # Dependências Node.js
├── README.md           # Este arquivo de documentação
└── run_servers.ps1     # Script de inicialização em lote para a VPS local
```

---

## 🛠️ Pré-requisitos

Para rodar a aplicação localmente na VPS ou rede interna, são necessários:

1. **Python 3.10+** instalado na máquina.
2. **Oracle Instant Client** instalado e configurado no sistema operacional (necessário para o funcionamento do driver no modo `Thick` devido a conexões corporativas criptografadas).
3. **Node.js 18+** e npm configurados.

---

## ⚙️ Instalação e Inicialização Rápida

### 1. Servidores Simultâneos (Recomendado no Windows)

Para maior facilidade no ambiente de VPS local, você pode iniciar o frontend e o backend simultaneamente com um único script PowerShell:

1. Abra o terminal na raiz da pasta `importador_nbs/`.
2. Execute o seguinte comando:
   ```powershell
   .\run_servers.ps1
   ```
   *O script irá abrir duas janelas separadas do PowerShell, uma rodando o backend na porta `8000` e outra rodando o frontend Vite.*

3. Acesse a aplicação no navegador em: **[http://localhost:5173](http://localhost:5173)**.

---

### 2. Inicialização Manual

Se preferir rodar os serviços individualmente ou estiver em ambiente sem suporte a scripts:

#### Backend:
1. Navegue até a pasta do backend:
   ```bash
   cd backend
   ```
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Inicialize a API com o Uvicorn:
   ```bash
   python -m uvicorn main:app --reload --port 8000
   ```
   *A documentação Swagger estará disponível interativamente em [http://localhost:8000/docs](http://localhost:8000/docs).*

#### Frontend:
1. Navegue até a pasta do frontend:
   ```bash
   cd ../frontend
   ```
2. Instale as dependências Node:
   ```bash
   npm install
   ```
3. Inicie o servidor de desenvolvimento Vite:
   ```bash
   npm run dev
   ```

---

## 🌐 Configurações de Ambiente (Banco de Dados)

Por padrão, a conexão está apontada para a base oficial local do NBS em `10.2.2.14:1521/nbs`. Caso precise alterar o destino do banco, defina as seguintes variáveis de ambiente no sistema operacional da VPS antes de executar o backend:

- `NBS_DB_USER` (padrão: `nbs`)
- `NBS_DB_PASSWORD` (padrão: `new`)
- `NBS_DB_DSN` (padrão: `10.2.2.14:1521/nbs`)
