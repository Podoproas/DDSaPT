import sys
import pika
import pickle
import geopandas as gpd
from shapely.geometry import shape


class Worker:
    def __init__(self, name):
        self.name = name
        self.json = None

    def run(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        channel = connection.channel()
        channel.queue_declare(queue='json_' + self.name)
        channel.basic_consume(queue='json_' + self.name, on_message_callback=self.json_load, auto_ack=True)
        channel.queue_declare(queue='exit_' + self.name)
        channel.basic_consume(queue='exit_' + self.name, on_message_callback=self.exit, auto_ack=True)
        channel.queue_declare(queue='coords_' + self.name)
        channel.basic_consume(queue='coords_' + self.name, on_message_callback=self.make_coords, auto_ack=True)
        channel.queue_declare(queue="ans")
        channel.start_consuming()

    def json_load(self, ch, method, properties, body):
        self.json = pickle.loads(body)

    def exit(self, ch, method, properties, body):
        sys.exit(0)

    def make_coords(self, ch, method, properties, body):
        coords = eval(pickle.loads(body))
        res = gpd.overlay(self.json,
                          gpd.GeoDataFrame([{'geometry': shape(coords)}]))
        ch.basic_publish(exchange="", routing_key="ans", body=pickle.dumps([res.to_json(), coords['coordinates'][0]]))
