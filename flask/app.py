from flask import render_template, request, make_response, jsonify, Flask, flash, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import StringField, SelectField, IntegerField, validators
import sys, traceback, os
import socket
import logging
import nbformat as nbf
from notebook.auth.security import passwd, passwd_check
from db_setup import init_db, db_session

HOST = '127.0.0.1'  # The server's hostname or IP address
PORT = 65432        # The port used by the server


app = Flask(__name__, template_folder='temp')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////mnt/internal/queue.db'
app.secret_key = "warumbraucheichdich"
app.config['UPLOAD_FOLDER'] = '/mnt/data'
app.config['PYTHONFILE_FOLDER'] = '/mnt/internal'

db = SQLAlchemy(app)
init_db()


# Models
class Task(db.Model):
    __tablename__ = "tasks"
 
    id = db.Column(db.Integer, primary_key=True)
    owner = db.Column(db.String)
    task_type = db.Column(db.String)
    duration = db.Column(db.Integer)
    program = db.Column(db.String)
    status = db.Column(db.String)
 
    def __repr__(self):
        return "%s - %10s - id: %s"%(self.owner, self.task_type, self.id)


# Forms
class TaskForm(FlaskForm):
    supported_tasks = [('single_python_file', 'einzelne .py'), ('jupyter_notebook', 'Jupyter Notebook')]
    task_type = SelectField('Task', choices=supported_tasks)
    owner = StringField('Ersteller', validators=[validators.Optional()])
    duration = IntegerField('geschätzte Dauer in Minuten', validators=[validators.Optional()])
    file = FileField('Program', validators=[FileRequired()])


class PwdForm(FlaskForm):
    owner = StringField('User', validators=[validators.DataRequired()])
    old_pwd = StringField('Old password', validators=[validators.DataRequired()])
    new_pwd = StringField('New password', validators=[validators.DataRequired()])
    

@app.route("/")
def index():
    # Update Scheduler
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall(b'update')
        data = s.recv(1024)

    qry = db_session.query(Task)
    results = qry.all()

    taskList = [vars(task) for task in results]
    # Keine Nachkommas
    for task in taskList:
        task['duration'] = int(task['duration'])
            
    return render_template('index.html', taskList=taskList)


@app.route("/addtask", methods=["GET", "POST"])
def add_task():
    """
    Neue Aufgabe zur Warteschlange hinzufügen
    """
    form = TaskForm()
        
    if form.validate_on_submit():
        # save to queue
        task = Task()
        task.owner = form.owner.data or "0"
        task.task_type = form.task_type.data
        task.duration = form.duration.data or 0
        
        # Save Script in folder of User and init standard pwd
        directory = os.path.join(app.config['PYTHONFILE_FOLDER'], secure_filename(task.owner))
        if not os.path.exists(directory):
            logging.info("Make Account for %s" % secure_filename(task.owner))
            os.makedirs(directory)
            with open(os.path.join(directory, "pwd"), "w+") as pwd:
                pwd.write(passwd(secure_filename(task.owner)))

        task.status = 'Ready'
        file = form.file.data
        task.program = secure_filename(file.filename)
        
        logging.info("Uploaded File: %s" % task.program)

        filepath = os.path.join(directory, task.program)

        file.save(filepath)

        # Convert to a notebook if not already
        if task.task_type == 'single_python_file':
            nb = nbf.v4.new_notebook()
            with open(filepath) as f:
                code = f.read()

            nb.cells.append(nbf.v4.new_code_cell(code))
            nbf.write(nb, filepath.replace('.py', '.ipynb'))
            os.remove(filepath)
            task.program = task.program.replace('.py', '.ipynb')

        db_session.add(task)
        db_session.commit()

        # Update Scheduler
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            s.sendall(b'update')
            data = s.recv(1024)

        logging.info('Received status: %s' % data.decode('utf-8'))
        
        return redirect('/')
 
    return render_template('addtask.html', form=form)


@app.route("/changepwd", methods=["GET", "POST"])
def change_pwd():
    """
    Change the standard password
    """
    form = PwdForm()

    if form.validate_on_submit():

        owner = secure_filename(form.owner.data)
        old_pwd = secure_filename(form.old_pwd.data)
        new_pwd = secure_filename(form.new_pwd.data)

        pwd_path = os.path.join(app.config['PYTHONFILE_FOLDER'], secure_filename(owner), "pwd")
        # Check if it is a valid user
        if not os.path.exists(pwd_path):
            flash("User %s hasn't created a task yet" % owner)
            logging.info("No User with name %s" % owner)
            return redirect("/changepwd")

        saved_pwd = open(pwd_path, 'r').read()
        with open(pwd_path, "w") as pwd:
            # Change password
            if passwd_check(saved_pwd, old_pwd):
                pwd.write(passwd(new_pwd))
                logging.info("Password changed for user %s" % owner)
                return redirect('/')
            flash("Old Password is wrong")

    return render_template('change_pwd.html', form=form)
    

@app.route("/upload", methods=["GET", "POST"])
def upload_dataset():
    """
    Upload a dataset to the database and show a fancy loading animation
    """
    if request.method == "POST":

        file = request.files["file"]

        filename = secure_filename(file.filename)
        logging.info("Uploaded Dataset: %s"%filename)
        try:
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        except:
            traceback.print_exc(file=sys.stderr)

        res = make_response(jsonify({"message": "File uploaded"}), 200)

        return res

    return render_template("upload.html")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, host='0.0.0.0')

