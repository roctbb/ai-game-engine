import pika
import typing
import pydantic
import runner
import asyncio
import logging
from settings import Settings

print('!!!')

logging.basicConfig(
    format="[%(asctime)s] %(levelname)s:\t %(message)s"
)

logger = logging.Logger('mainLogger')
logger.setLevel(logging.DEBUG)

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=Settings().rmq_hostname,
        port=Settings().rmq_port,
        virtual_host='/',
        credentials=pika.PlainCredentials(
            Settings().rmq_username,
            Settings().rmq_password,
        )
    )
)

RMQ_QUEUE = 'code_queue'

channel = connection.channel()
channel.queue_declare(queue=RMQ_QUEUE)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

class BodyProps(pydantic.BaseModel):
    code: str
    func: str
    timeout: float = 0.5
    args: list[typing.Any] = []

class ReturnProps(pydantic.BaseModel):
    error: bool
    return_list: list[typing.Any] = []

def run_solution(ch, method, props, body):
    logger.info('Running code')

    try:
        parsed_body = BodyProps.model_validate_json(body)
    except pydantic.ValidationError as e:
        for error in e.errors():
            logger.error(error)
        return

    runner_obj = runner.PythonCodeRunner(
        parsed_body.code,
        f'http://{Settings().pyston_hostname}:{Settings().pyston_port}/api/v2/',
    )

    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(
        runner_obj.run(
            parsed_body.func,
            parsed_body.timeout,
            tuple(parsed_body.args),
        )
    )
    loop.close()

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

    logger.info('Code ran successfully')

channel.basic_qos(prefetch_count=1)
channel.basic_consume(
    queue=RMQ_QUEUE,
    on_message_callback=run_solution,
)

logger.info('Basic logging')

channel.start_consuming()

loop.close()
