Запуск программы:
* export FLASK_APP=front.py
* python3 -m flask run --host localhost --port 8179
* python3 HeadWorker.py {num_of_workers}

Теперь WEB интерфейс доступен по адресу <http://localhost:8179/>
![img.png](img.png)

В верхнее окно забивается GeoJson, ниже - количество регионов

При нажатии на "Отправить" - генерируются GeoJson-ы регионов, которые можно скачать кнопкой "Отправить":
![img_1.png](img_1.png)
