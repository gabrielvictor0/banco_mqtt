from datetime import datetime, timezone
from flask import Flask, Response, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import json
import paho.mqtt.client as mqtt

import google.generativeai as genai

import smtplib 
import email.message

genai.configure(api_key="AIzaSyDoMqR5BvRd_ppu3tjjOvL9kTa1VyyXYgA")


# CONEXÃO COM O BANCO DE DADOS

app = Flask('registro')
# A conexão com banco haverá modificações na base de dados
app.config['SQLALCHEMY_TACK_MODIFICATIONS'] = False
# Configura a URI de conexão com o banco de dados MYSQL.
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:senai%40134@127.0.0.1/bd_medidor'
# Cria uma instância do SQLAlchemy, passando a aplicação Flask como parâmetro.
mybd = SQLAlchemy(app)


# CONEXÃO COM OS SENSORES

mqtt_dados = {}

def conexao_sensor(cliente, userdata, flags, rc):
    cliente.subscribe('projeto_integrado/SENAI134/Cienciadedados/GrupoX')


def msg_sensor(client, userdata, msg):
    global mqtt_dados
    # Decodificar a mensagem recebida de bytes para string
    valor = msg.payload.decode('utf-8')
    # Decodificar de string para JSON
    mqtt_dados = json.loads(valor)

    print(f'Mensagem Recebida: {mqtt_dados}')


    # Correlação Banco de Dados com Sensores
    with app.app_context():
        try:
            temperatura = mqtt_dados.get('temperature')
            pressao = mqtt_dados.get('pressure')
            altitude = mqtt_dados.get('altitude')
            umidade = mqtt_dados.get('humidity')
            co2 = mqtt_dados.get('co2')
            poeira  = 0
            tempo_registro = mqtt_dados.get('timestamp')
        
            if tempo_registro is None:
                print('Timestamp não encontrado')
                return
            
            try:
                tempo_oficial = datetime.fromtimestamp(int
                (tempo_registro), tz=timezone.utc)


            except Exception as ex:
                print(f'Erro ao converter timestamp: {str(ex)}')
                return
            
            #Criar o objeto que vai simular a tabela do banco

            novos_dados = Registro(
                temperatura = temperatura,
                pressao = pressao,
                altitude = altitude,
                umidade = umidade,
                co2 = co2,
                poeira = poeira,
                tempo_registro = tempo_oficial
            )

            # Adicionar novo registro ao banco
            mybd.session.add(novos_dados)
            mybd.session.commit()
            print('Dados foram inseridos com sucesso no banco de dados!')
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content("Faça um aviso sobre a temperetura atual para que a população possa se proteger de altas temperaturas. Resuma isto em 3 linhas")

            enviar_email(response.text)
        

        except Exception as e:
            print(f'Erro ao processar os dados do MQTT {str(e)}')
            mybd.session.rollback()


mqtt_client = mqtt.Client()
mqtt_client.on_connect = conexao_sensor
mqtt_client.on_message = msg_sensor
mqtt_client.connect('test.mosquitto.org', 1883, 60)

def start_mqtt():
    mqtt_client.loop_start()

class Registro(mybd.Model):
    __tablename__ = 'tb_registro'
    id = mybd.Column(mybd.Integer, primary_key=True, autoincrement=True)
    temperatura = mybd.Column(mybd.Numeric(10, 2))
    pressao = mybd.Column(mybd.Numeric(10, 2))
    altitude = mybd.Column(mybd.Numeric(10, 2))
    umidade = mybd.Column(mybd.Numeric(10, 2))
    co2 = mybd.Column(mybd.Numeric(10, 2))
    poeira = mybd.Column(mybd.Numeric(10, 2))
    tempo_registro = mybd.Column(mybd.DateTime)
    
