from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
import os
import logging
from database_helper import testar_conexao, importar_pecas_lote, importar_servicos_lote

# Configuração de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API Importador NBS - Omoda Jaecoo",
    description="Backend para tratamento e importação de Peças e Serviços TMO para o banco de dados ERP NBS.",
    version="1.0.0"
)

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Na VPS local, permite qualquer origem
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constantes de tratamento de Peças
def tratar_codigo_item(codigo):
    if pd.isna(codigo):
        return None
    return str(codigo).strip().upper()

def tratar_descricao(desc):
    if pd.isna(desc):
        return "PECA SEM DESCRICAO"
    desc_str = str(desc).strip().upper()
    if len(desc_str) > 100:
        desc_str = desc_str[:100]
    return desc_str

def tratar_ncm(ncm):
    if pd.isna(ncm):
        return None
    try:
        num_str = "".join([c for c in str(ncm) if c.isdigit()])
        if num_str:
            return int(num_str)
        return None
    except:
        return None

def tratar_float(val):
    if pd.isna(val):
        return 0.0
    try:
        # Lida com representação em formato brasileiro (ex: 1.250,50 ou string com R$)
        if isinstance(val, str):
            val = val.replace("R$", "").replace(" ", "")
            if "," in val and "." in val:
                val = val.replace(".", "").replace(",", ".")
            elif "," in val:
                val = val.replace(",", ".")
        return float(val)
    except:
        return 0.0

# Constantes e prefixos para Serviços TMO
prefixos_servicos = ["T19CEV", "T1EJPH", "T19CH", "T1GCPH", "T1EJP", "T19C", "T1EJ", "T1GC", "CHE", "T1PJ"]

def tratar_codigo_servico(codigo):
    cod = str(codigo).strip().upper()
    for pref in prefixos_servicos:
        if cod.startswith(pref):
            cod = cod[len(pref):]
            break
    if len(cod) > 15:
        cod = cod[-15:]
    return cod

mapeamento_grupos = {
    'T19C EV': (215, 786),     # Omoda E5 BEV
    'T19C HEV': (216, 787),    # Omoda 5 HEV
    'T1EJ PHEV': (217, 788),   # Jaecoo 7 PHEV
    'T1GC PHEV': (218, 789)    # Omoda 7 PHEV
}

def obter_grupo_subgrupo(cod_veiculo):
    veic = str(cod_veiculo).strip()
    return mapeamento_grupos.get(veic, (None, None))

def tratar_ut(tempo):
    try:
        return int(float(tempo))
    except:
        return 0

@app.get("/api/status-db")
def status_db():
    """
    Rota para testar a conexão com o banco de dados Oracle do NBS.
    """
    conectado = testar_conexao()
    if conectado:
        return {
            "status": "online",
            "message": "Conexão com o banco Oracle NBS ativa!",
            "database_dsn": os.getenv("NBS_DB_DSN", "10.2.2.14:1521/nbs")
        }
    else:
        return {
            "status": "offline",
            "message": "Não foi possível conectar ao banco de dados Oracle NBS.",
            "database_dsn": os.getenv("NBS_DB_DSN", "10.2.2.14:1521/nbs")
        }

