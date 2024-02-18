import json
from flask import Flask, request
from threading import Thread

class ParameterServer:
    """
    ParameterServer is a simple Flask-based web server for managing and updating parameters.

    Attributes:
        app (Flask): The Flask application instance.
        PARAMETERFILE (str): The filename for storing parameter values in JSON format.
        PAGENAME (str): The name for the webpage
        central_parameters (dict): A dictionary containing central parameter definitions.
        host (str): The host address for the server.
        port (int): The port number for the server.
        server_thread (Thread): The thread running the Flask server.

    Methods:
        __init__(self, host='0.0.0.0', port=5000):
            Initializes the ParameterServer instance.

        run_server(self):
            Starts the Flask server in a separate thread.

        index(self):
            Handles GET and POST requests for the root route ("/"). Displays parameter values and allows updates through a form.

        start_server(self):
            Starts the Flask server.

        stop_server(self):
            Stops the Flask server.

        get_parameter(self, parameter_name):
            Retrieves the current value of a specified parameter.

        get_parameter_names(self):
            Retrieves a list of parameter names.

    Example Usage:
        parameter_server = ParameterServer()
        parameter_server.start_server()
        parameter_names = parameter_server.get_parameter_names()
        print(parameter_names)
        parameter_server.stop_server()
    """

    def __init__(self, host='0.0.0.0', port=5000):
        self.app = Flask(__name__)
        self.app.route('/', methods=['GET', 'POST'])(self.index)
        self.PARAMETERFILE = 'parameters.json'
        self.PAGENAME = "ElectronFluxBalancer<br>parameter interface"
        self.central_parameters = {
            'House Battery':{
                'Control': {'options': ['on', 'off'], 'unit': '', 'type': 'enum', 'value': 'on'},
                'Charge below': {'min': 0.0, 'max': 0.6, 'unit': '€', 'type': 'number', 'step': 0.01, 'value': 0.08},
                'Charge limit': {'min': 0, 'max': 100, 'unit': '%', 'type': 'number', 'step': 1, 'value': 80},
                #'Emergency SOC': {'min': 10, 'max': 99, 'unit': '%', 'type': 'number', 'step': 1, 'value': 10},
            },
            'Car Solar':{
                'Control': {'options': ['on', 'off'], 'unit': '', 'type': 'enum', 'value': 'off'},
                'charge above house SOC': {'min': 10, 'max': 99, 'unit': '%', 'type': 'number', 'step': 1, 'value': 99},
            },
            'Car Grid':{
                'Control': {'options': ['on', 'off'], 'unit': '', 'type': 'enum', 'value': 'off'},
                'charge below': {'min': 0.0, 'max': 0.6, 'unit': '€', 'type': 'number', 'step': 0.01, 'value': 0.10},
                'Plan ahead': {'min': 0, 'max': 24, 'unit': 'h', 'type': 'number', 'step': 1, 'value': 8},
                'Finish at': {'min': 0, 'max': 24, 'unit': 'h', 'type': 'number', 'step': 1, 'value': 8},
            },
            'Heat Boiler':{
                'Control': {'options': ['on', 'off'], 'unit': '', 'type': 'enum'},
                'Heat above house SOC': {'min': 10, 'max': 99, 'unit': '%', 'type': 'number', 'step': 1, 'value': 50},
                'Setpoint': {'min': 45, 'max': 65, 'unit': '°C', 'type': 'number', 'step': 0.5, 'value': 50},
            },
        }

        # Load values from file if it exists, otherwise use defaults
        try:
            with open(self.PARAMETERFILE, 'r') as f:
                saved_values = json.load(f)
            for group, parameters in self.central_parameters.items():
                for key, param in parameters.items():
                    if group in saved_values and key in saved_values[group]:
                        param['value'] = saved_values[group][key]
                    else:
                        param['value'] = param.get('value', None)
        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
            for group, parameters in self.central_parameters.items():
                for key, param in parameters.items():
                    param['value'] = param.get('value', None)

        self.server_thread = Thread(target=self.run_server)

        # Store host and port as attributes
        self.host = host
        self.port = port

    def add_parameter(self, _name:str, _min:float, _max:float, _unit:str, _type:str, _step:float, _value ):
        self.central_parameters[_name] = {'min': _min, 'max': _max, 'unit': _unit, 'type': _type, 'step': _step, 'value': _value}

    def run_server(self):
        self.app.run(host=self.host, port=self.port)


    def index(self):  # the html representation
        if request.method == 'POST':
            for group, parameters in self.central_parameters.items():
                for key, param in parameters.items():
                    if param is not None:
                        if param.get('type') == 'number' and request.form[key] != '':
                            param['value'] = float(request.form[key])
                        elif param.get('type') == 'enum' and request.form[key] != '':
                            param['value'] = request.form[key]

            # Save to file
            j = {}
            for group, parameters in self.central_parameters.items():
                j[group] = {}
                for key, param in parameters.items():
                    j[group][key] = param['value']
            with open(self.PARAMETERFILE, 'w') as f:
                json.dump(j, f, indent=4 )

        html = f'<h1>{self.PAGENAME}</h1><form method="post"><table>'
        for group, parameters in self.central_parameters.items():
            html += f'<tr><td colspan="3"><strong>{group}</strong></td></tr>'  # Add group name as a separator
            for key, param in parameters.items():
                html += '<tr>'
                html += f'<td>&nbsp; {key}</td><td>'
                if param is not None:
                    if param.get('type') == 'number':
                        step = param.get('step', 1)  # Use 1 as default step if not specified
                        html += f'<input type="number" name="{key}" value="{param.get("value",None)}" min="{param["min"]}" max="{param["max"]}" step="{step}" size="5" />'
                    elif param['type'] == 'enum':
                        html += f'<select name="{key}">'
                        for option in param['options']:
                            selected = 'selected' if option == param.get('value',None) else ''
                            html += f'<option value="{option}" {selected}>{option}</option>'
                        html += '</select>'
                    html += f'</td><td>{param["unit"]}</td></tr>'
                else:
                    html += '</td><td></td></tr>'
        html += '</table><input type="submit" value="Submit"></form>'

        header = f"""<!DOCTYPE html>
        <html lang="en">
          <head> <meta charset="UTF-8" />
            <title>{self.PAGENAME}</title>
          </head><body>"""

        footer = """</body>
        </html>"""

        return header + html + footer

    def start_server(self):
        print(f"Starting server on http://{self.host}:{self.port}/")
        self.server_thread.start()

    def stop_server(self):
        # This is a basic way to stop the server. In a production environment, you might want a more robust solution.
        self.server_thread.join()


    def get_parameter(self, group_name, parameter_name):
        return self.central_parameters.get(group_name, {}).get(parameter_name, {}).get('value', None)

    def get_parameter_names(self):
        parameter_names = []
        for group, parameters in self.central_parameters.items():
            for parameter_name in parameters.keys():
                parameter_names.append(f"{group} - {parameter_name}")
        return parameter_names


if __name__ == '__main__':
    parameter_server = ParameterServer()
    parameter_server.start_server()
    # You can now use parameter_server.get_parameter('parameter_name') to get parameter values
    # Remember to stop the server when done using parameter_server.stop_server()

    # Example usage of get_parameter_names
    parameter_names = parameter_server.get_parameter_names()
    print(parameter_names)