def enviar_email(txt):
    corpo_email =  f""" {txt}"""
    msg = email.message.Message()
    msg['Subject'] = "Assunto"
    msg['From'] = 'otaldoclaitonrasta@gmail.com'
    msg['To'] = 'gabrielbiscola21@gmail.com'
    password = 'huvo uppg gyac qfyn'
    msg.add_header('Contect-Type', 'text/html')
    msg.set_payload(corpo_email)
    
    s = smtplib.SMTP('smtp.gmail.com:587')
    s.starttls()
    s.login(msg['From'],password)
    s.sendmail(msg['From'],[msg['To']], msg.as_string().encode('utf-8'))

@app.route("/registro", methods=["GET"])
def seleciona_registro():
    registro_objetos = Registro.query.all()
    registro_json = [registro.to_json() for registro in registro_objetos]

    return generate_response(200, "registro", registro_json)

@app.route("/registro/<id>", methods=["GET"])
def seleciona_registro_id(id):
    registro_objetos = Registro.query.filter_by(id=id).first()

    if registro_objetos:
        registro_json = registro_objetos.to_josn()

        return generate_response(200, "registro", registro_json)
    
    else:
        return generate_response(404, "registro", (), "Registro nao encontrado")
    
@app.route("/registro/<id>", methods=["GET"])
def delete_registro(id):
    registro = Registro.query.filter_by(id=id).first()

    if registro:
        try:
            mybd.session.delete(registro)
            mybd.session.commit()

            return generate_response(200, "registro", registro.to_json(), "Registro deletado com sucesso")
        except Exception as e:
            print("Erro", e)
            mybd.session.rollback()

            return generate_response(404, "registro", (), "Erro ao deletar")
    else:
        return generate_response(404, "registro", (), "Registro nao encontrado")
    
# --------------------------------------- SENSOR ------------------------------------------------------------
@app.route("/dados", methods=["GET"])
def get_data(id):
    registro = Registro.query.filter_by(id=id).first()
    
    return jsonify(mqtt_dados)


@app.route("/dados", methods=["POST"])
def create_data():
    try:
        data = request.get_json()

        if not data:
            return generate_response(400, "data", (), "Nenhum dado fornecido")


        print(f"Dados recebidos: {data}")
        temperatura = data.get("temperatura")
        pressao = data.get("pressao")
        altitude = data.get("altitude")
        umidade = data.get("umidade")
        co2 = data.get("co2")
        poeira = data.get("poeira")
        timestamp_unix = data.get("tempo_registro")

        try:
            tempo_oficial = datetime.fromtimestamp(int(timestamp_unix), tz=timezone.utc)
        except Exception as e:
            print("Erro", e)
            return generate_response(400, "error", (), "Timestamp invalido")

        novo_registro = Registro(
            temperatura=temperatura,
            pressao=pressao,
            altitude=altitude,
            umidade=umidade,
            co2=co2,
            poeira=poeira,
            tempo_registro=tempo_oficial
        )    
            
        mybd.session.add(novo_registro)
        print("Adicionando um novo registro")
        
        mybd.session.commit()
        print("Dados inseridos no banco de dados com sucesso")
        
        
        return generate_response(201, "data", novo_registro, "Dados recebidos com sucesso")
    
    except Exception as e:
        print("Erro", e)
        mybd.session.rollback()

        return generate_response(500, "data", (), "Falha ao processar os dados")

# --------------------------------------- FUNCTIONS ------------------------------------------------------------
def to_json_sensor(self):
    return {
        "id": self.id,
        "temperatura": float(self.temperatura),
        "pressao": float(self.pressao),
        "altitude": float(self.altitude),
        "umidade": float(self.umidade),
        "co2": float(self.co2),
        "poeira": float(self.poeira),
        "tempo_registro": self.tempo_registro.strftime('%Y-%m-%d %H:%M:%S') if self.tempo_registro else None
    }

def generate_response(status, keyContent, content, msg=False):
    body={}
    body[keyContent] = content

    if msg:
        body["mensagem"] = msg

    return Response(json.dumps(body), status=status, mimeType="application/json")


if __name__ == '__main__':
    with app.app_context():
        mybd.create_all()

        start_mqtt()
        app.run(port=5000, host="localhost", debug=True)