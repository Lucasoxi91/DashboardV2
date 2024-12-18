from flask import Flask, render_template_string
import psycopg2

def get_db_connection():
    conn = None
    try:
        conn = psycopg2.connect(
        host="ec2-44-220-222-138.compute-1.amazonaws.com",
        database="de84slt1iucctv",
        user="adaptativa_read",
        password="pe71d6441e182e2458c5fd7701d60d1d0023f68f74dbd0ea0f8e1211d05a14374",
        port="5432"
        ) 
   
    except Exception as e:
        print(f"Falha na conexão ao banco de dados: {e}")
    return conn

def execute_query():
    conn = get_db_connection()
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute("""

WITH AlunosSimulado AS (
    SELECT 
        ic2.name AS escola,
        ic.name AS turma,
        q.name AS nome_simulado,
        CASE 
            WHEN q.name LIKE '%LP%' THEN 'Língua Portuguesa'
            WHEN q.name LIKE '%MT%' THEN 'Matemática'
             WHEN q.name LIKE '%Minissim%' THEN 'Matemática'
              WHEN q.name LIKE '%minisim%' THEN 'Língua Portuguesa'
        END AS cursos, 
        COUNT(DISTINCT users.id) AS alunos_simulado
    FROM 
        quiz_user_progresses qup  
    INNER JOIN users ON users.id = qup.user_id 
    INNER JOIN quizzes q ON q.id = qup.quiz_id 
    INNER JOIN institution_enrollments ie ON ie.user_id = qup.user_id 
    INNER JOIN institution_classrooms ic ON ic.id = ie.classroom_id  
    INNER JOIN institution_levels il ON il.id = ic.level_id 
    INNER JOIN institution_courses ic3 ON ic3.id = il.course_id 
    INNER JOIN institution_colleges ic2 ON ic2.id = ic3.institution_college_id AND ic2.id = ie.college_id 
    INNER JOIN institutions i ON i.id = ic2.institution_id  
    WHERE qup.finished = TRUE 
    AND i.id IN (335, 336, 363)
    AND ic2.name <> 'Wiquadro'
    GROUP BY ic2.name, ic.name, q.name
),
TodosAlunosMatriculados AS (
    SELECT 
        ic2.name AS escola,
        ic.name AS turma,
        COUNT(DISTINCT ie.user_id) AS alunos_matriculados
    FROM 
        institution_enrollments ie
    INNER JOIN institution_classrooms ic ON ic.id = ie.classroom_id  
    INNER JOIN institution_levels il ON il.id = ic.level_id 
    INNER JOIN institution_courses ic3 ON ic3.id = il.course_id 
    INNER JOIN institution_colleges ic2 ON ic2.id = ic3.institution_college_id 
    INNER JOIN institutions i ON i.id = ic2.institution_id  
    WHERE i.id IN (335, 336, 363)
    AND ic2.name NOT IN ('Wiquadro','ESCOLA1', 'ESCOLA2', 'ESCOLA_SANDBOX')
    GROUP BY ic2.name, ic.name
)
SELECT 
    T.escola,
    T.turma,
    A.cursos AS Disciplina, 
    A.nome_simulado AS Simulado_Minisimulado, 
    COALESCE(A.alunos_simulado, 0) AS Simulados_concluídos, 
    COALESCE(T.alunos_matriculados, 0) AS Matriculados_na_Turma
FROM 
    TodosAlunosMatriculados T
LEFT JOIN AlunosSimulado A 
    ON T.escola = A.escola
    AND T.turma = A.turma
ORDER BY T.escola, T.turma, A.cursos;

                """)
                column_names = [desc[0] for desc in cur.description]
                results = cur.fetchall()
                return (column_names, results)
        except Exception as e:
            print(f"Falha na execução da consulta: {e}")
        finally:
            conn.close()
    return ([], [])  # Retorna listas vazias se a conexão falhar ou ocorrer uma exceção

app = Flask(__name__)

@app.route('/')
def index():
    column_names, query_results = execute_query()
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Resultados da Consulta</title>
        <style>
            body {
                font-family: 'Arial', sans-serif;
                margin: 0;
                padding: 0;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                background-color: #f5f5f5;
            }
            .header-container {
                text-align: center;
                margin: 20px;
            }
            .table-container {
                width: 80%;
                max-width: 1000px;
                box-shadow: 0 2px 3px rgba(0,0,0,0.1);
                background-color: #fff;
                margin: 20px 0;
            }
            table {
                border-collapse: collapse;
                width: 1000px;
            }
            th, td {
                text-align: center;
                padding: 10px;
                font-size: 16px;
                width: 25px

            }
            th {
                background-color: #007bff;
                color: white;
            }
            tr:nth-child(even) {background-color: #f2f2f2;}
        </style>
    </head>
    <body>
        <h1>Quantidade de Alunos Acessando</h1>
        <table>
            <thead>
                <tr>
                    {% for col_name in column_names %}
                    <th>{{ col_name }}</th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for row in query_results %}
                <tr>
                    {% for cell in row %}
                    <td>{{ cell }}</td>
                    {% endfor %}
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </body>
    </html>
    """
    return render_template_string(html_template, column_names=column_names, query_results=query_results)

if __name__ == "__main__":
    app.run(debug=True)