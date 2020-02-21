from flask import render_template, request, make_response, jsonify, Flask, flash, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField, MultipleFileField, validators
from flask_dropzone import Dropzone

import sys, traceback, os
import socket
import logging
import nbformat as nbf
from notebook.auth.security import passwd, passwd_check
from db_setup import init_db, db_session


# Connection to Scheduler
HOST = '127.0.0.1'
PORT = 65432

app = Flask(__name__, template_folder='temp')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////mnt/internal/queue.db'
app.secret_key = "warumbraucheichdich"
app.config['UPLOAD_FOLDER'] = '/mnt/data'
app.config['PYTHONFILE_FOLDER'] = '/mnt/internal'
app.config.update(
    DROPZONE_IN_FORM=True,
    DROPZONE_UPLOAD_ON_CLICK=True,
    DROPZONE_UPLOAD_ACTION='handle_drop',
    DROPZONE_UPLOAD_BTN_ID='submit',
    DROPZONE_UPLOAD_MULTIPLE=True,
    DROPZONE_PARALLEL_UPLOADS=10000,
)

db = SQLAlchemy(app)
dropzone = Dropzone(app)
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
    pwd = db.Column(db.String)
 
    def __repr__(self):
        return "%s - %10s - id: %s" % (self.owner, self.task_type, self.id)


# Forms
class TaskForm(FlaskForm):
    supported_tasks = [('python', 'Python file(s)'), ('jupyter_notebook', 'Jupyter Notebook'),
                       ('empty_notebook', 'Empty Notebook')]
    task_type = SelectField('Task', choices=supported_tasks)
    owner = StringField('Ersteller', validators=[validators.Optional()])
    duration = IntegerField('geschätzte Dauer in Minuten', validators=[validators.Optional()])
    files = MultipleFileField('Program / Module')
    main = StringField('Name of main if many files', validators=[validators.Optional()])


class PwdForm(FlaskForm):
    owner = StringField('User', validators=[validators.DataRequired()])
    old_pwd = StringField('Old password', validators=[validators.DataRequired()])
    new_pwd = StringField('New password', validators=[validators.DataRequired()])
    

@app.route("/")
def index():
    # Start Session
    session['status'] = True
    session['files'] = []
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


@app.route('/dropzone', methods=['POST'])
def handle_drop():
    """
    Handle uploads from the dropzone and save them in a folder for later use
    """
    session['files'] = []
    session['status'] = False
    for key, f in request.files.items():
        logging.info("%s uploaded over dopzone" % f.filename)
        if key.startswith('file'):
            f.save(os.path.join(app.config['PYTHONFILE_FOLDER'], secure_filename(f.filename)))
            session['files'] = session['files'] + [secure_filename(f.filename)]
    session['status'] = True
    return '', 204


@app.route("/addtask", methods=["GET", "POST"])
def add_task():
    """
    Neue Aufgabe zur Warteschlange hinzufügen
    """
    form = TaskForm()
        
    if form.validate_on_submit():
        # save to queue
        task = Task()
        task.owner = secure_filename(form.owner.data) or "dfki"
        task.task_type = form.task_type.data
        task.duration = form.duration.data or 0
        task.status = 'Ready'
        
        # Save Script in folder of User
        directory = os.path.join(app.config['PYTHONFILE_FOLDER'], task.owner)
        # init standard pwd if new
        if not os.path.exists(directory):
            logging.info("Make Account for %s" % task.owner)
            os.makedirs(directory)
            with open(os.path.join(directory, "pwd"), "w+") as pwd:
                pwd.write(passwd(task.owner))
        with open(os.path.join(directory, "pwd"), "r") as pwd:
            task.pwd = pwd.read()

        # Create empty notebook if none given
        if task.task_type == 'empty_notebook':
            nb = nbf.v4.new_notebook()
            nbf.write(nb, os.path.join(directory, "test.ipynb"))
            task.program = "test.ipynb"

        # Uploaded Files
        else:
            if session['status'] == False:
                flash("Uploaded Files not ready")
                return redirect("/addtask")
            elif len(session['files']) == 0:
                flash("Select a file")
                return redirect("/addtask")
            else:
                for file in session['files']:
                    try:
                        task.program = file
                        # Move to correct location
                        os.replace(os.path.join(app.config['PYTHONFILE_FOLDER'], file),
                                   os.path.join(directory, file))
                    # When no file provided
                    except IsADirectoryError:
                        flash("Select a file")
                        return redirect("/addtask")

        # Use main when specified
        if form.main.data != '':
            task.program = secure_filename(form.main.data)
            if not os.path.isfile(os.path.join(directory, task.program)):
                flash("This main file doesn't exist")
                return redirect("/addtask")

        # Else use last
        main_path = os.path.join(directory, task.program)

        # Convert only main to a notebook if not already
        if task.task_type == 'python':
            nb = nbf.v4.new_notebook()

            with open(main_path) as f:
                code = f.read()

            nb.cells.append(nbf.v4.new_code_cell(code))
            nbf.write(nb, main_path.replace('.py', '.ipynb'))
            os.remove(main_path)
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
            pwd.write(saved_pwd)
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

