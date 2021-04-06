import io
import sys
import lzma
import pika
import pickle
import random
import string
import osmnx as ox
from osmnx import truncate
import geopandas as gpd
from os import makedirs
from os.path import join, exists
from shapely.geometry import shape


class TileWorker:
    def __init__(self):
        self.cur_client = None
        self.cur_loaded_osm = None

    def run(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        channel = connection.channel()
        channel.queue_declare(queue='osm_passing')
        channel.basic_consume(queue='osm_passing', on_message_callback=self.osm_save, auto_ack=True)
        channel.start_consuming()

    def osm_save(self, ch, method, properties, body):
        temp = pickle.loads(body)
        osm = temp["xz"]
        client_id = temp["client_id"]
        ios = io.BytesIO(osm)
        encoded = lzma.open(ios).read()
        makedirs(join("generated_files", client_id), exist_ok=True)
        with open(join("generated_files", client_id, "full_map.osm"), "wb") as fout:
            fout.write(encoded)
        self.cur_client = client_id
        self.cur_loaded_osm = ox.graph_from_xml(join("generated_files", client_id, "full_map.osm"))
        self.make_bbox(client_id)
        ox.plot_graph(self.cur_loaded_osm, show=False, save=True, filepath=join("static", client_id + " full.jpg"))
        ch.queue_declare(queue=client_id)
        ch.queue_declare(queue=client_id + "_cords")
        ch.basic_consume(queue=client_id + "_cords", on_message_callback=self.new_cords, auto_ack=True)
        ch.basic_publish(exchange='',
                          routing_key=client_id,
                          body=client_id + " full.jpg")
        print("Published full map jpg: ", client_id + " full.jpg")

    def new_cords(self, ch, method, properties, body):
        dict_ = pickle.loads(body)
        print("new coords received in tile server", dict_)
        client_id = dict_["client_id"]
        self.load_bbox(client_id)
        percent_x0_offset = float(dict_["x0"]) / float(dict_["width"])
        percent_y0_offset = float(dict_["y0"]) / float(dict_["height"])
        percent_x1_offset = float(dict_["x1"]) / float(dict_["width"])
        percent_y1_offset = float(dict_["y1"]) / float(dict_["height"])
        min_x, min_y, max_x, max_y = self.bbox
        new_x0 = min_x + percent_x0_offset * (max_x - min_x)
        new_x1 = min_x + percent_x1_offset * (max_x - min_x)
        new_y0 = max_y - percent_y0_offset * (max_y - min_y)
        new_y1 = max_y - percent_y1_offset * (max_y - min_y)
        try:
            subgraph = truncate.truncate_graph_bbox(self.cur_loaded_osm, new_y0, new_y1, new_x0, new_x1, retain_all=True)
        except ValueError:
            ch.basic_publish(exchange='',
                             routing_key=client_id,
                             body="/static/" + client_id + " full.jpg")
            self.make_bbox(client_id)
            return
        self.save_bbox(client_id, [new_x0, new_y0, new_x1, new_y1])
        letters = string.ascii_lowercase
        id_ = ''.join(random.choice(letters) for _ in range(8))
        try:
            ox.plot_graph(subgraph, show=False, save=True, filepath=join("static", client_id + " new %s.jpg" % id_))
            ch.basic_publish(exchange='',
                             routing_key=client_id,
                             body="/static/" + client_id + " new %s.jpg" % id_)
        except ValueError:
            ch.basic_publish(exchange='',
                             routing_key=client_id,
                             body="/static/" + client_id + " full.jpg")
            self.make_bbox(client_id)

        print("Made a new image on ", new_x0, new_y0, new_x1, new_y1, self.bbox)

    def load_bbox(self, client_id):
        if exists(join("generated_files", client_id, "bbox")):
            self.bbox = pickle.load(open(join("generated_files", client_id, "bbox"), "rb"))
            print("Bbox loaded for client %s and they are:" % client_id, self.bbox)
            if self.cur_client != client_id:
                print("New graph loaded for client:", client_id)
                self.cur_loaded_osm = ox.graph_from_xml(join("generated_files", client_id, "full_map.osm"))
        else:
            print("No bbox for client:", client_id)

    def make_bbox(self, client_id):
        min_x, min_y, max_x, max_y = None, None, None, None
        for _, node in self.cur_loaded_osm.nodes.data():
            min_x = node['x'] if min_x is None else min(min_x, node['x'])
            min_y = node['y'] if min_y is None else min(min_y, node['y'])
            max_x = node['x'] if max_x is None else max(max_x, node['x'])
            max_y = node['y'] if max_y is None else max(max_y, node['y'])
        print("Made new bbox for client %s :", [min_x, min_y, max_x, max_y])
        pickle.dump([min_x, min_y, max_x, max_y], open(join("generated_files", client_id, "bbox"), "wb"))

    def save_bbox(self, client_id, bbox):
        pickle.dump(bbox, open(join("generated_files", client_id, "bbox"), "wb"))


if __name__ == "__main__":
    a = TileWorker()
    a.run()
