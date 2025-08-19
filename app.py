import os
import json
import requests
from flask import Flask, request, Response
from dotenv import load_dotenv
from nlp_processor import processar_mensagem
from datetime import datetime # Importa o módulo de data e hora

# Carrega as variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# Suas credenciais da Meta
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

# --- Banco de Dados Simulado ---
database = {}

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verificação do Webhook da Meta
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        else:
            return 'Verification token mismatch', 403
    
    if request.method == 'POST':
        data = request.get_json()
        
        if data and data.get('entry') and data['entry'][0].get('changes') and data['entry'][0]['changes'][0].get('value') and data['entry'][0]['changes'][0]['value'].get('messages'):
            message_data = data['entry'][0]['changes'][0]['value']['messages'][0]
            from_number = message_data['from']
            msg_body = message_data['text']['body']
            
            print(f"Mensagem de {from_number}: {msg_body}")

            # 1. Processa a mensagem com IA
            resultado_nlp = processar_mensagem(msg_body)
            intencao = resultado_nlp['intencao']
            entidades = resultado_nlp['entidades']

            # 2. Lógica de negócio
            if from_number not in database:
                database[from_number] = {"transacoes": [], "saldo": 0.0}

            resposta_texto = ""
            
            # --- LÓGICA ATUALIZADA COM NOVAS FUNÇÕES ---

            if intencao == "adicionar_despesa":
                valor = entidades.get('valor', 0)
                if valor > 0:
                    categoria = entidades.get('categoria', 'Geral')
                    # ADICIONA A DATA E HORA ATUAL À TRANSAÇÃO
                    transacao = {"tipo": "despesa", "valor": valor, "categoria": categoria, "data": datetime.now()}
                    database[from_number]['transacoes'].append(transacao)
                    database[from_number]['saldo'] -= valor
                    resposta_texto = f"✅ Despesa de R$ {valor:.2f} na categoria '{categoria}' registrada. Seu novo saldo é R$ {database[from_number]['saldo']:.2f}."
                else:
                    resposta_texto = "🤔 Não consegui identificar o valor da despesa. Tente algo como 'gastei 50 com café'."

            elif intencao == "adicionar_receita":
                valor = entidades.get('valor', 0)
                if valor > 0:
                    categoria = entidades.get('categoria', 'Receitas')
                    # ADICIONA A DATA E HORA ATUAL À TRANSAÇÃO
                    transacao = {"tipo": "receita", "valor": valor, "categoria": categoria, "data": datetime.now()}
                    database[from_number]['transacoes'].append(transacao)
                    database[from_number]['saldo'] += valor
                    resposta_texto = f"✅ Receita de R$ {valor:.2f} na categoria '{categoria}' registrada. Seu novo saldo é R$ {database[from_number]['saldo']:.2f}."
                else:
                    resposta_texto = "🤔 Não consegui identificar o valor da receita. Tente algo como 'recebi 500 de um trabalho'."

            elif intencao == "ver_saldo":
                saldo_atual = database[from_number]['saldo']
                resposta_texto = f"💰 Seu saldo atual é de R$ {saldo_atual:.2f}."

            # --- NOVA FUNÇÃO: LISTAR DESPESAS ---
            elif intencao == "listar_despesas":
                despesas = [t for t in database[from_number]['transacoes'] if t['tipo'] == 'despesa']
                if not despesas:
                    resposta_texto = "Você ainda não registrou nenhuma despesa."
                else:
                    resposta_texto = "🧾 *Suas últimas despesas:*\n"
                    # Mostra as últimas 10 para não poluir o chat
                    for t in reversed(despesas[-10:]):
                        resposta_texto += f"- R$ {t['valor']:.2f} em {t['categoria']} ({t['data'].strftime('%d/%m')})\n"

            # --- NOVA FUNÇÃO: LISTAR RECEITAS ---
            elif intencao == "listar_receitas":
                receitas = [t for t in database[from_number]['transacoes'] if t['tipo'] == 'receita']
                if not receitas:
                    resposta_texto = "Você ainda não registrou nenhuma receita."
                else:
                    resposta_texto = "📈 *Suas últimas receitas:*\n"
                    # Mostra as últimas 10
                    for t in reversed(receitas[-10:]):
                        resposta_texto += f"- R$ {t['valor']:.2f} em {t['categoria']} ({t['data'].strftime('%d/%m')})\n"
            
            # --- NOVA FUNÇÃO: RELATÓRIO MENSAL ---
            elif intencao == "relatorio_mensal":
                hoje = datetime.now()
                transacoes_mes = [t for t in database[from_number]['transacoes'] if t['data'].month == hoje.month and t['data'].year == hoje.year]
                
                if not transacoes_mes:
                    resposta_texto = f"Você não tem nenhuma transação registrada em {hoje.strftime('%B')}."
                else:
                    total_receitas = sum(t['valor'] for t in transacoes_mes if t['tipo'] == 'receita')
                    total_despesas = sum(t['valor'] for t in transacoes_mes if t['tipo'] == 'despesa')
                    balanco = total_receitas - total_despesas
                    
                    resposta_texto = f"📊 *Resumo de {hoje.strftime('%B/%Y')}:*\n\n"
                    resposta_texto += f"🟢 *Receitas:* R$ {total_receitas:.2f}\n"
                    resposta_texto += f"🔴 *Despesas:* R$ {total_despesas:.2f}\n"
                    resposta_texto += f"--------------------\n"
                    resposta_texto += f"⚖️ *Balanço:* R$ {balanco:.2f}"

            else:
                resposta_texto = (
                    "🤖 Olá! Sou seu assistente financeiro. O que você gostaria de fazer?\n\n"
                    "Você pode tentar:\n"
                    "- `Gastei 50 com almoço`\n"
                    "- `Recebi 1000 de salário`\n"
                    "- `Qual meu saldo?`\n"
                    "- `Listar minhas despesas`\n"
                    "- `Relatório mensal`"
                )

            # 3. Envia a resposta de volta para o usuário
            enviar_mensagem_whatsapp(from_number, resposta_texto)
            print("Banco de dados simulado:", database)

        return Response(status=200)

    return 'Método não permitido', 405


def enviar_mensagem_whatsapp(to_number, text):
    """
    Função para enviar a mensagem usando a API da Meta
    """
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
    print("Resposta da API da Meta:", response.status_code, response.json())
    return response

if __name__ == '__main__':
    app.run(port=5000, debug=True)