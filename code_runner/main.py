import pika
import typing
import pydantic
import runner
import asyncio
from settings import Settings

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

    runner_obj = runner.PythonCodeRunner(
        parsed_body.code,
        Settings().pyston_hostname,
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

channel.basic_qos(prefetch_count=1)
channel.basic_consume(
    queue=RMQ_QUEUE,
    on_message_callback=run_solution,
)

channel.start_consuming()
