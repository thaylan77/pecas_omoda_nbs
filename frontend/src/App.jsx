import React, { useState, useEffect } from 'react';
import './App.css';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [activeTab, setActiveTab] = useState('pecas');
  const [dbStatus, setDbStatus] = useState('verificando');
  const [dbMessage, setDbMessage] = useState('');
  
  // Parâmetros de importação de peças
  const [params, setParams] = useState({
    cod_empresa: 11,
    cod_fornecedor: 17,
    cod_fabricante: 21,
    cod_marca: 1,
    cod_grupo_interno: 90,
    cod_sub_grupo_interno: 1,
    cod_tributacao: '1',
    cod_classe_contabil: '5',
    cod_produto: 110303,
    cod_modelo: 116525,
  });

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadState, setUploadState] = useState('idle'); // idle, uploading, success, error
  const [errorMessage, setErrorMessage] = useState('');
  const [importResult, setImportResult] = useState(null);

  // Verificar status do banco ao inicializar e a cada 10 segundos
  useEffect(() => {
    verificarDb();
    const interval = setInterval(verificarDb, 10000);
    return () => clearInterval(interval);
  }, []);

  const verificarDb = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/status-db`);
      const data = await res.json();
      if (data.status === 'online') {
        setDbStatus('online');
        setDbMessage('Oracle NBS Conectado');
      } else {
        setDbStatus('offline');
        setDbMessage('Banco Desconectado');
      }
    } catch (err) {
      setDbStatus('offline');
      setDbMessage('API Offline');
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setParams(prev => ({
      ...prev,
      [name]: name.startsWith('cod_') && name !== 'cod_tributacao' && name !== 'cod_classe_contabil'
        ? parseInt(value) || 0
        : value
    }));
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
        setSelectedFile(file);
        setUploadState('idle');
        setImportResult(null);
        setErrorMessage('');
      } else {
        setErrorMessage('Por favor, envie apenas arquivos do Excel (.xlsx ou .xls).');
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setUploadState('idle');
      setImportResult(null);
      setErrorMessage('');
    }
  };

  const removerArquivo = () => {
    setSelectedFile(null);
    setUploadState('idle');
    setImportResult(null);
    setErrorMessage('');
  };

  const formatarTamanho = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const processarPlanilha = async () => {
    if (!selectedFile) return;

    setUploadState('uploading');
    setErrorMessage('');
    setImportResult(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    // Se for aba de peças, adiciona todos os parâmetros de mapeamento
    if (activeTab === 'pecas') {
      Object.keys(params).forEach(key => {
        formData.append(key, params[key]);
      });
    }

    const endpoint = activeTab === 'pecas' ? '/api/upload-pecas' : '/api/upload-servicos';

    try {
      const res = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setUploadState('success');
        setImportResult(data);
        // Atualizar status do banco depois de uma carga
        verificarDb();
      } else {
        setUploadState('error');
        setErrorMessage(data.detail || 'Ocorreu um erro ao importar a planilha.');
      }
    } catch (err) {
      setUploadState('error');
      setErrorMessage('Erro de comunicação com o servidor backend local.');
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar de navegação */}
      <aside className="sidebar glass-panel">
        <div className="brand-section">
          <div className="brand-logo">NBS Integrator</div>
        </div>

        {/* Status da conexão com o Banco */}
        <div className="db-status-container">
          <div className="db-status-label">Status do ERP NBS</div>
          <div className="db-status-value">
            <span className={`status-dot ${
              dbStatus === 'online' ? 'pulse-glow-green' : 
              dbStatus === 'offline' ? 'pulse-glow-red' : ''
            }`} style={{
              backgroundColor: dbStatus === 'online' ? '#10b981' : dbStatus === 'offline' ? '#ef4444' : '#64748b'
            }} />
            <span style={{ color: dbStatus === 'online' ? '#34d399' : dbStatus === 'offline' ? '#fca5a5' : '#94a3b8' }}>
              {dbMessage || 'Verificando...'}
            </span>
          </div>
        </div>

        {/* Menu */}
        <nav className="nav-menu">
          <button 
            className={`nav-item ${activeTab === 'pecas' ? 'active' : ''}`}
            onClick={() => { setActiveTab('pecas'); removerArquivo(); }}
          >
            <span>📦</span> Peças (Omoda Jaecoo)
          </button>
          <button 
            className={`nav-item ${activeTab === 'servicos' ? 'active' : ''}`}
            onClick={() => { setActiveTab('servicos'); removerArquivo(); }}
          >
            <span>🔧</span> Serviços TMO
          </button>
        </nav>
      </aside>

      {/* Área de Conteúdo Principal */}
      <main className="main-content">
        <header className="content-header">
          <h1>
            {activeTab === 'pecas' ? 'Importador de Peças' : 'Importador de Serviços TMO'}
          </h1>
          <p>
            {activeTab === 'pecas'
              ? 'Tratamento de planilha Excel de peças, inversão de preço (PPS para Venda e Preço Venda OJ para Custo) e cadastro em lote no NBS.'
              : 'Tratamento de tempos operacionais, associação a grupos de modelos de veículos e cadastro na base de Serviços do NBS.'}
          </p>
        </header>

        {/* Parâmetros Parametrizáveis - Apenas para Peças */}
        {activeTab === 'pecas' && (
          <section className="params-section glass-panel glow-purple">
            <div className="params-header" onClick={() => setShowAdvanced(!showAdvanced)}>
              <h3>Configurações de Cadastro NBS</h3>
              <span style={{ fontSize: '0.8rem', color: '#a855f7', fontWeight: 600 }}>
                {showAdvanced ? 'Ocultar Opções ▲' : 'Configurações Avançadas ▼'}
              </span>
            </div>
            
            <div className="params-grid" style={{ display: showAdvanced ? 'grid' : 'none' }}>
              <div className="form-group">
                <label>Empresa</label>
                <input type="number" name="cod_empresa" value={params.cod_empresa} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>Fornecedor</label>
                <input type="number" name="cod_fornecedor" value={params.cod_fornecedor} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>Fabricante (Montadora)</label>
                <input type="number" name="cod_fabricante" value={params.cod_fabricante} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>Marca</label>
                <input type="number" name="cod_marca" value={params.cod_marca} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>Produto (Chery Omoda)</label>
                <input type="number" name="cod_produto" value={params.cod_produto} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>Modelo (Chery Omoda)</label>
                <input type="number" name="cod_modelo" value={params.cod_modelo} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>Cód. Grupo Interno</label>
                <input type="number" name="cod_grupo_interno" value={params.cod_grupo_interno} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>Cód. Subgrupo Interno</label>
                <input type="number" name="cod_sub_grupo_interno" value={params.cod_sub_grupo_interno} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>Cód. Tributação</label>
                <input type="text" name="cod_tributacao" value={params.cod_tributacao} onChange={handleInputChange} />
              </div>
              <div className="form-group">
                <label>Classe Contábil</label>
                <input type="text" name="cod_classe_contabil" value={params.cod_classe_contabil} onChange={handleInputChange} />
              </div>
            </div>
            
            {!showAdvanced && (
              <div style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                Concessionária: <strong>Empresa 11 (Socel)</strong> | Fornecedor: <strong>17 (Omoda)</strong> | Fabricante: <strong>21</strong> | Catálogo: <strong>{params.cod_produto} - {params.cod_modelo}</strong>
              </div>
            )}
          </section>
        )}

        {/* Zona de Upload */}
        <section className="upload-wrapper">
          {errorMessage && (
            <div className="alert-box error">
              <span>⚠️</span>
              <div>{errorMessage}</div>
            </div>
          )}

          {!selectedFile ? (
            <div 
              className={`dropzone glass-panel ${dragActive ? 'drag-active' : ''}`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <div className="dropzone-icon">📥</div>
              <div className="dropzone-text">Arraste a planilha do Excel aqui</div>
              <div className="dropzone-subtext">ou clique para procurar em seu computador (apenas .xlsx ou .xls)</div>
              <input 
                type="file" 
                id="file-upload-input" 
                style={{ display: 'none' }} 
                accept=".xlsx, .xls"
                onChange={handleFileChange} 
              />
              <button 
                className="btn-primary" 
                style={{ marginTop: '1.25rem', padding: '0.5rem 1.25rem', fontSize: '0.85rem' }}
                onClick={() => document.getElementById('file-upload-input').click()}
              >
                Selecionar Arquivo
              </button>
            </div>
          ) : (
            <div className="file-selected-panel glass-panel glow-blue">
              <div className="file-info">
                <span style={{ fontSize: '1.75rem' }}>📄</span>
                <div>
                  <div className="file-name">{selectedFile.name}</div>
                  <div className="file-size">{formatarTamanho(selectedFile.size)}</div>
                </div>
              </div>
              <button className="btn-remove" onClick={removerArquivo}>Remover</button>
            </div>
          )}

          {selectedFile && uploadState !== 'success' && (
            <div className="actions-bar">
              <button 
                className="btn-primary" 
                onClick={processarPlanilha}
                disabled={uploadState === 'uploading'}
              >
                {uploadState === 'uploading' ? 'Processando...' : 'Iniciar Importação no Banco'}
              </button>
            </div>
          )}
        </section>

        {/* Indicador de processamento (scan line) */}
        {uploadState === 'uploading' && (
          <div className="glass-panel" style={{ padding: '3rem', position: 'relative', overflow: 'hidden', textAlign: 'center' }}>
            <div className="scan-line"></div>
            <div className="spinner" style={{ margin: '0 auto 1rem auto' }}></div>
            <h3 style={{ color: '#e2e8f0' }}>Processando e Gravando Dados...</h3>
            <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: '0.5rem' }}>
              Este processo pode levar alguns segundos devido ao número de registros e às transações de validação no Oracle.
            </p>
          </div>
        )}

        {/* Resultados e Pré-visualização da Importação */}
        {uploadState === 'success' && importResult && (
          <section className="results-panel glass-panel glow-emerald animate-fade-in">
            <div className="results-header">
              <div>
                <h3 style={{ fontSize: '1.25rem', color: '#f8fafc', fontWeight: 700 }}>Importação Concluída com Sucesso!</h3>
                <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: '0.25rem' }}>Planilha processada e comitada na base NBS.</p>
              </div>
              <span className="status-badge success">Concluído</span>
            </div>

            <div className="stats-grid">
              <div className="stat-card glass-card">
                <div className="stat-value">{importResult.total_linhas_excel}</div>
                <div className="stat-label">Linhas no Excel</div>
              </div>
              <div className="stat-card glass-card">
                <div className="stat-value" style={{ color: '#34d399' }}>{importResult.total_processados}</div>
                <div className="stat-label">Registros Gravados/Atualizados</div>
              </div>
              <div className="stat-card glass-card">
                <div className="stat-value" style={{ color: '#60a5fa' }}>{activeTab === 'pecas' ? '5 tabelas' : '1 tabela'}</div>
                <div className="stat-label">Tabelas Alimentadas</div>
              </div>
            </div>

            {/* Preview Grid */}
            {importResult.previa && importResult.previa.length > 0 && (
              <div>
                <h4 style={{ color: '#e2e8f0', marginBottom: '0.75rem', fontSize: '0.95rem', fontWeight: 600 }}>
                  Amostra dos Dados Importados (Primeiros 20 itens)
                </h4>
                <div className="preview-table-container glass-card">
                  <table className="preview-table">
                    <thead>
                      {activeTab === 'pecas' ? (
                        <tr>
                          <th>Código da Peça</th>
                          <th>Descrição</th>
                          <th>NCM</th>
                          <th>Preço de Custo (OJ Venda)</th>
                          <th>Preço de Venda (PPS)</th>
                          <th>Garantia</th>
                        </tr>
                      ) : (
                        <tr>
                          <th>Código Serviço</th>
                          <th>Código Fabricante</th>
                          <th>Tempo Operação (UT)</th>
                          <th>Grupo</th>
                          <th>Subgrupo</th>
                        </tr>
                      )}
                    </thead>
                    <tbody>
                      {activeTab === 'pecas' ? (
                        importResult.previa.map((item, idx) => (
                          <tr key={idx}>
                            <td style={{ fontWeight: 'bold', color: '#c084fc' }}>{item.COD_ITEM}</td>
                            <td>{item.DESCRICAO}</td>
                            <td>{item.CLASS_FISCAL || 'N/A'}</td>
                            <td style={{ color: '#34d399' }}>
                              {item.CUSTO_NUM ? `R$ ${item.CUSTO_NUM.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : 'R$ 0,00'}
                            </td>
                            <td style={{ color: '#60a5fa' }}>
                              {item.PRECO_VENDA_NUM ? `R$ ${item.PRECO_VENDA_NUM.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : 'R$ 0,00'}
                            </td>
                            <td>{item.GARANTIA_NUM ? `${item.GARANTIA_NUM} meses` : 'N/A'}</td>
                          </tr>
                        ))
                      ) : (
                        importResult.previa.map((item, idx) => (
                          <tr key={idx}>
                            <td style={{ fontWeight: 'bold', color: '#c084fc' }}>{item.COD_SERVICO}</td>
                            <td>{item.COD_FABRICANTE_VAL}</td>
                            <td style={{ color: '#34d399', fontWeight: 600 }}>{item.UT_VAL} UT</td>
                            <td>{item.COD_GRUPO_SERV || 'N/A'}</td>
                            <td>{item.COD_SUB_GRUPO_SERV || 'N/A'}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
