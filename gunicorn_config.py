# gunicorn_config.py
bind = "0.0.0.0:10000"
workers = 1
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"
