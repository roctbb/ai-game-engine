FROM python

COPY ./ ./

RUN pip install -r requirements.txt

CMD ["/bin/bash", "-c", "([ -d 'migrations' ] || flask db init) && flask db migrate && flask db upgrade && python3 server.py"]