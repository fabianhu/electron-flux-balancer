import json
from flask import Flask, request

app = Flask(__name__)

# Central definition of parameters
central_parameters = {
    'Charge car above house SOC': {'min': 10, 'max': 50, 'unit': '%', 'type': 'number', 'step': 1},
    'Boiler setpoint': {'min': -50, 'max': 65, 'unit': '°C', 'type': 'number', 'step': 0.5},
    'Charge from grid car below': {'min': 0.0, 'max': 0.6, 'unit': '€', 'type': 'number', 'step': 0.01},
    'Enable grid charge': {'options': ['on', 'off'], 'unit': '', 'type': 'enum'}
}

# Load values from file if it exists, otherwise use defaults
try:
    with open('parameters.json', 'r') as f:
        saved_values = json.load(f)
    for key, param in central_parameters.items():
        param['value'] = saved_values.get(key, param.get('value', None))
except FileNotFoundError:
    for key, param in central_parameters.items():
        param['value'] = param.get('value', None)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        for key, param in central_parameters.items():
            if param['type'] == 'number':
                param['value'] = float(request.form[key])
            elif param['type'] == 'enum':
                param['value'] = request.form[key]

        # Save only names and values to file
        with open('parameters.json', 'w') as f:
            json.dump({key: param['value'] for key, param in central_parameters.items()}, f)

    html = '<form method="post"><table>'
    for key, param in central_parameters.items():
        html += '<tr>'
        html += f'<td>{key}</td><td>'
        if param['type'] == 'number':
            step = param.get('step', 1)  # Use 1 as default step if not specified
            html += f'<input type="number" name="{key}" value="{param["value"]}" min="{param["min"]}" max="{param["max"]}" step="{step}" />'
        elif param['type'] == 'enum':
            html += f'<select name="{key}">'
            for option in param['options']:
                selected = 'selected' if option == param['value'] else ''
                html += f'<option value="{option}" {selected}>{option}</option>'
            html += '</select>'
        html += f'</td><td>{param["unit"]}</td></tr>'
    html += '</table><input type="submit" value="Submit"></form>'

    return html


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
