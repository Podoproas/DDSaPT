import os
import pika
import pickle
import json as jsn
from os.path import join
from flask import request
from zipfile import ZipFile
from flask import send_from_directory
from flask import Flask, redirect, url_for

app = Flask(__name__)
form = """
<div>
  <form action="/get_file/" method="post">
  %s
  <input type="submit">
</form>
"""
text_begin = """<p>Group %s<textarea style="margin: 0px; width: 660px; height: 205px;" name="group_%s">%s</textarea></p>"""

template = """
<div>
<h1><strong>Enter your geojson below:</strong></h1>
</div>
<div>
  <form action="/get_json/" method="post">
  <textarea name=json style="margin: 0px; width: 660px; height: 205px;"></textarea>
  <p><input name=number type="text" value="4" /> Number of regions</p>
  <input type="submit">
</form>
</div>
"""
received, ans = 0, []


@app.route('/', methods=['GET'])
@app.route('/cut_json/', methods=['GET'])
def get_json_window():
    try:
        addition = request.args['messages']
    except:
        addition = ""

    return template + addition


@app.route('/get_json/', methods=['POST'])
def get_json():
    try:
        json = eval(request.form["json"])
        if json is None:
            raise ValueError
    except:
        return redirect(url_for('.get_json_window',
                                messages="""<h1><span style="color: #ff0000;">JSON ERROR</span></h1>"""))
    try:
        proc_cnt = int(request.form["number"])
    except:
        return redirect(url_for('.get_json_window',
                                messages="""<h1><span style="color: #ff0000;">NUMBER ERROR</span></h1>"""))

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='json_passing')
    channel.basic_publish(exchange='',
                              routing_key='json_passing',
                              body=pickle.dumps({"json": json, "num_of_regions": proc_cnt}))
    channel.close()
    return redirect(url_for(".get_answer", messages=proc_cnt))


@app.route("/answer/", methods=["GET"])
def get_answer():
    global received, ans
    received = 0
    try:
        proc_cnt = int(request.args['messages'])
    except:
        proc_cnt = 1

    ans = []

    def print_part(ch, method, properties, body):
        global received, ans
        json, coords = pickle.loads(body)
        ans.append(eval(json))
        received += 1
        print(received, ans[-1])
        if received == proc_cnt:
            ch.stop_consuming()

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue="ans")
    channel.basic_consume("ans", on_message_callback=print_part, auto_ack=True)
    channel.start_consuming()
    return form % "\n".join(list(map(lambda x: text_begin % (x[0], x[0], jsn.dumps(x[1], indent=0)), enumerate(ans))))


@app.route("/get_file/", methods=["POST"])
def get_file():
    zipObj = ZipFile(join("generated_files", "answer.zip"), "w")
    for group in request.form:
        json = eval(request.form[group])
        jsn.dump(json, open(join("generated_files", group + ".geojson"), "w"), indent=4)
        zipObj.write(join("generated_files", group + ".geojson"))
        os.remove(join("generated_files", group + ".geojson"))
    zipObj.close()
    return send_from_directory("generated_files", "answer.zip", as_attachment=True)
