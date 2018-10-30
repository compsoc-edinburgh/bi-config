FROM python:3

RUN apt-get update -y && \
    apt-get install -y libldap2-dev libsasl2-dev && \
    pip install pipenv

WORKDIR /code
COPY ./Pipfile* /code/

RUN pipenv install --system --deploy

COPY . /code

EXPOSE 9991

CMD ["gunicorn", "-b", "0.0.0.0:9991", "app:app"]
