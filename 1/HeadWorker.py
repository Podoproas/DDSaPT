import sys
import pika
import pickle
import geopandas as gpd
from Worker import Worker
from shapely.geometry import shape
from multiprocessing import Process

message = '{"type": "Polygon", "coordinates": ' \
          '[[[%(x_up_left)s, %(y_up_left)s],' \
          '  [%(x_up_right)s, %(y_up_right)s],' \
          '  [%(x_bot_left)s, %(y_bot_left)s],' \
          '  [%(x_bot_right)s, %(y_bot_right)s],' \
          '  [%(x_up_left)s, %(y_up_left)s]]]}'


class HeadWorker:
    def __init__(self, num_of_proc):
        self.num_of_proc = num_of_proc
        self.workers = []
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()
        self.init_workers()

        self.channel.queue_declare(queue='ans')
        self.channel.queue_declare(queue='coords_master')

        self.channel.basic_consume(queue="coords_master", on_message_callback=self.make_coords, auto_ack=True)

        self.json = None
        self.num_of_regions = 0

    def init_workers(self):
        self.workers.append([None, "master"])
        while len(self.workers) < self.num_of_proc:
            self.workers.append(create_new_worker())
            self.workers[-1][0].start()
            self.channel.queue_declare(queue="coords_" + self.workers[-1][1])

    def destroy_workers(self):
        for worker in self.workers[1:]:
            self.channel.queue_declare(queue="exit_" + worker[1])
            self.channel.basic_publish(exchange='',
                                       routing_key="exit_" + worker[1],
                                       body=b"exit")
            worker[0].join()
        self.workers = []

    def send_json(self):
        for worker in self.workers[1:]:
            self.channel.queue_declare(queue="json_" + worker[1])
            self.channel.basic_publish(exchange='',
                                       routing_key="json_" + worker[1],
                                       body=pickle.dumps(self.json))

    def listen(self):
        self.channel.queue_declare(queue='json_passing')
        self.channel.basic_consume(queue='json_passing', on_message_callback=self.start_work, auto_ack=True)
        self.channel.start_consuming()

    def start_work(self, ch, method, properties, body):
        packet = pickle.loads(body)
        for i in range(len(packet["json"]["features"])):
            for prop in packet["json"]["features"][i]["properties"]:
                packet["json"]["features"][i][prop] = packet["json"]["features"][i]["properties"][prop]
            del packet["json"]["features"][i]["properties"]
            packet["json"]["features"][i]["geometry"] = shape(packet["json"]["features"][i]["geometry"])

        self.json = gpd.GeoDataFrame.from_dict(packet["json"]["features"])
        minx = self.json.bounds['minx'].min()
        miny = self.json.bounds['miny'].min()
        maxx = self.json.bounds['maxx'].max()
        maxy = self.json.bounds['maxy'].max()
        self.send_json()
        self.num_of_regions = packet["num_of_regions"]
        x, y = get_grid(self.num_of_regions)
        x_step = (maxx - minx) / x
        y_step = (maxy - miny) / y
        cur_worker = 0
        for i in range(x):
            for j in range(y):
                body = message % {"x_up_left": minx + i * x_step,
                                  "x_up_right": minx + (i + 1) * x_step,
                                  "x_bot_left": minx + (i + 1) * x_step,
                                  "x_bot_right": minx + i * x_step,
                                  "y_up_left": miny + j * y_step,
                                  "y_up_right": miny + j * y_step,
                                  "y_bot_left": miny + (j + 1) * y_step,
                                  "y_bot_right": miny + (j + 1) * y_step
                                  }
                self.channel.basic_publish(exchange='', routing_key="coords_" + self.workers[cur_worker][1],
                                           body=pickle.dumps(body))
                cur_worker = (cur_worker + 1) % len(self.workers)

    def make_coords(self, ch, method, properties, body):
        coords = eval(pickle.loads(body))
        res = gpd.overlay(self.json,
                          gpd.GeoDataFrame([{'geometry': shape(coords)}]))
        ch.basic_publish(exchange="", routing_key="ans", body=pickle.dumps([res.to_json(), coords['coordinates'][0]]))


def create_new_worker():
    create_new_worker.num_of_created += 1
    new_worker = Worker(name="worker_" + str(create_new_worker.num_of_created))
    return Process(target=new_worker.run), "worker_" + str(create_new_worker.num_of_created)


create_new_worker.num_of_created = 0


def get_grid(n):
    for i in range(int(n ** 0.5), 0, -1):
        if n % i == 0:
            return i, n // i


if __name__ == "__main__":
    a = HeadWorker(int(sys.argv[1]))
    try:
        a.listen()
    except Exception as err1:
        print(err1)
    finally:
        a.destroy_workers()
