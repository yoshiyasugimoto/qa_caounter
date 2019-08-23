import os

from flask import Flask
from attendance_manage.views import attendance_manage
from qa.views import qa

app = Flask(__name__)
app.secret_key = os.urandom(12)
app.register_blueprint(attendance_manage)
app.register_blueprint(qa)

if __name__ == '__main__':
    app.config['SESSION_TYPE'] = 'filesystem'
    app.run(debug=True)
