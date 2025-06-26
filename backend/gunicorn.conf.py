# Configurazione Gunicorn per il backend Flask
import multiprocessing

# Binding
bind = "0.0.0.0:8000"

# Workers
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"

# Timeout
timeout = 30
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "prometheus-remote-write-backend"

# Preload app
preload_app = True

# Max requests per worker
max_requests = 1000
max_requests_jitter = 50

# Worker restart
worker_tmp_dir = "/dev/shm"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190 