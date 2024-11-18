from flask import Flask, request, render_template_string, make_response
import os
import importlib.util
import csv
import io

app = Flask(__name__)

# Diretório onde os scripts Python estão localizados
SCRIPTS_DIR = os.path.join(os.getcwd(), 'scripts')

def list_scripts():
    return [f for f in os.listdir(SCRIPTS_DIR) if os.path.isfile(os.path.join(SCRIPTS_DIR, f)) and f.endswith('.py')]

def execute_script(script_path):
    spec = importlib.util.spec_from_file_location("module.name", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.execute_query()  # Assume que execute_query retorna (column_names, query_results)

@app.route('/', methods=['GET', 'POST'])
def index():
    scripts = list_scripts()
    column_names, query_results = [], []

    if request.method == 'POST':
        selected_script = request.form.get('script')
        if selected_script in scripts:
            script_path = os.path.join(SCRIPTS_DIR, selected_script)
            column_names, query_results = execute_script(script_path)

    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Executar Scripts Python</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.25/css/jquery.dataTables.css">
        <script type="text/javascript" src="https://code.jquery.com/jquery-3.5.1.js"></script>
        <script type="text/javascript" src="https://cdn.datatables.net/1.10.25/js/jquery.dataTables.js"></script>
        <script>$(document).ready(function() {$('#resultsTable').DataTable();});</script>
 <style>
            body {
                font-family: 'Segoe UI', Arial, sans-serif;
                background-color: #ffffff; /* branco */
                color: #333;
                padding: 20px;
            }
            .header-container h1, .header-container form {
                text-align: left;
                
            }

            table {
                border-collapse: collapse;
                width: 100%;
                background-color: white
            }
            th, td {
                padding: 8px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background-color: #00000;
                color: #333;
            }
            tr:hover {
                background-color: #ddd;
            }
            input[type="submit"] {
                background-color: #4CAF50; /* verde */
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            input[type="submit"]:hover {
                background-color: grey;
                color: #4CAF50;
            }
            select {
                padding: 10px;
                margin-right: 10px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <div>
            <h1>Resultados da Consulta</h1>
            <form method="post">
                <select name="script">
                    {% for script in scripts %}<option value="{{ script }}">{{ script }}</option>{% endfor %}
                </select>
                <input type="submit" value="Executar">
            </form>
            <br>
            <form action="/download_csv" method="post">
                <input type="hidden" name="script" value="{{ request.form.script }}">
                <input type="submit" value="Download CSV">
            </form>
                                  <br>
        </div>
        <table id="resultsTable" class="display">
            <thead><tr>{% for name in column_names %}<th>{{ name }}</th>{% endfor %}</tr></thead>
            <tbody>{% for row in query_results %}<tr>{% for cell in row %}<td>{{ cell }}</td>{% endfor %}</tr>{% endfor %}</tbody>
        </table>
    </body>
    </html>
    ''', scripts=scripts, column_names=column_names, query_results=query_results, request=request)

@app.route('/download_csv', methods=['POST'])
def download_csv():
    selected_script = request.form.get('script')
    if selected_script in list_scripts():
        script_path = os.path.join(SCRIPTS_DIR, selected_script)
        column_names, query_results = execute_script(script_path)

        si = io.StringIO()
        # Escreve a BOM
        si.write('\ufeff')
        cw = csv.writer(si, dialect='excel', delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        cw.writerow(column_names)
        cw.writerows(query_results)

        si.seek(0)
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=export.csv"
        output.headers["Content-Type"] = "text/csv; charset=utf-8"
        return output

    return "Script not found", 404

if __name__ == '__main__':
    app.run()

