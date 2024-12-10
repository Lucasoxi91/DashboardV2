from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, make_response,flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from flask_bcrypt import Bcrypt
from flask import session
from xhtml2pdf import pisa
from datetime import datetime 


from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, func, or_, case
from sqlalchemy.orm import relationship

import os
import io
import logging
import psycopg2
import csv
import importlib

# Configuração de logging
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'scripts')
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Configuração do banco de dados
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://adaptativa_read:pe71d6441e182e2458c5fd7701d60d1d0023f68f74dbd0ea0f8e1211d05a14374@ec2-44-220-222-138.compute-1.amazonaws.com:5432/de84slt1iucctv'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelos de banco de dados
class Users(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    last_sign_in_at = db.Column(db.DateTime)
    
    quiz_progresses = relationship('QuizUserProgress', back_populates='user')

class Quizzes(db.Model):
    __tablename__ = 'quizzes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    
    quiz_progresses = relationship('QuizUserProgress', back_populates='quiz')

class QuizUserProgress(db.Model):
    __tablename__ = 'quiz_user_progresses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    finished = db.Column(db.Boolean, default=False)
    
    user = relationship('Users', back_populates='quiz_progresses')
    quiz = relationship('Quizzes', back_populates='quiz_progresses')
    
    quiz_steps = relationship('QuizStep', back_populates='quiz_user_progress')

class QuizStep(db.Model):
    __tablename__ = 'quiz_step_progresses'
    
    id = db.Column(db.Integer, primary_key=True)
    quiz_user_progress_id = db.Column(db.Integer, db.ForeignKey('quiz_user_progresses.id'), nullable=False)
    step = db.Column(db.Integer)
    finished_at = db.Column(db.DateTime, nullable=True)
    
    quiz_user_progress = relationship('QuizUserProgress', back_populates='quiz_steps')

class User(UserMixin, db.Model):
    __tablename__ = 'educator_users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    encrypted_password = db.Column(db.String(255), nullable=False)

    def get_id(self):
        return self.id

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        logging.debug(f"Attempting login for email: {email}")
        
        user = User.query.filter_by(email=email).first()
        if user:
            logging.debug(f"User found: {user.email}")
            if bcrypt.check_password_hash(user.encrypted_password, password):
                login_user(user)
                logging.debug(f"User {email} logged in successfully.")
                return redirect(url_for('index'))
            else:
                logging.error("Password check failed.")
                error = "Usuário ou senha inválidos"
        else:
            logging.error("User not found.")
            error = "Usuário ou senha inválidos"

        return render_template('login.html', error=error)
    
    return render_template('login.html')




# Rota para logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("http://dashboardsafa.wilivro.tec.br/login?next=%2F")

# Rota principal
@app.route('/')
@login_required
def index():
    scripts = list_scripts()
    return render_template('index.html', scripts=scripts)

# Função para listar scripts disponíveis
def list_scripts():
    """Lista os scripts Python disponíveis na pasta 'scripts'."""
    scripts = [f for f in os.listdir(SCRIPTS_DIR) if f.endswith('.py')]
    return scripts

# Função para executar scripts
def execute_script(script_name, filters=None):
    logging.debug(f"Executing script: {script_name}")
    """Executa a função 'execute_query' do script selecionado e retorna seus resultados."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    spec = importlib.util.spec_from_file_location("module.name", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Adiciona filtros se forem fornecidos
    if filters:
        columns, result = module.execute_query(filters)
    else:
        columns, result = module.execute_query()
    
    return columns, result

# Rota para execução de scripts
@app.route('/execute', methods=['GET'])
@login_required
def execute():
    script_name = request.args.get('script')
    logging.debug(f"Executing script: {script_name}")
    
    if script_name in list_scripts():
        columns, data = execute_script(script_name)
        data_atual = datetime.now().strftime('%d/%m/%Y')
        script_name_clean = remove_extension(script_name)
        return render_template('tabela.html', columns=columns, data=data, data_atual=data_atual, script_name=script_name_clean)
    else:
        logging.error("Script not found")
        return "Script not found", 404

# Função para remover extensão de arquivo
def remove_extension(file_name):
    """Remove a extensão do arquivo para uma apresentação mais limpa."""
    return os.path.splitext(file_name)[0]

# Rota de relatório
@app.route('/relatorio', methods=['GET', 'POST'])
@login_required
def relatorio():
    if request.method == 'POST':
        disciplina = request.form.get('disciplina')
        curso = request.form.get('curso')
        dias = request.form.get('dias')

        columns, data = generate_report_data(disciplina, curso, dias)
        return render_template('relatorio.html', columns=columns, data=data)

    return render_template('relatorio.html')

# Função para gerar dados de relatório
def generate_report_data(disciplina, curso, dias):
    conn = get_db_connection()
    cur = conn.cursor()

    query = """
    WITH CursoAlunos AS (
        SELECT 
            ic2.name AS escola,
            UPPER(regexp_replace(ic.name, '[^0-9A-Za-z ]', '', 'g')) AS turma,
            COUNT(DISTINCT ie.user_id) AS matriculados,
            COUNT(DISTINCT CASE 
                WHEN qup.finished = FALSE 
                    AND users.last_sign_in_at >= (CURRENT_DATE - INTERVAL %s DAY) THEN users.id 
                END) AS frequentando,
            COUNT(DISTINCT CASE 
                WHEN qup.finished = FALSE 
                    AND users.last_sign_in_at IS NULL THEN users.id 
                END) AS nunca_acessou,
            COUNT(DISTINCT CASE 
                WHEN qup.finished = FALSE 
                    AND users.last_sign_in_at < (CURRENT_DATE - INTERVAL %s DAY) THEN users.id 
                END) AS nao_acessa_ha_x_dias,
            COUNT(DISTINCT CASE 
                WHEN qup.finished = TRUE THEN users.id 
                END) AS concluidos
        FROM 
            users
        LEFT JOIN institution_enrollments ie ON ie.user_id = users.id
        LEFT JOIN institution_classrooms ic ON ic.id = ie.classroom_id
        LEFT JOIN institution_colleges ic2 ON ic2.id = ic.id
        LEFT JOIN institutions i ON i.id = ic2.institution_id
        LEFT JOIN quiz_user_progresses qup ON qup.user_id = users.id
        LEFT JOIN quizzes q ON q.id = qup.quiz_id
        WHERE 
            i.name ILIKE '%2024%'
            AND UPPER(ic.name) NOT LIKE '%NICA%'
        GROUP BY ic2.name, ic.name
    )
    SELECT * FROM CursoAlunos;
    """

    cur.execute(query, (dias, dias))
    data = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    conn.close()

    return columns, data

# Rota para gerar relatório com lógica corrigida
@app.route('/generate_report', methods=['POST'])
def generate_report():
    try:
        # Captura os parâmetros do formulário
        disciplina = request.form.get('disciplina', '')
        curso = request.form.get('curso', '')
        dias = request.form.get('dias', 0)

        # Validação básica
        if not disciplina or not curso or not dias:
            return jsonify({"error": "Todos os campos são obrigatórios."}), 400

        try:
            dias = int(dias)
        except ValueError:
            return jsonify({"error": "O campo 'dias' deve ser um número inteiro."}), 400

        # Determina o padrão do simulado
        curso_parts = curso.split(" ")
        if "Matemática" in disciplina:
            curso_ano = curso_parts[1].split("°")[0]
            curso_disciplina = "MT"
        elif "Língua Portuguesa" in disciplina:
            curso_ano = curso_parts[2].split("°")[0]
            curso_disciplina = "LP"
        else:
            return jsonify({"error": "Disciplina inválida."}), 400

        curso_numero = curso_parts[-3].replace("Curso", "C").strip()

        # Definir o padrão de simulado (03% é para pegar apenas o simulado 03)
        simulado_pattern_03 = f"%Sim Geral {curso_ano}º {curso_disciplina} C{curso_numero} 03%"

        # Query SQL ajustada com a exclusão das escolas e o filtro para apenas o simulado 03 em "concluídos"
        query = text(f"""
                WITH CursoAlunos AS ( 
                    SELECT
                        ic2.name AS escola,
                        UPPER(
                            CASE 
                                WHEN cl.name = 'NICA' THEN 'UNICA' 
                                ELSE regexp_replace(cl.name, '[^0-9A-Za-z ]', '', 'g') 
                            END
                        ) AS turma,
                        ARRAY_AGG(DISTINCT u.id) AS matriculados_ids,

                        ARRAY_AGG(DISTINCT CASE
                                        WHEN qup.finished = TRUE
                                        AND u.last_sign_in_at IS NOT NULL
                                        AND u.last_sign_in_at >= NOW() - INTERVAL '21 DAY'
                                        AND u.id NOT IN (
                                                SELECT u2.id
                                                FROM users u2
                                                LEFT JOIN quiz_user_progresses qup2 ON qup2.user_id = u2.id
                                                LEFT JOIN quizzes q2 ON q2.id = qup2.quiz_id
                                                WHERE qup2.finished = TRUE 
                                                AND q2.name ILIKE :simulado_pattern_03
                                            ) THEN u.id
                                        END) AS frequentando_ids,

                        ARRAY_AGG(DISTINCT CASE
                                        WHEN u.last_sign_in_at IS NULL THEN u.id
                                        END) AS nunca_acessou_ids,

                        ARRAY_AGG(DISTINCT CASE
                                        WHEN u.last_sign_in_at IS NOT NULL
                                        AND u.last_sign_in_at < NOW() - INTERVAL '21 DAY'
                                        AND u.last_sign_in_at >= NOW() - INTERVAL '21 DAY'
                                        AND u.id NOT IN (
                                                SELECT u2.id
                                                FROM users u2
                                                LEFT JOIN quiz_user_progresses qup2 ON qup2.user_id = u2.id
                                                LEFT JOIN quizzes q2 ON q2.id = qup2.quiz_id
                                                WHERE qup2.finished = TRUE 
                                                AND q2.name ILIKE :simulado_pattern_03
                                            ) THEN u.id
                                        END) AS nao_acessa_ha_x_dias_ids,

                        ARRAY_AGG(DISTINCT CASE
                                        WHEN u.last_sign_in_at IS NOT NULL
                                        AND u.last_sign_in_at < NOW() - INTERVAL '21 DAY'
                                        AND u.id NOT IN (
                                                SELECT u2.id
                                                FROM users u2
                                                LEFT JOIN quiz_user_progresses qup2 ON qup2.user_id = u2.id
                                                LEFT JOIN quizzes q2 ON q2.id = qup2.quiz_id
                                                WHERE qup2.finished = TRUE 
                                                AND q2.name ILIKE :simulado_pattern_03
                                            ) THEN u.id
                                        END) AS nao_acessa_ha_mais_de_x_dias_ids,

                        ARRAY_AGG(DISTINCT CASE
                                        WHEN qup.finished = TRUE 
                                        AND q.name ILIKE :simulado_pattern_03 THEN u.id
                                        END) AS concluidos_ids

                    FROM
                        users u
                    LEFT JOIN institution_enrollments ie ON ie.user_id = u.id
                    LEFT JOIN institution_classrooms cl ON cl.id = ie.classroom_id
                    LEFT JOIN institution_levels il ON il.id = cl.level_id
                    LEFT JOIN institution_courses ic ON ic.id = il.course_id
                    LEFT JOIN institution_colleges ic2 ON ic2.id = ic.institution_college_id
                    LEFT JOIN institutions inst ON inst.id = ic2.institution_id
                    LEFT JOIN quiz_user_progresses qup ON qup.user_id = u.id
                    LEFT JOIN quizzes q ON q.id = qup.quiz_id
                    WHERE inst.name ILIKE :curso
                    AND ic2.name != 'Wiquadro'
                    GROUP BY ic2.name, cl.name
                )
                SELECT * FROM CursoAlunos;


        """)

        # Log da consulta SQL
        logging.debug(f"Consulta SQL: {query}")
        logging.debug(f"Parâmetros: simulado_pattern_03={simulado_pattern_03}, curso={curso}")

        # Executando a consulta
        result = db.session.execute(query, {'simulado_pattern_03': simulado_pattern_03, 'curso': f'%{curso}%'})

        results = []
        for row in result:
            results.append({
                "escola": row[0],
                "turma": row[1],
                "matriculados": len(row[2]),  # Contagem de alunos matriculados
                "matriculados_ids": row[2],  # IDs dos alunos matriculados
                "frequentando": len([i for i in row[3] if i is not None]),  # Contagem dos que estão frequentando
                "frequentando_ids": [i for i in row[3] if i is not None],  # IDs dos alunos frequentando
                "nunca_acessou": len([i for i in row[4] if i is not None]),  # Contagem dos que nunca acessaram
                "nunca_acessou_ids": [i for i in row[4] if i is not None],  # IDs dos alunos que nunca acessaram
                "nao_acessa_ha_x_dias": len([i for i in row[5] if i is not None]),  # Contagem dos que não acessam há X dias
                "nao_acessa_ha_x_dias_ids": [i for i in row[5] if i is not None],  # IDs dos alunos que não acessam há X dias
                "nao_acessa_ha_mais_de_x_dias": len([i for i in row[6] if i is not None]),  # Contagem dos que não acessam há mais de X dias
                "nao_acessa_ha_mais_de_x_dias_ids": [i for i in row[6] if i is not None],  # IDs dos alunos que não acessam há mais de X dias
                "concluidos": len([i for i in row[7] if i is not None]),  # Contagem dos que concluíram o simulado 03
                "concluidos_ids": [i for i in row[7] if i is not None]  # IDs dos alunos que concluíram o simulado 03
            })

        return jsonify(results)

    except Exception as e:
        logging.error(f"Erro ao gerar relatório: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_schools', methods=['GET'])
def get_schools():
    try:
        # Obtendo o curso selecionado do frontend
        curso = request.args.get('curso')

        # Verificação inicial se o curso foi passado corretamente
        if not curso:
            return jsonify({"error": "Curso não fornecido"}), 400

        # Conectando ao banco de dados PostgreSQL
        conn = psycopg2.connect(
            host="ec2-44-220-222-138.compute-1.amazonaws.com",
            database="de84slt1iucctv",
            user="adaptativa_read",
            password="pe71d6441e182e2458c5fd7701d60d1d0023f68f74dbd0ea0f8e1211d05a14374",
            port="5432"
        )
        cursor = conn.cursor()

        # Consultando as escolas associadas ao curso
        query = """
             SELECT DISTINCT ic.name
            FROM institution_colleges ic
            INNER JOIN institution_enrollments ie ON ie.college_id = ic.id
            INNER JOIN institutions i ON i.id = ic.institution_id
            WHERE i.name = %s
        """

        cursor.execute(query, (curso,))
        escolas = cursor.fetchall()

        # Fechando a conexão
        cursor.close()
        conn.close()

        # Preparando o retorno da lista de escolas
        escolas_list = [escola[0] for escola in escolas]
        return jsonify({"schools": escolas_list})

    except Exception as e:
        print(f"Erro ao buscar escolas: {str(e)}")
        return jsonify({"error": "Erro ao buscar escolas."}), 500




# Função para gerar descritores com filtros@app.route('/gerar_relatorio_descritores', methods=['POST'])
@app.route('/gerar_relatorio_descritores', methods=['GET'])
def gerar_relatorio_descritores():
    try:
        # Obtendo os parâmetros da URL
        disciplina = request.args.get('disciplina')
        instituicao = request.args.get('curso')
        escola = request.args.get('escola')
        nota_corte = request.args.get('nota_corte')

        # Validação dos parâmetros
        if not disciplina or not instituicao or not escola or not nota_corte:
            return jsonify({"error": "Parâmetros obrigatórios faltando ou inválidos."}), 400

        # Convertendo nota de corte para número
        try:
            nota_corte = float(nota_corte)
        except ValueError:
            return jsonify({"error": "Nota de corte deve ser um número válido."}), 400

        # Log para verificação dos dados recebidos
        print(f"Disciplina: {disciplina}, Curso: {instituicao}, Escola: {escola}, Nota de Corte: {nota_corte}")

        # Estabelecendo a conexão com o banco de dados PostgreSQL
        conn = psycopg2.connect(
            host="ec2-44-220-222-138.compute-1.amazonaws.com",
            database="de84slt1iucctv",
            user="adaptativa_read",
            password="pe71d6441e182e2458c5fd7701d60d1d0023f68f74dbd0ea0f8e1211d05a14374",
            port="5432"
        )
        cursor = conn.cursor()

        # Construindo o nome do quiz dinamicamente com base nos parâmetros
        try:
            curso_parts = instituicao.split(" ")
            curso_ano = curso_parts[1].split("°")[0] if "Matemática" in disciplina else curso_parts[2].split("°")[0]
            curso_disciplina = "MT" if "Matemática" in disciplina else "LP"
            curso_numero = curso_parts[-3].replace("Curso", "C").strip()
            simulado_pattern_03 = f"%Sim Geral {curso_ano}º {curso_disciplina} C{curso_numero} 03%"
        except IndexError:
            return jsonify({"error": "Erro ao processar o curso. Verifique o formato do curso."}), 400

        # SQL com parâmetros ajustados
        query = f"""
        WITH SelectedData AS (
            SELECT
                qaur.user_id,
                qaur.quiz_id,
                qur.topic_name,
                qaur.result
            FROM quiz_user_answer_results qaur
            JOIN quiz_user_answer_reports qur
                ON qur.question_id = qaur.question_id 
                AND qur.quiz_id = qaur.quiz_id 
                AND qur.user_id = qaur.user_id 
            WHERE qaur.quiz_id IN (
                SELECT id 
                FROM quizzes 
                WHERE name ILIKE '{simulado_pattern_03}' -- Parâmetro para o simulado
            )
        ),
        UniqueEnrollments AS (
            SELECT DISTINCT
                u.id AS aluno_id,
                cl.id AS turma_id,
                CASE
                    WHEN cl.name ILIKE 'turma%' THEN TRIM(SPLIT_PART(cl.name, ' ', 2)) -- Exemplo: "Turma A" → "A"
                    ELSE cl.name
                END AS turma_nome,
                ic2.name AS escola_nome,
                inst.name AS instituicao_nome
            FROM users u
            JOIN institution_enrollments ie ON ie.user_id = u.id
            JOIN institution_classrooms cl ON cl.id = ie.classroom_id
            JOIN institution_colleges ic2 ON ic2.id = ie.college_id
            JOIN institutions inst ON inst.id = ic2.institution_id
            WHERE inst.name ILIKE '%{instituicao}%' -- Parâmetro para instituição
              AND ic2.name ILIKE '%{escola}%' -- Parâmetro para escola
        ),
        AggregatedResults AS (
            SELECT
                ue.escola_nome AS escola,
                ue.turma_nome AS turma,
                COUNT(DISTINCT ue.aluno_id) AS alunos_concluidos, -- Contar alunos únicos
                sd.topic_name AS descritor,
                ROUND(AVG(CASE WHEN sd.result = 'right' THEN 100 ELSE 0 END)::numeric, 1) AS acertos
            FROM SelectedData sd
            JOIN UniqueEnrollments ue ON ue.aluno_id = sd.user_id
            GROUP BY ue.escola_nome, ue.turma_nome, sd.topic_name
            HAVING ROUND(AVG(CASE WHEN sd.result = 'right' THEN 100 ELSE 0 END)::numeric, 1) <= {nota_corte} -- Parâmetro para nota de corte
            ORDER BY ue.escola_nome, ue.turma_nome, sd.topic_name
        )
        SELECT 
            escola, 
            turma, 
            alunos_concluidos, 
            descritor, 
            acertos
        FROM AggregatedResults;
        """

        # Log da consulta gerada
        print(f"SQL Gerado: {query}")

        # Executando a consulta
        cursor.execute(query)
        dados = cursor.fetchall()

        # Fechando a conexão
        cursor.close()
        conn.close()

        # Preparando os dados para JSON
        dados_json = [
            {
                "escola": row[0],
                "turma": row[1],
                "alunos_concluidos": row[2],
                "descritor": row[3],
                "acertos": row[4]
            }
            for row in dados
        ]

        # Retornando os dados como JSON
        return jsonify(dados_json)

    except Exception as e:
        print(f"Erro: {str(e)}")
        return jsonify({"error": "Ocorreu um erro ao gerar o relatório."}), 500


  


@app.route('/gerar_relatorio_descritores_total', methods=['POST'])
def gerar_relatorio_descritores_total():
    try:
        # Pegando os dados do formulário
        disciplina = request.form.get('disciplina')
        instituicao = request.form.get('curso')
        nota_corte = request.form.get('nota_corte')

        # Log para verificação dos dados recebidos
        print(f"Disciplina: {disciplina}, Curso: {instituicao}, Nota de Corte: {nota_corte}")

        # Estabelecendo a conexão com o banco de dados PostgreSQL
        conn = psycopg2.connect(
            host="ec2-44-220-222-138.compute-1.amazonaws.com",
            database="de84slt1iucctv",
            user="adaptativa_read",
            password="pe71d6441e182e2458c5fd7701d60d1d0023f68f74dbd0ea0f8e1211d05a14374",
            port="5432",
            options="-c client_encoding=WIN1252"
        )
        cursor = conn.cursor()

        # Corrigir a extração de partes do curso levando em consideração o número de palavras na disciplina
        curso_parts = instituicao.split(" ")

        # Extração correta para o ano e número do curso levando em conta a quantidade de palavras na disciplina
        if "Língua Portuguesa" in disciplina:
            curso_ano = curso_parts[2].split("°")[0]  # Extração do ano para "Língua Portuguesa"
            curso_numero = curso_parts[-3].replace("Curso", "C").strip()  # Extrai o número do curso (C1, C2, etc)
        else:  # Caso "Matemática"
            curso_ano = curso_parts[1].split("°")[0]  # Extração do ano para "Matemática"
            curso_numero = curso_parts[-3].replace("Curso", "C").strip()

        curso_disciplina = "MT" if "Matemática" in disciplina else "LP"  # Define LP para Língua Portuguesa

        # Padrão correto do simulado
        simulado_pattern_03 = f"%Sim Geral {curso_ano}º {curso_disciplina} C{curso_numero} 03%"

        # Query com o padrão do simulado corrigido
        curso_query = f"%{instituicao}%"

        # SQL para gerar o relatório total
        query = f"""

        WITH SelectedData AS (
            SELECT
                qaur.user_id,
                qaur.quiz_id,
                qur.topic_name,
                qaur.result
            FROM quiz_user_answer_results qaur
            JOIN quiz_user_answer_reports qur
                ON qur.question_id = qaur.question_id 
                AND qur.quiz_id = qaur.quiz_id 
                AND qur.user_id = qaur.user_id 
            WHERE qaur.quiz_id IN (
                SELECT id 
                FROM quizzes 
                WHERE name ILIKE '{simulado_pattern_03}' -- Parâmetro para o simulado
            )
        ),
        UniqueEnrollments AS (
            -- Garantir alunos únicos por turma, com instituição e escola dinâmicas
            SELECT DISTINCT
                u.id AS aluno_id,
                cl.id AS turma_id,
                CASE
                    WHEN cl.name ILIKE 'turma%' THEN TRIM(SPLIT_PART(cl.name, ' ', 2))  
                    ELSE cl.name
                END AS turma_nome,
                ic2.name AS escola_nome,
                inst.name AS instituicao_nome
            FROM users u
            JOIN institution_enrollments ie ON ie.user_id = u.id
            JOIN institution_classrooms cl ON cl.id = ie.classroom_id
            JOIN institution_colleges ic2 ON ic2.id = ie.college_id
            JOIN institutions inst ON inst.id = ic2.institution_id
            WHERE inst.name ILIKE '%{instituicao}%' -- Parâmetro para instituição
            AND ic2.name NOT ILIKE '%Wiquadro%' -- Excluir escola "Wiquadro"
        ),
        AggregatedResults AS (
            SELECT
                ue.escola_nome AS escola,
                ue.turma_nome AS turma,
                COUNT(DISTINCT ue.aluno_id) AS alunos_concluidos, -- Contar alunos únicos
                sd.topic_name AS descritor,
                -- Calcular percentual de acertos
                ROUND(AVG(CASE WHEN sd.result = 'right' THEN 100 ELSE 0 END)::numeric, 1) AS acertos
            FROM SelectedData sd
            JOIN UniqueEnrollments ue ON ue.aluno_id = sd.user_id
            GROUP BY ue.escola_nome, ue.turma_nome, sd.topic_name
            HAVING ROUND(AVG(CASE WHEN sd.result = 'right' THEN 100 ELSE 0 END)::numeric, 1) <= {nota_corte}
            ORDER BY ue.escola_nome, ue.turma_nome, sd.topic_name
        )
        SELECT 
            escola,
            turma,
            alunos_concluidos,
            descritor,
            acertos
        FROM AggregatedResults;
 

        """

        # Log da consulta gerada
        print(f"SQL Gerado: {query}")

        # Executando a consulta
        cursor.execute(query)
        dados = cursor.fetchall()

        # Fechando a conexão
        cursor.close()
        conn.close()

        dados_json = [
            {
                "escola": row[0],
                "turma": row[1],
                "alunos_concluidos": row[2],
                "descritor": row[3],
                "acertos": row[4]
            }
            for row in dados
        ]

        # Retornando os dados como JSON
        return jsonify(dados_json)

    except Exception as e:
        print(f"Erro: {str(e)}")
        return jsonify({"error": "Ocorreu um erro ao gerar o relatório."}), 500



@app.route('/descritores.html')
def descritores():
    return render_template('descritores.html')

@app.route('/descritorestotal')
def descritorestotal():
    return render_template('descritorestotal.html')


@app.route('/consultar_descritores', methods=['POST'])
def consultar_descritores():
    data = request.json
    disciplina = data.get('disciplina')
    curso = data.get('curso')
    nota_corte = data.get('nota_corte')

    # Verifica se todos os campos estão preenchidos
    if not all([disciplina, curso, nota_corte]):
        return jsonify({'error': 'Por favor, preencha todos os campos.'}), 400

    # Chama a função para gerar os descritores
    dados = gerar_relatorio_descritores(disciplina, curso, nota_corte)

    return jsonify(dados)

# Rota para obter detalhes dos alunos
@app.route('/student_details', methods=['GET'])
def student_details():
    try:
        # Captura os parâmetros da query string
        student_ids = request.args.get('student_ids')
        disciplina = request.args.get('disciplina')
        curso = request.args.get('curso')

        if not student_ids or not disciplina or not curso:
            logging.error("Missing required parameters: student_ids, disciplina, or curso.")
            return jsonify({"error": "Parâmetros obrigatórios ausentes."}), 400

        # Converte a string dos IDs para uma lista de IDs
        student_ids = student_ids.split(',')
        student_ids = [s.strip() for s in student_ids if s.strip()]  # Remove espaços vazios e strings vazias

        logging.info(f"Received student_ids: {student_ids}")
        logging.info(f"Received disciplina: {disciplina}")
        logging.info(f"Received curso: {curso}")

        # Função para obter os alunos pelos IDs
        students = get_students_by_ids(student_ids, disciplina, curso)

        if not students:
            logging.warning("No students found for the given criteria.")
            return jsonify({"warning": "Nenhum aluno encontrado para os critérios fornecidos."}), 404

        return render_template('student_details.html', students=students)

    except Exception as e:
        logging.error(f"Erro ao obter detalhes dos alunos: {e}")
        return jsonify({"error": str(e)}), 500




# Função para buscar estudantes por IDs
def get_students_by_ids(student_ids, disciplina, curso):
    logging.info(f"Received student_ids: {student_ids}")
    logging.info(f"Received disciplina: {disciplina}")
    logging.info(f"Received curso: {curso}")

    # Gera partes do curso para criar o padrão de simulado
    curso_parts = curso.split(" ")

    if "Matemática" in disciplina:
        curso_ano = curso_parts[1].split("°")[0]
        curso_disciplina = "MT"
    elif "Língua Portuguesa" in disciplina:
        curso_ano = curso_parts[2].split("°")[0]
        curso_disciplina = "LP"
    else:
        logging.error(f"Disciplina não suportada: {disciplina}")
        return []

    curso_numero = curso_parts[-3].replace("Curso", "C").strip()

    # Gera os padrões de simulado
    simulado_patterns = [
        f'%Sim Geral {curso_ano}º {curso_disciplina} C{curso_numero} 03%',
        f'%Sim Geral {curso_ano}º {curso_disciplina} C{curso_numero} 02%',
        f'%Sim Geral {curso_ano}º {curso_disciplina} C{curso_numero} 01%'
    ]

    logging.debug(f"Generated simulado patterns: {simulado_patterns}")

    # Subquery para obter os dados dos quizzes e selecionar apenas o simulado mais recente (maior)
    subquery = (
        db.session.query(
            Users.id.label('student_id'),
            Quizzes.name.label('last_quiz_name'),
            func.max(QuizStep.finished_at).label('last_finished_at'),
            func.row_number().over(
                partition_by=Users.id,
                order_by=func.regexp_replace(Quizzes.name, '[^0-9]', '', 'g').cast(db.Integer).desc()
            ).label('row_num')
        )
        .join(QuizUserProgress, QuizUserProgress.user_id == Users.id)
        .join(Quizzes, Quizzes.id == QuizUserProgress.quiz_id)
        .join(QuizStep, QuizStep.quiz_user_progress_id == QuizUserProgress.id)
        .filter(
            QuizUserProgress.finished == True,
            or_(*[Quizzes.name.ilike(pattern) for pattern in simulado_patterns])
        )
        .group_by(Users.id, Quizzes.name)
        .subquery()
    )

    # Query principal para buscar os alunos com base no subquery
    students = (
        db.session.query(
            Users.id.label('id'),
            Users.name.label('name'),
            case(
                (subquery.c.last_finished_at.isnot(None), subquery.c.last_quiz_name),
                else_='Simulado não realizado'
            ).label('progress'),
            func.coalesce(
                func.to_char(Users.last_sign_in_at, 'DD/MM/YYYY HH24:MI'),
                'Nunca acessou'
            ).label('last_sign_in_at')
        )
        .outerjoin(subquery, subquery.c.student_id == Users.id)
        .filter(Users.id.in_(student_ids))  # Filtra pelos IDs dos alunos
        .filter(or_(subquery.c.row_num == 1, subquery.c.row_num.is_(None)))  # Garante que apenas o simulado mais recente seja retornado
        .order_by(subquery.c.last_finished_at.desc().nulls_last())
        .all()
    )

    # Logging dos resultados encontrados
    logging.info(f"Found {len(students)} students for the criteria.")

    student_list = [
        {
            "id": student.id,
            "name": student.name,
            "progress": student.progress,
            "last_sign_in_at": student.last_sign_in_at
        }
        for student in students
    ]

    logging.debug(f"Generated student list: {student_list}")

    return student_list

# Rota para obter estudantes
@app.route('/get_students', methods=['POST'])
def get_students():
    try:
        data = request.get_json()
        student_ids = data.get('student_ids', [])

        if not student_ids:
            return jsonify([])

        students = db.session.query(Users.name).filter(Users.id.in_(student_ids)).all()
        student_names = [student.name for student in students]
        
        print("Nomes dos alunos retornados:", student_names)
    
        return jsonify(student_names)
    except Exception as e:
        logging.error(f"Erro ao obter a lista de alunos: {e}")
        return jsonify({"error": str(e)}), 500

def get_db_connection():
    return psycopg2.connect(
        host="ec2-44-220-222-138.compute-1.amazonaws.com",
        database="de84slt1iucctv",
        user="adaptativa_read",
        password="pe71d6441e182e2458c5fd7701d60d1d0023f68f74dbd0ea0f8e1211d05a14374",
        port="5432"
    )

# Rota para obter cursos
@app.route('/get_courses', methods=['GET'])
@login_required
def get_courses():
    disciplina = request.args.get('disciplina')

    if not disciplina:
        return jsonify({"error": "Disciplina não fornecida"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        disciplina = disciplina.strip()
        query = f"""
        SELECT DISTINCT name 
        FROM institutions 
        WHERE name ILIKE '%{disciplina}%' AND name ILIKE '%2024%'
        """
        cur.execute(query)
        courses = [row[0] for row in cur.fetchall()]
    except Exception as e:
        logging.error(f"Erro ao obter cursos: {e}")
        courses = []
    finally:
        conn.close()

    return jsonify(courses=courses)

# Rota para gerar CSV
@app.route('/generate_csv', methods=['POST'])
@login_required
def generate_csv():
    try:
        data = request.get_json()
        columns = data.get('columns', [])
        rows = data.get('data', [])
        script_name = data.get('script_name', 'resultados')

        if not columns or not rows:
            return jsonify({"error": "Nenhum dado disponível para exportação."}), 400
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quoting=csv.QUOTE_NONNUMERIC, lineterminator='\n')
        writer.writerow(columns)
        writer.writerows(rows)

        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename={script_name}.csv'
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Rota para gerar PDF
@app.route('/generate_pdf', methods=['POST'])
@login_required
def generate_pdf():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Dados não fornecidos"}), 400
    
    columns = data.get('columns', [])
    filtered_data = data.get('data', [])
    script_name = data.get('script_name', 'resultados')

    if not columns or not filtered_data:
        return jsonify({"error": "Sem dados para gerar PDF"}), 400

    try:
        html_content = render_template(
            'pdf_template.html',
            columns=columns,
            data=filtered_data,
            data_atual=datetime.now().strftime('%d/%m/%Y'),
            script_name=script_name
        )

        pdf = render_pdf(html_content)

        if not pdf:
            return jsonify({"error": "Erro ao gerar PDF"}), 500

        response = make_response(pdf.read())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={script_name}.pdf'
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Função para renderizar PDF
def render_pdf(html_content):
    output = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=output)
    if pisa_status.err:
        return None
    output.seek(0)
    return output



# Execução da aplicação
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
