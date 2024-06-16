The task is in the file trxiod2021_prak2.pdf

A project with Flask that implements a multi-threaded geojson display system with cutting out pieces, where the work 
itself is done by individual nodes (with an architecture similar to high-load services like google.maps and yandex.maps)
using RabbitMQ

Before Launching the program make sure RabbitMQ Server is running.

Launching the program:
* export FLASK_APP=front.py
* python -m flask run --host localhost --port 8179
* python tile_worker.py
