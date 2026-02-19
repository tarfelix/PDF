import fitz  # PyMuPDF

# --- Constantes Visuais ---
DEFAULT_BRAND = {
    "name": "Soares, Picon Sociedade de Advogados",
    "primary": "#0F3D73",
    "secondary": "#1E5AA7",
    "accent": "#2E7DFF",
    "bg_light": "#E9F2FB",
    "bg_dark": "#0B0F14",
    "text_dark": "#0B0F14",
    "text_light": "#F8FAFC",
    "logo_url": "",  
    "subtitle": "Mais de 50 anos de atuação na advocacia consultiva e contenciosa",
}

# --- Constantes do Sistema ---
VISUAL_PREVIEW_SIZE_LIMIT_MB = 50

# Fallbacks de encriptação/permissões (PyMuPDF)
ENCRYPT_AES_256 = getattr(fitz, "ENCRYPT_AES_256", getattr(fitz, "PDF_ENCRYPT_AES_256", 0))
PERM_PRINT      = getattr(fitz, "PERM_PRINT",      getattr(fitz, "PDF_PERM_PRINT",      0))
PERM_COPY       = getattr(fitz, "PERM_COPY",       getattr(fitz, "PDF_PERM_COPY",       0))
PERM_ANNOTATE   = getattr(fitz, "PERM_ANNOTATE",   getattr(fitz, "PDF_PERM_ANNOTATE",   0))

# --- Palavras-chave Jurídicas ---
LEGAL_KEYWORDS = {
    "Petição Inicial": ['petição inicial', 'inicial'],
    "Defesa/Contestação": ['defesa', 'contestação', 'contestacao'],
    "Réplica": ['réplica', 'replica', 'impugnação à contestação', 'impugnacao a contestacao'],
    "Sentença": ['sentença', 'sentenca'],
    "Acórdão": ['acórdão', 'acordao'],
    "Decisão": ['decisão', 'decisao', 'decisão interlocutória', 'decisao interlocutoria'],
    "Despacho": ['despacho'],
    "Recurso": ['recurso', 'agravo', 'embargos', 'apelação', 'apelacao'],
    "Ata de Audiência": ['ata de audiência', 'ata de audiencia', 'termo de audiência', 'termo de audiencia'],
    "Laudo": ['laudo', 'parecer técnico', 'parecer tecnico'],
    "Manifestação/Petição": ['manifestação', 'manifestacao', 'petição', 'peticao', 'requerimento'],
    "Documento": ['documento'],
    "Capa": ['capa'],
    "Índice/Sumário": ['índice', 'indice', 'sumário', 'sumario'],
}

# Regex para scan de conteúdo (mais específico que keywords simples)
# Procura por cabeçalhos em caixa alta ou início de parágrafos
LEGAL_REGEX_PATTERNS = {
    "Petição Inicial": [r"(?i)^excelent[íi]ssimo", r"(?i)^peti[çc][ãa]o\s+inicial"],
    "Sentença": [r"(?i)^senten[çc][ãa]", r"(?i)^vistos,\s+etc", r"(?i)^s\s+e\s+n\s+t\s+e\s+n\s+[çc]\s+a"],
    "Acórdão": [r"(?i)^ac[óo]rd[ãa]o", r"(?i)^voto"],
    "Decisão": [r"(?i)^decis[ãa]o", r"(?i)^vistos"],
    "Contestação": [r"(?i)^contesta[çc][ãa]o"],
    "Recurso": [r"(?i)^raz[õo]es\s+de\s+apela[çc][ãa]o", r"(?i)^agravo\s+de\s+instrumento", r"(?i)^embargos\s+de\s+declara[çc][ãa]o"],
    "Laudo Pericial": [r"(?i)^laudo\s+pericial", r"(?i)^parecer\s+t[ée]cnico"],
}

PRE_SELECTED = [
    "Petição Inicial", "Sentença", "Acórdão", "Decisão", "Despacho",
    "Defesa/Contestação", "Réplica", "Recurso", "Ata de Audiência", "Laudo", "Manifestação/Petição"
]
