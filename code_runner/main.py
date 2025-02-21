import pika
import typing
import pydantic
import runner
import asyncio
import logging
from settings import Settings

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="[%(asctime)s] %(levelname)s:\t %(message)s"
)

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=Settings().rmq_hostname,
        port=Settings().rmq_port,
    )
)

RMQ_QUEUE = 'code_queue'

channel = connection.channel()
channel.queue_declare(queue=RMQ_QUEUE)

class BodyProps(pydantic.BaseModel):
    code: str
    func: str
    timeout: float = 0.5
    args: list[typing.Any] = []

class ReturnProps(pydantic.BaseModel):
    error: bool
    return_list: list[typing.Any] = []

def run_solution(ch, method, props, body):
    parsed_body = BodyProps.model_validate(body)

    logging.info('Running code')

    runner_obj = runner.PythonCodeRunner(
        parsed_body.code,
        f'http://{Settings().pyston_hostname}:{Settings().pyston_port}/api/v2/',
    )

    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(
        runner_obj.run(
            parsed_body.func,
            parsed_body.timeout,
            parsed_body.args,
        )
    )

    serialized_result = ReturnProps(
        error=result[0], 
        return_list=result[1]
    ).model_dump_json()

    ch.basic_publish(
        exchange='',
        routing_key=props.reply_to,
        properties=pika.BasicProperties(
            correlation_id=props.correlation_id
        ),
        body=serialized_result,
    )
    ch.basic_ack(delivery_tag=method.delivery_tag)

    logging.info('Code ran successfully')

channel.basic_qos(prefetch_count=1)
channel.basic_consume(
    queue=RMQ_QUEUE,
    on_message_callback=run_solution,
)

logging.info('Basic logging')

channel.start_consuming()
