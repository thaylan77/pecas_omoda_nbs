import oracledb
import pandas as pd
import os
import logging
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env (se existir)
load_dotenv()

# Configuração de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configurações do Banco Oracle por padrão
DB_USER = os.getenv("NBS_DB_USER", "nbs")
DB_PASSWORD = os.getenv("NBS_DB_PASSWORD", "new")
DB_DSN = os.getenv("NBS_DB_DSN", "10.2.2.14:1521/nbs")

# Inicialização única do Oracle client Thick
_thick_initialized = False

def inicializar_client_thick():
    global _thick_initialized
    if not _thick_initialized:
        try:
            oracledb.init_oracle_client()
            _thick_initialized = True
            logger.info("Modo Thick do oracledb inicializado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao inicializar o modo Thick do oracledb: {e}")
            raise e

def obter_conexao():
    inicializar_client_thick()
    try:
        connection = oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=DB_DSN
        )
        return connection
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {e}")
        raise e

def testar_conexao():
    try:
        conn = obter_conexao()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM dual")
        res = cursor.fetchone()
        cursor.close()
        conn.close()
        if res and res[0] == 1:
            return True
        return False
    except Exception as e:
        logger.error(f"Teste de conexão falhou: {e}")
        return False

def importar_pecas_lote(
    df: pd.DataFrame, 
    cod_empresa: int = 11, 
    cod_fornecedor: int = 17, 
    cod_fabricante: int = 21,
    cod_marca: int = 1,
    cod_grupo_interno: int = 90,
    cod_sub_grupo_interno: int = 1,
    cod_tributacao: str = "1",
    cod_classe_contabil: str = "5",
    cod_produto: int = 110303,
    cod_modelo: int = 116525
):
    """
    Executa a carga das peças na base NBS.
    Realiza o MERGE nas tabelas: ITENS, ITENS_FORNECEDOR, ESTOQUE, ITENS_CUSTOS, AGRUPADOS_PRODMOD_PECA.
    """
    conn = obter_conexao()
    cursor = conn.cursor()
    
    total_linhas = len(df)
    logger.info(f"Iniciando carga de {total_linhas} peças no banco...")
    
    # Preparando dados
    dados_itens = []
    dados_itens_fornecedor = []
    dados_estoque = []
    dados_custos = []
    dados_agrupados = []
    
    for _, row in df.iterrows():
        cod_item = row['COD_ITEM']
        descricao = row['DESCRICAO']
        class_fiscal = row['CLASS_FISCAL'] # NCM
        custo = row['CUSTO_NUM']
        preco_venda = row['PRECO_VENDA_NUM']
        garantia = row['GARANTIA_NUM']
        
        # 1. ITENS
        dados_itens.append((
            cod_item, descricao, class_fiscal, 
            cod_grupo_interno, cod_sub_grupo_interno, cod_tributacao, 
            cod_classe_contabil, "E", "UN", "N", "A", "N"
        ))
        
        # 2. ITENS_FORNECEDOR
        dados_itens_fornecedor.append((
            cod_item, cod_fornecedor, cod_fabricante, cod_marca,
            custo, custo, preco_venda, garantia, "S", "C", "E", "N", cod_classe_contabil, 0.0
        ))
        
        # 3. ESTOQUE
        dados_estoque.append((
            cod_item, cod_fornecedor, cod_empresa,
            0, 0, 0, custo
        ))
        
        # 4. ITENS_CUSTOS
        dados_custos.append((
            cod_item, cod_fornecedor, cod_empresa,
            custo, custo, preco_venda, garantia, "E", "S", cod_item
        ))
        
        # 5. AGRUPADOS_PRODMOD_PECA
        dados_agrupados.append((
            cod_produto, cod_modelo, cod_item, cod_fornecedor
        ))
        
    # SQLs de MERGE
    merge_itens = """
    MERGE INTO ITENS dest
    USING (
        SELECT :1 AS COD_ITEM, :2 AS DESCRICAO, :3 AS CLASS_FISCAL,
               :4 AS COD_GRUPO_INTERNO, :5 AS COD_SUB_GRUPO_INTERNO, :6 AS COD_TRIBUTACAO,
               :7 AS COD_CLASSE_CONTABIL, :8 AS TIPO_ITEM, :9 AS UNIDADE,
               :10 AS KIT, :11 AS STATUS, :12 AS COD_ORIGEM FROM dual
    ) src
    ON (dest.COD_ITEM = src.COD_ITEM)
    WHEN MATCHED THEN
        UPDATE SET dest.DESCRICAO = src.DESCRICAO,
                   dest.CLASS_FISCAL = src.CLASS_FISCAL,
                   dest.COD_GRUPO_INTERNO = src.COD_GRUPO_INTERNO,
                   dest.COD_SUB_GRUPO_INTERNO = src.COD_SUB_GRUPO_INTERNO,
                   dest.COD_TRIBUTACAO = src.COD_TRIBUTACAO,
                   dest.COD_CLASSE_CONTABIL = src.COD_CLASSE_CONTABIL,
                   dest.TIPO_ITEM = src.TIPO_ITEM,
                   dest.STATUS = src.STATUS
    WHEN NOT MATCHED THEN
        INSERT (COD_ITEM, DESCRICAO, CLASS_FISCAL, COD_GRUPO_INTERNO, COD_SUB_GRUPO_INTERNO, 
                COD_TRIBUTACAO, COD_CLASSE_CONTABIL, TIPO_ITEM, UNIDADE, KIT, STATUS, COD_ORIGEM)
        VALUES (src.COD_ITEM, src.DESCRICAO, src.CLASS_FISCAL, src.COD_GRUPO_INTERNO, src.COD_SUB_GRUPO_INTERNO,
                src.COD_TRIBUTACAO, src.COD_CLASSE_CONTABIL, src.TIPO_ITEM, src.UNIDADE, src.KIT, src.STATUS, src.COD_ORIGEM)
    """
    
    merge_itens_forn = """
    MERGE INTO ITENS_FORNECEDOR dest
    USING (
        SELECT :1 AS COD_ITEM, :2 AS COD_FORNECEDOR, :3 AS COD_FABRICANTE, :4 AS COD_MARCA,
               :5 AS CUSTO_FORNECEDOR, :6 AS CUSTO_CONTABIL, :7 AS PRECO_VENDA, :8 AS PRECO_GARANTIA,
               :9 AS GARANTIA, :10 AS COD_CURVA, :11 AS TIPO_ITEM, :12 AS COD_ORIGEM,
               :13 AS COD_CLASSE_CONTABIL, :14 AS DESCONTO_ESPECIFICO FROM dual
    ) src
    ON (dest.COD_ITEM = src.COD_ITEM AND dest.COD_FORNECEDOR = src.COD_FORNECEDOR)
    WHEN MATCHED THEN
        UPDATE SET dest.COD_FABRICANTE = src.COD_FABRICANTE,
                   dest.COD_MARCA = src.COD_MARCA,
                   dest.CUSTO_FORNECEDOR = src.CUSTO_FORNECEDOR,
                   dest.CUSTO_CONTABIL = src.CUSTO_CONTABIL,
                   dest.PRECO_VENDA = src.PRECO_VENDA,
                   dest.PRECO_GARANTIA = src.PRECO_GARANTIA,
                   dest.GARANTIA = src.GARANTIA,
                   dest.COD_CURVA = src.COD_CURVA,
                   dest.TIPO_ITEM = src.TIPO_ITEM,
                   dest.COD_CLASSE_CONTABIL = src.COD_CLASSE_CONTABIL
    WHEN NOT MATCHED THEN
        INSERT (COD_ITEM, COD_FORNECEDOR, COD_FABRICANTE, COD_MARCA, CUSTO_FORNECEDOR, CUSTO_CONTABIL, 
                PRECO_VENDA, PRECO_GARANTIA, GARANTIA, COD_CURVA, TIPO_ITEM, COD_ORIGEM, 
                COD_CLASSE_CONTABIL, DESCONTO_ESPECIFICO)
        VALUES (src.COD_ITEM, src.COD_FORNECEDOR, src.COD_FABRICANTE, src.COD_MARCA, src.CUSTO_FORNECEDOR, src.CUSTO_CONTABIL,
                src.PRECO_VENDA, src.PRECO_GARANTIA, src.GARANTIA, src.COD_CURVA, src.TIPO_ITEM, src.COD_ORIGEM,
                src.COD_CLASSE_CONTABIL, src.DESCONTO_ESPECIFICO)
    """
    
    merge_estoque = """
    MERGE INTO ESTOQUE dest
    USING (
        SELECT :1 AS COD_ITEM, :2 AS COD_FORNECEDOR, :3 AS COD_EMPRESA,
               :4 AS QTDE, :5 AS RESERVADO, :6 AS PENDENTE, :7 AS CUSTO_CONTABIL FROM dual
    ) src
    ON (dest.COD_ITEM = src.COD_ITEM AND dest.COD_FORNECEDOR = src.COD_FORNECEDOR AND dest.COD_EMPRESA = src.COD_EMPRESA)
    WHEN MATCHED THEN
        UPDATE SET dest.CUSTO_CONTABIL = src.CUSTO_CONTABIL
    WHEN NOT MATCHED THEN
        INSERT (COD_ITEM, COD_FORNECEDOR, COD_EMPRESA, QTDE, RESERVADO, PENDENTE, CUSTO_CONTABIL)
        VALUES (src.COD_ITEM, src.COD_FORNECEDOR, src.COD_EMPRESA, src.QTDE, src.RESERVADO, src.PENDENTE, src.CUSTO_CONTABIL)
    """
    
    merge_custos = """
    MERGE INTO ITENS_CUSTOS dest
    USING (
        SELECT :1 AS COD_ITEM, :2 AS COD_FORNECEDOR, :3 AS COD_EMPRESA,
               :4 AS CUSTO_FORNECEDOR, :5 AS CUSTO_CONTABIL, :6 AS PRECO_VENDA,
               :7 AS PRECO_GARANTIA, :8 AS TIPO_ITEM, :9 AS ATIVO,
               :10 AS COD_FISCAL_ITEM,
               SYSDATE AS DATA_INCLUSAO FROM dual
    ) src
    ON (dest.COD_ITEM = src.COD_ITEM AND dest.COD_FORNECEDOR = src.COD_FORNECEDOR AND dest.COD_EMPRESA = src.COD_EMPRESA)
    WHEN MATCHED THEN
        UPDATE SET dest.CUSTO_FORNECEDOR = src.CUSTO_FORNECEDOR,
                   dest.CUSTO_CONTABIL = src.CUSTO_CONTABIL,
                   dest.PRECO_VENDA = src.PRECO_VENDA,
                   dest.PRECO_GARANTIA = src.PRECO_GARANTIA,
                   dest.TIPO_ITEM = src.TIPO_ITEM,
                   dest.ATIVO = src.ATIVO
    WHEN NOT MATCHED THEN
        INSERT (COD_ITEM, COD_FORNECEDOR, COD_EMPRESA, CUSTO_FORNECEDOR, CUSTO_CONTABIL, 
                PRECO_VENDA, PRECO_GARANTIA, TIPO_ITEM, ATIVO, COD_FISCAL_ITEM, DATA_INCLUSAO)
        VALUES (src.COD_ITEM, src.COD_FORNECEDOR, src.COD_EMPRESA, src.CUSTO_FORNECEDOR, src.CUSTO_CONTABIL,
                src.PRECO_VENDA, src.PRECO_GARANTIA, src.TIPO_ITEM, src.ATIVO, src.COD_FISCAL_ITEM, src.DATA_INCLUSAO)
    """
    
    merge_agrupados = """
    MERGE INTO AGRUPADOS_PRODMOD_PECA dest
    USING (
        SELECT :1 AS COD_PRODUTO, :2 AS COD_MODELO, :3 AS COD_ITEM, :4 AS COD_FORNECEDOR FROM dual
    ) src
    ON (dest.COD_PRODUTO = src.COD_PRODUTO 
        AND dest.COD_MODELO = src.COD_MODELO 
        AND dest.COD_ITEM = src.COD_ITEM 
        AND dest.COD_FORNECEDOR = src.COD_FORNECEDOR)
    WHEN NOT MATCHED THEN
        INSERT (ID, COD_PRODUTO, COD_MODELO, COD_ITEM, COD_FORNECEDOR)
        VALUES (SEQ_AGRUPADO_PROD_MOD.NEXTVAL, src.COD_PRODUTO, src.COD_MODELO, src.COD_ITEM, src.COD_FORNECEDOR)
    """
    
    batch_size = 1000
    try:
        # Inserindo em blocos e confirmando a transação
        for i in range(0, len(dados_itens), batch_size):
            cursor.executemany(merge_itens, dados_itens[i:i+batch_size])
            cursor.executemany(merge_itens_forn, dados_itens_fornecedor[i:i+batch_size])
            cursor.executemany(merge_estoque, dados_estoque[i:i+batch_size])
            cursor.executemany(merge_custos, dados_custos[i:i+batch_size])
            cursor.executemany(merge_agrupados, dados_agrupados[i:i+batch_size])
            conn.commit()
            logger.info(f"Progresso de peças importadas: {min(i + batch_size, total_linhas)}/{total_linhas}")
            
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erro na transação de peças: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        raise e

