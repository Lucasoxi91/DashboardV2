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
                            
        WITH QuizData AS (
    SELECT 
        i.name as curso,
        ic2.name as escola,
        ic2.id as escola_id,
         'Curso ' || (REGEXP_MATCHES(q.name, 'C([0-9]+)'))[1] || ' Simulado ' || (REGEXP_MATCHES(q.name, '[0-9]{2}$'))[1] AS simulado,
        count(DISTINCT users.id) as n_user_id,  -- DISTINCT adicionado aqui
        ROUND(AVG(qg.average)::numeric, 1) as grade_avg  -- Média de notas arredondada para uma casa decimal
    FROM 
        quiz_user_progresses qup  
    INNER JOIN users on qup.user_id = users.id 
    INNER JOIN quizzes q on qup.quiz_id = q.id
    INNER JOIN institution_enrollments ie on qup.user_id = ie.user_id
    INNER JOIN institution_classrooms ic on ic.id = ie.classroom_id  
    INNER JOIN institution_levels il on il.id = ic.level_id 
    INNER JOIN institution_courses ic3 on ic3.id = il.course_id 
    INNER JOIN institution_colleges ic2 on ic2.id = ic3.institution_college_id and ic2.id = ie.college_id 
    INNER JOIN institutions i on i.id = ic2.institution_id  
    INNER JOIN regions r on ic2.region_id = r.id 
    INNER JOIN cities c on c.id = r.city_id 
    INNER JOIN institutions_quizzes iq on iq.institution_id = i.id and iq.quiz_id = q.id
    INNER JOIN quiz_grades qg on qg.user_id = users.id and qg.quiz_id = q.id 
    WHERE qup.finished = true 
    AND i.name ILIKE '%2024%'
    AND LOWER(ic2.name) NOT IN ('wiquadro', 'teste', 'escola demonstração', 'escola1', 'escola2')
    GROUP BY i.name, ic2.name, ic2.id, q.name
), 
EnrollmentData AS (
    SELECT  
        i.name as curso,
        count(DISTINCT ie.user_id) as matriculados,  -- DISTINCT adicionado aqui
        ic2.name as escola,
        ic2.id as escola_id
    FROM 
        institution_classrooms ic 
    INNER JOIN institution_levels il on il.id = ic.level_id 
    INNER JOIN institution_courses ic3 on ic3.id = il.course_id 
    INNER JOIN institution_colleges ic2 on ic2.id = ic3.institution_college_id  
    INNER JOIN institutions i on i.id = ic2.institution_id  
    INNER JOIN institution_enrollments ie on ie.institution_id = i.id and ie.classroom_id = ic.id and ie.college_id = ic2.id 
    WHERE i.name ILIKE '%2024%'
    AND LOWER(ic2.name) NOT IN ('wiquadro', 'teste', 'escola demonstração', 'escola1', 'escola2')
    GROUP BY i.name, ic2.name, ic2.id
)
SELECT 
    qd.curso,
    qd.escola,
    qd.simulado,
    qd.n_user_id as finalizaram,
    ed.matriculados,
    ROUND((CAST(qd.n_user_id AS numeric) / COALESCE(NULLIF(ed.matriculados, 0), 1)) * 100, 1) AS Taxa_de_Participação,  -- Tratamento de divisão por zero com COALESCE
    qd.grade_avg AS média_de_notas
FROM QuizData qd
INNER JOIN EnrollmentData ed ON qd.curso = ed.curso AND qd.escola_id = ed.escola_id
ORDER BY qd.curso, qd.escola, qd.simulado;




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