import spacy
import re

# Carrega o modelo de linguagem em português
nlp = spacy.load("pt_core_news_lg")

def processar_mensagem(texto):
    """
    Analisa a mensagem do usuário para extrair a intenção e as entidades.
    """
    doc = nlp(texto.lower())
    intencao = "intencao_desconhecida" # Define um padrão

    # --- NOVAS PALAVRAS-CHAVE PARA AS NOVAS FUNÇÕES ---
    palavras_despesa = ["gastar", "comprar", "pagar", "despesa"]
    palavras_receita = ["receber", "ganhar", "salário", "receita", "pix", "depósito"]
    palavras_saldo = ["saldo", "ver", "mostrar", "quanto"]
    palavras_listar_despesas = ["listar despesas", "minhas despesas", "meus gastos", "ver gastos"]
    palavras_listar_receitas = ["listar receitas", "minhas receitas", "meus ganhos", "ver receitas"]
    palavras_relatorio = ["relatório", "resumo", "mensal", "gastos do mês"]

    # --- LÓGICA DE INTENÇÃO ATUALIZADA ---
    # Verifica frases inteiras primeiro para maior precisão
    if any(frase in texto.lower() for frase in palavras_listar_despesas):
        intencao = "listar_despesas"
    elif any(frase in texto.lower() for frase in palavras_listar_receitas):
        intencao = "listar_receitas"
    # Se não for uma frase específica, verifica por palavras-chave
    elif any(token.lemma_ in palavras_relatorio for token in doc):
        intencao = "relatorio_mensal"
    elif any(token.lemma_ in palavras_despesa for token in doc):
        intencao = "adicionar_despesa"
    elif any(token.lemma_ in palavras_receita for token in doc):
        intencao = "adicionar_receita"
    elif any(token.lemma_ in palavras_saldo for token in doc):
        intencao = "ver_saldo"

    # --- EXTRAÇÃO DE ENTIDADES (VALOR E CATEGORIA) ---
    entidades = {}
    
    # Extrai valor monetário
    valor_encontrado = re.search(r'(\d+[\.,]?\d*)', texto)
    if valor_encontrado:
        valor_str = valor_encontrado.group(1).replace(',', '.')
        entidades['valor'] = float(valor_str)

    # Extrai categoria (o que vem depois de preposições como "com", "em", "para")
    preposicoes = ["com", "em", "para", "no", "na", "de"]
    for i, token in enumerate(doc):
        if token.text in preposicoes:
            # Tenta pegar o próximo token como categoria, se for um substantivo
            if i + 1 < len(doc) and doc[i+1].pos_ in ["NOUN", "PROPN"]:
                 entidades['categoria'] = doc[i+1].text
                 break
    
    # Define uma categoria padrão se nenhuma for encontrada
    if 'valor' in entidades and 'categoria' not in entidades:
        if intencao == "adicionar_despesa":
            entidades['categoria'] = 'Geral'
        elif intencao == "adicionar_receita":
            entidades['categoria'] = 'Receitas'

    return {"intencao": intencao, "entidades": entidades}