def importar_servicos_lote(dados_atualizacao):
    """
    Executa o MERGE dos serviços na base NBS.
    """
    conn = obter_conexao()
    cursor = conn.cursor()
    
    total_linhas = len(dados_atualizacao)
    logger.info(f"Iniciando carga de {total_linhas} serviços no banco...")
    
    sql_merge_completar = """
    MERGE INTO SERVICOS dest
    USING (
        SELECT :1 AS COD_SERVICO, 
               :2 AS COD_FABRICANTE, 
               :3 AS UT, 
               :4 AS COD_GRUPO_SERV, 
               :5 AS COD_SUB_GRUPO_SERV,
               :6 AS COMO_COBRAR,
               :7 AS TERCEIROS,
               :8 AS LAVAGEM,
               :9 AS AUTORIZACAO,
               :10 AS LUBRIFICACAO,
               :11 AS RETEM_IRRF,
               :12 AS NAO_FORCAR_APONTAMENTO,
               :13 AS NAO_RETEM_PCC,
               :14 AS RETEM_INSS,
               :15 AS NAO_PERMITE_APONTAMENTO,
               :16 AS CALC_SERV_TEMP,
               :17 AS TROCA_OLEO,
               :18 AS NAO_USAR_DWP,
               :19 AS PODE_TER_REMESSA,
               :20 AS TERCEIRO_REMESSA
         FROM dual
    ) src
    ON (dest.COD_SERVICO = src.COD_SERVICO)
    WHEN MATCHED THEN
        UPDATE SET dest.COD_FABRICANTE = src.COD_FABRICANTE,
                   dest.UT = src.UT,
                   dest.COD_GRUPO_SERV = src.COD_GRUPO_SERV,
                   dest.COD_SUB_GRUPO_SERV = src.COD_SUB_GRUPO_SERV,
                   dest.COMO_COBRAR = src.COMO_COBRAR,
                   dest.TERCEIROS = src.TERCEIROS,
                   dest.LAVAGEM = src.LAVAGEM,
                   dest.AUTORIZACAO = src.AUTORIZACAO,
                   dest.LUBRIFICACAO = src.LUBRIFICACAO,
                   dest.RETEM_IRRF = src.RETEM_IRRF,
                   dest.NAO_FORCAR_APONTAMENTO = src.NAO_FORCAR_APONTAMENTO,
                   dest.NAO_RETEM_PCC = src.NAO_RETEM_PCC,
                   dest.RETEM_INSS = src.RETEM_INSS,
                   dest.NAO_PERMITE_APONTAMENTO = src.NAO_PERMITE_APONTAMENTO,
                   dest.CALC_SERV_TEMP = src.CALC_SERV_TEMP,
                   dest.TROCA_OLEO = src.TROCA_OLEO,
                   dest.NAO_USAR_DWP = src.NAO_USAR_DWP,
                   dest.PODE_TER_REMESSA = src.PODE_TER_REMESSA,
                   dest.TERCEIRO_REMESSA = src.TERCEIRO_REMESSA
    """
    
    batch_size = 1000
    try:
        for i in range(0, len(dados_atualizacao), batch_size):
            batch = dados_atualizacao[i:i+batch_size]
            cursor.executemany(sql_merge_completar, batch)
            conn.commit()
            logger.info(f"Progresso de serviços importados: {min(i + batch_size, total_linhas)}/{total_linhas}")
            
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erro na transação de serviços: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        raise e
