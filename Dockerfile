FROM python

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY ge_sdk ge_sdk

RUN python3 -m build ge_sdk
RUN pip install ge_sdk/dist/ge_sdk-1.0.0-py3-none-any.whl

COPY ./ ./

CMD ["/bin/bash", "-c", "([ -d 'migrations' ] || flask db init) && flask db migrate && flask db upgrade && python3 server.py"]
