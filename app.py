import os
import json
import requests
from flask import Flask, request, Response
from dotenv import load_dotenv
from datetime import datetime
from collections import defaultdict # Usado para facilitar a soma no relatório

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)

# Suas credenciais
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Rota para manter o servidor do Render acordado
@app.route('/')
def home():
    return "Servidor do Bot Financeiro está ativo.", 200

# --- Banco de Dados Simulado e Controle de Mensagens ---
database = {}
processed_message_ids = set()

# --- FUNÇÃO ATUALIZADA: IA com instruções aprimoradas ---
def get_ai_interpretation(user_message):
    """
    Envia a mensagem do usuário para a API do Gemini e retorna uma interpretação estruturada.
    """
    if not GEMINI_API_KEY:
        print("ERRO CRÍTICO: A variável GEMINI_API_KEY não foi encontrada.")
        return {"intent": "api_error", "error": "API Key not configured"}

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"

    # PROMPT MELHORADO: Instruímos a IA a extrair a categoria específica da fala do usuário.
    prompt = f"""
    Aja como um assistente financeiro. Analise a mensagem do usuário e extraia a intenção e as entidades em formato JSON.

    - A 'intent' pode ser: 'add_expense', 'add_income', 'check_balance', 'list_expenses', 'list_incomes', 'monthly_report', ou 'unclear'.
    - A entidade 'value' é o valor numérico da transação.
    - A entidade 'category' é o item ou motivo específico da transação, extraído diretamente da fala do usuário. NÃO use palavras genéricas como 'despesa' ou 'receita' como categoria, a menos que seja a única opção.

    Exemplos:
    - Mensagem: "Gastei 500 reais com plantas" -> category: "plantas"
    - Mensagem: "recebi 1000 do meu salário" -> category: "salário"
    - Mensagem: "pagamento do aluguel 1500" -> category: "aluguel"
    - Mensagem: "entrou um pix" -> category: "pix" (se não houver mais detalhes)

    Mensagem do usuário a ser analisada: "{user_message}"
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "intent": {"type": "STRING"},
                    "entities": {
                        "type": "OBJECT",
                        "properties": {
                            "value": {"type": "NUMBER"},
                            "category": {"type": "STRING"}
                        }
                    }
                }
            }
        }
    }
    headers = {'Content-Type': 'application/json'}

    try:
        print("Enviando requisição para a API do Gemini...")
        response = requests.post(api_url, headers=headers, json=payload, timeout=25)
        response.raise_for_status()

        result = response.json()
        json_text = result['candidates'][0]['content']['parts'][0]['text']
        print(f"Resposta JSON da IA recebida: {json_text}")
        return json.loads(json_text)

    except requests.exceptions.HTTPError as http_err:
        print(f"ERRO HTTP ao chamar a API do Gemini: {http_err}")
        print(f"Resposta do Servidor: {response.text}")
        return {"intent": "api_error", "error": "HTTP Error"}
        
    except requests.exceptions.RequestException as e:
        print(f"ERRO de Conexão ao chamar a API do Gemini: {e}")
        return {"intent": "api_error", "error": "Connection Error"}
        
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"ERRO ao processar a resposta da IA: {e}")
        print(f"Resposta bruta recebida: {result if 'result' in locals() else 'N/A'}")
        return {"intent": "api_error", "error": "Parsing Error"}


@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        else:
            return 'Verification token mismatch', 403
    
    if request.method == 'POST':
        data = request.get_json()
        
        if data and data.get('entry') and data['entry'][0].get('changes') and data['entry'][0]['changes'][0].get('value') and data['entry'][0]['changes'][0]['value'].get('messages'):
            message_data = data['entry'][0]['changes'][0]['value']['messages'][0]
            message_id = message_data.get('id')
            
            if message_id in processed_message_ids:
                return Response(status=200)
            
            processed_message_ids.add(message_id)

            from_number = message_data['from']
            msg_body = message_data['text']['body']
            
            print(f"\n--- Nova Mensagem de {from_number}: {msg_body} ---")

            ai_response = get_ai_interpretation(msg_body)
            intencao = ai_response.get('intent', 'unclear')
            entidades = ai_response.get('entities', {})

            if from_number not in database:
                database[from_number] = {"transacoes": [], "saldo": 0.0}

            resposta_texto = ""
            
            if intencao == "add_expense":
                valor = entidades.get('value', 0)
                if valor > 0:
                    # A IA agora nos dá a categoria específica!
                    categoria = entidades.get('category', 'Geral').lower()
                    transacao = {"tipo": "despesa", "valor": valor, "categoria": categoria, "data": datetime.now()}
                    database[from_number]['transacoes'].append(transacao)
                    database[from_number]['saldo'] -= valor
                    resposta_texto = f"✅ Despesa de R$ {valor:.2f} em '{categoria}' registrada. Saldo: R$ {database[from_number]['saldo']:.2f}."
                else:
                    resposta_texto = "🤔 Não consegui identificar o valor da despesa."

            elif intencao == "add_income":
                valor = entidades.get('value', 0)
                if valor > 0:
                    categoria = entidades.get('category', 'Receitas').lower()
                    transacao = {"tipo": "receita", "valor": valor, "categoria": categoria, "data": datetime.now()}
                    database[from_number]['transacoes'].append(transacao)
                    database[from_number]['saldo'] += valor
                    resposta_texto = f"✅ Receita de R$ {valor:.2f} em '{categoria}' registrada. Saldo: R$ {database[from_number]['saldo']:.2f}."
                else:
                    resposta_texto = "🤔 Não consegui identificar o valor da receita."

            elif intencao == "check_balance":
                saldo_atual = database[from_number]['saldo']
                resposta_texto = f"💰 Seu saldo atual é de R$ {saldo_atual:.2f}."

            elif intencao == "list_expenses":
                despesas = [t for t in database[from_number]['transacoes'] if t['tipo'] == 'despesa']
                if not despesas:
                    resposta_texto = "Você ainda não registrou nenhuma despesa."
                else:
                    resposta_texto = "🧾 *Suas últimas despesas:*\n"
                    for t in reversed(despesas[-10:]):
                        resposta_texto += f"- R$ {t['valor']:.2f} em {t['categoria']} ({t['data'].strftime('%d/%m')})\n"

            elif intencao == "list_incomes":
                receitas = [t for t in database[from_number]['transacoes'] if t['tipo'] == 'receita']
                if not receitas:
                    resposta_texto = "Você ainda não registrou nenhuma receita."
                else:
                    resposta_texto = "📈 *Suas últimas receitas:*\n"
                    for t in reversed(receitas[-10:]):
                        resposta_texto += f"- R$ {t['valor']:.2f} em {t['categoria']} ({t['data'].strftime('%d/%m')})\n"
            
            # --- RELATÓRIO MENSAL APRIMORADO ---
            elif intencao == "monthly_report":
                hoje = datetime.now()
                transacoes_mes = [t for t in database[from_number]['transacoes'] if t['data'].month == hoje.month and t['data'].year == hoje.year]
                
                if not transacoes_mes:
                    resposta_texto = f"Você não tem transações em {hoje.strftime('%B')}."
                else:
                    despesas_por_categoria = defaultdict(float)
                    receitas_por_categoria = defaultdict(float)

                    for t in transacoes_mes:
                        if t['tipo'] == 'despesa':
                            despesas_por_categoria[t['categoria']] += t['valor']
                        elif t['tipo'] == 'receita':
                            receitas_por_categoria[t['categoria']] += t['valor']

                    total_receitas = sum(receitas_por_categoria.values())
                    total_despesas = sum(despesas_por_categoria.values())
                    balanco = total_receitas - total_despesas

                    resposta_texto = f"📊 *Resumo Detalhado de {hoje.strftime('%B/%Y')}:*\n\n"

                    if receitas_por_categoria:
                        resposta_texto += "🟢 *Receitas:*\n"
                        for categoria, valor in sorted(receitas_por_categoria.items(), key=lambda item: item[1], reverse=True):
                            resposta_texto += f"  - {categoria.capitalize()}: R$ {valor:.2f}\n"
                        resposta_texto += f"  *Total de Receitas:* R$ {total_receitas:.2f}\n\n"
                    
                    if despesas_por_categoria:
                        resposta_texto += "🔴 *Despesas:*\n"
                        for categoria, valor in sorted(despesas_por_categoria.items(), key=lambda item: item[1], reverse=True):
                            resposta_texto += f"  - {categoria.capitalize()}: R$ {valor:.2f}\n"
                        resposta_texto += f"  *Total de Despesas:* R$ {total_despesas:.2f}\n\n"

                    resposta_texto += f"--------------------\n"
                    resposta_texto += f"⚖️ *Balanço do Mês:* R$ {balanco:.2f}"

            else:
                resposta_texto = (
                    "🤖 Desculpe, não entendi. Como posso ajudar?\n\n"
                    "Tente algo como:\n"
                    "- `Comprei pão por 10 reais`\n"
                    "- `Recebi um pix de 500`\n"
                    "- `relatório mensal`"
                )

            enviar_mensagem_whatsapp(from_number, resposta_texto)
            print("Banco de dados simulado:", database)

        return Response(status=200)

    return 'Método não permitido', 405

def enviar_mensagem_whatsapp(to_number, text):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "text": {"body": text}
    }
    response = requests.post(url, headers=headers, json=data)
    print("Resposta da API da Meta:", response.status_code)
    return response
if __name__ == '__main__':
    app.run()