@app.post("/api/upload-pecas")
async def upload_pecas(
    file: UploadFile = File(...),
    cod_empresa: int = Form(11),
    cod_fornecedor: int = Form(17),
    cod_fabricante: int = Form(21),
    cod_marca: int = Form(1),
    cod_grupo_interno: int = Form(90),
    cod_sub_grupo_interno: int = Form(1),
    cod_tributacao: str = Form("1"),
    cod_classe_contabil: str = Form("5"),
    cod_produto: int = Form(110303),
    cod_modelo: int = Form(116525)
):
    """
    Recebe um arquivo Excel de Peças, executa a validação, inversão de preços (PPS -> Venda e Venda OJ -> Custo)
    e efetua a carga no banco.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Formato de arquivo inválido. Apenas .xlsx ou .xls são permitidos."
        )
        
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        logger.info(f"Recebido arquivo de Peças: {file.filename} com {len(df)} linhas.")
        
        # Validação de colunas obrigatórias
        colunas_esperadas = ["CÓDIGO DA PEÇA", "DESCRIÇÃO", "PPS", "PREÇO VENDA OJ"]
        for col in colunas_esperadas:
            if col not in df.columns:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Coluna obrigatória não localizada: '{col}'. Verifique a planilha."
                )
                
        # NCM e GARANTIA são opcionais
        if "NCM" not in df.columns:
            df["NCM"] = None
        if "GARANTIA" not in df.columns:
            df["GARANTIA"] = 0
            
        # Tratamento de dados
        df['COD_ITEM'] = df['CÓDIGO DA PEÇA'].apply(tratar_codigo_item)
        df['DESCRICAO'] = df['DESCRIÇÃO'].apply(tratar_descricao)
        df['CLASS_FISCAL'] = df['NCM'].apply(tratar_ncm)
        
        # Mapeamento e inversão de preços:
        # PRECO_VENDA_NUM = PPS (Preço Público Sugerido)
        # CUSTO_NUM = PREÇO VENDA OJ (Custo real para a concessionária)
        df['PRECO_VENDA_NUM'] = df['PPS'].apply(tratar_float)
        df['CUSTO_NUM'] = df['PREÇO VENDA OJ'].apply(tratar_float)
        df['GARANTIA_NUM'] = df['GARANTIA'].apply(tratar_float)
        
        # Filtrar códigos inválidos/nulos
        df = df.dropna(subset=['COD_ITEM'])
        df = df[df['COD_ITEM'] != '']
        
        # Remover duplicatas mantendo o maior preço
        df_sorted = df.sort_values(by='PRECO_VENDA_NUM', ascending=False)
        df_unicos = df_sorted.drop_duplicates(subset=['COD_ITEM'], keep='first')
        
        total_unicas = len(df_unicos)
        if total_unicas == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nenhum item válido identificado no arquivo Excel."
            )
            
        # Prévia para o frontend (primeiros 20 itens)
        previa_itens = df_unicos.head(20)[['COD_ITEM', 'DESCRICAO', 'CLASS_FISCAL', 'CUSTO_NUM', 'PRECO_VENDA_NUM', 'GARANTIA_NUM']].to_dict(orient='records')
        
        # Importar em lote no banco
        importar_pecas_lote(
            df_unicos,
            cod_empresa=cod_empresa,
            cod_fornecedor=cod_fornecedor,
            cod_fabricante=cod_fabricante,
            cod_marca=cod_marca,
            cod_grupo_interno=cod_grupo_interno,
            cod_sub_grupo_interno=cod_sub_grupo_interno,
            cod_tributacao=cod_tributacao,
            cod_classe_contabil=cod_classe_contabil,
            cod_produto=cod_produto,
            cod_modelo=cod_modelo
        )
        
        return {
            "success": True,
            "filename": file.filename,
            "total_linhas_excel": len(df),
            "total_processados": total_unicas,
            "previa": previa_itens
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erro ao processar importação de Peças: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro no processamento do arquivo: {str(e)}"
        )

@app.post("/api/upload-servicos")
async def upload_servicos(
    file: UploadFile = File(...)
):
    """
    Recebe um arquivo Excel de Serviços TMO (Tabela de tempos operacionais da montadora),
    trata chaves, categoriza por veículo/grupo e faz a gravação em lote.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Formato de arquivo inválido. Apenas .xlsx ou .xls são permitidos."
        )
        
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        logger.info(f"Recebido arquivo de Serviços: {file.filename} com {len(df)} linhas.")
        
        # Validação de colunas obrigatórias
        colunas_esperadas = ["Código da Operação", "Tempo Operação", "Código do Veículo"]
        for col in colunas_esperadas:
            if col not in df.columns:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Coluna obrigatória não localizada: '{col}'. Verifique a planilha."
                )
                
        # Tratamento de dados
        df['COD_SERVICO'] = df['Código da Operação'].apply(tratar_codigo_servico)
        df['COD_FABRICANTE_VAL'] = df['Código da Operação'].astype(str).str.strip().str.upper()
        df['UT_VAL'] = df['Tempo Operação'].apply(tratar_ut)
        
        # Adicionar grupo e subgrupo
        df['GRUPO_SUBGRUPO'] = df['Código do Veículo'].apply(obter_grupo_subgrupo)
        df['COD_GRUPO_SERV'] = df['GRUPO_SUBGRUPO'].apply(lambda x: x[0])
        df['COD_SUB_GRUPO_SERV'] = df['GRUPO_SUBGRUPO'].apply(lambda x: x[1])
        
        # Remover duplicadas pelo COD_SERVICO
        df_unicos = df.drop_duplicates(subset=['COD_SERVICO'], keep='first')
        
        total_unicos = len(df_unicos)
        if total_unicos == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nenhum serviço válido identificado no arquivo Excel."
            )
            
        # Preparando dados para gravação em lote
        dados_atualizacao = []
        for _, row in df_unicos.iterrows():
            dados_atualizacao.append((
                row['COD_SERVICO'],
                row['COD_FABRICANTE_VAL'],
                row['UT_VAL'],
                row['COD_GRUPO_SERV'],
                row['COD_SUB_GRUPO_SERV'],
                'T',  # COMO_COBRAR (T = Tempo)
                'N',  # TERCEIROS
                'N',  # LAVAGEM
                'N',  # AUTORIZACAO
                'N',  # LUBRIFICACAO
                'N',  # RETEM_IRRF
                'N',  # NAO_FORCAR_APONTAMENTO
                'N',  # NAO_RETEM_PCC
                'N',  # RETEM_INSS
                'N',  # NAO_PERMITE_APONTAMENTO
                'N',  # CALC_SERV_TEMP
                'N',  # TROCA_OLEO
                'N',  # NAO_USAR_DWP
                'N',  # PODE_TER_REMESSA
                'N'   # TERCEIRO_REMESSA
            ))
            
        previa_servicos = df_unicos.head(20)[['COD_SERVICO', 'COD_FABRICANTE_VAL', 'UT_VAL', 'COD_GRUPO_SERV', 'COD_SUB_GRUPO_SERV']].to_dict(orient='records')
        
        # Importar em lote
        importar_servicos_lote(dados_atualizacao)
        
        return {
            "success": True,
            "filename": file.filename,
            "total_linhas_excel": len(df),
            "total_processados": total_unicos,
            "previa": previa_servicos
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Erro ao processar importação de Serviços: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro no processamento do arquivo: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    # Rodar o app localmente na porta 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
