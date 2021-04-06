import os
import pika
import pickle
import random
import string
import json as jsn
from os.path import join
from flask import request
from zipfile import ZipFile
from flask import send_file, send_from_directory
from flask import Flask, Response, redirect, url_for, flash, render_template


upload_template = """
<h1>Upload OSM file:</h1>
<div>
	<form action="/load_osm/" method="post" enctype=multipart/form-data>
	<input type=file name=osm_file>
	<input type="submit">
    </form>
</div>
"""


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = "static"
app.secret_key = "super secret key"
ALLOWED_EXTENSIONS = ["osm"]

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='osm_passing')
pictures = dict()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 2)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET'])
@app.route('/upload/', methods=['GET'])
def download_map():
    return upload_template


@app.route('/load_osm/', methods=["POST"])
def load_map():
    if 'osm_file' not in request.files:
        flash("No file part")
        return redirect("/upload/")
    file = request.files['osm_file']
    if file.filename == '':
        flash('No selected file')
        return redirect("/upload/")

    if file and allowed_file(file.filename):
        new_client_id = send_file_to_back(file)
        channel.queue_declare(new_client_id)
        return redirect(url_for(".view_map", id_=new_client_id))
    else:
        flash("File format is wrong")
        return redirect("/upload/")


@app.route('/view_map/', methods=['GET'])
def view_map():

    # def get_one_picture_name(ch, method, properties, body):
    #     pictures[client_id] = body.decode("utf-8")
    #     ch.stop_consuming()

    client_id = request.args['id_']
    # channel.basic_consume(queue=client_id, on_message_callback=get_one_picture_name, auto_ack=True)
    method_frame, header_frame, body = channel.basic_get(client_id)
    while not method_frame:
        method_frame, header_frame, body = channel.basic_get(client_id)
    pictures[client_id] = body.decode("utf-8")
    channel.basic_ack(method_frame.delivery_tag)
    print("One picture received for client %s named %s" % (client_id, pictures[client_id]))
    return render_template("index.html", image=pictures[client_id], client_id=client_id)


def send_file_to_back(file):
    letters = string.ascii_lowercase
    id_ = ''.join(random.choice(letters) for _ in range(16))
    channel.basic_publish(exchange='',
                          routing_key='osm_passing',
                          body=pickle.dumps({"xz": file.read(), "client_id": id_}))

    return id_


@app.route('/send_cors/', methods=['POST'])
def coors():
    client_id = request.form["client_id"]
    channel.basic_publish(exchange='',
                          routing_key=client_id + "_cords",
                          body=pickle.dumps(request.form))
    print("Sent coords fro tile-server")

    method_frame, header_frame, body = channel.basic_get(client_id)
    while not method_frame:
        method_frame, header_frame, body = channel.basic_get(client_id)
    pictures[client_id] = body.decode("utf-8")
    channel.basic_ack(method_frame.delivery_tag)
    print("One picture received for client %s named %s" % (client_id, pictures[client_id]))
    return pictures[client_id]
