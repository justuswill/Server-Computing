FROM pytorch/pytorch:latest
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt
ENV PY_FILE=
ENV JUPYTER_PWD=
ENV JUPYTER_STATUS=Ready
EXPOSE 8888
COPY entrypoint.sh /
RUN chmod 777 /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
