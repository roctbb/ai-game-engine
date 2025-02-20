from celery import Celery
import sandbox_run

app = Celery('tasks', backend='redis://localhost', broker='redis://localhost')

@app.task
def send(code, function, args, timeout):
    result = sandbox_run.start_execute(code, function, [args], timeout)
    return result